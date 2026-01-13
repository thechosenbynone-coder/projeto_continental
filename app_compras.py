import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
import locale

# 👉 NOVO IMPORT (APENAS ISSO FOI ADICIONADO)
from styles.theme import aplicar_tema

# =====================================================
# 1. CONFIGURAÇÕES INICIAIS
# =====================================================
st.set_page_config(
    page_title="Portal de Inteligência em Suprimentos",
    page_icon="🏗️",
    layout="wide"
)

# 👉 APLICA O TEMA GLOBAL (CSS EXTERNO)
aplicar_tema()

# Detecta idioma do sistema
lang, _ = locale.getdefaultlocale()
APP_LANG = 'pt' if lang and lang.lower().startswith('pt') else 'en'

TEXT = {
    'pt': {
        'title': "🏗️ Portal de Inteligência em Suprimentos",
        'period': "📅 Período de Análise",
        'select_year': "Selecione os anos fiscais",
        'exec_review': "📌 Visão Executiva",
        'total_spend': "💰 Gasto Total",
        'tabs': [
            "📌 Visão Executiva",
            "📊 Dashboard",
            "📇 Gestão de Fornecedores",
            "💰 Cockpit de Negociação",
            "🔍 Busca Avançada"
        ]
    },
    'en': {
        'title': "🏗️ Procurement Intelligence Portal",
        'period': "📅 Analysis Period",
        'select_year': "Select fiscal years",
        'exec_review': "📌 Executive Review",
        'total_spend': "💰 Total Spend",
        'tabs': [
            "📌 Executive Review",
            "📊 Dashboard",
            "📇 Vendor Management",
            "💰 Negotiation Cockpit",
            "🔍 Advanced Search"
        ]
    }
}
T = TEXT[APP_LANG]

# =====================================================
# 2. FUNÇÕES DE FORMATAÇÃO
# =====================================================
def format_brl(v):
    if pd.isna(v): 
        return "R$ 0,00"
    try:
        val = f"{float(v):,.2f}"
        return f"R$ {val.replace(',', 'X').replace('.', ',').replace('X', '.')}"
    except:
        return str(v)

def format_perc(v):
    if pd.isna(v): 
        return "0,0%"
    try:
        val = f"{float(v)*100:.1f}"
        return f"{val.replace('.', ',')}%"
    except:
        return str(v)

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
    df['mes_ano'] = df['data_emissao'].dt.strftime('%Y-%m')

    df['desc_prod'] = df['desc_prod'].astype(str).str.upper().str.strip()
    df['ncm'] = df['ncm'].astype(str).str.replace('.', '', regex=False)

    cols_imposto = ['v_icms', 'v_ipi', 'v_pis', 'v_cofins', 'v_iss']
    for col in cols_imposto:
        if col not in df.columns:
            df[col] = 0.0

    df['Imposto_Total'] = df[cols_imposto].sum(axis=1)

    if 'cod_prod' not in df.columns:
        df['cod_prod'] = ''
    df['cod_prod'] = df['cod_prod'].astype(str)

    return df

df_full = carregar_dados()

if df_full.empty:
    st.error("⚠️ Base de dados vazia. Rode o extrator primeiro.")
    st.stop()

# =====================================================
# 4. FILTROS
# =====================================================
st.title(T['title'])

anos_disponiveis = sorted(df_full['ano'].unique())
sel_anos = st.pills(
    T['select_year'],
    options=anos_disponiveis,
    selection_mode="multi",
    default=anos_disponiveis
)

if not sel_anos:
    st.warning("Selecione pelo menos um ano para visualizar os dados.")
    st.stop()

df = df_full[df_full['ano'].isin(sel_anos)].copy()
st.divider()

# =====================================================
# 5. CLASSIFICAÇÃO DE MATERIAIS
# =====================================================
def classificar_material(row):
    desc, ncm = row['desc_prod'], row['ncm']

    if ncm.startswith(('2710','3403')) or 'OLEO' in desc:
        return '🔴 QUÍMICO (CRÍTICO)'
    if 'CABO DE ACO' in desc or 'MANILHA' in desc:
        return '🟡 IÇAMENTO (CRÍTICO)'
    if 'LUVA' in desc or 'CAPACETE' in desc:
        return '🟠 EPI (CRÍTICO)'
    if 'TUBO' in desc or 'VALVULA' in desc:
        return '💧 HIDRÁULICA'
    if 'CABO' in desc or 'DISJUNTOR' in desc:
        return '⚡ ELÉTRICA'
    if 'CIMENTO' in desc or 'AREIA' in desc:
        return '🧱 CIVIL'
    if 'CHAVE' in desc or 'BROCA' in desc:
        return '🔧 FERRAMENTAS'

    return '📦 GERAL'

df['Categoria'] = df.apply(classificar_material, axis=1)

# =====================================================
# 6. AGREGAÇÕES
# =====================================================
df_grouped = df.groupby(
    ['desc_prod', 'ncm', 'cod_prod', 'Categoria']
).agg(
    Total_Gasto=('v_total_item', 'sum'),
    Qtd_Total=('qtd', 'sum'),
    Menor_Preco=('v_unit', 'min')
).reset_index()

df_last = (
    df.sort_values('data_emissao')
      .drop_duplicates(['desc_prod', 'ncm', 'cod_prod'], keep='last')
      [['desc_prod', 'ncm', 'cod_prod', 'v_unit', 'nome_emit', 'data_emissao']]
      .rename(columns={
          'v_unit': 'Ultimo_Preco',
          'nome_emit': 'Ultimo_Forn',
          'data_emissao': 'Ultima_Data'
      })
)

df_final = df_grouped.merge(df_last, on=['desc_prod', 'ncm', 'cod_prod'])
df_final['Variacao_Preco'] = (
    (df_final['Ultimo_Preco'] - df_final['Menor_Preco']) /
    df_final['Menor_Preco']
)
df_final['Saving_Potencial'] = (
    df_final['Total_Gasto'] -
    (df_final['Menor_Preco'] * df_final['Qtd_Total'])
)

# =====================================================
# 7. INTERFACE
# =====================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs(T['tabs'])

with tab1:
    st.subheader(T['exec_review'])
    st.metric("💰 Gasto Total", format_brl(df['v_total_item'].sum()))
    st.metric("💸 Imposto Total", format_brl(df['Imposto_Total'].sum()))
