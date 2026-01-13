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
# (Importe as outras tabs aqui quando criar os arquivos: ui.tab_dashboard, etc)

# Configuração da Página
st.set_page_config(page_title="Portal de Inteligência em Suprimentos", page_icon="🏗️", layout="wide")
aplicar_tema()

# ... (Mantenha sua função carregar_dados aqui ou mova para data/database.py) ...
# Para facilitar, vou assumir que você manteve carregar_dados aqui por enquanto.
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
    st.stop()

# Filtros
anos = sorted(df_full['ano'].unique())
sel_anos = st.pills("Selecione Ano", anos, selection_mode="multi", default=anos)
if not sel_anos: st.stop()
df = df_full[df_full['ano'].isin(sel_anos)].copy()

# --- APLICAÇÃO DA INTELIGÊNCIA (USANDO O MÓDULO NOVO) ---
# Aqui usamos a função que importamos de utils.classifiers
df['Categoria'] = df.apply(classificar_material, axis=1)

# --- RENDERIZAÇÃO DAS ABAS ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Visão Geral", "Dashboard", "Fornecedores", "Negociação", "Busca"])

with tab4:
    # Chama a função do módulo UI passando os dados já tratados
    render_tab_negociacao(df)

# (Preencha as outras abas chamando suas respectivas funções)
