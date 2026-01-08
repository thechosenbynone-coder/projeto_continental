import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os

# --- 1. CONFIGURAÇÃO VISUAL (AUTORIDADE) ---
st.set_page_config(page_title="Portal de Inteligência em Suprimentos", page_icon="🏗️", layout="wide")

st.markdown("""
    <style>
    /* Design System Corporativo */
    div[data-testid="stMetric"] {
        background-color: var(--secondary-background-color);
        border-left: 5px solid #004280; /* Tarja lateral azul para destaque */
        padding: 15px;
        border-radius: 5px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    [data-testid="stMetricValue"] {
        font-size: 24px !important;
        font-weight: 700;
        color: var(--primary-color) !important;
    }
    .card-fornecedor {
        background-color: var(--secondary-background-color);
        padding: 20px;
        border-radius: 8px;
        border: 1px solid rgba(128, 128, 128, 0.2);
        margin-bottom: 20px;
        border-left: 5px solid #ff4b4b; /* Tarja vermelha se for crítico */
    }
    .card-normal {
        border-left: 5px solid #09ab3b; /* Tarja verde se for ok */
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. FERRAMENTAS ---
with st.sidebar.expander("📂 Debug: Arquivos", expanded=False):
    st.write(os.listdir())

def format_brl(valor):
    if pd.isna(valor): return "R$ 0,00"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def format_perc(valor):
    if pd.isna(valor): return "0%"
    return f"{valor:.1f}%"

# --- 3. CARREGAMENTO ---
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
        df['mes_ano'] = df['data_emissao'].dt.strftime('%Y-%m') # Para gráfico mensal
        df['ncm'] = df['ncm'].astype(str).str.replace('.', '', regex=False)
        df['desc_prod'] = df['desc_prod'].astype(str).str.upper().str.strip()
        return df
    except: return pd.DataFrame()

df_full = carregar_dados()

if df_full.empty:
    st.warning("⚠️ Base de dados não carregada. Verifique o upload.")
    st.stop()

# --- 4. TOPO E FILTROS ---
c1, c2 = st.columns([2, 1])
with c1: 
    st.title("🏗️ Portal de Inteligência em Suprimentos")
    st.caption("Strategic Sourcing & Compliance Dashboard")
with c2:
    anos = sorted(df_full['ano'].unique(), reverse=True)
    sel = st.multiselect("Período:", anos, default=anos)

if not sel: st.stop()
df = df_full[df_full['ano'].isin(sel)].copy()
st.divider()

# --- 5. CLASSIFICAÇÃO INTELIGENTE ---
def classificar_material(row):
    desc = row['desc_prod']
    ncm = row.get('ncm', '')

    termos_anti_epi = ['REDUCAO', 'RED ', 'RED.', ' R.R ', 'SOLDAVEL', 'ROSCA', 'NPT', 'BSP', 'JOELHO', 'TE ', ' TÊ ', 'NIPLE', 'ADAPTADOR', 'CURVA', 'CONEXAO', 'UNIAO', 'LBS', 'CLASSE', 'SCH', 'DN ', ' Ø', 'CARBONO', 'INOX', 'ACO ', 'AÇO ', 'GALVANIZAD', 'LATÃO', 'LATAO', 'COBRE', 'FERRO', 'ESGOTO', 'SIFAO', 'PLUVIAL']
    termos_hidraulica = termos_anti_epi + ['VALVULA', 'TUBO', 'PVC', 'ABRACADEIRA', 'CAIXA D AGUA', 'REGISTRO']
    termos_eletrica = ['CABO', 'FIO', 'DISJUNTOR', 'LAMPADA', 'RELE', 'CONTATOR', 'TOMADA', 'PLUGUE', 'INTERRUPTOR', 'ELETRODUTO', 'TERMINAL', 'CANALETA']
    termos_construcao = ['CIMENTO', 'AREIA', 'TIJOLO', 'BLOCO', 'ARGAMASSA', 'PISO', 'TINTA', 'VERNIZ', 'SELADOR', 'CAL', 'TELHA']
    termos_ferramenta = ['CHAVE', 'ALICATE', 'MARTELO', 'SERRA', 'DISCO', 'BROCA', 'FURADEIRA', 'LIXADEIRA', 'PARAFUSADEIRA', 'TRENA']
    termos_fixacao = ['PARAFUSO', 'PORCA', 'ARRUELA', 'CHUMBADOR', 'BARRA ROSCADA', 'PREGO', 'REBITE']
    termos_epi_keyword = ['LUVA', 'BOTA', 'CAPACETE', 'OCULOS', 'PROTETOR', 'MASCARA', 'CINTO', 'TALABARTE', 'RESPIRADOR']

    if ncm.startswith(('2710', '3403', '3814')) or (any(x in desc for x in ['OLEO', 'GRAXA', 'LUBRIFICANTE', 'SOLVENTE', 'THINNER']) and 'ALIMENT' not in desc):
        return '🔴 QUÍMICO (CRÍTICO)', 'FISPQ + LO + CTF'
    if any(x in desc for x in ['CABO DE ACO', 'CINTA DE CARGA', 'MANILHA', 'GANCHO', 'ESTROPO']):
        return '🟡 CABOS E CORRENTES (CRÍTICO)', 'Certificado Qualidade'
    
    eh_ncm_epi = ncm.startswith(('6116', '4015', '4203', '6403', '6506', '9020', '9004', '6307'))
    tem_termo_epi = any(t in desc for t in termos_epi_keyword)
    tem_termo_proibido = any(t in desc for t in termos_anti_epi)

    if (eh_ncm_epi or tem_termo_epi) and not tem_termo_proibido:
        return '🟠 EPI (CRÍTICO)', 'CA Válido + Ficha Entrega'

    if ncm.startswith(('3917', '7307', '8481')) or any(t in desc for t in termos_hidraulica): return '💧 HIDRÁULICA', 'Geral'
    if ncm.startswith(('8544', '8536', '8538', '9405')) or any(t in desc for t in termos_eletrica): return '⚡ ELÉTRICA', 'Geral'
    if ncm.startswith(('6810', '6907', '2523')) or any(t in desc for t in termos_construcao): return '🧱 CONSTRUÇÃO CIVIL', 'Geral'
    if ncm.startswith(('8202', '8203', '8204', '8205', '8207')) or any(t in desc for t in termos_ferramenta): return '🔧 FERRAMENTAS', 'Geral'
    if ncm.startswith(('7318')) or any(t in desc for t in termos_fixacao): return '🔩 FIXAÇÃO', 'Geral'
    return '📦 OUTROS / GERAL', 'Geral'

# --- 6. PROCESSAMENTO ANALÍTICO ---
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

# Cálculo de Saving Potencial (Se tivéssemos pago o menor preço sempre)
df_final['Custo_Se_Menor'] = df_final['Menor_Preco_Historico'] * df_final['Qtd_Total']
saving_potencial = df_final['Total_Gasto'].sum() - df_final['Custo_Se_Menor'].sum()

# --- 7. INTERFACE ---
aba1, aba2, aba3 = st.tabs(["📊 Dashboard Estratégico", "📋 Auditoria & Cadastro", "🔍 Busca de Materiais"])

# ABA 1: STRATEGIC DASHBOARD
with aba1:
    st.markdown("### 📈 KPIs de Performance")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Gasto Total (Spend)", format_brl(df['v_total_item'].sum()))
    k2.metric("Fornecedores Ativos", df['cnpj_emit'].nunique())
    # O Pulo do Gato: Saving Potencial
    k3.metric("Oportunidade de Saving", format_brl(saving_potencial), help="Diferença entre o preço pago e o menor preço histórico registrado.")
    k4.metric("Itens Controlados (Compliance)", len(df_final[df_final['Categoria'].str.contains('CRÍTICO')]))

    st.markdown("---")
    
    # Linha do Tempo (Evolução)
    st.subheader("Evolução Mensal de Gastos")
    df_timeline = df.groupby('mes_ano')['v_total_item'].sum().reset_index().sort_values('mes_ano')
    fig_time = px.line(df_timeline, x='mes_ano', y='v_total_item', markers=True, 
                       labels={'mes_ano': 'Mês', 'v_total_item': 'Valor Gasto'},
                       color_discrete_sequence=['#004280'])
    st.plotly_chart(fig_time, use_container_width=True)

    c_g1, c_g2 = st.columns(2)
    with c_g1:
        st.subheader("Curva ABC (Fornecedores)")
        top_forn = df.groupby('nome_emit')['v_total_item'].sum().nlargest(10).reset_index()
        fig_bar = px.bar(top_forn, x='v_total_item', y='nome_emit', orientation='h', text_auto='.2s')
        fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_bar, use_container_width=True)
    with c_g2:
        st.subheader("Share por Categoria")
        fig_pie = px.pie(df_final.groupby('Categoria')['Total_Gasto'].sum().reset_index(), values='Total_Gasto', names='Categoria', hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)

# ABA 2: AUDITORIA & CADASTRO
with aba2:
    st.markdown("### 🕵️ Ficha Cadastral e Risco")
    
    lista_fornecedores = df.groupby('nome_emit')['v_total_item'].sum().sort_values(ascending=False).index.tolist()
    fornecedor_sel = st.selectbox("Selecione o Parceiro:", lista_fornecedores, index=None, placeholder="Digite para pesquisar...")
    st.markdown("---")
    
    if fornecedor_sel:
        # Prepara dados
        itens_do_fornecedor = df[df['nome_emit'] == fornecedor_sel]['desc_prod'].unique()
        todos_itens_f = df_final[df_final['desc_prod'].isin(itens_do_fornecedor)].copy()
        todos_itens_f['Risco'] = todos_itens_f['Categoria'].str.contains('CRÍTICO')
        todos_itens_f = todos_itens_f.sort_values(['Risco', 'desc_prod'], ascending=[False, True])
        
        dados_f = df[df['nome_emit'] == fornecedor_sel].iloc[0]
        total_f = df[df['nome_emit'] == fornecedor_sel]['v_total_item'].sum()
        riscos_f = todos_itens_f[todos_itens_f['Risco'] == True]
        
        # Monta endereço completo
        endereco = f"{dados_f.get('xLgr', '')}, {dados_f.get('nro', '')} - {dados_f.get('xBairro', '')}"
        cidade = f"{dados_f.get('xMun', '')}/{dados_f.get('uf_emit', '')}"
        cep = dados_f.get('cep', '')
        
        css_class = "card-fornecedor" if not riscos_f.empty else "card-fornecedor card-normal"
        status_text = "🚨 FORNECEDOR CRÍTICO" if not riscos_f.empty else "✅ HOMOLOGADO / GERAL"
        status_color = "#ff4b4b" if not riscos_f.empty else "#09ab3b"

        ca, cb = st.columns([1, 2])
        with ca:
            st.markdown(f"""
            <div class="{css_class}">
                <h3 style="margin:0; color: #004280;">{fornecedor_sel}</h3>
                <p style="font-size: 12px; color: #666;">CNPJ: {dados_f.get('cnpj_emit')}</p>
                <hr>
                <p><b>📍 Endereço:</b><br>{endereco}<br>{cidade} - CEP: {cep}</p>
                <hr>
                <h2 style="color: {status_color}; margin-top: 10px;">{status_text}</h2>
                <p>Total Transacionado: <b>{format_brl(total_f)}</b></p>
            </div>
            """, unsafe_allow_html=True)
            
            if not riscos_f.empty:
                st.warning(f"⚠️ Atenção: Este parceiro fornece {len(riscos_f)} itens que exigem documentação (CA, FISPQ, etc).")

        with cb:
            st.write(f"**Mix de Produtos ({len(todos_itens_f)} SKUs):**")
            st.dataframe(
                todos_itens_f[['desc_prod', 'Categoria', 'Exigencia']]
                .style.map(lambda x: 'color: #ff4b4b; font-weight: bold' if 'CRÍTICO' in str(x) else '', subset=['Categoria']),
                hide_index=True, use_container_width=True, height=500
            )

# ABA 3: BUSCA DE MATERIAIS
with aba3:
    st.markdown("### 🔍 Pesquisa de Histórico de Preços")
    c_s, c_f = st.columns([3, 1])
    termo = c_s.text_input("Descrição do Material:", placeholder="Ex: Luva, Cabo, Parafuso...")
    cat = c_f.multiselect("Filtrar Família:", sorted(df_final['Categoria'].unique()))
    
    view = df_final.copy()
    if cat: view = view[view['Categoria'].isin(cat)]
    if termo:
        for p in termo.upper().split(): view = view[view['desc_prod'].str.contains(p)]

    st.dataframe(
        view[['Categoria', 'desc_prod', 'Menor_Preco_Historico', 'Preco_Ultima_Compra', 'Variacao_Preco', 'Forn_Ultima_Compra', 'Data_Ultima']]
        .sort_values('Data_Ultima', ascending=False)
        .style.format({'Menor_Preco_Historico': format_brl, 'Preco_Ultima_Compra': format_brl, 'Variacao_Preco': format_perc, 'Data_Ultima': '{:%d/%m/%Y}'})
        .map(lambda x: 'color: #ff4b4b; font-weight: bold' if x > 10 else ('color: #09ab3b' if x == 0 else ''), subset=['Variacao_Preco']),
        use_container_width=True, height=600
    )
