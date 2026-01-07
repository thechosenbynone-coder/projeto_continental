import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Gestão de Suprimentos 5.0", page_icon="🏗️", layout="wide")

# CSS para formatar tabelas e métricas
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 26px !important; color: #004280; }
    div[data-testid="stMetric"] { background-color: #f8f9fa; border: 1px solid #dee2e6; padding: 10px; border-radius: 5px; }
    .stDataFrame { font-size: 14px; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÃO DE FORMATAÇÃO BRL ---
def format_brl(valor):
    if pd.isna(valor): return "R$ 0,00"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- 1. CARREGAMENTO DE DADOS ---
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
    # Limpeza do NCM e Descrição
    df['ncm'] = df['ncm'].astype(str).str.replace('.', '', regex=False)
    df['desc_prod'] = df['desc_prod'].astype(str).str.upper().str.strip()
    return df

df_raw = carregar_dados()

if df_raw.empty:
    st.stop()

# --- 2. INTELIGÊNCIA DE CATEGORIZAÇÃO (CRÍTICA E GERAL) ---
def classificar_material(row):
    desc = row['desc_prod']
    ncm = row.get('ncm', '')

    # --- LISTAS DE PALAVRAS CHAVE ---
    termos_hidraulica = ['CONEXAO', 'VALVULA', 'TUBO', 'JOELHO', 'TE', 'NIPLE', 'ADAPTADOR', 'RED', 'LUVA RED', 'ROSCA', 'SOLDAVEL', 'PVC', 'COBRE', 'ESGOTO', 'ENGATE', 'ABRACADEIRA']
    termos_eletrica = ['CABO', 'FIO', 'DISJUNTOR', 'LAMPADA', 'RELE', 'CONTATOR', 'TOMADA', 'PLUGUE', 'INTERRUPTOR', 'ELETRODUTO', 'TERMINAL']
    termos_construcao = ['CIMENTO', 'AREIA', 'TIJOLO', 'BLOCO', 'ARGAMASSA', 'PISO', 'TINTA', 'VERNIZ', 'SELADOR']
    termos_ferramenta = ['CHAVE', 'ALICATE', 'MARTELO', 'SERRA', 'DISCO', 'BROCA', 'FURADEIRA', 'LIXADEIRA', 'PARAFUSADEIRA']
    termos_fixacao = ['PARAFUSO', 'PORCA', 'ARRUELA', 'CHUMBADOR', 'BARRA ROSCADA']
    termos_epi = ['LUVA', 'BOTA', 'CAPACETE', 'OCULOS', 'PROTETOR', 'MASCARA', 'CINTO', 'TALABARTE']

    # --- 1. CHECAGEM DE CRITICIDADE (Regras de Ouro) ---
    
    # REGRA EPI: Só é EPI se tiver palavras de EPI E NÃO tiver palavras de Hidráulica/Construção
    # Ex: "LUVA RED" tem "LUVA" mas tem "RED", então NÃO é EPI.
    eh_epi_potencial = any(t in desc for t in termos_epi) or ncm.startswith(('4015', '4203', '6116', '6403', '6506', '9020'))
    tem_termo_tecnico = any(t in desc for t in termos_hidraulica + termos_eletrica + termos_fixacao)
    
    if eh_epi_potencial and not tem_termo_tecnico:
        return '🟠 EPI (CRÍTICO)', 'CA Válido + Ficha Entrega'

    # Químicos
    if ncm.startswith(('2710', '3403', '3814')) or (any(x in desc for x in ['OLEO', 'GRAXA', 'LUBRIFICANTE', 'SOLVENTE', 'THINNER']) and 'ALIMENT' not in desc):
        return '🔴 QUÍMICO (CRÍTICO)', 'FISPQ + LO + CTF'
    
    # Içamento / Pressão Crítica
    if any(x in desc for x in ['CABO DE ACO', 'CINTA DE CARGA', 'MANILHA']):
        return '🟡 IÇAMENTO (CRÍTICO)', 'Certificado Qualidade'

    # --- 2. CATEGORIZAÇÃO GERAL (Se não foi Crítico) ---
    
    if ncm.startswith(('3917', '7307', '8481')) or any(t in desc for t in termos_hidraulica):
        return '💧 HIDRÁULICA', 'Geral'
        
    if ncm.startswith(('8544', '8536', '8538')) or any(t in desc for t in termos_eletrica):
        return '⚡ ELÉTRICA', 'Geral'
    
    if any(t in desc for t in termos_construcao):
        return '🧱 CONSTRUÇÃO CIVIL', 'Geral'
    
    if ncm.startswith(('8202', '8203', '8204', '8205', '8207')) or any(t in desc for t in termos_ferramenta):
        return '🔧 FERRAMENTAS', 'Geral'
        
    if ncm.startswith(('7318')) or any(t in desc for t in termos_fixacao):
        return '🔩 FIXAÇÃO', 'Geral'

    return '📦 OUTROS / GERAL', 'Geral'

# Processamento Inteligente
# Agrupamos por Produto para tirar a média e achar o fornecedor mais barato
df_grouped = df_raw.groupby(['desc_prod', 'u_medida', 'ncm']).agg(
    Total_Gasto=('v_total_item', 'sum'),
    Qtd_Total=('qtd', 'sum'),
    Media_Preco=('v_unit', 'mean'),
    Menor_Preco=('v_unit', 'min'),
    Maior_Preco=('v_unit', 'max'),
    Ultima_Compra=('data_emissao', 'max')
).reset_index()

# Aplica a classificação
df_grouped[['Categoria', 'Exigencia']] = df_grouped.apply(lambda x: pd.Series(classificar_material(x)), axis=1)

# Descobre QUEM vendeu o menor preço (Lookup)
# Essa parte é pesada, fazemos um merge otimizado
df_min_prices = df_raw.sort_values('v_unit', ascending=True).drop_duplicates(['desc_prod'])[['desc_prod', 'nome_emit']]
df_grouped = df_grouped.merge(df_min_prices, on='desc_prod', how='left')
df_grouped.rename(columns={'nome_emit': 'Forn_Menor_Preco'}, inplace=True)


# --- INTERFACE ---

st.title("🏗️ Portal de Compras & Inteligência")

# ABAS REORGANIZADAS PARA O FLUXO DE TRABALHO
aba_busca, aba_dash, aba_vendor = st.tabs(["🔍 Busca de Preços (Histórico)", "📊 Dashboard Gerencial", "📋 Vendor List & Compliance"])

# === ABA 1: BUSCA INTELIGENTE (O "GOOGLE" DO ESTOQUE) ===
with aba_busca:
    st.markdown("### 🔎 Pesquisa de Histórico de Compras")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    termo_busca = col1.text_input("O que você precisa comprar?", placeholder="Ex: Luva, Cabo 10mm, Parafuso...")
    filtro_cat = col2.multiselect("Filtrar Categoria", sorted(df_grouped['Categoria'].unique()))
    
    # FILTRO REAL (ESCONDE O QUE NÃO É)
    df_view = df_grouped.copy()
    
    if filtro_cat:
        df_view = df_view[df_view['Categoria'].isin(filtro_cat)]
    
    if termo_busca:
        # Busca inteligente (várias palavras)
        palavras = termo_busca.upper().split()
        for p in palavras:
            df_view = df_view[df_view['desc_prod'].str.contains(p)]

    # Métrica Rápida da Busca
    if termo_busca:
        st.caption(f"Encontramos {len(df_view)} itens correspondentes.")

    # Tabela Formatada e Limpa
    st.dataframe(
        df_view[['Categoria', 'desc_prod', 'u_medida', 'Menor_Preco', 'Media_Preco', 'Forn_Menor_Preco', 'Ultima_Compra']]
        .sort_values('Ultima_Compra', ascending=False)
        .style.format({
            'Menor_Preco': format_brl,
            'Media_Preco': format_brl,
            'Ultima_Compra': '{:%d/%m/%Y}'
        })
        .map(lambda x: 'color: red; font-weight: bold' if 'CRÍTICO' in str(x) else '', subset=['Categoria']),
        use_container_width=True,
        height=600
    )

# === ABA 2: DASHBOARD ===
with aba_dash:
    # Cards Formatados
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Gasto (Histórico)", format_brl(df_raw['v_total_item'].sum()))
    c2.metric("Fornecedores Ativos", df_raw['cnpj_emit'].nunique())
    c3.metric("Itens Críticos", len(df_grouped[df_grouped['Categoria'].str.contains('CRÍTICO')]))
    c4.metric("Total de Itens", len(df_grouped))

    st.markdown("---")
    
    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        st.subheader("Gastos por Categoria")
        df_cat_sum = df_grouped.groupby('Categoria')['Total_Gasto'].sum().reset_index().sort_values('Total_Gasto', ascending=False)
        fig_bar = px.bar(df_cat_sum, x='Total_Gasto', y='Categoria', orientation='h', text_auto='.2s')
        fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_bar, use_container_width=True)
        
    with col_g2:
        st.subheader("Curva ABC (Top 10 Fornecedores)")
        df_abc = df_raw.groupby('nome_emit')['v_total_item'].sum().nlargest(10).reset_index()
        fig_pie = px.pie(df_abc, values='v_total_item', names='nome_emit', hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)

# === ABA 3: VENDOR LIST & COMPLIANCE ===
with aba_vendor:
    st.subheader("Auditoria de Fornecedores")
    
    lista_forn = sorted(df_raw['nome_emit'].unique())
    fornecedor_sel = st.selectbox("Selecione o Fornecedor:", lista_forn)
    
    # Dados do Fornecedor
    dados_f = df_raw[df_raw['nome_emit'] == fornecedor_sel].iloc[0]
    total_f = df_raw[df_raw['nome_emit'] == fornecedor_sel]['v_total_item'].sum()
    
    # Itens fornecidos por ele
    itens_f = df_grouped[df_grouped['Forn_Menor_Preco'] == fornecedor_sel] # Simplificado para demo
    # Pega todos os itens que ele já vendeu na base raw para ser mais preciso no risco
    itens_raw_f = df_raw[df_raw['nome_emit'] == fornecedor_sel]['desc_prod'].unique()
    riscos_f = df_grouped[df_grouped['desc_prod'].isin(itens_raw_f) & df_grouped['Categoria'].str.contains('CRÍTICO')]
    
    col_a, col_b = st.columns([1, 2])
    
    with col_a:
        st.info("Ficha Cadastral")
        st.write(f"**CNPJ:** {dados_f.get('cnpj_emit', 'N/A')}")
        st.write(f"**Local:** {dados_f.get('xMun', '')} - {dados_f.get('uf_emit', '')}")
        st.write(f"**Total Comprado:** {format_brl(total_f)}")
        
        if not riscos_f.empty:
            st.error(f"🚨 FORNECEDOR CRÍTICO ({len(riscos_f)} itens)")
            st.write("**Exigências:**")
            for exig in riscos_f['Exigencia'].unique():
                st.write(f"- {exig}")
        else:
            st.success("✅ Fornecedor Geral (Sem risco identificado)")
            
    with col_b:
        st.write("**Histórico de Itens Críticos deste Fornecedor:**")
        if not riscos_f.empty:
            st.dataframe(riscos_f[['desc_prod', 'Categoria', 'Exigencia']], use_container_width=True)
        else:
            st.write("Nenhum item crítico encontrado no histórico.")
