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
        .style.format({'Menor_Preco_Historico': format_brl, 'Preco_Ultima_Compra': format_brl, 'Variacao_Preco': format_perc, 'Data_Ultima': '{:%d/%m/%Y}'})
        .map(lambda x: 'color: red; font-weight: bold' if x > 10 else ('color: green' if x == 0 else ''), subset=['Variacao_Preco']),
        use_container_width=True, height=600
    )

# ABA 2: DASHBOARD
with aba_dash:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Gasto", format_brl(df['v_total_item'].sum()))
    c2.metric("Fornecedores", df['cnpj_emit'].nunique())
    c3.metric("Itens Críticos", len(df_final[df_final['Categoria'].str.contains('CRÍTICO')]))
    c4.metric("Notas Fiscais", df['n_nf'].nunique())

    st.markdown("---")
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.subheader("Gastos por Categoria")
        fig_bar = px.bar(df_final.groupby('Categoria')['Total_Gasto'].sum().reset_index().sort_values('Total_Gasto', ascending=False), 
                         x='Total_Gasto', y='Categoria', orientation='h', text_auto='.2s')
        st.plotly_chart(fig_bar, use_container_width=True)
    with col_g2:
        st.subheader("Top 10 Fornecedores")
        fig_pie = px.pie(df.groupby('nome_emit')['v_total_item'].sum().nlargest(10).reset_index(), values='v_total_item', names='nome_emit', hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)

# ABA 3: VENDOR LIST (AGORA MOSTRA TUDO)
with aba_vendor:
    st.subheader("Consulta de Fornecedor")
    fornecedor_sel = st.selectbox("Selecione:", df.groupby('nome_emit')['v_total_item'].sum().sort_values(ascending=False).index)
    
    # 1. Busca TODOS os itens desse fornecedor (Independente de risco)
    itens_do_fornecedor = df[df['nome_emit'] == fornecedor_sel]['desc_prod'].unique()
    
    # 2. Pega a classificação e dados da base consolidada
    todos_itens_f = df_final[df_final['desc_prod'].isin(itens_do_fornecedor)].copy()
    
    # 3. Cria coluna auxiliar para ordenar (Críticos primeiro)
    todos_itens_f['Risco'] = todos_itens_f['Categoria'].str.contains('CRÍTICO')
    todos_itens_f = todos_itens_f.sort_values(['Risco', 'desc_prod'], ascending=[False, True])
    
    # 4. Dados Cadastrais e Alertas
    dados_f = df[df['nome_emit'] == fornecedor_sel].iloc[0]
    total_f = df[df['nome_emit'] == fornecedor_sel]['v_total_item'].sum()
    riscos_f = todos_itens_f[todos_itens_f['Risco'] == True]
    
    col_a, col_b = st.columns([1, 2])
    with col_a:
        st.info("Dados Cadastrais")
        st.write(f"**CNPJ:** {dados_f.get('cnpj_emit')}")
        st.write(f"**Local:** {dados_f.get('xMun')}/{dados_f.get('uf_emit')}")
        st.write(f"**Total Comprado:** {format_brl(total_f)}")
        
        if not riscos_f.empty:
            st.error(f"🚨 FORNECEDOR CRÍTICO")
            st.write(f"Identificamos {len(riscos_f)} itens de risco no mix de produtos.")
        else:
            st.success("✅ Fornecedor Geral")
            
    with col_b:
        st.write(f"**Histórico Completo ({len(todos_itens_f)} itens fornecidos):**")
        st.dataframe(
            todos_itens_f[['desc_prod', 'Categoria', 'Exigencia']]
            .style.map(lambda x: 'color: red; font-weight: bold' if 'CRÍTICO' in str(x) else '', subset=['Categoria']),
            hide_index=True, 
            use_container_width=True
        )
