import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os

# --- 1. CONFIGURAÇÃO (Modo Adaptativo) ---
st.set_page_config(page_title="Gestão de Suprimentos V11", page_icon="💎", layout="wide")

# CSS QUE SE ADAPTA AO TEMA (DARK/LIGHT)
st.markdown("""
    <style>
    /* Estilo dos CARDS (Métricas) */
    div[data-testid="stMetric"] {
        /* Usa a cor secundária do tema (cinza claro no Light, cinza escuro no Dark) */
        background-color: var(--secondary-background-color);
        border: 1px solid var(--text-color); /* Borda sutil */
        border-color: rgba(128, 128, 128, 0.2);
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* Ajuste para o valor da métrica ficar destacado */
    [data-testid="stMetricValue"] {
        font-size: 26px !important;
        font-weight: 700;
        /* Cor primária do Streamlit (vermelho padrão ou customizado) */
        color: var(--primary-color) !important;
    }
    
    /* Estilo do Cartão de Fornecedor (HTML) */
    .card-fornecedor {
        background-color: var(--secondary-background-color);
        padding: 20px;
        border-radius: 10px;
        border: 1px solid rgba(128, 128, 128, 0.2);
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES ---
def format_brl(valor):
    if pd.isna(valor): return "R$ 0,00"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def format_perc(valor):
    if pd.isna(valor): return "0%"
    return f"{valor:.1f}%"

# --- 2. DADOS ---
@st.cache_data
def carregar_dados():
    db_path = "compras_suprimentos.db"
    if not os.path.exists(db_path):
        st.error("⚠️ Banco de dados não encontrado.")
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
if df_full.empty: st.stop()

# --- 3. TOPO ---
c1, c2 = st.columns([1, 2])
with c1: st.title("💎 Portal Suprimentos")
with c2:
    anos = sorted(df_full['ano'].unique(), reverse=True)
    st.write("Período:")
    sel = st.multiselect("Selecione:", anos, default=anos, label_visibility="collapsed")

if not sel: st.stop()
df = df_full[df_full['ano'].isin(sel)].copy()
st.divider()

# --- 4. LÓGICA DE CLASSIFICAÇÃO ---
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

    if ncm.startswith(('2710', '3403', '3814', '3208', '3209')) or (any(x in desc for x in ['OLEO', 'GRAXA', 'LUBRIFICANTE', 'SOLVENTE', 'THINNER', 'ADESIVO']) and 'ALIMENT' not in desc):
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

# --- 5. INTERFACE (SEM BUG DE ABAS) ---
aba1, aba2, aba3 = st.tabs(["📊 Dashboard", "📋 Auditoria", "🔍 Busca"])

# ABA 1
with aba1:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Gasto Total", format_brl(df['v_total_item'].sum()))
    c2.metric("Fornecedores", df['cnpj_emit'].nunique())
    c3.metric("Mix Crítico", len(df_final[df_final['Categoria'].str.contains('CRÍTICO')]))
    c4.metric("Notas", df['n_nf'].nunique())

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.subheader("Gasto por Categoria")
        fig_cat = px.bar(df_final.groupby('Categoria')['Total_Gasto'].sum().reset_index().sort_values('Total_Gasto', ascending=True), 
                         x='Total_Gasto', y='Categoria', orientation='h', text_auto='.2s')
        st.plotly_chart(fig_cat, use_container_width=True)
    with col_g2:
        st.subheader("Top Fornecedores")
        fig_pie = px.pie(df.groupby('nome_emit')['v_total_item'].sum().nlargest(10).reset_index(), values='v_total_item', names='nome_emit', hole=0.5)
        st.plotly_chart(fig_pie, use_container_width=True)

# ABA 2
with aba2:
    lista_fornecedores = df.groupby('nome_emit')['v_total_item'].sum().sort_values(ascending=False).index.tolist()
    fornecedor_sel = st.selectbox("Selecione o Fornecedor:", lista_fornecedores, index=None, placeholder="Digite para buscar...")
    
    st.markdown("---")
    
    if fornecedor_sel:
        itens_do_fornecedor = df[df['nome_emit'] == fornecedor_sel]['desc_prod'].unique()
        todos_itens_f = df_final[df_final['desc_prod'].isin(itens_do_fornecedor)].copy()
        todos_itens_f['Risco'] = todos_itens_f['Categoria'].str.contains('CRÍTICO')
        todos_itens_f = todos_itens_f.sort_values(['Risco', 'desc_prod'], ascending=[False, True])
        
        dados_f = df[df['nome_emit'] == fornecedor_sel].iloc[0]
        total_f = df[df['nome_emit'] == fornecedor_sel]['v_total_item'].sum()
        riscos_f = todos_itens_f[todos_itens_f['Risco'] == True]
        
        ca, cb = st.columns([1, 2])
        with ca:
            # HTML ADAPTATIVO (Usa classes do container em vez de style inline fixo)
            st.markdown(f"""
            <div class="card-fornecedor">
                <h3>{fornecedor_sel}</h3>
                <p><b>CNPJ:</b> {dados_f.get('cnpj_emit')}</p>
                <p><b>Local:</b> {dados_f.get('xMun')}/{dados_f.get('uf_emit')}</p>
                <hr>
                <h2>{format_brl(total_f)}</h2>
            </div>
            """, unsafe_allow_html=True)
            
            if not riscos_f.empty:
                st.error(f"🚨 FORNECEDOR CRÍTICO ({len(riscos_f)} itens)")
            else:
                st.success("✅ Fornecedor Geral")

        with cb:
            st.write("Histórico de Vendas:")
            st.dataframe(
                todos_itens_f[['desc_prod', 'Categoria', 'Exigencia']]
                .style.map(lambda x: 'color: #ff4b4b; font-weight: bold' if 'CRÍTICO' in str(x) else '', subset=['Categoria']),
                hide_index=True, use_container_width=True, height=400
            )

# ABA 3
with aba3:
    c_s, c_f = st.columns([3, 1])
    termo = c_s.text_input("Buscar Item:", placeholder="Ex: Luva...")
    cat = c_f.multiselect("Categoria:", sorted(df_final['Categoria'].unique()))
    
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
