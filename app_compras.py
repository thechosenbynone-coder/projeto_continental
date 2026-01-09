import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os

# =====================================================
# 1. CONFIGURAÇÃO & DESIGN (V26 - UX REFINADA)
# =====================================================
st.set_page_config(
    page_title="Portal de Inteligência em Suprimentos",
    page_icon="🏗️",
    layout="wide"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* Cards Métricas */
    div[data-testid="stMetric"] {
        background-color: var(--secondary-background-color);
        border: 1px solid rgba(128,128,128,0.2);
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #004280;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    [data-testid="stMetricValue"] {
        font-size: 26px !important;
        font-weight: 700;
        color: var(--primary-color) !important;
    }

    /* Cartão de Fornecedor */
    .card-fornecedor {
        background-color: var(--secondary-background-color);
        padding: 25px;
        border-radius: 12px;
        border: 1px solid rgba(128,128,128,0.2);
        margin-bottom: 20px;
        border-top: 5px solid #004280;
    }
    
    /* Ajuste de tabelas para não quebrar linha em cabeçalho */
    th { white-space: nowrap; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. FUNÇÕES FORMATADORAS (TEXTO PURO)
# =====================================================
# Importante: Retorna STRING para forçar visual BR na tabela
def format_brl_str(v):
    if pd.isna(v): return "R$ 0,00"
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# =====================================================
# 3. CARREGAMENTO DE DADOS
# =====================================================
@st.cache_data
def carregar_dados():
    if not os.path.exists("compras_suprimentos.db"): return pd.DataFrame()
    conn = sqlite3.connect("compras_suprimentos.db")
    df = pd.read_sql("SELECT * FROM base_compras", conn)
    conn.close()
    if df.empty: return pd.DataFrame()

    df['data_emissao'] = pd.to_datetime(df['data_emissao'])
    df['ano'] = df['data_emissao'].dt.year
    df['mes_ano'] = df['data_emissao'].dt.strftime('%Y-%m')
    df['desc_prod'] = df['desc_prod'].astype(str).str.upper().str.strip()
    df['ncm'] = df['ncm'].astype(str).str.replace('.', '', regex=False)
    if 'cod_prod' not in df.columns: df['cod_prod'] = ''
    df['cod_prod'] = df['cod_prod'].astype(str).str.strip()
    
    return df

df_full = carregar_dados()
if df_full.empty:
    st.error("⚠️ Base de dados vazia. Rode o extrator.")
    st.stop()

# =====================================================
# 4. FILTROS
# =====================================================
st.title("🏗️ Portal de Inteligência em Suprimentos")

with st.container():
    st.write("##### 📅 Período de Análise")
    anos_disponiveis = sorted(df_full['ano'].unique())
    sel_anos = st.pills(
        "Selecione os anos fiscais:",
        options=anos_disponiveis,
        selection_mode="multi",
        default=anos_disponiveis,
        label_visibility="collapsed"
    )

if not sel_anos:
    st.warning("Selecione pelo menos um ano acima.")
    st.stop()

df = df_full[df_full['ano'].isin(sel_anos)].copy()
st.divider()

# =====================================================
# 5. CLASSIFICAÇÃO
# =====================================================
def classificar_material(row):
    desc = row['desc_prod']
    ncm = row['ncm']
    termos_anti_epi = ['REDUCAO', 'RED ', 'SOLDAVEL', 'ROSCA', 'NPT', 'BSP', 'JOELHO', 'TE ', 'NIPLE', 'ADAPTADOR', 'CURVA', 'CONEXAO', 'UNIAO', 'LBS', 'CLASSE', 'SCH', 'DN ', 'CARBONO', 'INOX', 'ACO ', 'AÇO ', 'GALVANIZAD', 'LATÃO', 'FERRO', 'ESGOTO', 'SIFAO']
    
    if ncm.startswith(('2710','3403')) or (any(x in desc for x in ['OLEO','GRAXA','SOLVENTE']) and 'ALIMENT' not in desc):
        return '🔴 QUÍMICO (CRÍTICO)'
    if any(x in desc for x in ['CABO DE ACO','CINTA DE CARGA','MANILHA','GANCHO']):
        return '🟡 IÇAMENTO (CRÍTICO)'
    
    eh_epi = ncm.startswith(('6116','4015','4203','6403','6506','9020','9004','6307'))
    tem_termo = any(t in desc for t in ['LUVA','BOTA','CAPACETE','OCULOS','PROTETOR','MASCARA','CINTO','RESPIRADOR'])
    bloqueio = any(t in desc for t in termos_anti_epi)

    if (eh_epi or tem_termo) and not bloqueio:
        return '🟠 EPI (CRÍTICO)'
    
    if any(x in desc for x in ['TUBO','PVC','VALVULA','REGISTRO','CONEXAO']): return '💧 HIDRÁULICA'
    if any(x in desc for x in ['CABO','DISJUNTOR','LAMPADA','RELE','FIO']): return '⚡ ELÉTRICA'
    if any(x in desc for x in ['CIMENTO','AREIA','ARGAMASSA','TIJOLO']): return '🧱 CIVIL'
    if any(x in desc for x in ['CHAVE','BROCA','MARTELO','SERRA']): return '🔧 FERRAMENTAS'
    return '📦 GERAL'

df_grouped = df.groupby(['desc_prod', 'ncm', 'cod_prod']).agg(
    Total_Gasto=('v_total_item','sum'),
    Qtd_Total=('qtd','sum'),
    Menor_Preco=('v_unit','min'),
).reset_index()

df_grouped['Categoria'] = df_grouped.apply(classificar_material, axis=1)

df_last = df.sort_values('data_emissao').drop_duplicates(['desc_prod','ncm','cod_prod'], keep='last')[['desc_prod','ncm','cod_prod','v_unit','nome_emit','n_nf','data_emissao']]
df_last.rename(columns={'v_unit':'Ultimo_Preco', 'nome_emit':'Ultimo_Forn', 'n_nf':'Ultima_NF', 'data_emissao':'Ultima_Data'}, inplace=True)

df_final = df_grouped.merge(df_last, on=['desc_prod','ncm','cod_prod'], how='left')
df_final['Variacao_Preco'] = ((df_final['Ultimo_Preco'] - df_final['Menor_Preco']) / df_final['Menor_Preco'])
df_final['Saving_Potencial'] = df_final['Total_Gasto'] - (df_final['Menor_Preco'] * df_final['Qtd_Total'])
spend_critico = df_final[df_final['Categoria'].str.contains('CRÍTICO')]['Total_Gasto'].sum()

# =====================================================
# 6. LAYOUT PRINCIPAL
# =====================================================
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Dashboard", 
    "📇 Cadastro & Auditoria", 
    "📉 Histórico de Preços", 
    "🔍 Busca Avançada"
])

# --- TAB 1: DASHBOARD ---
with tab1:
    # 1. KPIs
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Gasto Total (Spend)", format_brl_str(df['v_total_item'].sum()))
    c2.metric("Fornecedores Ativos", df['cnpj_emit'].nunique())
    c3.metric("Risco Compliance", format_brl_str(spend_critico), delta="Itens Críticos") 
    c4.metric("Saving Potencial", format_brl_str(df_final['Saving_Potencial'].sum()))

    # 2. Evolução
    st.subheader("Evolução Financeira")
    # Gráfico de Área é visualmente mais "cheio" e bonito que linha simples
    fig_line = px.area(df.groupby('mes_ano')['v_total_item'].sum().reset_index(), x='mes_ano', y='v_total_item', markers=True)
    fig_line.update_layout(yaxis_tickformat="R$ ,.2f", xaxis_title=None, yaxis_title=None, height=300)
    st.plotly_chart(fig_line, use_container_width=True)

    # 3. TOP 10 (VISUAL ENXUTO)
    st.markdown("---")
    col_abc_forn, col_abc_mat = st.columns(2)
    
    with col_abc_forn:
        st.subheader("🏆 Top 10 Fornecedores (R$)")
        top_f = df.groupby('nome_emit')['v_total_item'].sum().nlargest(10).reset_index()
        
        # Ajuste: Altura dinâmica (se tiver só 2 itens, fica pequeno. Se tiver 10, cresce)
        altura_dinamica = 150 + (len(top_f) * 30)
        
        fig_bar_f = px.bar(top_f, x='v_total_item', y='nome_emit', orientation='h', text_auto='.2s')
        # Bargap 0.3 deixa a barra mais fina e elegante
        fig_bar_f.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_tickformat="R$ ,.2f", height=altura_dinamica, margin=dict(l=0, r=0, t=0, b=0), bargap=0.3)
        st.plotly_chart(fig_bar_f, use_container_width=True)
        
        # O botão de detalhe
        with st.expander("🔎 Ver dados detalhados dos Top Fornecedores"):
            df_view_f = top_f.copy()
            df_view_f['Total'] = df_view_f['v_total_item'].apply(format_brl_str)
            st.dataframe(df_view_f[['nome_emit', 'Total']], hide_index=True, use_container_width=True)
    
    with col_abc_mat:
        st.subheader("📦 Top 10 Materiais (R$)")
        top_m = df_final.groupby('desc_prod')['Total_Gasto'].sum().nlargest(10).reset_index()
        
        altura_dinamica_m = 150 + (len(top_m) * 30)
        
        fig_bar_m = px.bar(top_m, x='Total_Gasto', y='desc_prod', orientation='h', text_auto='.2s')
        fig_bar_m.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_tickformat="R$ ,.2f", height=altura_dinamica_m, margin=dict(l=0, r=0, t=0, b=0), bargap=0.3)
        fig_bar_m.update_traces(marker_color='#ff7f0e') 
        st.plotly_chart(fig_bar_m, use_container_width=True)
        
        with st.expander("🔎 Ver dados detalhados dos Top Materiais"):
            df_view_m = top_m.copy()
            df_view_m['Total'] = df_view_m['Total_Gasto'].apply(format_brl_str)
            st.dataframe(df_view_m[['desc_prod', 'Total']], hide_index=True, use_container_width=True)

    # 4. Categorias
    st.markdown("---")
    st.subheader("Gastos por Família")
    fig_pie = px.pie(df_final.groupby('Categoria')['Total_Gasto'].sum().reset_index(), values='Total_Gasto', names='Categoria', hole=0.5)
    fig_pie.update_layout(height=350)
    st.plotly_chart(fig_pie, use_container_width=True)

# --- TAB 2: CADASTRO & AUDITORIA ---
with tab2:
    st.markdown("##### 🕵️ Ficha Cadastral")
    lista_f = df.groupby('nome_emit')['v_total_item'].sum().sort_values(ascending=False).index
    forn_sel = st.selectbox("Selecione para ver o cadastro:", lista_f, index=None, placeholder="Digite o nome do fornecedor...")
    
    if forn_sel:
        dados = df[df['nome_emit'] == forn_sel].iloc[0]
        total = df[df['nome_emit'] == forn_sel]['v_total_item'].sum()
        
        st.markdown(f"""
        <div class="card-fornecedor">
            <h3 style="margin:0;">🏢 {forn_sel}</h3>
            <p style="color:#666;">CNPJ: {dados['cnpj_emit']}</p>
            <hr>
            <p><b>📍 Endereço Cadastrado na NF:</b></p>
            <p>{dados.get('xLgr','')}, {dados.get('nro','')} - {dados.get('xBairro','')}</p>
            <p>{dados.get('xMun','')}/{dados.get('uf_emit','')} - CEP: {dados.get('cep','')}</p>
            <hr>
            <p><b>Performance:</b></p>
            <h2>Volume Total: {format_brl_str(total)}</h2>
        </div>
        """, unsafe_allow_html=True)

        st.write("**Produtos Fornecidos:**")
        view_forn = df_final[df_final['desc_prod'].isin(df[df['nome_emit'] == forn_sel]['desc_prod'].unique())].copy()
        view_forn['Total'] = view_forn['Total_Gasto'].apply(format_brl_str)
        
        st.dataframe(
            view_forn[['cod_prod', 'desc_prod', 'Categoria', 'Total']],
            column_config={"cod_prod": "Ref. Fornecedor", "desc_prod": "Descrição", "Categoria": "Família"},
            use_container_width=True, hide_index=True
        )

# --- TAB 3: HISTÓRICO DE PREÇOS (TABELA FORMATADA CORRETAMENTE) ---
with tab3:
    st.markdown("### 📉 Evolução e Variação de Preços")
    
    df_final['display_name'] = df_final['desc_prod'] + " | Ref: " + df_final['cod_prod']
    item_bid_display = st.selectbox("Selecione o Item (Descrição | Código):", df_final.sort_values('Total_Gasto', ascending=False)['display_name'].unique())
    
    if item_bid_display:
        desc_sel = item_bid_display.split(" | Ref: ")[0]
        cod_sel = item_bid_display.split(" | Ref: ")[1]
        
        df_item = df[(df['desc_prod'] == desc_sel) & (df['cod_prod'] == cod_sel)].copy()
        
        m1, m2, m3 = st.columns(3)
        # Formatação aqui funciona porque st.metric aceita string
        m1.metric("Melhor Preço Já Pago", format_brl_str(df_item['v_unit'].min()))
        m2.metric("Pior Preço Já Pago", format_brl_str(df_item['v_unit'].max()))
        m3.metric("Preço Médio", format_brl_str(df_item['v_unit'].mean()))
        
        fig_comp = px.line(df_item.sort_values('data_emissao'), x='data_emissao', y='v_unit', color='nome_emit', markers=True,
                           title=f"Histórico de Compras: {desc_sel}")
        fig_comp.update_layout(yaxis_tickformat="R$ ,.2f", xaxis_title="Data", yaxis_title="Preço Unit.")
        st.plotly_chart(fig_comp, use_container_width=True)

        # TABELA CORRIGIDA: Convertendo para String para forçar visual BR
        df_view_item = df_item[['data_emissao','nome_emit','n_nf','qtd','v_unit','v_total_item']].sort_values('data_emissao', ascending=False).copy()
        df_view_item['Unitário'] = df_view_item['v_unit'].apply(format_brl_str)
        df_view_item['Total'] = df_view_item['v_total_item'].apply(format_brl_str)
        
        st.dataframe(
            df_view_item[['data_emissao','nome_emit','n_nf','qtd','Unitário','Total']],
            column_config={"data_emissao": st.column_config.DateColumn("Data", format="DD/MM/YYYY")},
            use_container_width=True, hide_index=True
        )

# --- TAB 4: BUSCA AVANÇADA ---
with tab4:
    st.markdown("##### 🔎 Pesquisar na Base de Dados")
    c_busca, c_cat = st.columns([3, 1])
    termo = c_busca.text_input("O que você procura?", placeholder="Ex: Cimento, Luva, Parafuso...")
    cat_sel = c_cat.multiselect("Filtrar por Família:", df_final['Categoria'].unique())
    
    view = df_final.copy()
    if termo: view = view[view['desc_prod'].str.contains(termo.upper())]
    if cat_sel: view = view[view['Categoria'].isin(cat_sel)]

    # Formatação String para Tabela
    view['Melhor Preço'] = view['Menor_Preco'].apply(format_brl_str)
    view['Último Pago'] = view['Ultimo_Preco'].apply(format_brl_str)
    
    st.dataframe(
        view[['Categoria', 'cod_prod', 'desc_prod', 'Melhor Preço', 'Último Pago', 'Variacao_Preco', 'Ultimo_Forn', 'Ultima_Data']],
        column_config={
            "Categoria": st.column_config.TextColumn("Família", width="medium"),
            "cod_prod": st.column_config.TextColumn("Ref.", width="small"),
            "desc_prod": st.column_config.TextColumn("Descrição", width="large"),
            "Variacao_Preco": st.column_config.ProgressColumn("Var. %", format="%.1f%%", min_value=0, max_value=1),
            "Ultima_Data": st.column_config.DateColumn("Última Compra", format="DD/MM/YYYY")
        },
        use_container_width=True, hide_index=True, height=600
    )
