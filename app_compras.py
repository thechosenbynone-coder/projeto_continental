import streamlit as st
import pandas as pd
import sqlite3
import os
import locale

# --- IMPORTS DOS MÓDULOS DE INTELIGÊNCIA ---
from styles.theme import aplicar_tema
from utils.classifiers import classificar_materiais_turbo
from utils.formatters import format_brl, format_perc
from utils.normalizer import normalizar_unidades_v1
from utils.compliance import validar_compliance

# --- IMPORTS DAS INTERFACES VISUAIS (ABAS) ---
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

# Aplica o tema visual (CSS)
aplicar_tema()

# Configuração de Idioma (Moeda e Data)
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
# 2. CARREGAMENTO DE DADOS E NORMALIZAÇÃO
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

    # --- TRATAMENTOS BÁSICOS ---
    df['data_emissao'] = pd.to_datetime(df['data_emissao'])
    df['ano'] = df['data_emissao'].dt.year
    df['mes_ano'] = df['data_emissao'].dt.strftime('%Y-%m')
    df['desc_prod'] = df['desc_prod'].astype(str).str.upper().str.strip()
    df['ncm'] = df['ncm'].astype(str).str.replace('.', '', regex=False)

    # Cálculo de Impostos Totais
    cols_imposto = ['v_icms', 'v_ipi', 'v_pis', 'v_cofins', 'v_iss']
    for col in cols_imposto:
        if col not in df.columns:
            df[col] = 0.0
    df['Imposto_Total'] = df[cols_imposto].sum(axis=1)

    if 'cod_prod' not in df.columns:
        df['cod_prod'] = ''
    df['cod_prod'] = df['cod_prod'].astype(str)
    
    # --- INTELIGÊNCIA DE UNIDADES (DETETIVE CX vs UN) ---
    # Normaliza quantidades e preços para evitar distorções (Ex: Caixa com 100 vs Unidade)
    # Cria as colunas: 'v_unit_real', 'qtd_real', 'un_real'
    df = normalizar_unidades_v1(df)

    return df

df_full = carregar_dados()

if df_full.empty:
    st.error("⚠️ Base de dados não encontrada ou vazia. Verifique se o extrator foi executado.")
    st.stop()

# =====================================================
# 3. PROCESSAMENTO GLOBAL (INTELIGÊNCIA NA BASE COMPLETA)
# =====================================================

# A) Classificação Turbo (Taxonomia e Cross-Referencing)
# Aplica categorias (Químico, EPI, Hidráulica...) na base completa
df_full['Categoria'] = classificar_materiais_turbo(df_full)

# B) Auditoria de Compliance
# Verifica se EPIs têm CA na descrição e marca riscos
df_full = validar_compliance(df_full)

# C) Cálculo de Estatísticas GLOBAIS (Histórico Completo)
# Necessário para a Aba de Fornecedores calcular o Score justo (comparando com o mercado todo)
df_grouped_full = df_full.groupby(['desc_prod', 'ncm', 'cod_prod', 'Categoria']).agg(
    Total_Gasto=('v_total_item', 'sum'),
    Qtd_Total=('qtd_real', 'sum'), 
    Menor_Preco=('v_unit_real', 'min') # Menor preço histórico global
).reset_index()

df_last_full = (
    df_full.sort_values('data_emissao')
    .drop_duplicates(['desc_prod', 'ncm', 'cod_prod'], keep='last')
    [['desc_prod', 'ncm', 'cod_prod', 'v_unit_real', 'nome_emit', 'data_emissao']]
)

# Tabela Mestra Global (Sem filtros de data)
df_final_full = df_grouped_full.merge(df_last_full, on=['desc_prod', 'ncm', 'cod_prod'])

# =====================================================
# 4. SIDEBAR E FILTROS TÁTICOS
# =====================================================
with st.sidebar:
    st.title("⚙️ Filtros")
    anos_disponiveis = sorted(df_full['ano'].unique(), reverse=True)
    sel_anos = st.multiselect("Anos Fiscais:", options=anos_disponiveis, default=anos_disponiveis[:1])

    if not sel_anos:
        st.warning("Selecione pelo menos um ano.")
        st.stop()

# Cria o DataFrame FILTRADO apenas para as abas de análise tática (Review, Dashboard)
df_filtered = df_full[df_full['ano'].isin(sel_anos)].copy()

# Estatísticas TÁTICAS (Baseadas apenas no período selecionado)
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

# =====================================================
# 5. RENDERIZAÇÃO DAS ABAS
# =====================================================
st.title(T['title'])
tab1, tab2, tab3, tab4, tab5 = st.tabs(T['tabs'])

# Abas 1, 2 e 4: Respeitam o filtro de ano (Análise do Período)
with tab1: render_tab_exec_review(df_filtered, df_final_filtered)
with tab2: render_tab_dashboard(df_filtered, df_final_filtered)
with tab4: render_tab_negociacao(df_filtered)

# Abas 3 e 5: Ignoram o filtro de ano (Análise de Histórico/Inteligência)
# Passamos df_full e df_final_full para ter acesso a todo o histórico
with tab3: render_tab_fornecedores(df_full, df_final_full)
with tab5: render_tab_busca(df_full)
