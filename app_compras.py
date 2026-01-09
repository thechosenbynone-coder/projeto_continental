import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os

# =====================================================
# 1. CONFIGURAÇÃO & DESIGN SYSTEM (CSS PROFISSIONAL)
# =====================================================
st.set_page_config(
    page_title="Portal de Inteligência em Suprimentos",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS AVANÇADO PARA VISUAL DE SISTEMA SaaS
st.markdown("""
<style>
    /* Importando fonte corporativa limpa */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"]  {
        font-family: 'Inter', sans-serif;
    }

    /* Fundo geral mais suave */
    .stApp {
        background-color: #f4f6f9;
    }

    /* ESTILO DOS CARDS (METRICAS) */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
        transition: transform 0.2s ease;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.08);
        border-color: #004280;
    }
    [data-testid="stMetricLabel"] {
        color: #6c757d;
        font-size: 14px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    [data-testid="stMetricValue"] {
        color: #1a1a1a !important;
        font-size: 28px !important;
        font-weight: 700;
    }

    /* CONTAINER DE GRÁFICOS (EFEITO CARD) */
    .chart-container {
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #e0e0e0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        margin-bottom: 20px;
    }

    /* SIDEBAR PROFISSIONAL */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e0e0e0;
    }
    
    /* CABEÇALHO TABELAS */
    thead tr th:first-child {display:none}
    tbody th {display:none}
    
    /* CARTÃO DE FORNECEDOR (HTML) */
    .card-fornecedor {
        background-color: white;
        padding: 24px;
        border-radius: 12px;
        border-left: 6px solid #004280;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
    }
    .card-critico { border-left-color: #dc3545; }
    .card-ok { border-left-color: #28a745; }
    
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. FUNÇÕES & HELPERS
# =====================================================
def format_brl(v):
    if pd.isna(v): return "R$ 0,00"
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def format_perc(v):
    if pd.isna(v): return "0%"
    return f"{v:.1f}%"

# =====================================================
# 3. CARREGAMENTO DE DADOS (ENGINE)
# =====================================================
@st.cache_data
def carregar_dados():
    if not os.path.exists("compras_suprimentos.db"):
        return pd.DataFrame()

    conn = sqlite3.connect("compras_suprimentos.db")
    df = pd.read_sql("SELECT * FROM base_compras", conn)
    conn.close()

    if df.empty: return pd.DataFrame()

    df['data_emissao'] = pd.to_datetime(df['data_emissao'])
    df['ano'] = df['data_emissao'].dt.year
    df['mes_ano'] = df['data_emissao'].dt.strftime('%Y-%m')
    df['bimestre'] = df['data_emissao'].dt.to_period('2M').astype(str)
    df['desc_prod'] = df['desc_prod'].astype(str).str.upper().str.strip()
    df['ncm'] = df['ncm'].astype(str).str.replace('.', '', regex=False)
    
    return df

df_full = carregar_dados()
if df_full.empty:
    st.error("⛔ SISTEMA OFFLINE: Base de dados não conectada.")
    st.stop()

# =====================================================
# 4. SIDEBAR (NAVEGAÇÃO)
# =====================================================
with st.sidebar:
    st.markdown("### 🏗️ Sourcing Intel")
    st.caption("v.2.0 Enterprise")
    st.markdown("---")
    
    st.subheader("Filtros Globais")
    anos = sorted(df_full['ano'].unique(), reverse=True)
    sel_anos = st.multiselect("Ano Fiscal:", anos, default=anos)
    
    ufs = sorted(df_full['uf_emit'].dropna().unique())
    sel_uf = st.multiselect("Região (UF):", ufs, default=ufs)
    
    st.markdown("---")
    st.info("💡 **Dica:** Utilize os filtros para refinar os KPIs do dashboard.")

if not sel_anos: st.stop()
df = df_full[(df_full['ano'].isin(sel_anos)) & (df_full['uf_emit'].isin(sel_uf))].copy()

# =====================================================
# 5. LÓGICA DE NEGÓCIO (CLASSIFICAÇÃO)
# =====================================================
def classificar_material(row):
    desc = row['desc_prod']
    ncm = row['ncm']
    termos_anti_epi = ['REDUCAO', 'RED ', 'SOLDAVEL', 'ROSCA', 'NPT', 'BSP', 'JOELHO', 'TE ', 'NIPLE', 'ADAPTADOR', 'CURVA', 'CONEXAO', 'UNIAO', 'LBS', 'CLASSE', 'SCH', 'DN ', 'CARBONO', 'INOX', 'ACO ', 'AÇO ', 'GALVANIZAD', 'LATÃO', 'FERRO', 'ESGOTO', 'SIFAO']
    
    if ncm.startswith(('2710','3403')) or (any(x in desc for x in ['OLEO','GRAXA','SOLVENTE','THINNER']) and 'ALIMENT' not in desc):
        return '🔴 QUÍMICO', 'FISPQ/CTF'
    if any(x in desc for x in ['CABO DE ACO','CINTA DE CARGA','MANILHA','GANCHO']):
        return '🟡 IÇAMENTO', 'Certificado'
    
    eh_epi = ncm.startswith(('6116','4015','4203','6403','6506','9020','9004','6307'))
    tem_termo = any(t in desc for t in ['LUVA','BOTA','CAPACETE','OCULOS','PROTETOR','MASCARA','CINTO','RESPIRADOR'])
    bloqueio = any(t in desc for t in termos_anti_epi)

    if (eh_epi or tem_termo) and not bloqueio:
        return '🟠 EPI', 'CA/Ficha'
    
    if any(x in desc for x in ['TUBO','PVC','VALVULA','REGISTRO','CONEXAO']): return '💧 HIDRÁULICA', 'Geral'
    if any(x in desc for x in ['CABO','DISJUNTOR','LAMPADA','RELE','FIO']): return '⚡ ELÉTRICA', 'Geral'
    if any(x in desc for x in ['CIMENTO','AREIA','ARGAMASSA','TIJOLO']): return '🧱 CIVIL', 'Geral'
    if any(x in desc for x in ['CHAVE','BROCA','MARTELO','SERRA']): return '🔧 FERRAMENTAS', 'Geral'
    return '📦 GERAL', 'Geral'

# ETL EM MEMÓRIA
df_grouped = df.groupby(['desc_prod','ncm']).agg(
    Total_Gasto=('v_total_item','sum'),
    Qtd_Total=('qtd','sum'),
    Menor_Preco=('v_unit','min'),
    Maior_Preco=('v_unit','max')
).reset_index()

df_grouped[['Categoria','Exigencia']] = df_grouped.apply(lambda x: pd.Series(classificar_material(x)), axis=1)

df_last = df.sort_values('data_emissao').drop_duplicates(['desc_prod','ncm'], keep='last')[['desc_prod','ncm','v_unit','nome_emit','n_nf','data_emissao']]
df_last.rename(columns={'v_unit':'Ultimo_Preco', 'nome_emit':'Ultimo_Forn', 'n_nf':'Ultima_NF', 'data_emissao':'Ultima_Data'}, inplace=True)

df_final = df_grouped.merge(df_last, on=['desc_prod','ncm'], how='left')
df_final['Variacao_Preco'] = ((df_final['Ultimo_Preco'] - df_final['Menor_Preco']) / df_final['Menor_Preco']) # Para barra de progresso (0.0 a 1.0)
df_final['Variacao_Pct'] = df_final['Variacao_Preco'] * 100 # Para mostrar texto
df_final['Saving_Potencial'] = df_final['Total_Gasto'] - (df_final['Menor_Preco'] * df_final['Qtd_Total'])

# =====================================================
# 6. LAYOUT DA PLATAFORMA
# =====================================================
st.markdown("## 📊 Visão Geral da Operação")
st.markdown("---")

# ABAS COM ÍCONES E NOMES CURTOS
tab1, tab2, tab3, tab4 = st.tabs(["Dashboard", "Auditoria", "Bid Leveling", "Pesquisa Avançada"])

# --- TAB 1: DASHBOARD EXECUTIVO ---
with tab1:
    # 1. KPIs FINANCEIROS (LINHA 1)
    st.markdown("##### 💰 Performance Financeira")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Spend Total", format_brl(df['v_total_item'].sum()), delta="YTD")
    c2.metric("Saving Potencial", format_brl(df_final['Saving_Potencial'].sum()), delta="Oportunidade", delta_color="normal")
    c3.metric("Ticket Médio", format_brl(df['v_total_item'].mean()))
    c4.metric("% Spend Crítico", format_perc(df_final[df_final['Categoria'].str.contains('CRÍTICO')]['Total_Gasto'].sum() / df['v_total_item'].sum() * 100))

    # 2. KPIs OPERACIONAIS (LINHA 2)
    st.markdown("##### ⚙️ Indicadores Operacionais")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Fornecedores Ativos", df['cnpj_emit'].nunique())
    k2.metric("Itens Gerenciados", df_final['desc_prod'].nunique())
    k3.metric("Notas Processadas", df['n_nf'].nunique())
    k4.metric("Itens Monofornecedor", (df.groupby('desc_prod')['nome_emit'].nunique() == 1).sum(), delta="Risco Supply", delta_color="inverse")

    st.markdown("###") # Espaço

    # 3. GRÁFICOS EM CONTAINERS (VISUAL LIMPO)
    col_g1, col_g2 = st.columns([2, 1])
    
    with col_g1:
        with st.container():
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            st.subheader("📈 Evolução de Spend (Bimestral)")
            df_time = df.groupby('bimestre')['v_total_item'].sum().reset_index()
            fig_line = px.area(df_time, x='bimestre', y='v_total_item', markers=True)
            fig_line.update_traces(line_color='#004280', fillcolor='rgba(0, 66, 128, 0.1)')
            fig_line.update_layout(plot_bgcolor='white', yaxis_tickformat="R$ ,.2s", margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_line, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

    with col_g2:
        with st.container():
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            st.subheader("🍩 Share por Categoria")
            fig_pie = px.pie(df_final.groupby('Categoria')['Total_Gasto'].sum().reset_index(), 
                             values='Total_Gasto', names='Categoria', hole=0.6,
                             color_discrete_sequence=px.colors.qualitative.Prism)
            fig_pie.update_layout(showlegend=False, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_pie, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

# --- TAB 2: AUDITORIA (CARD UI) ---
with tab2:
    st.markdown("##### 🕵️ Dossiê do Fornecedor")
    col_sel, col_vazio = st.columns([1, 2])
    forn_sel = col_sel.selectbox("Selecione para auditar:", df.groupby('nome_emit')['v_total_item'].sum().sort_values(ascending=False).index, index=None, placeholder="Digite o nome...")

    if forn_sel:
        dados_f = df[df['nome_emit'] == forn_sel].iloc[0]
        total_f = df[df['nome_emit'] == forn_sel]['v_total_item'].sum()
        mix_f = df_final[df_final['desc_prod'].isin(df[df['nome_emit'] == forn_sel]['desc_prod'].unique())].copy()
        
        has_risk = any("CRÍTICO" in x for x in mix_f['Categoria'])
        card_class = "card-critico" if has_risk else "card-ok"
        status_txt = "🚨 Fornecedor Crítico (EPI/Químico)" if has_risk else "✅ Fornecedor Geral"

        # CARD HTML
        st.markdown(f"""
        <div class="card-fornecedor {card_class}">
            <h2 style="margin:0; color:#1a1a1a;">{forn_sel}</h2>
            <p style="color:#666; font-size:14px;">CNPJ: {dados_f['cnpj_emit']}</p>
            <div style="display:flex; justify-content:space-between; margin-top:20px;">
                <div>
                    <p style="font-weight:bold; margin-bottom:5px;">📍 Localização</p>
                    <p style="margin:0; font-size:13px;">{dados_f.get('xLgr','')}, {dados_f.get('nro','')}</p>
                    <p style="margin:0; font-size:13px;">{dados_f.get('xBairro','')} - {dados_f.get('xMun','')}/{dados_f.get('uf_emit','')}</p>
                    <p style="margin:0; font-size:13px;">CEP: {dados_f.get('cep','')}</p>
                </div>
                <div style="text-align:right;">
                    <p style="font-weight:bold; margin-bottom:5px;">💵 Volume Total</p>
                    <h3 style="margin:0; color:#004280;">{format_brl(total_f)}</h3>
                    <p style="color:{'#dc3545' if has_risk else '#28a745'}; font-weight:bold; margin-top:10px;">{status_txt}</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        st.dataframe(
            mix_f[['desc_prod', 'Categoria', 'Exigencia', 'Total_Gasto']],
            column_config={
                "Total_Gasto": st.column_config.ProgressColumn("Volume (R$)", format="R$ %.2f", min_value=0, max_value=mix_f['Total_Gasto'].max()),
            },
            use_container_width=True, hide_index=True
        )

# --- TAB 3: COMPARADOR (PLOTLY CLEAN) ---
with tab3:
    st.markdown("##### ⚖️ Bid Leveling (Comparativo)")
    item_bid = st.selectbox("Selecione o Item:", df_final.sort_values('Total_Gasto', ascending=False)['desc_prod'].unique())
    
    if item_bid:
        df_item = df[df['desc_prod'] == item_bid].copy()
        
        fig_scatter = px.scatter(df_item, x='data_emissao', y='v_unit', color='nome_emit', size='qtd',
                                 title=f"Dispersão de Preços: {item_bid}",
                                 labels={'v_unit': 'Preço Unitário (R$)', 'data_emissao': 'Data', 'nome_emit': 'Fornecedor'})
        fig_scatter.update_layout(plot_bgcolor='white', yaxis_tickformat="R$ ,.2f", xaxis_title=None)
        fig_scatter.update_xaxes(showgrid=True, gridcolor='#eee')
        fig_scatter.update_yaxes(showgrid=True, gridcolor='#eee')
        st.plotly_chart(fig_scatter, use_container_width=True)

# --- TAB 4: PESQUISA (DATA EDITOR PRO) ---
with tab4:
    st.markdown("##### 🔎 Busca Avançada de Materiais")
    col_search, col_fam = st.columns([3, 1])
    termo = col_search.text_input("Buscar Item:", placeholder="Ex: Luva, Cabo...")
    cat_filtro = col_fam.multiselect("Categoria:", sorted(df_final['Categoria'].unique()))
    
    view = df_final.copy()
    if termo:
        view = view[view['desc_prod'].str.contains(termo.upper()) | view['ncm'].str.contains(termo)]
    if cat_filtro:
        view = view[view['Categoria'].isin(cat_filtro)]

    # AQUI ESTÁ O SEGREDO DO VISUAL PROFISSIONAL EM TABELAS:
    st.dataframe(
        view[['Categoria', 'desc_prod', 'Menor_Preco', 'Ultimo_Preco', 'Variacao_Preco', 'Ultimo_Forn', 'Ultima_Data']],
        column_config={
            "Categoria": st.column_config.TextColumn("Família", width="medium"),
            "desc_prod": st.column_config.TextColumn("Descrição", width="large"),
            "Menor_Preco": st.column_config.NumberColumn("Melhor Preço (Hist)", format="R$ %.2f"),
            "Ultimo_Preco": st.column_config.NumberColumn("Último Pago", format="R$ %.2f"),
            "Variacao_Preco": st.column_config.ProgressColumn(
                "Var. Preço (%)", 
                help="O quanto pagamos a mais na última compra comparado ao mínimo histórico",
                format="%.1f%%", 
                min_value=0, 
                max_value=1
            ),
            "Ultima_Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY")
        },
        use_container_width=True,
        hide_index=True,
        height=600
    )
