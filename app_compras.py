import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os

# =====================================================
# 1. CONFIGURAÇÃO
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
    font-size: 24px !important;
    font-weight: 700;
    color: var(--primary-color) !important;
}
.card-fornecedor {
    background-color: var(--secondary-background-color);
    padding: 20px;
    border-radius: 10px;
    border: 1px solid rgba(128,128,128,0.2);
}
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. FUNÇÕES
# =====================================================
def format_brl(v):
    if pd.isna(v): return "R$ 0,00"
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def format_perc(v):
    if pd.isna(v): return "0%"
    return f"{v:.1f}%"

# =====================================================
# 3. CARREGAMENTO
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
    df['mes_ano'] = df['data_emissao'].dt.strftime('%Y-%m')
    df['bimestre'] = df['data_emissao'].dt.to_period('2M').astype(str)
    df['desc_prod'] = df['desc_prod'].astype(str).str.upper().str.strip()
    df['ncm'] = df['ncm'].astype(str).str.replace('.', '', regex=False)

    return df

df_full = carregar_dados()
if df_full.empty:
    st.warning("⚠️ Base de dados não carregada.")
    st.stop()

# =====================================================
# 4. FILTROS
# =====================================================
with st.sidebar:
    st.title("🎛️ Painel de Controle")
    anos = sorted(df_full['ano'].unique(), reverse=True)
    sel_anos = st.multiselect("Anos:", anos, default=anos)
    ufs = sorted(df_full['uf_emit'].dropna().unique())
    sel_uf = st.multiselect("Estados (UF):", ufs, default=ufs)

df = df_full[
    (df_full['ano'].isin(sel_anos)) &
    (df_full['uf_emit'].isin(sel_uf))
].copy()

# =====================================================
# 5. CLASSIFICAÇÃO (ORIGINAL)
# =====================================================
def classificar_material(row):
    desc = row['desc_prod']
    ncm = row['ncm']

    if ncm.startswith(('2710','3403')) or 'OLEO' in desc:
        return '🔴 QUÍMICO (CRÍTICO)', 'FISPQ'
    if any(x in desc for x in ['LUVA','CAPACETE','OCULOS','BOTA','RESPIRADOR']):
        return '🟠 EPI (CRÍTICO)', 'CA'
    if any(x in desc for x in ['TUBO','PVC','VALVULA','REGISTRO']):
        return '💧 HIDRÁULICA', 'Geral'
    if any(x in desc for x in ['CABO','DISJUNTOR','LAMPADA']):
        return '⚡ ELÉTRICA', 'Geral'
    if any(x in desc for x in ['CHAVE','BROCA','MARTELO']):
        return '🔧 FERRAMENTAS', 'Geral'
    if any(x in desc for x in ['CIMENTO','AREIA','ARGAMASSA']):
        return '🧱 CIVIL', 'Geral'
    return '📦 GERAL', 'Geral'

# =====================================================
# 6. ETL (ORIGINAL + COMPLEMENTOS)
# =====================================================
df_grouped = df.groupby(['desc_prod','ncm']).agg(
    Total_Gasto=('v_total_item','sum'),
    Qtd_Total=('qtd','sum'),
    Menor_Preco=('v_unit','min')
).reset_index()

df_grouped[['Categoria','Exigencia']] = df_grouped.apply(
    lambda x: pd.Series(classificar_material(x)), axis=1
)

df_last = df.sort_values('data_emissao').drop_duplicates(
    ['desc_prod','ncm'], keep='last'
)[['desc_prod','ncm','v_unit','nome_emit','n_nf','data_emissao']]

df_last.rename(columns={
    'v_unit':'Preco_Ultima',
    'nome_emit':'Forn_Ultimo',
    'n_nf':'NF_Ultima',
    'data_emissao':'Data_Ultima'
}, inplace=True)

df_final = df_grouped.merge(df_last, on=['desc_prod','ncm'], how='left')

df_final['Variacao_Preco'] = (
    (df_final['Preco_Ultima'] - df_final['Menor_Preco']) /
    df_final['Menor_Preco'] * 100
)

# =====================================================
# 7. MÉTRICAS ADICIONAIS (SEM REMOVER AS SUAS)
# =====================================================
spend_total = df['v_total_item'].sum()
saving_potencial = spend_total - (df_final['Menor_Preco'] * df_final['Qtd_Total']).sum()

dependencia_top5 = (
    df.groupby('nome_emit')['v_total_item'].sum()
    .nlargest(5).sum() / spend_total * 100
)

itens_monof = (df.groupby('desc_prod')['nome_emit'].nunique() == 1).sum()

spend_critico = df_final[df_final['Categoria'].str.contains('CRÍTICO')]['Total_Gasto'].sum()

# =====================================================
# 8. INTERFACE
# =====================================================
st.title("🏗️ Portal de Inteligência em Suprimentos")
st.divider()

aba1, aba2, aba3, aba4 = st.tabs([
    "📊 Dashboard Executivo",
    "📋 Auditoria & Cadastro",
    "⚖️ Comparador de Preços",
    "🔍 Busca de Materiais"
])

# =====================================================
# ABA 1 – DASHBOARD (MELHORADO, NÃO REESCRITO)
# =====================================================
with aba1:
    k1,k2,k3,k4 = st.columns(4)
    k1.metric("Spend Total", format_brl(spend_total))
    k2.metric("Fornecedores", df['cnpj_emit'].nunique())
    k3.metric("Saving Potencial", format_brl(saving_potencial))
    k4.metric("Itens Críticos", df_final['Categoria'].str.contains('CRÍTICO').sum())

    # NOVA LINHA (ADICIONADA)
    k5,k6,k7,k8 = st.columns(4)
    k5.metric("% Spend Crítico", format_perc(spend_critico/spend_total*100))
    k6.metric("Dependência Top 5", format_perc(dependencia_top5))
    k7.metric("Itens Monofornecedor", itens_monof)
    k8.metric("Categorias Ativas", df_final['Categoria'].nunique())

    st.subheader("📈 Evolução Bimestral de Compras")
    fig = px.line(
        df.groupby('bimestre')['v_total_item'].sum().reset_index(),
        x='bimestre', y='v_total_item', markers=True
    )
    fig.update_layout(yaxis_tickformat="R$ ,.0f")
    st.plotly_chart(fig, use_container_width=True)

    c1,c2 = st.columns(2)
    with c1:
        st.subheader("🏷️ Curva ABC – Itens")
        fig = px.bar(
            df_final.sort_values('Total_Gasto', ascending=False).head(12),
            x='Total_Gasto', y='desc_prod', orientation='h'
        )
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("📊 Share por Categoria")
        fig = px.pie(
            df_final.groupby('Categoria')['Total_Gasto'].sum().reset_index(),
            values='Total_Gasto', names='Categoria', hole=0.4
        )
        st.plotly_chart(fig, use_container_width=True)

# As abas 2, 3 e 4 permanecem IGUAIS às suas
# (não removi nada do que você validou)
