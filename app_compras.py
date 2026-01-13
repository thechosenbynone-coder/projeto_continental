import streamlit as st
import pandas as pd
import sqlite3
import os
import locale

# --- IMPORTS DOS MÓDULOS (A Mágica Acontece Aqui) ---
from styles.theme import aplicar_tema
from utils.classifiers import classificar_material
from utils.formatters import format_brl

# Importando as abas
from ui.tab_exec_review import render_tab_exec_review
from ui.tab_dashboard import render_tab_dashboard
from ui.tab_fornecedores import render_tab_fornecedores
from ui.tab_negociacao import render_tab_negociacao
from ui.tab_busca import render_tab_busca

# =====================================================
# CONFIGURAÇÃO GERAL
# =====================================================
st.set_page_config(page_title="Portal de Inteligência em Suprimentos", page_icon="🏗️", layout="wide")

# Aplica o tema visual (CSS)
aplicar_tema()

# Detecta idioma
lang, _ = locale.getdefaultlocale()
APP_LANG = 'pt' if lang and lang.lower().startswith('pt') else 'en'
TEXT = {
    'pt': {'title': "🏗️ Portal de Inteligência em Suprimentos", 'tabs': ["📌 Visão Executiva", "📊 Dashboard", "📇 Gestão de Fornecedores", "💰 Cockpit de Negociação", "🔍 Busca Avançada"]},
    'en': {'title': "🏗️ Procurement Intelligence Portal", 'tabs': ["📌 Executive Review", "📊 Dashboard", "📇 Vendor Management", "💰 Negotiation Cockpit", "🔍 Advanced Search"]}
}
T = TEXT[APP_LANG]

# =====================================================
# CARGA DE DADOS
# =====================================================
@st.cache_data
def carregar_dados():
    if not os.path.exists("compras_suprimentos.db"): return pd.DataFrame()
    conn = sqlite3.connect("compras_suprimentos.db")
    df = pd.read_sql("SELECT * FROM base_compras", conn)
    conn.close()
    if df.empty: return pd.DataFrame()
    
    # Tratamentos Básicos
    df['data_emissao'] = pd.to_datetime(df['data_emissao'])
    df['ano'] = df['data_emissao'].dt.year
    df['mes_ano'] = df['data_emissao'].dt.strftime('%Y-%m')
    df['desc_prod'] = df['desc_prod'].astype(str).str.upper().str.strip()
    df['ncm'] = df['ncm'].astype(str).str.replace('.', '', regex=False)
    
    # Colunas de Imposto e Código
    cols_imposto = ['v_icms','v_ipi','v_pis','v_cofins','v_iss']
    for col in cols_imposto:
        if col not in df.columns: df[col] = 0.0
    df['Imposto_Total'] = df[cols_imposto].sum(axis=1)
    if 'cod_prod' not in df.columns: df['cod_prod'] = ''
    df['cod_prod'] = df['cod_prod'].astype(str)
    
    return df

df_full = carregar_dados()
if df_full.empty:
    st.error("⚠️ Base de dados vazia. Rode o extrator primeiro.")
    st.stop()

# =====================================================
# FILTROS E PROCESSAMENTO
# =====================================================
st.title(T['title'])
anos = sorted(df_full['ano'].unique())
sel_anos = st.pills("Selecione Ano", anos, selection_mode="multi", default=anos)

if not sel_anos:
    st.warning("Selecione pelo menos um ano.")
    st.stop()

df = df_full[df_full['ano'].isin(sel_anos)].copy()
st.divider()

# --- APLICAÇÃO DA INTELIGÊNCIA ---
# Classifica item a item
df['Categoria'] = df.apply(classificar_material, axis=1)

# Agrupamento Geral (usado em várias abas)
df_grouped = df.groupby(['desc_prod','ncm','cod_prod', 'Categoria']).agg(
    Total_Gasto=('v_total_item','sum'),
    Qtd_Total=('qtd','sum'),
    Menor_Preco=('v_unit','min')
).reset_index()

# Pega última compra para comparações
df_last = df.sort_values('data_emissao').drop_duplicates(['desc_prod','ncm','cod_prod'], keep='last')[['desc_prod','ncm','cod_prod','v_unit','nome_emit','data_emissao']]
df_last.rename(columns={'v_unit':'Ultimo_Preco', 'nome_emit':'Ultimo_Forn', 'data_emissao':'Ultima_Data'}, inplace=True)

# Merge Final para análises consolidadas
df_final = df_grouped.merge(df_last, on=['desc_prod','ncm','cod_prod'])
df_final['Variacao_Preco'] = (df_final['Ultimo_Preco'] - df_final['Menor_Preco']) / df_final['Menor_Preco']
df_final['Saving_Potencial'] = df_final['Total_Gasto'] - (df_final['Menor_Preco'] * df_final['Qtd_Total'])

# =====================================================
# INTERFACE (RENDERIZAÇÃO)
# =====================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs(T['tabs'])

with tab1: render_tab_exec_review(df, df_final)
with tab2: render_tab_dashboard(df, df_final)
with tab3: render_tab_fornecedores(df, df_final)
with tab4: render_tab_negociacao(df) # Esta aba calcula seus próprios agregados
with tab5: render_tab_busca(df_final)
