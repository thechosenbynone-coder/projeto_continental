import streamlit as st
import pandas as pd
import sqlite3
import os
import locale

# --- IMPORTS DOS TEUS MÓDULOS ---
from styles.theme import aplicar_tema
from utils.classifiers import classificar_materiais_turbo
from utils.formatters import format_brl, format_perc

# Importando as funções das abas (Devem estar preenchidas nos arquivos da pasta ui)
from ui.tab_exec_review import render_tab_exec_review
from ui.tab_dashboard import render_tab_dashboard
from ui.tab_fornecedores import render_tab_fornecedores
from ui.tab_negociacao import render_tab_negociacao
from ui.tab_busca import render_tab_busca

# =====================================================
# 1. CONFIGURAÇÕES INICIAIS
# =====================================================
st.set_page_config(
    page_title="Portal de Inteligência em Suprimentos",
    page_icon="🏗️",
    layout="wide"
)

# Aplica o tema visual centralizado
aplicar_tema()

# Configuração de Idioma
lang, _ = locale.getdefaultlocale()
APP_LANG = 'pt' if lang and lang.lower().startswith('pt') else 'en'

TEXT = {
    'pt': {
        'title': "🏗️ Portal de Inteligência em Suprimentos",
        'tabs': ["📌 Visão Executiva", "📊 Dashboard", "📇 Gestão de Fornecedores", "💰 Cockpit de Negociação", "🔍 Busca Avançada"]
    },
    'en': {
        'title': "🏗️ Procurement Intelligence Portal",
        'tabs': ["📌 Executive Review", "📊 Dashboard", "📇 Vendor Management", "💰 Negotiation Cockpit", "🔍 Advanced Search"]
    }
}
T = TEXT[APP_LANG]

# =====================================================
# 2. CARREGAMENTO DE DADOS
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

    # Tratamentos de data e texto
    df['data_emissao'] = pd.to_datetime(df['data_emissao'])
    df['ano'] = df['data_emissao'].dt.year
    df['mes_ano'] = df['data_emissao'].dt.strftime('%Y-%m')
    df['desc_prod'] = df['desc_prod'].astype(str).str.upper().str.strip()
    df['ncm'] = df['ncm'].astype(str).str.replace('.', '', regex=False)

    # Cálculo de Impostos
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
    st.error("⚠️ Base de dados não encontrada ou vazia.")
    st.stop()

# =====================================================
# 3. SIDEBAR E FILTROS
# =====================================================
with st.sidebar:
    st.title("⚙️ Filtros")
    anos_disponiveis = sorted(df_full['ano'].unique(), reverse=True)
    sel_anos = st.multiselect("Anos Fiscais:", options=anos_disponiveis, default=anos_disponiveis[:1])

    if not sel_anos:
        st.warning("Selecione um ano.")
        st.stop()

df = df_full[df_full['ano'].isin(sel_anos)].copy()

# =====================================================
# 4. PROCESSAMENTO (USANDO OS NOVOS MÓDULOS)
# =====================================================
# Usa o classificador vetorizado para alta performance
df['Categoria'] = classificar_materiais_turbo(df)

# Agregações para as abas de análise
df_grouped = df.groupby(['desc_prod', 'ncm', 'cod_prod', 'Categoria']).agg(
    Total_Gasto=('v_total_item', 'sum'),
    Qtd_Total=('qtd', 'sum'),
    Menor_Preco=('v_unit', 'min')
).reset_index()

df_last = (
    df.sort_values('data_emissao')
      .drop_duplicates(['desc_prod', 'ncm', 'cod_prod'], keep='last')
      [['desc_prod', 'ncm', 'cod_prod', 'v_unit', 'nome_emit', 'data_emissao']]
      .rename(columns={'v_unit': 'Ultimo_Preco', 'nome_emit': 'Ultimo_Forn', 'data_emissao': 'Ultima_Data'})
)

df_final = df_grouped.merge(df_last, on=['desc_prod', 'ncm', 'cod_prod'])
df_final['Saving_Potencial'] = df_final['Total_Gasto'] - (df_final['Menor_Preco'] * df_final['Qtd_Total'])

# =====================================================
# 5. RENDERIZAÇÃO DAS ABAS
# =====================================================
st.title(T['title'])
tab1, tab2, tab3, tab4, tab5 = st.tabs(T['tabs'])

with tab1: render_tab_exec_review(df, df_final)
with tab2: render_tab_dashboard(df, df_final)
with tab3: render_tab_fornecedores(df, df_final)
with tab4: render_tab_negociacao(df)
with tab5: render_tab_busca(df_full)

