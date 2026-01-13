import streamlit as st
import pandas as pd
import sqlite3
import os
import locale

# --- IMPORTS DOS SEUS NOVOS MÓDULOS ---
from styles.theme import aplicar_tema
from utils.classifiers import classificar_material
from utils.formatters import format_brl, format_perc
from ui.tab_negociacao import render_tab_negociacao

# Configuração da Página
st.set_page_config(page_title="Portal de Inteligência em Suprimentos", page_icon="🏗️", layout="wide")
aplicar_tema()

# Detecta idioma
lang, _ = locale.getdefaultlocale()
APP_LANG = 'pt' if lang and lang.lower().startswith('pt') else 'en'

TEXT = {
    'pt': {'title': "🏗️ Portal de Inteligência em Suprimentos", 'tabs': ["📌 Visão Executiva", "📊 Dashboard", "📇 Gestão de Fornecedores", "💰 Cockpit de Negociação", "🔍 Busca Avançada"]},
    'en': {'title': "🏗️ Procurement Intelligence Portal", 'tabs': ["📌 Executive Review", "📊 Dashboard", "📇 Vendor Management", "💰 Negotiation Cockpit", "🔍 Advanced Search"]}
}
T = TEXT[APP_LANG]

# Carga de Dados
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
    st.error("⚠️ Base de dados vazia.")
    st.stop()

# Filtros
st.title(T['title'])
anos = sorted(df_full['ano'].unique())
sel_anos = st.pills("Selecione Ano", anos, selection_mode="multi", default=anos)
if not sel_anos: st.stop()
df = df_full[df_full['ano'].isin(sel_anos)].copy()

# --- APLICAÇÃO DA INTELIGÊNCIA (USANDO O MÓDULO NOVO) ---
# Aqui usamos a função que importamos de utils.classifiers
df['Categoria'] = df.apply(classificar_material, axis=1)

# --- RENDERIZAÇÃO DAS ABAS ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(T['tabs'])

# Aba 1: Executiva (Código simplificado mantido aqui por enquanto)
with tab1:
    st.metric("💰 Gasto Total", format_brl(df['v_total_item'].sum()))
    st.metric("💸 Imposto Total", format_brl(df['Imposto_Total'].sum()))

# Aba 4: Negociação (Agora chama o módulo externo!)
with tab4:
    render_tab_negociacao(df)

# (Nota: As outras abas precisam ter seu código migrado para pastas 'ui' também, 
# mas com essa estrutura o sistema já roda a aba de negociação de forma modular)
