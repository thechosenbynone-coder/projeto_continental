import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal de Suprimentos & Compliance", page_icon="🛡️", layout="wide")

# CSS para garantir que os números nos balões fiquem visíveis (Azul sobre Cinza)
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { color: #004280 !important; font-size: 28px !important; }
    [data-testid="stMetricLabel"] { color: #333333 !important; font-weight: bold !important; }
    div[data-testid="stMetric"] { background-color: #f0f2f6; padding: 15px; border-radius: 10px; border: 1px solid #d1d5db; }
    .stTabs [aria-selected="true"] { background-color: #004280 !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 1. CARREGAR DADOS ---
@st.cache_data
def carregar_dados():
    # Procura o arquivo na mesma pasta do script
    caminho_db = "compras_suprimentos.db"
    if not os.path.exists(caminho_db):
        st.error(f"Arquivo {caminho_db} não encontrado! Certifique-se de que ele está na mesma pasta do app.")
        return pd.DataFrame()
    
    conn = sqlite3.connect(caminho_db)
    df = pd.read_sql_query("SELECT * FROM base_compras", conn)
    conn.close()
    df['data_emissao'] = pd.to_datetime(df['data_emissao'])
    if 'ncm' in df.columns:
        df['ncm'] = df['ncm'].astype(str).str.replace('.', '', regex=False)
    return df

df = carregar_dados()

if df.empty:
    st.stop()

# --- 2. CÉREBRO DE COMPLIANCE (PESOS DE RISCO) ---
def definir_risco_detalhado(row):
    desc = str(row['desc_prod']).upper()
    ncm = str(row.get('ncm', '0000'))
    
    if ncm.startswith(('2710', '3403', '3208', '3209', '3814')) or any(x in desc for x in ['OLEO', 'GRAXA', 'LUBRIFICANTE', 'TINTA']):
        return '🔴 CRÍTICO - QUÍMICO', 'LO + CTF + FISPQ', 100
    
    if ncm.startswith(('4015', '4203', '6116', '6403', '6506', '9020')) or any(x in desc for x in ['LUVA', 'BOTA', 'CAPACETE', 'OCULOS', 'MASCARA']):
        if not any(x in desc for x in ['ESGOTO', 'PVC', 'CONEXAO']):
            return '🟠 CRÍTICO - EPI', 'CA Válido + NR-06', 50
            
    if ncm.startswith(('4009', '7307', '8481')) and any(x in desc for x in ['HIDRAULI', 'PRESSAO', 'MANGUEIRA']):
        return '🟡 CRÍTICO - PRESSÃO', 'Teste Hidrostático + NR-12', 30
        
    return '🟢 GERAL', 'Cadastro Regular', 1

# Processamento
df_itens = df.groupby(['cod_prod', 'desc_prod', 'u_medida', 'ncm']).agg(
    Total_Gasto=('v_total_item', 'sum'),
    Qtd_Total=('qtd', 'sum')
).reset_index()

df_itens[['Categoria', 'Exigencia', 'Peso_Risco']] = df_itens.apply(lambda r: pd.Series(definir_risco_detalhado(r)), axis=1)

# Ranking de Fornecedores por Risco
df_merge = df.merge(df_itens[['desc_prod', 'ncm', 'Categoria', 'Peso_Risco']], on=['desc_prod', 'ncm'])
df_ranking_forn = df_merge.groupby('nome_emit').agg(
    Total_Financeiro=('v_total_item', 'sum'),
    Qtd_Itens_Criticos=('Peso_Risco', lambda x: (x > 1).sum()),
    Score_Risco=('Peso_Risco', 'sum')
).reset_index().sort_values('Score_Risco', ascending=False)

# --- 3. INTERFACE ---
st.title("🛡️ Portal de Inteligência em Suprimentos")
st.markdown("Monitoramento Estratégico de Vendor List e Compliance Técnico")

# KPIs
m1, m2, m3, m4 = st.columns(4)
m1.metric("Gasto Total", f"R$ {df['v_total_item'].sum():,.2f}")
m2.metric("Fornecedores Ativos", f"{df['cnpj_emit'].nunique()}")
m3.metric("Itens Críticos", f"{len(df_itens[df_itens['Peso_Risco'] > 1])}")
m4.metric("Itens Cadastrados", f"{len(df_itens)}")

st.markdown("---")

aba1, aba2, aba3 = st.tabs(["📊 Dashboard de Risco", "📋 Ficha de Qualificação", "🔎 Biblioteca de Itens"])

with aba1:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Gasto por Categoria de Risco")
        df_pizza = df_itens.groupby('Categoria')['Total_Gasto'].sum().reset_index()
        fig_p = px.pie(df_pizza, values='Total_Gasto', names='Categoria', 
                     color_discrete_map={'🔴 CRÍTICO - QUÍMICO':'#dc2626', '🟠 CRÍTICO - EPI':'#f97316', '🟡 CRÍTICO - PRESSÃO':'#facc15', '🟢 GERAL':'#3b82f6'},
                     hole=0.4)
        st.plotly_chart(fig_p)

    with c2:
        st.subheader("Top 10 Fornecedores (Índice de Risco)")
        df_top = df_ranking_forn.head(10)
        fig_r = px.bar(df_top, x='Score_Risco', y='nome_emit', orientation='h', labels={'Score_Risco': 'Risco Acumulado'})
        fig_r.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_r)

with aba2:
    st.subheader("Auditoria por Fornecedor")
    fornecedor_sel = st.selectbox("Selecione o Fornecedor:", df_ranking_forn['nome_emit'])
    row_rank = df_ranking_forn[df_ranking_forn['nome_emit'] == fornecedor_sel].iloc[0]
    
    col_a, col_b = st.columns([1, 2])
    with col_a:
        st.info(f"**Resumo Financeiro**")
        st.write(f"💰 Total: R$ {row_rank['Total_Financeiro']:,.2f}")
        st.write(f"⚠️ Itens Críticos: {row_rank['Qtd_Itens_Criticos']}")
    
    with col_b:
        itens_f = df_merge[df_merge['nome_emit'] == fornecedor_sel]
        itens_f_crit = itens_f[itens_f['Peso_Risco'] > 1].drop_duplicates('desc_prod')
        if not itens_f_crit.empty:
            st.warning("🚨 Este fornecedor exige auditoria de documentos (6.1.2).")
            st.dataframe(itens_f_crit[['desc_prod', 'Categoria']], hide_index=True)
        else:
            st.success("✅ Fornecedor de Itens Gerais.")

with aba3:
    st.subheader("Biblioteca Geral de Materiais")
    st.dataframe(
        df_itens[['Categoria', 'desc_prod', 'ncm', 'Total_Gasto']]
        .sort_values('Total_Gasto', ascending=False)
        .style.format({'Total_Gasto': 'R$ {:.2f}'}),
        height=500, use_container_width=True
    )
