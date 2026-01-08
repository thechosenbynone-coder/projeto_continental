import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os

# =====================================================
# 1. CONFIGURAÇÃO GERAL
# =====================================================
st.set_page_config(
    page_title="Portal de Inteligência em Suprimentos",
    page_icon="🏗️",
    layout="wide"
)

st.markdown("""
<style>
div[data-testid="stMetric"] {
    background-color: var(--secondary-background-color);
    border-left: 5px solid #004280;
    padding: 15px;
    border-radius: 10px;
}
[data-testid="stMetricValue"] {
    font-size: 22px !important;
    font-weight: 700;
}
.card {
    background-color: var(--secondary-background-color);
    padding: 18px;
    border-radius: 10px;
    border: 1px solid rgba(120,120,120,.2);
}
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. FUNÇÕES AUXILIARES
# =====================================================
def format_brl(v):
    if pd.isna(v): return "R$ 0,00"
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def format_perc(v):
    if pd.isna(v): return "0%"
    return f"{v:.1f}%"

# =====================================================
# 3. CARREGAMENTO DE DADOS
# =====================================================
@st.cache_data
def carregar_dados():
    if not os.path.exists("compras_suprimentos.db"):
        return pd.DataFrame()
    conn = sqlite3.connect("compras_suprimentos.db")
    df = pd.read_sql("SELECT * FROM base_compras", conn)
    conn.close()
    if df.empty:
        return pd.DataFrame()

    df['data_emissao'] = pd.to_datetime(df['data_emissao'])
    df['ano'] = df['data_emissao'].dt.year
    df['mes_ano'] = df['data_emissao'].dt.to_period('M').astype(str)
    df['bimestre'] = df['data_emissao'].dt.to_period('2M').astype(str)
    df['desc_prod'] = df['desc_prod'].astype(str).str.upper().str.strip()
    df['ncm'] = df['ncm'].astype(str).str.replace('.', '', regex=False)
    return df

df_full = carregar_dados()
if df_full.empty:
    st.warning("⚠️ Base de dados não encontrada.")
    st.stop()

# =====================================================
# 4. FILTROS GLOBAIS
# =====================================================
with st.sidebar:
    st.title("🎛️ Filtros")
    anos = sorted(df_full['ano'].unique(), reverse=True)
    sel_anos = st.multiselect("Ano", anos, default=anos)
    ufs = sorted(df_full['uf_emit'].dropna().unique())
    sel_ufs = st.multiselect("UF", ufs, default=ufs)

df = df_full[
    (df_full['ano'].isin(sel_anos)) &
    (df_full['uf_emit'].isin(sel_ufs))
].copy()

# =====================================================
# 5. CLASSIFICAÇÃO DE MATERIAL
# =====================================================
def classificar_material(row):
    d = row['desc_prod']
    n = row['ncm']

    epi = ['LUVA','CAPACETE','OCULOS','BOTA','RESPIRADOR','MASCARA','CINTO','TALABARTE']
    hid = ['TUBO','PVC','REGISTRO','VALVULA','JOELHO','CONEXAO']
    ele = ['CABO','FIO','DISJUNTOR','LAMPADA','TOMADA','INTERRUPTOR']
    ferr = ['CHAVE','BROCA','SERRA','MARTELO','FURADEIRA']
    civ = ['CIMENTO','AREIA','TIJOLO','ARGAMASSA','PISO','TINTA']

    if n.startswith(('2710','3403')) or 'OLEO' in d:
        return '🔴 QUÍMICO (CRÍTICO)', 'FISPQ'
    if any(x in d for x in epi):
        return '🟠 EPI (CRÍTICO)', 'CA'
    if any(x in d for x in hid):
        return '💧 HIDRÁULICA', 'Geral'
    if any(x in d for x in ele):
        return '⚡ ELÉTRICA', 'Geral'
    if any(x in d for x in ferr):
        return '🔧 FERRAMENTAS', 'Geral'
    if any(x in d for x in civ):
        return '🧱 CIVIL', 'Geral'
    return '📦 GERAL', 'Geral'

# =====================================================
# 6. ETL EXECUTIVO
# =====================================================
df_group = df.groupby(['desc_prod','ncm']).agg(
    Total_Gasto=('v_total_item','sum'),
    Qtd=('qtd','sum'),
    Menor_Preco=('v_unit','min')
).reset_index()

df_group[['Categoria','Exigencia']] = df_group.apply(
    lambda x: pd.Series(classificar_material(x)), axis=1
)

last = df.sort_values('data_emissao').drop_duplicates(
    ['desc_prod','ncm'], keep='last'
)[['desc_prod','ncm','v_unit','nome_emit','data_emissao']]

df_final = df_group.merge(last, on=['desc_prod','ncm'], how='left')
df_final.rename(columns={
    'v_unit':'Preco_Ultimo',
    'nome_emit':'Fornecedor_Ultimo'
}, inplace=True)

df_final['Variacao_Preco'] = (
    (df_final['Preco_Ultimo'] - df_final['Menor_Preco']) /
    df_final['Menor_Preco'] * 100
)

# =====================================================
# 7. MÉTRICAS EXECUTIVAS
# =====================================================
spend_total = df['v_total_item'].sum()
saving = spend_total - (df_final['Menor_Preco'] * df_final['Qtd']).sum()
spend_critico = df_final[df_final['Categoria'].str.contains('CRÍTICO')]['Total_Gasto'].sum()
inflacao = df.groupby('mes_ano')['v_unit'].mean().pct_change().mean() * 100
dependencia_top5 = (
    df.groupby('nome_emit')['v_total_item'].sum()
    .nlargest(5).sum() / spend_total * 100
)
itens_monof = (df.groupby('desc_prod')['nome_emit'].nunique() == 1).sum()

# =====================================================
# 8. INTERFACE
# =====================================================
st.title("🏗️ Portal de Inteligência em Suprimentos")
st.divider()

aba1, aba2, aba3 = st.tabs([
    "📊 Visão Diretoria",
    "⚠️ Riscos & Concentração",
    "🔎 Análise Detalhada"
])

# =====================================================
# ABA 1 – VISÃO DIRETORIA
# =====================================================
with aba1:
    st.subheader("📊 Indicadores-Chave")

    k1,k2,k3,k4 = st.columns(4)
    k1.metric("Spend Total", format_brl(spend_total))
    k2.metric("Saving Potencial", format_brl(saving))
    k3.metric("Inflação Interna", format_perc(inflacao))
    k4.metric("Dependência Top 5", format_perc(dependencia_top5))

    k5,k6,k7,k8 = st.columns(4)
    k5.metric("% Spend Crítico", format_perc(spend_critico/spend_total*100))
    k6.metric("Itens Críticos", df_final['Categoria'].str.contains('CRÍTICO').sum())
    k7.metric("Itens Monofornecedor", itens_monof)
    k8.metric("Fornecedores Ativos", df['nome_emit'].nunique())

    st.subheader("📈 Evolução Bimestral de Compras")
    fig = px.line(
        df.groupby('bimestre')['v_total_item'].sum().reset_index(),
        x='bimestre', y='v_total_item', markers=True
    )
    fig.update_layout(yaxis_tickformat="R$ ,.0f")
    st.plotly_chart(fig, use_container_width=True)

    c1,c2 = st.columns(2)
    with c1:
        st.subheader("📊 Spend por Categoria")
        fig = px.bar(
            df_final.groupby('Categoria')['Total_Gasto'].sum().reset_index(),
            x='Total_Gasto', y='Categoria', orientation='h'
        )
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("🏷️ Top 10 Itens por Gasto")
        fig = px.bar(
            df_final.sort_values('Total_Gasto', ascending=False).head(10),
            x='Total_Gasto', y='desc_prod', orientation='h'
        )
        st.plotly_chart(fig, use_container_width=True)

# =====================================================
# ABA 2 – RISCOS
# =====================================================
with aba2:
    c1,c2 = st.columns(2)

    with c1:
        st.subheader("⚠️ Maior Aumento de Preço")
        fig = px.bar(
            df_final.sort_values('Variacao_Preco', ascending=False).head(10),
            x='Variacao_Preco', y='desc_prod', orientation='h'
        )
        fig.update_layout(xaxis_tickformat=".0f")
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("🧨 Concentração de Fornecedores (Pareto)")
        pareto = df.groupby('nome_emit')['v_total_item'].sum().sort_values(ascending=False).reset_index()
        pareto['acumulado'] = pareto['v_total_item'].cumsum()/pareto['v_total_item'].sum()
        fig = px.line(pareto.head(15), x='nome_emit', y='acumulado', markers=True)
        fig.update_layout(yaxis_tickformat=".0%")
        st.plotly_chart(fig, use_container_width=True)

# =====================================================
# ABA 3 – ANÁLISE DETALHADA
# =====================================================
with aba3:
    item = st.selectbox("Selecione um material", df_final['desc_prod'].unique())
    base = df[df['desc_prod'] == item]

    st.metric("Preço Mínimo", format_brl(base['v_unit'].min()))
    st.metric("Preço Médio", format_brl(base['v_unit'].mean()))
    st.metric("Último Preço", format_brl(base.sort_values('data_emissao').iloc[-1]['v_unit']))

    fig = px.scatter(
        base, x='data_emissao', y='v_unit',
        color='nome_emit', size='qtd'
    )
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        base[['data_emissao','nome_emit','qtd','v_unit','v_total_item']]
        .sort_values('data_emissao', ascending=False)
        .style.format({'v_unit':format_brl,'v_total_item':format_brl}),
        use_container_width=True
    )
