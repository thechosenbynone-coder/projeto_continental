import streamlit as st
import pandas as pd
import sqlite3
import os
import locale

# --- IMPORTS ---
from styles.theme import aplicar_tema
from utils.classifiers import classificar_materiais_turbo
from utils.formatters import format_brl, format_perc
from utils.normalizer import normalizar_unidades_v1
from utils.compliance import validar_compliance # OBRIGATÓRIO

from ui.tab_exec_review import render_tab_exec_review
from ui.tab_dashboard import render_tab_dashboard
from ui.tab_fornecedores import render_tab_fornecedores
from ui.tab_negociacao import render_tab_negociacao
from ui.tab_busca import render_tab_busca

# 1. CONFIGURAÇÃO
st.set_page_config(page_title="Portal v2.0 (Compliance Ativo)", page_icon="🏗️", layout="wide")
aplicar_tema()

# 2. CARGA DE DADOS
@st.cache_data
def carregar_dados():
    if not os.path.exists("compras_suprimentos.db"): return pd.DataFrame()
    conn = sqlite3.connect("compras_suprimentos.db")
    df = pd.read_sql("SELECT * FROM base_compras", conn)
    conn.close()
    if df.empty: return pd.DataFrame()

    df['data_emissao'] = pd.to_datetime(df['data_emissao'])
    df['ano'] = df['data_emissao'].dt.year
    df['mes_ano'] = df['data_emissao'].dt.strftime('%Y-%m')
    df['desc_prod'] = df['desc_prod'].astype(str).str.upper().str.strip()
    df['ncm'] = df['ncm'].astype(str).str.replace('.', '', regex=False)
    
    # Colunas de Imposto
    for col in ['v_icms', 'v_ipi', 'v_pis', 'v_cofins', 'v_iss']:
        if col not in df.columns: df[col] = 0.0
    df['Imposto_Total'] = df[['v_icms', 'v_ipi', 'v_pis', 'v_cofins', 'v_iss']].sum(axis=1)
    
    if 'cod_prod' not in df.columns: df['cod_prod'] = ''
    
    # Normalização (CX -> UN)
    df = normalizar_unidades_v1(df)
    return df

df_full = carregar_dados()

if df_full.empty:
    st.error("Erro: Base vazia. Rode o extrator.py novamente.")
    st.stop()

# 3. INTELIGÊNCIA (BASE COMPLETA)
# Classifica
df_full['Categoria'] = classificar_materiais_turbo(df_full)
# Audita Compliance
df_full = validar_compliance(df_full)

# Cria Base Estatística Global (Para Score de Fornecedores)
df_grouped_full = df_full.groupby(['desc_prod', 'ncm', 'cod_prod', 'Categoria']).agg(
    Total_Gasto=('v_total_item', 'sum'),
    Qtd_Total=('qtd_real', 'sum'), 
    Menor_Preco=('v_unit_real', 'min') 
).reset_index()

df_last_full = (
    df_full.sort_values('data_emissao')
    .drop_duplicates(['desc_prod', 'ncm', 'cod_prod'], keep='last')
    [['desc_prod', 'ncm', 'cod_prod', 'v_unit_real', 'nome_emit', 'data_emissao']]
)
df_final_full = df_grouped_full.merge(df_last_full, on=['desc_prod', 'ncm', 'cod_prod'])

# 4. SIDEBAR (FILTRO DE ANO)
with st.sidebar:
    st.title("⚙️ Filtros")
    anos = sorted(df_full['ano'].unique(), reverse=True)
    sel_anos = st.multiselect("Anos Fiscais:", options=anos, default=anos[:1])
    if not sel_anos: st.stop()

# Cria DF Filtrado (Apenas para Dashboards Táticos)
df_filtered = df_full[df_full['ano'].isin(sel_anos)].copy()

# Base Estatística Filtrada
df_grouped = df_filtered.groupby(['desc_prod', 'ncm', 'cod_prod', 'Categoria']).agg(
    Total_Gasto=('v_total_item', 'sum'),
    Qtd_Total=('qtd_real', 'sum'),
    Menor_Preco=('v_unit_real', 'min')
).reset_index()

df_last = (
    df_filtered.sort_values('data_emissao')
      .drop_duplicates(['desc_prod', 'ncm', 'cod_prod'], keep='last')
      [['desc_prod', 'ncm', 'cod_prod', 'v_unit_real', 'nome_emit', 'data_emissao']]
      .rename(columns={'v_unit_real': 'Ultimo_Preco', 'nome_emit': 'Ultimo_Forn', 'data_emissao': 'Ultima_Data'})
)
df_final_filtered = df_grouped.merge(df_last, on=['desc_prod', 'ncm', 'cod_prod'])
df_final_filtered['Saving_Potencial'] = df_final_filtered['Total_Gasto'] - (df_final_filtered['Menor_Preco'] * df_final_filtered['Qtd_Total'])

# 5. RENDERIZAÇÃO
st.title("🏗️ Portal de Inteligência em Suprimentos")
tabs = st.tabs(["📌 Visão Executiva", "📊 Dashboard", "📇 Gestão de Fornecedores", "💰 Cockpit", "🔍 Busca"])

with tabs[0]: render_tab_exec_review(df_filtered, df_final_filtered)
with tabs[1]: render_tab_dashboard(df_filtered, df_final_filtered)

# --- O PULO DO GATO ESTÁ AQUI ---
# Passamos df_full (SEM FILTRO) para a Tab 3
with tabs[2]: render_tab_fornecedores(df_full, df_final_full) 

with tabs[3]: render_tab_negociacao(df_filtered)
with tabs[4]: render_tab_busca(df_full)
