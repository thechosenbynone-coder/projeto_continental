import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os

# --- 1. CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Gestão de Suprimentos V10", page_icon="💎", layout="wide")

# CSS "ANTI-BUG" (Força contraste e remove conflitos)
st.markdown("""
    <style>
    /* 1. Força o fundo claro e texto escuro globalmente */
    [data-testid="stAppViewContainer"] {
        background-color: #f5f7f9;
        color: #000000 !important;
    }
    
    /* 2. Garante que títulos e textos sejam pretos/cinza escuros */
    h1, h2, h3, h4, h5, h6, p, span, div {
        color: #262730 !important;
    }
    
    /* 3. Estilo dos CARDS (Métricas) */
    div[data-testid="stMetric"] {
        background-color: #ffffff !important;
        border: 1px solid #d1d5db;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    /* Ajuste específico para o valor da métrica ficar AZUL */
    [data-testid="stMetricValue"] div {
        color: #004280 !important; 
        font-size: 28px !important;
        font-weight: 700;
    }
    
    /* 4. Tabelas com fundo branco para leitura */
    .stDataFrame {
        background-color: white;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES UTILITÁRIAS ---
def format_brl(valor):
    if pd.isna(valor): return "R$ 0,00"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def format_perc(valor):
    if pd.isna(valor): return "0%"
    return f"{valor:.1f}%"

# --- 2. CARREGAMENTO DE DADOS ---
@st.cache_data
def carregar_dados():
    db_path = "compras_suprimentos.db"
    if not os.path.exists(db_path):
        st.error("⚠️ Banco de dados não encontrado. Rode o extrator primeiro.")
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

# --- 3. TOPO E FILTROS ---
col_logo, col_filtro = st.columns([1, 2])

with col_logo:
    st.title("💎 Portal de Suprimentos")

with col_filtro:
    anos_disponiveis = sorted(df_full['ano'].unique(), reverse=True)
    st.write("**Período de Análise:**")
    anos_selecionados = st.multiselect(
        "Selecione:", 
        options=anos_disponiveis, 
        default=anos_disponiveis,
        label_visibility="collapsed"
    )

if not anos_selecionados:
    st.warning("👆 Selecione um ano acima.")
    st.stop()

df = df_full[df_full['ano'].isin(anos_selecionados)].copy()
st.markdown("---")

# --- 4. INTELIGÊNCIA (LÓGICA V9) ---
def classificar_material(row):
    desc = row['desc_prod']
    ncm = row.get('ncm', '')

    termos_anti_epi = ['REDUCAO', 'SOLDAVEL', 'ESGOTO', 'ROSCA', 'JOELHO', 'TE ', ' TÊ ', 'NIPLE', 'ADAPTADOR', 'CURVA', 'CONEXAO']
    termos_hidraulica = termos_anti_epi + ['VALVULA', 'TUBO', 'PVC', 'COBRE', 'ABRACADEIRA', 'SIFAO', 'CAIXA D AGUA']
    termos_eletrica = ['CABO', 'FIO', 'DISJUNTOR', 'LAMPADA', 'RELE', 'CONTATOR', 'TOMADA', 'PLUGUE', 'INTERRUPTOR', 'ELETRODUTO', 'TERMINAL', 'CANALETA']
    termos_construcao = ['CIMENTO', 'AREIA', 'TIJOLO', 'BLOCO', 'ARGAMASSA', 'PISO', 'TINTA', 'VERNIZ', 'SELADOR', 'CAL', 'TELHA']
    termos_ferramenta = ['CHAVE', 'ALICATE', 'MARTELO', 'SERRA', 'DISCO', 'BROCA', 'FURADEIRA', 'LIXADEIRA', 'PARAFUSADEIRA', 'TRENA']
    termos_fixacao = ['PARAFUSO', 'PORCA', 'ARRUELA', 'CHUMBADOR', 'BARRA ROSCADA', 'PREGO', 'REBITE']
    termos_epi_keyword = ['LUVA', 'BOTA', 'CAPACETE', 'OCULOS', 'PROTETOR', 'MASCARA', 'CINTO', 'TALABARTE', 'RESPIRADOR']

    # 1. Químicos
    if ncm.startswith(('2710', '3403', '3814', '3208', '3209')) or (any(x in desc for x in ['OLEO', 'GRAXA', 'LUBRIFICANTE', 'SOLVENTE', 'THINNER', 'ADESIVO']) and 'ALIMENT' not in desc):
        return '🔴 QUÍMICO (CRÍTICO)', 'FISPQ + LO + CTF'
    # 2. Içamento
    if any(x in desc for x in ['CABO DE ACO', 'CINTA DE CARGA', 'MANILHA', 'GANCHO', 'ESTROPO']):
        return '🟡 CABOS E CORRENTES (CRÍTICO)', 'Certificado Qualidade'
    # 3. EPI
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

df_grouped = df.groupby(['desc_prod', 'u_medida', 'ncm']).agg(
    Total_Gasto=('v_total_item', 'sum'),
    Qtd_Total=('qtd', 'sum'),
    Menor_Preco_Historico=('v_unit', 'min'),
).reset_index()

df_grouped[['Categoria', 'Exigencia']] = df_grouped.apply(lambda x: pd.Series(classificar_material(x)), axis=1)

df_sorted = df.sort_values('data_emissao', ascending=False)
df_last = df_sorted.drop_duplicates(['desc_prod', 'ncm'])[['desc_prod', 'ncm', 'v_unit', 'nome_emit', 'n_nf', 'data_emissao']]
df_last.rename(columns={'v_unit': 'Preco_Ultima_Compra', 'nome_emit': 'Forn_Ultima_Compra', 'n_nf': 'NF_Ultima', 'data_emissao': 'Data_Ultima'}, inplace=True)

df_final = df_grouped.merge(df_last, on=['desc_prod', 'ncm'], how='left')
df_final['Variacao_Preco'] = ((df_final['Preco_Ultima_Compra'] - df_final['Menor_Preco_Historico']) / df_final['Menor_Preco_Historico']) * 100

# --- 5. INTERFACE (ABAS PADRÃO PARA EVITAR BUG DE PULO) ---

aba1, aba2, aba3 = st.tabs(["📊 Dashboard Executivo", "📋 Auditoria de Fornecedor", "🔍 Busca de Itens"])

# === ABA 1: DASHBOARD ===
with aba1:
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Gasto Total", format_brl(df['v_total_item'].sum()))
    k2.metric("Fornecedores", df['cnpj_emit'].nunique())
    k3.metric("Mix Crítico", len(df_final[df_final['Categoria'].str.contains('CRÍTICO')]))
    k4.metric("Notas", df['n_nf'].nunique())

    st.write("")
    
    col_charts_1, col_charts_2 = st.columns(2)
    with col_charts_1:
        st.subheader("Gasto por Categoria")
        fig_cat = px.bar(df_final.groupby('Categoria')['Total_Gasto'].sum().reset_index().sort_values('Total_Gasto', ascending=True), 
                         x='Total_Gasto', y='Categoria', orientation='h', text_auto='.2s', color_discrete_sequence=['#004280'])
        st.plotly_chart(fig_cat, use_container_width=True)
        
    with col_charts_2:
        st.subheader("Top 10 Fornecedores")
        top_forn = df.groupby('nome_emit')['v_total_item'].sum().nlargest(10).reset_index()
        fig_pie = px.pie(top_forn, values='v_total_item', names='nome_emit', hole=0.5, color_discrete_sequence=px.colors.sequential.Blues_r)
        st.plotly_chart(fig_pie, use_container_width=True)

# === ABA 2: VENDOR LIST ===
with aba2:
    st.subheader("Auditoria Detalhada")
    
    lista_fornecedores = df.groupby('nome_emit')['v_total_item'].sum().sort_values(ascending=False).index.tolist()
    
    fornecedor_sel = st.selectbox(
        "Busque o Fornecedor:", 
        lista_fornecedores, 
        index=None, 
        placeholder="Digite o nome..."
    )
    
    st.markdown("---")

    if fornecedor_sel:
        itens_do_fornecedor = df[df['nome_emit'] == fornecedor_sel]['desc_prod'].unique()
        todos_itens_f = df_final[df_final['desc_prod'].isin(itens_do_fornecedor)].copy()
        todos_itens_f['Risco'] = todos_itens_f['Categoria'].str.contains('CRÍTICO')
        todos_itens_f = todos_itens_f.sort_values(['Risco', 'desc_
