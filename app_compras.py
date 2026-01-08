import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os

# --- 1. CONFIGURAÇÃO VISUAL PREMIUM ---
st.set_page_config(page_title="Gestão de Suprimentos Premium", page_icon="💎", layout="wide")

# CSS PERSONALIZADO (A MÁGICA DO DESIGN)
st.markdown("""
    <style>
    /* Fundo geral mais limpo */
    .stApp {
        background-color: #f8f9fa;
    }
    
    /* Estilo dos CARDS (Métricas) */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 15px 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        text-align: center;
    }
    [data-testid="stMetricLabel"] {
        font-weight: bold;
        color: #555;
        font-size: 14px;
    }
    [data-testid="stMetricValue"] {
        color: #004280;
        font-size: 32px !important;
        font-weight: 700;
    }

    /* Estilo das Abas */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #ffffff;
        border-radius: 8px;
        padding: 10px 20px;
        border: 1px solid #e0e0e0;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #004280 !important;
        color: white !important;
        border: none;
    }

    /* Tabelas mais bonitas */
    .stDataFrame {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
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

# --- 3. TOPO DO DASHBOARD (FILTRO MODERNO) ---
col_logo, col_filtro = st.columns([1, 2])

with col_logo:
    st.title("💎 Portal de Suprimentos")
    st.markdown("**Controle de Vendor List & Compliance**")

with col_filtro:
    # FILTRO NO TOPO (Mais elegante que sidebar)
    anos_disponiveis = sorted(df_full['ano'].unique(), reverse=True)
    st.write("📅 **Período de Análise:**")
    anos_selecionados = st.multiselect(
        "Selecione os anos:", 
        options=anos_disponiveis, 
        default=anos_disponiveis,
        label_visibility="collapsed" # Esconde o label padrão feio
    )

if not anos_selecionados:
    st.warning("👆 Por favor, selecione pelo menos um ano acima para começar.")
    st.stop()

df = df_full[df_full['ano'].isin(anos_selecionados)].copy()
st.markdown("---") # Linha separadora elegante

# --- 4. INTELIGÊNCIA DE DADOS (Lógica Blindada V9) ---
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

# --- 5. INTERFACE PRINCIPAL ---

aba1, aba2, aba3 = st.tabs(["📊 Dashboard Executivo", "📋 Auditoria de Fornecedor", "🔍 Busca de Itens"])

# === ABA 1: DASHBOARD (Cards Bonitos) ===
with aba1:
    st.markdown("### 📈 Visão Geral da Operação")
    
    # KPIs em Cards
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Gasto Total", format_brl(df['v_total_item'].sum()))
    k2.metric("Fornecedores Ativos", df['cnpj_emit'].nunique())
    k3.metric("Itens Críticos (Mix)", len(df_final[df_final['Categoria'].str.contains('CRÍTICO')]))
    k4.metric("Notas Processadas", df['n_nf'].nunique())

    st.markdown("<br>", unsafe_allow_html=True) # Espaçamento
    
    col_charts_1, col_charts_2 = st.columns(2)
    with col_charts_1:
        st.markdown("#### 🍩 Gasto por Categoria")
        fig_cat = px.bar(df_final.groupby('Categoria')['Total_Gasto'].sum().reset_index().sort_values('Total_Gasto', ascending=True), 
                         x='Total_Gasto', y='Categoria', orientation='h', text_auto='.2s', color_discrete_sequence=['#004280'])
        fig_cat.update_layout(plot_bgcolor="white", margin=dict(t=10,l=10,b=10,r=10))
        st.plotly_chart(fig_cat, use_container_width=True)
        
    with col_charts_2:
        st.markdown("#### 🏆 Top 10 Fornecedores")
        top_forn = df.groupby('nome_emit')['v_total_item'].sum().nlargest(10).reset_index()
        fig_pie = px.pie(top_forn, values='v_total_item', names='nome_emit', hole=0.5, color_discrete_sequence=px.colors.sequential.Blues_r)
        st.plotly_chart(fig_pie, use_container_width=True)

# === ABA 2: VENDOR LIST (Clean e Funcional) ===
with aba2:
    st.markdown("### 🕵️ Auditoria Detalhada")
    
    lista_fornecedores = df.groupby('nome_emit')['v_total_item'].sum().sort_values(ascending=False).index.tolist()
    
    # SELECTBOX SEM SELEÇÃO PRÉVIA (Index=None)
    fornecedor_sel = st.selectbox(
        "Selecione um Fornecedor para auditar:", 
        lista_fornecedores, 
        index=None, 
        placeholder="Digite o nome do fornecedor..."
    )
    
    st.markdown("---")

    if fornecedor_sel:
        # Lógica de Auditoria
        itens_do_fornecedor = df[df['nome_emit'] == fornecedor_sel]['desc_prod'].unique()
        todos_itens_f = df_final[df_final['desc_prod'].isin(itens_do_fornecedor)].copy()
        todos_itens_f['Risco'] = todos_itens_f['Categoria'].str.contains('CRÍTICO')
        todos_itens_f = todos_itens_f.sort_values(['Risco', 'desc_prod'], ascending=[False, True])
        
        dados_f = df[df['nome_emit'] == fornecedor_sel].iloc[0]
        total_f = df[df['nome_emit'] == fornecedor_sel]['v_total_item'].sum()
        riscos_f = todos_itens_f[todos_itens_f['Risco'] == True]
        
        c_info, c_table = st.columns([1, 2])
        
        with c_info:
            st.markdown(f"""
            <div style="background-color: white; padding: 20px; border-radius: 10px; border: 1px solid #ddd;">
                <h3 style="color: #004280; margin-top: 0;">{fornecedor_sel}</h3>
                <p><b>CNPJ:</b> {dados_f.get('cnpj_emit')}</p>
                <p><b>Cidade:</b> {dados_f.get('xMun')}/{dados_f.get('uf_emit')}</p>
                <hr>
                <p style="font-size: 20px;"><b>Total:</b> {format_brl(total_f)}</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.write("")
            if not riscos_f.empty:
                st.error(f"🚨 **ATENÇÃO:** Fornecedor Crítico")
                st.write(f"Vende {len(riscos_f)} itens controlados.")
            else:
                st.success("✅ Fornecedor Geral (Baixo Risco)")

        with c_table:
            st.subheader("Histórico de Vendas")
            st.dataframe(
                todos_itens_f[['desc_prod', 'Categoria', 'Exigencia']]
                .style.map(lambda x: 'color: red; font-weight: bold' if 'CRÍTICO' in str(x) else '', subset=['Categoria']),
                hide_index=True,
                use_container_width=True,
                height=400
            )
    else:
        st.info("👆 Selecione um fornecedor acima para ver a ficha completa.")

# === ABA 3: BUSCA (Otimizada) ===
with aba3:
    st.markdown("### 🔎 Pesquisa Inteligente de Preços")
    
    c_search, c_filter = st.columns([3, 1])
    termo_busca = c_search.text_input("O que você procura?", placeholder="Ex: Luva, Cabo, Parafuso...")
    filtro_cat = c_filter.multiselect("Filtrar Categoria", sorted(df_final['Categoria'].unique()))
    
    df_view = df_final.copy()
    if filtro_cat: df_view = df_view[df_view['Categoria'].isin(filtro_cat)]
    if termo_busca:
        for p in termo_busca.upper().split():
            df_view = df_view[df_view['desc_prod'].str.contains(p)]

    st.dataframe(
        df_view[['Categoria', 'desc_prod', 'Menor_Preco_Historico', 'Preco_Ultima_Compra', 'Variacao_Preco', 'Forn_Ultima_Compra', 'Data_Ultima']]
        .sort_values('Data_Ultima', ascending=False)
        .style.format({
            'Menor_Preco_Historico': format_brl, 
            'Preco_Ultima_Compra': format_brl, 
            'Variacao_Preco': format_perc, 
            'Data_Ultima': '{:%d/%m/%Y}'
        })
        .map(lambda x: 'color: #d9534f; font-weight: bold' if x > 10 else ('color: #5cb85c' if x == 0 else ''), subset=['Variacao_Preco']),
        use_container_width=True, 
        height=600
    )
