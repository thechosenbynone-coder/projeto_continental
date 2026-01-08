import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os

# --- 1. CONFIGURAÇÃO (MODO ADAPTATIVO & GUINDASTE 🏗️) ---
st.set_page_config(page_title="Portal de Inteligência em Suprimentos", page_icon="🏗️", layout="wide")

st.markdown("""
    <style>
    /* CSS Adaptativo que respeita o tema do usuário */
    div[data-testid="stMetric"] {
        background-color: var(--secondary-background-color);
        border-left: 5px solid #004280;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    [data-testid="stMetricValue"] {
        font-size: 24px !important;
        font-weight: 700;
        color: var(--primary-color) !important;
    }
    .card-fornecedor {
        background-color: var(--secondary-background-color);
        padding: 20px;
        border-radius: 10px;
        border: 1px solid rgba(128, 128, 128, 0.2);
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE FORMATAÇÃO ---
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
    st.warning("⚠️ Base de dados não carregada. Verifique o arquivo compras_suprimentos.db")
    st.stop()

# --- 3. FILTROS GLOBAIS (SIDEBAR) ---
with st.sidebar:
    st.title("🎛️ Painel de Controle")
    anos = sorted(df_full['ano'].unique(), reverse=True)
    sel_anos = st.multiselect("Anos:", anos, default=anos)
    ufs = sorted(df_full['uf_emit'].dropna().unique())
    sel_uf = st.multiselect("Estados (UF):", ufs, default=ufs)

if not sel_anos: st.stop()
df = df_full[(df_full['ano'].isin(sel_anos)) & (df_full['uf_emit'].isin(sel_uf))].copy()

# --- 4. LÓGICA DE CATEGORIZAÇÃO (V12 CORRIGIDA) ---
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
        return '🔴 QUÍMICO (CRÍTICO)', 'FISPQ/LO/CTF'
    if any(x in desc for x in ['CABO DE ACO', 'CINTA DE CARGA', 'MANILHA', 'GANCHO', 'ESTROPO']):
        return '🟡 IÇAMENTO (CRÍTICO)', 'Certificado'
    
    eh_ncm_epi = ncm.startswith(('6116', '4015', '4203', '6403', '6506', '9020', '9004', '6307'))
    tem_termo_epi = any(t in desc for t in termos_epi_keyword)
    tem_termo_proibido = any(t in desc for t in termos_anti_epi)

    if (eh_ncm_epi or tem_termo_epi) and not tem_termo_proibido:
        return '🟠 EPI (CRÍTICO)', 'CA Válido'

    if ncm.startswith(('3917', '7307', '8481')) or any(t in desc for t in termos_hidraulica): return '💧 HIDRÁULICA', 'Geral'
    if ncm.startswith(('8544', '8536', '8538', '9405')) or any(t in desc for t in termos_eletrica): return '⚡ ELÉTRICA', 'Geral'
    if ncm.startswith(('6810', '6907', '2523')) or any(t in desc for t in termos_construcao): return '🧱 CIVIL', 'Geral'
    if ncm.startswith(('8202', '8203', '8204', '8205', '8207')) or any(t in desc for t in termos_ferramenta): return '🔧 FERRAMENTAS', 'Geral'
    return '📦 GERAL', 'Geral'

# --- 5. PROCESSAMENTO ETL ---
df_grouped = df.groupby(['desc_prod', 'u_medida', 'ncm']).agg(
    Total_Gasto=('v_total_item', 'sum'),
    Qtd_Total=('qtd', 'sum'),
    Menor_Preco_Historico=('v_unit', 'min'),
).reset_index()

df_grouped[['Categoria', 'Exigencia']] = df_grouped.apply(lambda x: pd.Series(classificar_material(x)), axis=1)
df_sorted = df.sort_values('data_emissao', ascending=False)
df_last = df_sorted.drop_duplicates(['desc_prod', 'ncm'])[['desc_prod', 'ncm', 'v_unit', 'nome_emit', 'n_nf', 'data_emissao']]
df_last.rename(columns={'v_unit': 'Preco_Ultima', 'nome_emit': 'Forn_Ultimo', 'n_nf': 'NF_Ultima', 'data_emissao': 'Data_Ultima'}, inplace=True)
df_final = df_grouped.merge(df_last, on=['desc_prod', 'ncm'], how='left')
df_final['Variacao_Preco'] = ((df_final['Preco_Ultima'] - df_final['Menor_Preco_Historico']) / df_final['Menor_Preco_Historico']) * 100
saving_potencial = df_final['Total_Gasto'].sum() - (df_final['Menor_Preco_Historico'] * df_final['Qtd_Total']).sum()

# --- 6. INTERFACE ---
st.title("🏗️ Portal de Inteligência em Suprimentos")
st.divider()

aba1, aba2, aba3, aba4 = st.tabs(["📊 Dashboard Executivo", "📋 Auditoria & Cadastro", "⚖️ Comparador de Preços", "🔍 Busca de Materiais"])

# ABA 1: DASHBOARD (Recuperado)
with aba1:
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Spend Total", format_brl(df['v_total_item'].sum()))
    k2.metric("Fornecedores", df['cnpj_emit'].nunique())
    k3.metric("Saving Potencial", format_brl(saving_potencial))
    k4.metric("Itens Críticos", len(df_final[df_final['Categoria'].str.contains('CRÍTICO')]))

    st.subheader("Evolução Mensal de Compras")
    fig_line = px.line(df.groupby('mes_ano')['v_total_item'].sum().reset_index().sort_values('mes_ano'), 
                       x='mes_ano', y='v_total_item', markers=True, color_discrete_sequence=['#004280'])
    fig_line.update_traces(hovertemplate='Mês: %{x}<br>Gasto: R$ %{y:,.2f}')
    st.plotly_chart(fig_line, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Curva ABC (Fornecedores)")
        fig_abc = px.bar(df.groupby('nome_emit')['v_total_item'].sum().nlargest(10).reset_index(), x='v_total_item', y='nome_emit', orientation='h', text_auto='.2s')
        fig_abc.update_layout(xaxis_title="Total Gasto (R$)", yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_abc, use_container_width=True)
    with c2:
        st.subheader("Share por Categoria")
        fig_pie = px.pie(df_final.groupby('Categoria')['Total_Gasto'].sum().reset_index(), values='Total_Gasto', names='Categoria', hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)

# ABA 2: AUDITORIA (Recuperada com Endereço)
with aba2:
    lista_f = df.groupby('nome_emit')['v_total_item'].sum().sort_values(ascending=False).index.tolist()
    forn_sel = st.selectbox("Selecione o Fornecedor:", lista_f, index=None, placeholder="Digite para buscar...")
    if forn_sel:
        dados_f = df[df['nome_emit'] == forn_sel].iloc[0]
        total_f = df[df['nome_emit'] == forn_sel]['v_total_item'].sum()
        mix_f = df_final[df_final['desc_prod'].isin(df[df['nome_emit'] == forn_sel]['desc_prod'].unique())].copy()
        mix_f = mix_f.sort_values(by=['Categoria', 'desc_prod'], ascending=[True, True])
        
        ca, cb = st.columns([1, 2])
        with ca:
            st.markdown(f"""
            <div class="card-fornecedor">
                <h3 style="margin:0; color:#004280;">{forn_sel}</h3>
                <p style="font-size:12px;">CNPJ: {dados_f['cnpj_emit']}</p>
                <hr>
                <p><b>📍 Endereço:</b><br>{dados_f.get('xLgr','')}, {dados_f.get('nro','')}<br>{dados_f.get('xBairro','')}<br>{dados_f.get('xMun','')}/{dados_f.get('uf_emit','')} - CEP: {dados_f.get('cep','')}</p>
                <hr>
                <h2 style="color:#004280;">{format_brl(total_f)}</h2>
            </div>
            """, unsafe_allow_html=True)
            if any("CRÍTICO" in x for x in mix_f['Categoria']): st.error("🚨 Fornecedor fornece itens Críticos!")
            else: st.success("✅ Fornecedor Geral")
        with cb:
            st.write("Mix Fornecido:")
            st.dataframe(mix_f[['desc_prod', 'Categoria', 'Exigencia']].style.map(lambda x: 'color:#ff4b4b;font-weight:bold' if 'CRÍTICO' in str(x) else '', subset=['Categoria']), hide_index=True, use_container_width=True, height=450)

# ABA 3: COMPARADOR (Formatado com Moeda)
with aba3:
    st.markdown("### ⚖️ Comparador Histórico de Concorrência")
    item_sel = st.selectbox("Escolha um material para analisar:", df_final.sort_values('Total_Gasto', ascending=False)['desc_prod'].unique())
    if item_sel:
        df_item = df[df['desc_prod'] == item_sel].copy()
        
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Melhor Preço", format_brl(df_item['v_unit'].min()))
        col_m2.metric("Preço Médio", format_brl(df_item['v_unit'].mean()))
        col_m3.metric("Último Preço", format_brl(df_item['v_unit'].iloc[0]))
        
        fig_scatter = px.scatter(df_item, x='data_emissao', y='v_unit', color='nome_emit', size='qtd',
                                 labels={'v_unit': 'Preço Unitário (R$)', 'data_emissao': 'Data Compra', 'nome_emit': 'Fornecedor'},
                                 title=f"Dispersão de Preços: {item_sel}")
        fig_scatter.update_layout(yaxis_tickformat="R$ ,.2f")
        st.plotly_chart(fig_scatter, use_container_width=True)
        
        st.write("Histórico Completo do Item:")
        st.dataframe(df_item[['data_emissao', 'nome_emit', 'n_nf', 'qtd', 'v_unit', 'v_total_item']].sort_values('data_emissao', ascending=False)
                     .style.format({'data_emissao': '{:%d/%m/%Y}', 'v_unit': format_brl, 'v_total_item': format_brl}), hide_index=True, use_container_width=True)

# ABA 4: BUSCA (Variação de Preço de volta)
with aba3: # Note: st.tabs order
    pass # Already defined above

with aba4:
    st.markdown("### 🔍 Busca de Materiais & Raio-X")
    t_busca = st.text_input("Filtrar por nome ou NCM:", placeholder="Ex: LUVA RASPA...")
    
    view = df_final.copy()
    if t_busca:
        for p in t_busca.upper().split(): view = view[view['desc_prod'].str.contains(p)]

    st.dataframe(
        view[['Categoria', 'desc_prod', 'Menor_Preco_Historico', 'Preco_Ultima', 'Variacao_Preco', 'Forn_Ultimo', 'NF_Ultima', 'Data_Ultima']]
        .sort_values('Data_Ultima', ascending=False)
        .style.format({'Menor_Preco_Historico': format_brl, 'Preco_Ultima': format_brl, 'Variacao_Preco': format_perc, 'Data_Ultima': '{:%d/%m/%Y}'})
        .map(lambda x: 'color: #ff4b4b; font-weight: bold' if x > 10 else ('color: #09ab3b' if x == 0 else ''), subset=['Variacao_Preco']),
        use_container_width=True, height=500
    )
