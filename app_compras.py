import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Gestão de Suprimentos 9.0", page_icon="🏗️", layout="wide")

st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 26px !important; color: #004280; }
    div[data-testid="stMetric"] { background-color: #f8f9fa; border: 1px solid #dee2e6; padding: 10px; border-radius: 5px; }
    .stDataFrame { font-size: 14px; }
    </style>
    """, unsafe_allow_html=True)

def format_brl(valor):
    if pd.isna(valor): return "R$ 0,00"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def format_perc(valor):
    if pd.isna(valor): return "0%"
    return f"{valor:.1f}%"

# --- 1. CARREGAMENTO ---
@st.cache_data
def carregar_dados():
    db_path = "compras_suprimentos.db"
    if not os.path.exists(db_path):
        st.error("Erro: Banco de dados não encontrado.")
        return pd.DataFrame()
    
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM base_compras", conn)
    conn.close()
    
    df['data_emissao'] = pd.to_datetime(df['data_emissao'])
    df['ano'] = df['data_emissao'].dt.year
    df['ncm'] = df['ncm'].astype(str).str.replace('.', '', regex=False)
    df['desc_prod'] = df['desc_prod'].astype(str).str.upper().str.strip()
    return df

df_full = carregar_dados()

if df_full.empty:
    st.stop()

# --- 2. FILTRO DE ANOS ---
st.sidebar.header("📅 Período de Análise")
anos_disponiveis = sorted(df_full['ano'].unique(), reverse=True)
anos_selecionados = st.sidebar.multiselect(
    "Selecione os Anos:", 
    options=anos_disponiveis, 
    default=anos_disponiveis
)

if not anos_selecionados:
    st.warning("Selecione pelo menos um ano.")
    st.stop()

df = df_full[df_full['ano'].isin(anos_selecionados)].copy()

# --- 3. CLASSIFICAÇÃO BLINDADA ---
def classificar_material(row):
    desc = row['desc_prod']
    ncm = row.get('ncm', '')

    # Listas de Palavras
    termos_anti_epi = ['REDUCAO', 'SOLDAVEL', 'ESGOTO', 'ROSCA', 'JOELHO', 'TE ', ' TÊ ', 'NIPLE', 'ADAPTADOR', 'CURVA', 'CONEXAO']
    
    termos_hidraulica = termos_anti_epi + ['VALVULA', 'TUBO', 'PVC', 'COBRE', 'ABRACADEIRA', 'SIFAO', 'CAIXA D AGUA']
    termos_eletrica = ['CABO', 'FIO', 'DISJUNTOR', 'LAMPADA', 'RELE', 'CONTATOR', 'TOMADA', 'PLUGUE', 'INTERRUPTOR', 'ELETRODUTO', 'TERMINAL', 'CANALETA']
    termos_construcao = ['CIMENTO', 'AREIA', 'TIJOLO', 'BLOCO', 'ARGAMASSA', 'PISO', 'TINTA', 'VERNIZ', 'SELADOR', 'CAL', 'TELHA']
    termos_ferramenta = ['CHAVE', 'ALICATE', 'MARTELO', 'SERRA', 'DISCO', 'BROCA', 'FURADEIRA', 'LIXADEIRA', 'PARAFUSADEIRA', 'TRENA']
    termos_fixacao = ['PARAFUSO', 'PORCA', 'ARRUELA', 'CHUMBADOR', 'BARRA ROSCADA', 'PREGO', 'REBITE']
    termos_epi_keyword = ['LUVA', 'BOTA', 'CAPACETE', 'OCULOS', 'PROTETOR', 'MASCARA', 'CINTO', 'TALABARTE', 'RESPIRADOR']

    # --- HIERARQUIA ---
    # 1. Químicos
    if ncm.startswith(('2710', '3403', '3814', '3208', '3209')) or (any(x in desc for x in ['OLEO', 'GRAXA', 'LUBRIFICANTE', 'SOLVENTE', 'THINNER', 'ADESIVO']) and 'ALIMENT' not in desc):
        return '🔴 QUÍMICO (CRÍTICO)', 'FISPQ + LO + CTF'
    
    # 2. Içamento
    if any(x in desc for x in ['CABO DE ACO', 'CINTA DE CARGA', 'MANILHA', 'GANCHO', 'ESTROPO']):
        return '🟡 CABOS E CORRENTES (CRÍTICO)', 'Certificado Qualidade'

    # 3. EPI (Regra Corrigida)
    eh_ncm_epi = ncm.startswith(('6116', '4015', '4203', '6403', '6506', '9020', '9004', '6307'))
    tem_termo_epi = any(t in desc for t in termos_epi_keyword)
    tem_termo_proibido = any(t in desc for t in termos_anti_epi)

    if (eh_ncm_epi or tem_termo_epi) and not tem_termo_proibido:
        return '🟠 EPI (CRÍTICO)', 'CA Válido + Ficha Entrega'

    # 4. Gerais
    if ncm.startswith(('3917', '7307', '8481')) or any(t in desc for t in termos_hidraulica): return '💧 HIDRÁULICA', 'Geral'
    if ncm.startswith(('8544', '8536', '8538', '9405')) or any(t in desc for t in termos_eletrica): return '⚡ ELÉTRICA', 'Geral'
    if ncm.startswith(('6810', '6907', '2523')) or any(t in desc for t in termos_construcao): return '🧱 CONSTRUÇÃO CIVIL', 'Geral'
    if ncm.startswith(('8202', '8203', '8204', '8205', '8207')) or any(t in desc for t in termos_ferramenta): return '🔧 FERRAMENTAS', 'Geral'
    if ncm.startswith(('7318')) or any(t in desc for t in termos_fixacao): return '🔩 FIXAÇÃO', 'Geral'

    return '📦 OUTROS / GERAL', 'Geral'

# --- PROCESSAMENTO ---
df_grouped = df.groupby(['desc_prod', 'u_medida', 'ncm']).agg(
    Total_Gasto=('v_total_item', 'sum'),
    Qtd_Total=('qtd', 'sum'),
    Menor_Preco_Historico=('v_unit', 'min'),
).reset_index()

df_grouped[['Categoria', 'Exigencia']] = df_grouped.apply(lambda x: pd.Series(classificar_material(x)), axis=1)

# Lógica da Última Compra
df_sorted = df.sort_values('data_emissao', ascending=False)
df_last = df_sorted.drop_duplicates(['desc_prod', 'ncm'])[['desc_prod', 'ncm', 'v_unit', 'nome_emit', 'n_nf', 'data_emissao']]
df_last.rename(columns={
    'v_unit': 'Preco_Ultima_Compra', 
    'nome_emit': 'Forn_Ultima_Compra',
    'n_nf': 'NF_Ultima',
    'data_emissao': 'Data_Ultima'
}, inplace=True)

df_final = df_grouped.merge(df_last, on=['desc_prod', 'ncm'], how='left')
df_final['Variacao_Preco'] = ((df_final['Preco_Ultima_Compra'] - df_final['Menor_Preco_Historico']) / df_final['Menor_Preco_Historico']) * 100

# --- INTERFACE ---
st.title("🏗️ Portal de Compras & Inteligência")
st.write(f"**Visualizando dados de:** {', '.join(map(str, anos_selecionados))}")

aba_busca, aba_dash, aba_vendor = st.tabs(["🔍 Busca de Preços", "📊 Dashboard Gerencial", "📋 Auditoria Fornecedores"])

# ABA 1: BUSCA
with aba_busca:
    col1, col2 = st.columns([3, 1])
    termo_busca = col1.text_input("Pesquisar Item:", placeholder="Digite para filtrar...")
    filtro_cat = col2.multiselect("Filtrar por Categoria", sorted(df_final['Categoria'].unique()))
    
    df_view = df_final.copy()
    if filtro_cat: df_view = df_view[df_view['Categoria'].isin(filtro_cat)]
    if termo_busca:
        for p in termo_busca.upper().split():
            df_view = df_view[df_view['desc_prod'].str.contains(p)]

    st.dataframe(
        df_view[['Categoria', 'desc_prod', 'Menor_Preco_Historico', 'Preco_Ultima_Compra', 'Variacao_Preco', 'Forn_Ultima_Compra', 'NF_Ultima', 'Data_Ultima']]
        .sort_values('Data_Ultima', ascending=False)
        .style.format({'Menor_Preco_Historico': format_brl, 'Preco_Ultima_Compra': format_brl, 'Variacao_Preco
