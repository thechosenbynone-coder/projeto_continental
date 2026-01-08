import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os

# --- 1. CONFIGURAÇÃO DE SISTEMA (LAYOUT PROFISSIONAL) ---
st.set_page_config(page_title="Sourcing Intelligence System", page_icon="🏗️", layout="wide")

st.markdown("""
    <style>
    /* UI de Sistema */
    .main { background-color: #f8f9fa; }
    
    div[data-testid="stMetric"] {
        background-color: white;
        border-left: 5px solid #004280;
        padding: 15px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    /* Tabelas compactas para densidade de informação */
    .dataframe { font-size: 12px !important; }
    
    /* Cartões de Destaque */
    .card-system {
        background-color: white;
        padding: 20px;
        border-radius: 8px;
        border: 1px solid #ddd;
        border-top: 3px solid #004280;
        margin-bottom: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CARREGAMENTO DE DADOS ---
@st.cache_data
def carregar_dados():
    db_path = "compras_suprimentos.db"
    try:
        if not os.path.exists(db_path): return pd.DataFrame()
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query("SELECT * FROM base_compras", conn)
        conn.close()
        if df.empty: return pd.DataFrame()

        df['data_emissao'] = pd.to_datetime(df['data_emissao'])
        df['ano'] = df['data_emissao'].dt.year
        df['mes_ano'] = df['data_emissao'].dt.strftime('%Y-%m')
        df['ncm'] = df['ncm'].astype(str).str.replace('.', '', regex=False)
        df['desc_prod'] = df['desc_prod'].astype(str).str.upper().str.strip()
        return df
    except: return pd.DataFrame()

df_full = carregar_dados()

if df_full.empty:
    st.error("⛔ SISTEMA OFFLINE: Base de dados não encontrada ou vazia.")
    st.stop()

# --- 3. SIDEBAR DE CONTROLE (SISTEMA TEM MENU LATERAL) ---
with st.sidebar:
    st.title("🎛️ Filtros Globais")
    anos = sorted(df_full['ano'].unique(), reverse=True)
    sel_anos = st.multiselect("Ano Fiscal:", anos, default=anos)
    
    # Filtro de UF (Novo)
    ufs = sorted(df_full['uf_emit'].dropna().unique())
    sel_uf = st.multiselect("Estado (UF):", ufs, default=ufs)
    
    st.markdown("---")
    st.caption("Versão Sistema: v17.0.1")

if not sel_anos: st.stop()

# Aplica filtros globais
df = df_full[df_full['ano'].isin(sel_anos)].copy()
if sel_uf: df = df[df['uf_emit'].isin(sel_uf)]

# --- 4. CLASSIFICAÇÃO (CORE BUSINESS LOGIC) ---
def classificar_material(row):
    desc = row['desc_prod']
    ncm = row.get('ncm', '')

    termos_anti_epi = ['REDUCAO', 'RED ', 'RED.', ' R.R ', 'SOLDAVEL', 'ROSCA', 'NPT', 'BSP', 'JOELHO', 'TE ', ' TÊ ', 'NIPLE', 'ADAPTADOR', 'CURVA', 'CONEXAO', 'UNIAO', 'LBS', 'CLASSE', 'SCH', 'DN ', ' Ø', 'CARBONO', 'INOX', 'ACO ', 'AÇO ', 'GALVANIZAD', 'LATÃO', 'LATAO', 'COBRE', 'FERRO', 'ESGOTO', 'SIFAO', 'PLUVIAL']
    termos_hidraulica = termos_anti_epi + ['VALVULA', 'TUBO', 'PVC', 'ABRACADEIRA', 'CAIXA D AGUA', 'REGISTRO']
    termos_eletrica = ['CABO', 'FIO', 'DISJUNTOR', 'LAMPADA', 'RELE', 'CONTATOR', 'TOMADA', 'PLUGUE', 'INTERRUPTOR', 'ELETRODUTO', 'TERMINAL', 'CANALETA']
    termos_construcao = ['CIMENTO', 'AREIA', 'TIJOLO', 'BLOCO', 'ARGAMASSA', 'PISO', 'TINTA', 'VERNIZ', 'SELADOR', 'CAL', 'TELHA']
    termos_ferramenta = ['CHAVE', 'ALICATE', 'MARTELO', 'SERRA', 'DISCO', 'BROCA', 'FURADEIRA', 'LIXADEIRA', 'PARAFUSADEIRA', 'TRENA']
    termos_epi_keyword = ['LUVA', 'BOTA', 'CAPACETE', 'OCULOS', 'PROTETOR', 'MASCARA', 'CINTO', 'TALABARTE', 'RESPIRADOR']

    if ncm.startswith(('2710', '3403', '3814')) or (any(x in desc for x in ['OLEO', 'GRAXA', 'LUBRIFICANTE', 'SOLVENTE', 'THINNER']) and 'ALIMENT' not in desc):
        return '🔴 QUÍMICO', 'FISPQ/CTF'
    if any(x in desc for x in ['CABO DE ACO', 'CINTA DE CARGA', 'MANILHA', 'GANCHO', 'ESTROPO']):
        return '🟡 IÇAMENTO', 'Certificado'
    
    eh_ncm_epi = ncm.startswith(('6116', '4015', '4203', '6403', '6506', '9020', '9004', '6307'))
    tem_termo_epi = any(t in desc for t in termos_epi_keyword)
    tem_termo_proibido = any(t in desc for t in termos_anti_epi)

    if (eh_ncm_epi or tem_termo_epi) and not tem_termo_proibido:
        return '🟠 EPI', 'CA/Ficha'

    if ncm.startswith(('3917', '7307', '8481')) or any(t in desc for t in termos_hidraulica): return '💧 HIDRÁULICA', 'Geral'
    if ncm.startswith(('8544', '8536', '8538', '9405')) or any(t in desc for t in termos_eletrica): return '⚡ ELÉTRICA', 'Geral'
    if ncm.startswith(('6810', '6907', '2523')) or any(t in desc for t in termos_construcao): return '🧱 CIVIL', 'Geral'
    if ncm.startswith(('8202', '8203', '8204', '8205', '8207')) or any(t in desc for t in termos_ferramenta): return '🔧 FERRAMENTAS', 'Geral'
    return '📦 GERAL', 'Geral'

def format_brl(valor): return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
def format_perc(valor): return f"{valor:.1f}%"

# Processamento de Dados (ETL em memória)
df_grouped = df.groupby(['desc_prod', 'u_medida', 'ncm']).agg(
    Total_Gasto=('v_total_item', 'sum'),
    Qtd_Total=('qtd', 'sum'),
    Menor_Preco_Historico=('v_unit', 'min'),
    Maior_Preco_Historico=('v_unit', 'max'),
    Media_Preco=('v_unit', 'mean')
).reset_index()

df_grouped[['Categoria', 'Exigencia']] = df_grouped.apply(lambda x: pd.Series(classificar_material(x)), axis=1)
df_sorted = df.sort_values('data_emissao', ascending=False)
df_last = df_sorted.drop_duplicates(['desc_prod', 'ncm'])[['desc_prod', 'ncm', 'v_unit', 'nome_emit', 'n_nf', 'data_emissao']]
df_last.rename(columns={'v_unit': 'Ultimo_Preco', 'nome_emit': 'Ultimo_Forn', 'n_nf': 'Ultima_NF', 'data_emissao': 'Ultima_Data'}, inplace=True)
df_final = df_grouped.merge(df_last, on=['desc_prod', 'ncm'], how='left')
df_final['Var_Preco'] = ((df_final['Ultimo_Preco'] - df_final['Menor_Preco_Historico']) / df_final['Menor_Preco_Historico']) * 100
df_final['Saving_Potencial'] = df_final['Total_Gasto'] - (df_final['Menor_Preco_Historico'] * df_final['Qtd_Total'])

# --- 5. INTERFACE DO SISTEMA ---
st.title("🏗️ Sourcing Intelligence System")
st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(["📊 Executive View", "⚖️ Comparador (Bid)", "📋 Vendor Management", "🔎 Item Search"])

# ABA 1: VISÃO EXECUTIVA
with tab1:
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Spend Total", format_brl(df['v_total_item'].sum()))
    k2.metric("Fornecedores", df['cnpj_emit'].nunique())
    k3.metric("Saving Perdido", format_brl(df_final['Saving_Potencial'].sum()), delta_color="inverse")
    k4.metric("Itens Críticos", len(df_final[df_final['Categoria'].isin(['🟠 EPI', '🔴 QUÍMICO', '🟡 IÇAMENTO'])]))

    col_chart1, col_chart2 = st.columns([2, 1])
    with col_chart1:
        st.subheader("Spend Analysis (Tempo)")
        fig = px.area(df.groupby('mes_ano')['v_total_item'].sum().reset_index(), x='mes_ano', y='v_total_item', markers=True)
        st.plotly_chart(fig, use_container_width=True)
    with col_chart2:
        st.subheader("Share por Categoria")
        fig2 = px.pie(df_final.groupby('Categoria')['Total_Gasto'].sum().reset_index(), values='Total_Gasto', names='Categoria', hole=0.6)
        st.plotly_chart(fig2, use_container_width=True)

# ABA 2: COMPARADOR (NOVA FUNCIONALIDADE DE SISTEMA)
with tab2:
    st.markdown("### ⚖️ Comparativo de Concorrência")
    st.info("Selecione um item para ver a variação de preço entre diferentes fornecedores ao longo do tempo.")
    
    # Selectbox de Itens
    itens_lista = df_final.sort_values('Total_Gasto', ascending=False)['desc_prod'].unique()
    item_bid = st.selectbox("Selecione o Item para Comparar:", itens_lista, index=0)
    
    if item_bid:
        # Dados específicos do item
        df_item = df[df['desc_prod'] == item_bid].copy()
        
        # Estatísticas do Item
        c_min, c_med, c_max = st.columns(3)
        stats = df_item['v_unit'].describe()
        c_min.metric("Melhor Preço Pago", format_brl(stats['min']))
        c_med.metric("Preço Médio", format_brl(stats['mean']))
        c_max.metric("Pior Preço Pago", format_brl(stats['max']))
        
        # GRÁFICO DE DISPERSÃO (COMPARATIVO VISUAL)
        st.markdown("#### Dispersão de Preços por Fornecedor")
        fig_scatter = px.scatter(df_item, x='data_emissao', y='v_unit', color='nome_emit', 
                                 size='qtd', hover_data=['n_nf'],
                                 labels={'v_unit': 'Preço Unitário', 'data_emissao': 'Data Compra', 'nome_emit': 'Fornecedor'},
                                 title=f"Histórico de Preços: {item_bid}")
        st.plotly_chart(fig_scatter, use_container_width=True)
        
        # Tabela Comparativa
        st.markdown("#### Tabela Detalhada")
        st.dataframe(df_item[['data_emissao', 'nome_emit', 'n_nf', 'qtd', 'v_unit', 'v_total_item']].sort_values('v_unit'), use_container_width=True)

# ABA 3: VENDOR MANAGEMENT
with tab3:
    col_sel, col_btn = st.columns([3, 1])
    forn_sel = col_sel.selectbox("Gestão de Fornecedor:", df.groupby('nome_emit')['v_total_item'].sum().sort_values(ascending=False).index)
    
    if forn_sel:
        dados_f = df[df['nome_emit'] == forn_sel].iloc[0]
        total_f = df[df['nome_emit'] == forn_sel]['v_total_item'].sum()
        
        # Layout de "Ficha de Cadastro"
        st.markdown(f"""
        <div class="card-system">
            <h3>🏢 {forn_sel}</h3>
            <p><b>CNPJ:</b> {dados_f['cnpj_emit']} &nbsp;|&nbsp; <b>Local:</b> {dados_f['xMun']}/{dados_f['uf_emit']}</p>
            <p><b>Endereço:</b> {dados_f['xLgr']}, {dados_f['nro']} - {dados_f['xBairro']}</p>
            <hr>
            <h2>Volume Total: {format_brl(total_f)}</h2>
        </div>
        """, unsafe_allow_html=True)
        
        # Produtos fornecidos
        st.subheader("Mix de Produtos")
        mix = df[df['nome_emit'] == forn_sel].groupby(['desc_prod', 'ncm']).agg(
            Qtd=('qtd', 'sum'),
            Media_Preco=('v_unit', 'mean'),
            Ultima_Venda=('data_emissao', 'max')
        ).reset_index()
        st.dataframe(mix, use_container_width=True)
        
        # Botão de Exportação (Simulado)
        st.download_button(
            label="📥 Baixar Ficha do Fornecedor (CSV)",
            data=mix.to_csv(index=False).encode('utf-8'),
            file_name=f"ficha_{forn_sel.replace(' ', '_')}.csv",
            mime='text/csv',
        )

# ABA 4: BUSCA GERAL
with tab4:
    col_search, col_filter = st.columns([3, 1])
    termo = col_search.text_input("Pesquisa Global:", placeholder="Digite NCM, Nome, Código...")
    
    view = df_final.copy()
    if termo:
        view = view[view['desc_prod'].str.contains(termo.upper()) | view['ncm'].str.contains(termo)]

    st.dataframe(
        view[['Categoria', 'desc_prod', 'Menor_Preco_Historico', 'Ultimo_Preco', 'Ultimo_Forn', 'Ultima_Data']]
        .sort_values('Ultima_Data', ascending=False)
        .style.format({'Menor_Preco_Historico': format_brl, 'Ultimo_Preco': format_brl, 'Ultima_Data': '{:%d/%m/%Y}'}),
        use_container_width=True, height=600
    )
