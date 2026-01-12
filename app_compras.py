import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
import locale

# =====================================================
# 1. IDIOMA AUTOMÁTICO (PT / EN)
# =====================================================
lang, _ = locale.getdefaultlocale()

if lang and lang.lower().startswith('pt'):
    APP_LANG = 'pt'
else:
    APP_LANG = 'en'

TEXT = {
    'pt': {
        'title': "🏗️ Portal de Inteligência em Suprimentos",
        'period': "📅 Período de Análise",
        'select_year': "Selecione os anos fiscais",
        'exec_review': "📌 Visão Executiva",
        'total_spend': "💰 Gasto Total",
        'critical_spend': "⚠️ Gasto Crítico",
        'saving': "🎯 Oportunidade de Saving",
        'supplier_conc': "🏢 Concentração de Fornecedores",
        'price_vol': "📈 Volatilidade de Preços",
        'top3': "Top 3 fornecedores",
        'variation': "Variação >20%",
        'key_insights': "🧠 Principais Insights",
        'spend_trend': "📊 Evolução de Gastos",
        'tabs': [
            "📌 Visão Executiva",
            "📊 Dashboard",
            "📇 Cadastro & Auditoria",
            "📉 Histórico de Preços",
            "🔍 Busca Avançada"
        ]
    },
    'en': {
        'title': "🏗️ Procurement Intelligence Portal",
        'period': "📅 Analysis Period",
        'select_year': "Select fiscal years",
        'exec_review': "📌 Executive Review",
        'total_spend': "💰 Total Spend",
        'critical_spend': "⚠️ Critical Spend",
        'saving': "🎯 Saving Opportunity",
        'supplier_conc': "🏢 Supplier Concentration",
        'price_vol': "📈 Price Volatility",
        'top3': "Top 3 suppliers",
        'variation': "Variation >20%",
        'key_insights': "🧠 Key Insights",
        'spend_trend': "📊 Spend Trend",
        'tabs': [
            "📌 Executive Review",
            "📊 Dashboard",
            "📇 Supplier Profile",
            "📉 Price History",
            "🔍 Advanced Search"
        ]
    }
}

T = TEXT[APP_LANG]

# =====================================================
# 2. CONFIGURAÇÃO STREAMLIT
# =====================================================
st.set_page_config(
    page_title=T['title'],
    page_icon="🏗️",
    layout="wide"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    div[data-testid="stMetric"] {
        background-color: var(--secondary-background-color);
        border: 1px solid rgba(128,128,128,0.2);
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #004280;
    }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 3. FUNÇÕES
# =====================================================
def format_brl(v):
    if pd.isna(v): return "R$ 0,00"
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# =====================================================
# 4. CARREGAMENTO DE DADOS
# =====================================================
@st.cache_data
def carregar_dados():
    if not os.path.exists("compras_suprimentos.db"):
        return pd.DataFrame()

    conn = sqlite3.connect("compras_suprimentos.db")
    df = pd.read_sql("SELECT * FROM base_compras", conn)
    conn.close()

    df['data_emissao'] = pd.to_datetime(df['data_emissao'])
    df['ano'] = df['data_emissao'].dt.year
    df['mes_ano'] = df['data_emissao'].dt.strftime('%Y-%m')
    df['desc_prod'] = df['desc_prod'].astype(str).str.upper().str.strip()
    df['ncm'] = df['ncm'].astype(str).str.replace('.', '', regex=False)
    df['cod_prod'] = df.get('cod_prod', '').astype(str)

    return df

df_full = carregar_dados()
if df_full.empty:
    st.error("⚠️ Base de dados vazia.")
    st.stop()

# =====================================================
# 5. FILTROS
# =====================================================
st.title(T['title'])

anos = sorted(df_full['ano'].unique())
sel_anos = st.pills(
    T['select_year'],
    options=anos,
    selection_mode="multi",
    default=anos
)

df = df_full[df_full['ano'].isin(sel_anos)].copy()
st.divider()

# =====================================================
# 6. CLASSIFICAÇÃO DE MATERIAL
# =====================================================
def classificar_material(row):
    desc, ncm = row['desc_prod'], row['ncm']

    if ncm.startswith(('2710','3403')) or any(x in desc for x in ['OLEO','GRAXA']):
        return '🔴 QUÍMICO (CRÍTICO)'
    if any(x in desc for x in ['CABO DE ACO','MANILHA','GANCHO']):
        return '🟡 IÇAMENTO (CRÍTICO)'
    if any(x in desc for x in ['LUVA','CAPACETE','OCULOS','BOTA']):
        return '🟠 EPI (CRÍTICO)'
    if any(x in desc for x in ['TUBO','PVC','VALVULA']):
        return '💧 HIDRÁULICA'
    if any(x in desc for x in ['CABO','DISJUNTOR','FIO']):
        return '⚡ ELÉTRICA'
    return '📦 GERAL'

df_grouped = df.groupby(['desc_prod','ncm','cod_prod']).agg(
    Total_Gasto=('v_total_item','sum'),
    Qtd_Total=('qtd','sum'),
    Menor_Preco=('v_unit','min')
).reset_index()

df_grouped['Categoria'] = df_grouped.apply(classificar_material, axis=1)

df_last = df.sort_values('data_emissao').drop_duplicates(
    ['desc_prod','ncm','cod_prod'], keep='last'
)[['desc_prod','ncm','cod_prod','v_unit','nome_emit','data_emissao']]

df_last.rename(columns={
    'v_unit':'Ultimo_Preco',
    'nome_emit':'Ultimo_Forn',
    'data_emissao':'Ultima_Data'
}, inplace=True)

df_final = df_grouped.merge(df_last, on=['desc_prod','ncm','cod_prod'])
df_final['Variacao_Preco'] = (
    (df_final['Ultimo_Preco'] - df_final['Menor_Preco']) /
    df_final['Menor_Preco']
)
df_final['Saving_Potencial'] = (
    df_final['Total_Gasto'] -
    (df_final['Menor_Preco'] * df_final['Qtd_Total'])
)

# =====================================================
# 7. TABS
# =====================================================
tab_exec, tab_dash, tab_cad, tab_hist, tab_busca = st.tabs(T['tabs'])

# =====================================================
# 8. EXECUTIVE REVIEW
# =====================================================
with tab_exec:
    st.subheader(T['exec_review'])

    total_spend = df['v_total_item'].sum()
    critical_spend = df_final[df_final['Categoria'].str.contains('CRÍTICO')]['Total_Gasto'].sum()
    saving_total = df_final['Saving_Potencial'].sum()

    top3_pct = (
        df.groupby('nome_emit')['v_total_item']
        .sum().nlargest(3).sum() / total_spend
    )

    volatile_items = df_final[df_final['Variacao_Preco'] > 0.2].shape[0]

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric(T['total_spend'], format_brl(total_spend))
    c2.metric(T['critical_spend'], format_brl(critical_spend), f"{critical_spend/total_spend:.0%}")
    c3.metric(T['saving'], format_brl(saving_total))
    c4.metric(T['supplier_conc'], f"{top3_pct:.0%}", T['top3'])
    c5.metric(T['price_vol'], volatile_items, T['variation'])

    st.markdown(f"""
    ### {T['key_insights']}
    - ⚠️ **{critical_spend/total_spend:.0%}** do gasto está concentrado em itens críticos  
    - 🏢 **{T['top3']}** concentram **{top3_pct:.0%}** do gasto total  
    - 🎯 Economia potencial estimada em **{format_brl(saving_total)}**
    """)

    fig = px.area(
        df.groupby('mes_ano')['v_total_item'].sum().reset_index(),
        x='mes_ano',
        y='v_total_item'
    )
    fig.update_layout(height=280, yaxis_tickformat="R$ ,.2f")
    st.plotly_chart(fig, use_container_width=True)

# =====================================================
# As demais abas (Dashboard, Cadastro, Histórico, Busca)
# podem ser mantidas exatamente como você já tem.
# =====================================================
