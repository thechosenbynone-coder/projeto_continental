import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os

# --- CONFIGURAÇÃO VISUAL (LAYOUT CONGELADO) ---
st.set_page_config(page_title="Gestão de Suprimentos 6.0", page_icon="🏗️", layout="wide")

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

# --- 2. FILTRO DE ANOS (SIDEBAR) ---
st.sidebar.header("📅 Período de Análise")
anos_disponiveis = sorted(df_full['ano'].unique(), reverse=True)
anos_selecionados = st.sidebar.multiselect(
    "Selecione os Anos:", 
    options=anos_disponiveis, 
    default=anos_disponiveis
)

# Filtra o DataFrame Globalmente
if not anos_selecionados:
    st.warning("Selecione pelo menos um ano na barra lateral.")
    st.stop()

df = df_full[df_full['ano'].isin(anos_selecionados)].copy()

# --- 3. CATEGORIZAÇÃO (COM CORREÇÃO DE CABOS) ---
def classificar_material(row):
    desc = row['desc_prod']
    ncm = row.get('ncm', '')

    termos_hidraulica = ['CONEXAO', 'VALVULA', 'TUBO', 'JOELHO', 'TE', 'NIPLE', 'ADAPTADOR', 'RED', 'LUVA RED', 'ROSCA', 'SOLDAVEL', 'PVC', 'COBRE', 'ESGOTO', 'ENGATE', 'ABRACADEIRA']
    termos_eletrica = ['CABO', 'FIO', 'DISJUNTOR', 'LAMPADA', 'RELE', 'CONTATOR', 'TOMADA', 'PLUGUE', 'INTERRUPTOR', 'ELETRODUTO', 'TERMINAL']
    termos_construcao = ['CIMENTO', 'AREIA', 'TIJOLO', 'BLOCO', 'ARGAMASSA', 'PISO', 'TINTA', 'VERNIZ', 'SELADOR']
    termos_ferramenta = ['CHAVE', 'ALICATE', 'MARTELO', 'SERRA', 'DISCO', 'BROCA', 'FURADEIRA', 'LIXADEIRA', 'PARAFUSADEIRA']
    termos_fixacao = ['PARAFUSO', 'PORCA', 'ARRUELA', 'CHUMBADOR', 'BARRA ROSCADA']
    termos_epi = ['LUVA', 'BOTA', 'CAPACETE', 'OCULOS', 'PROTETOR', 'MASCARA', 'CINTO', 'TALABARTE']

    # --- REGRAS CRÍTICAS ---
    
    # EPI vs Hidráulica (Regra Anti-Erro)
    eh_epi_potencial = any(t in desc for t in termos_epi) or ncm.startswith(('4015', '4203', '6116', '6403', '6506', '9020'))
    tem_termo_tecnico = any(t in desc for t in termos_hidraulica + termos_eletrica + termos_fixacao)
    
    if eh_epi_potencial and not tem_termo_tecnico:
        return '🟠 EPI (CRÍTICO)', 'CA Válido + Ficha Entrega'

    # Químicos
    if ncm.startswith(('2710', '3403', '3814')) or (any(x in desc for x in ['OLEO', 'GRAXA', 'LUBRIFICANTE', 'SOLVENTE', 'THINNER']) and 'ALIMENT' not in desc):
        return '🔴 QUÍMICO (CRÍTICO)', 'FISPQ + LO + CTF'
    
    # Cabos e Correntes (Nome Atualizado)
    if any(x in desc for x in ['CABO DE ACO', 'CINTA DE CARGA', 'MANILHA']):
        return '🟡 CABOS E CORRENTES (CRÍTICO)', 'Certificado Qualidade'

    # --- REGRAS GERAIS ---
    if ncm.startswith(('3917', '7307', '8481')) or any(t in desc for t in termos_hidraulica): return '💧 HIDRÁULICA', 'Geral'
    if ncm.startswith(('8544', '8536', '8538')) or any(t in desc for t in termos_eletrica): return '⚡ ELÉTRICA', 'Geral'
    if any(t in desc for t in termos_construcao): return '🧱 CONSTRUÇÃO CIVIL', 'Geral'
    if ncm.startswith(('8202', '8203', '8204', '8205', '8207')) or any(t in desc for t in termos_ferramenta): return '🔧 FERRAMENTAS', 'Geral'
    if ncm.startswith(('7318')) or any(t in desc for t in termos_fixacao): return '🔩 FIXAÇÃO', 'Geral'

    return '📦 OUTROS / GERAL', 'Geral'

# Processamento Principal
df_grouped = df.groupby(['desc_prod', 'u_medida', 'ncm']).agg(
    Total_Gasto=('v_total_item', 'sum'),
    Qtd_Total=('qtd', 'sum'),
    Menor_Preco_Historico=('v_unit', 'min'),
).reset_index()

df_grouped[['Categoria', 'Exigencia']] = df_grouped.apply(lambda x: pd.Series(classificar_material(x)), axis=1)

# Lógica da ÚLTIMA COMPRA (O que define o fornecedor atual)
df_sorted = df.sort_values('data_emissao', ascending=False)
df_last = df_sorted.drop_duplicates(['desc_prod', 'ncm'])[['desc_prod', 'ncm', 'v_unit', 'nome_emit', 'n_nf', 'data_emissao']]
df_last.rename(columns={
    'v_unit': 'Preco_Ultima_Compra', 
    'nome_emit': 'Forn_Ultima_Compra',
    'n_nf': 'NF_Ultima',
    'data_emissao': 'Data_Ultima'
}, inplace=True)

# Merge: Base Agrupada + Dados da Última Compra
df_final = df_grouped.merge(df_last, on=['desc_prod', 'ncm'], how='left')

# Cálculo de Variação (Último vs Menor Histórico)
df_final['Variacao_Preco'] = ((df_final['Preco_Ultima_Compra'] - df_final['Menor_Preco_Historico']) / df_final['Menor_Preco_Historico']) * 100


# --- INTERFACE ---
st.title("🏗️ Portal de Compras & Inteligência")
st.write(f"**Visualizando dados de:** {', '.join(map(str, anos_selecionados))}")

aba_busca, aba_dash, aba_vendor = st.tabs(["🔍 Busca de Preços", "📊 Dashboard Gerencial", "📋 Auditoria Fornecedores"])

# === ABA 1: BUSCA DE PREÇOS (REFORMULADA) ===
with aba_busca:
    col1, col2 = st.columns([3, 1])
    termo_busca = col1.text_input("Pesquisar Item:", placeholder="Digite para filtrar...")
    filtro_cat = col2.multiselect("Filtrar por Categoria", sorted(df_final['Categoria'].unique()))
    
    df_view = df_final.copy()
    
    if filtro_cat:
        df_view = df_view[df_view['Categoria'].isin(filtro_cat)]
    
    if termo_busca:
        palavras = termo_busca.upper().split()
        for p in palavras:
            df_view = df_view[df_view['desc_prod'].str.contains(p)]

    # Colunas que o usuário pediu
    cols_show = [
        'Categoria', 'desc_prod', 'u_medida', 
        'Menor_Preco_Historico', 'Preco_Ultima_Compra', 'Variacao_Preco',
        'Forn_Ultima_Compra', 'NF_Ultima', 'Data_Ultima'
    ]

    st.dataframe(
        df_view[cols_show]
        .sort_values('Data_Ultima', ascending=False)
        .style.format({
            'Menor_Preco_Historico': format_brl,
            'Preco_Ultima_Compra': format_brl,
            'Variacao_Preco': format_perc,
            'Data_Ultima': '{:%d/%m/%Y}'
        })
        # Variação Alta fica Vermelha, Variação Baixa fica Verde
        .map(lambda x: 'color: red; font-weight: bold' if x > 10 else ('color: green' if x == 0 else ''), subset=['Variacao_Preco']),
        use_container_width=True,
        height=600
    )

# === ABA 2: DASHBOARD (COM FILTRO DE ANO) ===
with aba_dash:
    c1, c2, c3, c4 = st.columns(4)
    # KPIs agora respondem ao filtro de ano lá de cima
    c1.metric("Total Gasto (Período)", format_brl(df['v_total_item'].sum()))
    c2.metric("Fornecedores Ativos", df['cnpj_emit'].nunique())
    c3.metric("Itens Críticos Comprados", len(df_final[df_final['Categoria'].str.contains('CRÍTICO')]))
    c4.metric("Total de Notas", df['n_nf'].nunique())

    st.markdown("---")
    
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.subheader("Onde gastamos mais?")
        df_cat_sum = df_final.groupby('Categoria')['Total_Gasto'].sum().reset_index().sort_values('Total_Gasto', ascending=False)
        fig_bar = px.bar(df_cat_sum, x='Total_Gasto', y='Categoria', orientation='h', text_auto='.2s')
        fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_bar, use_container_width=True)
        
    with col_g2:
        st.subheader("Top 10 Fornecedores (Neste Período)")
        df_abc = df.groupby('nome_emit')['v_total_item'].sum().nlargest(10).reset_index()
        fig_pie = px.pie(df_abc, values='v_total_item', names='nome_emit', hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)

# === ABA 3: VENDOR LIST (AUDITORIA) ===
with aba_vendor:
    st.subheader("Consulta de Fornecedor")
    fornecedor_sel = st.selectbox("Selecione:", sorted(df['nome_emit'].unique()))
    
    dados_f = df[df['nome_emit'] == fornecedor_sel].iloc[0]
    total_f = df[df['nome_emit'] == fornecedor_sel]['v_total_item'].sum()
    
    # Risco baseado no histórico completo desse fornecedor no período
    itens_raw_f = df[df['nome_emit'] == fornecedor_sel]['desc_prod'].unique()
    riscos_f = df_final[df_final['desc_prod'].isin(itens_raw_f) & df_final['Categoria'].str.contains('CRÍTICO')]
    
    col_a, col_b = st.columns([1, 2])
    with col_a:
        st.info("Dados Cadastrais")
        st.write(f"**CNPJ:** {dados_f.get('cnpj_emit', 'N/A')}")
        st.write(f"**Local:** {dados_f.get('xMun', '')}-{dados_f.get('uf_emit', '')}")
        st.write(f"**Total no Período:** {format_brl(total_f)}")
        
        if not riscos_f.empty:
            st.error(f"🚨 FORNECEDOR CRÍTICO")
            for ex in riscos_f['Exigencia'].unique():
                st.write(f"• {ex}")
        else:
            st.success("✅ Sem Itens Críticos")
            
    with col_b:
        st.write("**Histórico de Itens Críticos:**")
        if not riscos_f.empty:
            st.dataframe(riscos_f[['desc_prod', 'Categoria', 'Exigencia']], hide_index=True, use_container_width=True)
        else:
            st.caption("Nenhum item crítico fornecido neste período.")
