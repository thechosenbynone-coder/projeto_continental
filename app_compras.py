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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    div[data-testid="stMetric"] {
        background-color: var(--secondary-background-color);
        border: 1px solid rgba(128,128,128,0.2);
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #004280;
    }
    
    .card-fornecedor {
        background-color: var(--secondary-background-color);
        padding: 25px;
        border-radius: 12px;
        border: 1px solid rgba(128,128,128,0.2);
        margin-bottom: 20px;
        border-top: 5px solid #004280;
    }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. FUNÇÕES
# =====================================================
def format_brl_str(v):
    if pd.isna(v): return "R$ 0,00"
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# =====================================================
# 3. DADOS
# =====================================================
@st.cache_data
def carregar_dados():
    if not os.path.exists("compras_suprimentos.db"): return pd.DataFrame()
    conn = sqlite3.connect("compras_suprimentos.db")
    df = pd.read_sql("SELECT * FROM base_compras", conn)
    conn.close()

    df['data_emissao'] = pd.to_datetime(df['data_emissao'])
    df['ano'] = df['data_emissao'].dt.year
    df['mes_ano'] = df['data_emissao'].dt.strftime('%Y-%m')
    df['desc_prod'] = df['desc_prod'].astype(str).str.upper().str.strip()
    df['ncm'] = df['ncm'].astype(str).str.replace('.', '', regex=False)
    df['cod_prod'] = df.get('cod_prod', '').astype(str).str.strip()
    return df

df_full = carregar_dados()
if df_full.empty:
    st.error("⚠️ Base vazia.")
    st.stop()

# =====================================================
# 4. FILTROS
# =====================================================
st.title("🏗️ Portal de Inteligência em Suprimentos")

anos = sorted(df_full['ano'].unique())
sel_anos = st.pills("Ano Fiscal", anos, selection_mode="multi", default=anos)

df = df_full[df_full['ano'].isin(sel_anos)].copy()
st.divider()

# =====================================================
# 5. CLASSIFICAÇÃO
# =====================================================
def classificar_material(row):
    desc, ncm = row['desc_prod'], row['ncm']
    if ncm.startswith(('2710','3403')) or 'OLEO' in desc:
        return '🔴 QUÍMICO (CRÍTICO)'
    if any(x in desc for x in ['CABO DE ACO','MANILHA','GANCHO']):
        return '🟡 IÇAMENTO (CRÍTICO)'
    if any(x in desc for x in ['LUVA','CAPACETE','OCULOS']):
        return '🟠 EPI (CRÍTICO)'
    if 'TUBO' in desc: return '💧 HIDRÁULICA'
    if 'CABO' in desc: return '⚡ ELÉTRICA'
    return '📦 GERAL'

df_grouped = df.groupby(['desc_prod','ncm','cod_prod']).agg(
    Total_Gasto=('v_total_item','sum'),
    Qtd_Total=('qtd','sum'),
    Menor_Preco=('v_unit','min')
).reset_index()

df_grouped['Categoria'] = df_grouped.apply(classificar_material, axis=1)

df_last = df.sort_values('data_emissao').drop_duplicates(
    ['desc_prod','ncm','cod_prod'], keep='last'
)[['desc_prod','ncm','cod_prod','v_unit','nome_emit','n_nf','data_emissao']]

df_last.rename(columns={
    'v_unit':'Ultimo_Preco',
    'nome_emit':'Ultimo_Forn',
    'n_nf':'Ultima_NF',
    'data_emissao':'Ultima_Data'
}, inplace=True)

df_final = df_grouped.merge(df_last, on=['desc_prod','ncm','cod_prod'])
df_final['Variacao_Preco'] = (df_final['Ultimo_Preco'] - df_final['Menor_Preco']) / df_final['Menor_Preco']
df_final['Saving_Potencial'] = df_final['Total_Gasto'] - (df_final['Menor_Preco'] * df_final['Qtd_Total'])

# =====================================================
# 6. TABS
# =====================================================
tab_exec, tab_dash, tab_cad, tab_hist, tab_busca = st.tabs([
    "📌 Executive Review",
    "📊 Dashboard",
    "📇 Cadastro",
    "📉 Histórico",
    "🔍 Busca"
])

# =====================================================
# EXECUTIVE REVIEW
# =====================================================
with tab_exec:
    st.subheader("📌 Executive Review")

    total_spend = df['v_total_item'].sum()
    critical_spend = df_final[df_final['Categoria'].str.contains('CRÍTICO')]['Total_Gasto'].sum()
    critical_pct = critical_spend / total_spend if total_spend else 0

    saving_total = df_final['Saving_Potencial'].sum()

    top3_pct = (
        df.groupby('nome_emit')['v_total_item']
        .sum().nlargest(3).sum() / total_spend
        if total_spend else 0
    )

    volatile_items = df_final[df_final['Variacao_Preco'] > 0.2].shape[0]

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("💰 Total Spend", format_brl_str(total_spend))
    c2.metric("⚠️ Critical Spend", format_brl_str(critical_spend), f"{critical_pct:.0%}")
    c3.metric("🎯 Saving Opportunity", format_brl_str(saving_total))
    c4.metric("🏢 Supplier Concentration", f"{top3_pct:.0%}", "Top 3 suppliers")
    c5.metric("📈 Price Volatility", volatile_items, ">20% variation")

    st.markdown("### 🧠 Key Insights")
    st.markdown(f"""
    - ⚠️ **{critical_pct:.0%}** of spend is related to critical materials.
    - 🏢 **Top 3 suppliers** represent **{top3_pct:.0%}** of total spend.
    - 🎯 Identified **{format_brl_str(saving_total)}** in potential savings.
    """)

    st.markdown("### 📊 Spend Trend")
    fig = px.area(
        df.groupby('mes_ano')['v_total_item'].sum().reset_index(),
        x='mes_ano',
        y='v_total_item'
    )
    fig.update_layout(height=280, yaxis_tickformat="R$ ,.2f")
    st.plotly_chart(fig, use_container_width=True)

# =====================================================
# (SEU DASHBOARD ORIGINAL CONTINUA IGUAL AQUI)
# 👉 pode manter o restante do código sem alteração
# =====================================================
