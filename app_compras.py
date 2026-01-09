import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os

# =====================================================
# 1. CONFIGURAÇÃO & DESIGN SYSTEM
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
        border-radius: 8px;
        border-left: 5px solid #004280;
    }
    
    [data-testid="stMetricValue"] {
        font-size: 26px !important;
        font-weight: 700;
        color: var(--primary-color) !important;
    }

    /* Tabelas e Gráficos */
    .stDataFrame { border: 1px solid rgba(128,128,128,0.2); border-radius: 8px; }
    
    /* Cartão de Fornecedor */
    .card-fornecedor {
        background-color: var(--secondary-background-color);
        padding: 20px;
        border-radius: 10px;
        border: 1px solid rgba(128,128,128,0.2);
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. FUNÇÕES FORMATADORAS
# =====================================================
def format_brl(v):
    if pd.isna(v): return "R$ 0,00"
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def format_perc(v):
    if pd.isna(v): return "0%"
    return f"{v:.1f}%"

# =====================================================
# 3. CARREGAMENTO DE DADOS
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
    df['desc_prod'] = df['desc_prod'].astype(str).str.upper().str.strip()
    df['ncm'] = df['ncm'].astype(str).str.replace('.', '', regex=False)
    
    return df

df_full = carregar_dados()
if df_full.empty:
    st.error("⚠️ Base de dados vazia. Rode o extrator novo e faça upload do .db")
    st.stop()

# =====================================================
# 4. FILTROS (Sem o filtro de Estado que você não queria)
# =====================================================
with st.sidebar:
    st.title("🎛️ Filtros")
    anos = sorted(df_full['ano'].unique(), reverse=True)
    sel_anos = st.multiselect("Ano Fiscal:", anos, default=anos)

if not sel_anos: st.stop()
df = df_full[df_full['ano'].isin(sel_anos)].copy()

# =====================================================
# 5. CLASSIFICAÇÃO & ETL
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

# Agrupa por Descrição e NCM
df_grouped = df.groupby(['desc_prod','ncm']).agg(
    Total_Gasto=('v_total_item','sum'),
    Qtd_Total=('qtd','sum'),
    Menor_Preco=('v_unit','min'),
).reset_index()

df_grouped['Categoria'] = df_grouped.apply(classificar_material, axis=1)

# Pega dados da última compra
df_last = df.sort_values('data_emissao').drop_duplicates(['desc_prod','ncm'], keep='last')[['desc_prod','ncm','v_unit','nome_emit','n_nf','data_emissao']]
df_last.rename(columns={'v_unit':'Ultimo_Preco', 'nome_emit':'Ultimo_Forn', 'n_nf':'Ultima_NF', 'data_emissao':'Ultima_Data'}, inplace=True)

df_final = df_grouped.merge(df_last, on=['desc_prod','ncm'], how='left')

# Cálculos Finais
df_final['Variacao_Preco'] = ((df_final['Ultimo_Preco'] - df_final['Menor_Preco']) / df_final['Menor_Preco'])
df_final['Saving_Potencial'] = df_final['Total_Gasto'] - (df_final['Menor_Preco'] * df_final['Qtd_Total'])

# CORREÇÃO DO SPEND CRÍTICO
spend_critico = df_final[df_final['Categoria'].str.contains('CRÍTICO')]['Total_Gasto'].sum()

# =====================================================
# 6. INTERFACE V21
# =====================================================
st.title("🏗️ Portal de Inteligência em Suprimentos")
st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(["Dashboard", "Auditoria", "Bid Leveling (Comparador)", "Pesquisa"])

# --- TAB 1: DASHBOARD ---
with tab1:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Spend Total", format_brl(df['v_total_item'].sum()))
    c2.metric("Fornecedores", df['cnpj_emit'].nunique())
    # Agora o Spend Crítico vai funcionar
    c3.metric("Spend Crítico (Risco)", format_brl(spend_critico), delta="Compliance") 
    c4.metric("Saving Potencial", format_brl(df_final['Saving_Potencial'].sum()))

    st.subheader("Evolução de Gastos (Linha do Tempo)")
    # Gráfico simples e direto
    fig_line = px.line(df.groupby('mes_ano')['v_total_item'].sum().reset_index(), x='mes_ano', y='v_total_item', markers=True)
    fig_line.update_layout(yaxis_tickformat="R$ ,.2f", xaxis_title="Mês", yaxis_title="Valor Gasto")
    st.plotly_chart(fig_line, use_container_width=True)

    col_abc, col_cat = st.columns(2)
    with col_abc:
        st.subheader("Curva ABC (Top 10 Fornecedores)")
        top_f = df.groupby('nome_emit')['v_total_item'].sum().nlargest(10).reset_index()
        fig_bar = px.bar(top_f, x='v_total_item', y='nome_emit', orientation='h', text_auto='.2s')
        fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_tickformat="R$ ,.2f")
        st.plotly_chart(fig_bar, use_container_width=True)
    
    with col_cat:
        st.subheader("Share por Categoria")
        fig_pie = px.pie(df_final.groupby('Categoria')['Total_Gasto'].sum().reset_index(), values='Total_Gasto', names='Categoria', hole=0.5)
        st.plotly_chart(fig_pie, use_container_width=True)

# --- TAB 2: AUDITORIA ---
with tab2:
    lista_f = df.groupby('nome_emit')['v_total_item'].sum().sort_values(ascending=False).index
    forn_sel = st.selectbox("Selecione Fornecedor:", lista_f, index=None, placeholder="Digite o nome...")
    
    if forn_sel:
        dados = df[df['nome_emit'] == forn_sel].iloc[0]
        total = df[df['nome_emit'] == forn_sel]['v_total_item'].sum()
        
        # HTML que respeita o tema (sem cor de fundo fixa)
        st.markdown(f"""
        <div class="card-fornecedor">
            <h3 style="margin:0;">{forn_sel}</h3>
            <p>CNPJ: {dados['cnpj_emit']}</p>
            <hr>
            <p>📍 {dados.get('xLgr','')}, {dados.get('nro','')} - {dados.get('xBairro','')}</p>
            <p>{dados.get('xMun','')}/{dados.get('uf_emit','')} - CEP: {dados.get('cep','')}</p>
            <hr>
            <h2>Volume: {format_brl(total)}</h2>
        </div>
        """, unsafe_allow_html=True)

        st.dataframe(
            df_final[df_final['desc_prod'].isin(df[df['nome_emit'] == forn_sel]['desc_prod'].unique())][['desc_prod','Categoria','Total_Gasto']],
            column_config={"Total_Gasto": st.column_config.NumberColumn("Total", format="R$ %.2f")},
            use_container_width=True, hide_index=True
        )

# --- TAB 3: BID LEVELING (CORRIGIDO - FÁCIL DE ENTENDER) ---
with tab3:
    st.markdown("### 📉 Histórico de Preços (Comparativo)")
    st.info("Veja como o preço do item mudou ao longo do tempo e quem vendeu mais barato.")
    
    item_bid = st.selectbox("Selecione o Item:", df_final.sort_values('Total_Gasto', ascending=False)['desc_prod'].unique())
    
    if item_bid:
        df_item = df[df['desc_prod'] == item_bid].copy()
        
        # MÉTRICAS DE RESUMO
        m1, m2, m3 = st.columns(3)
        m1.metric("Melhor Preço Pago", format_brl(df_item['v_unit'].min()))
        m2.metric("Pior Preço Pago", format_brl(df_item['v_unit'].max()))
        m3.metric("Média", format_brl(df_item['v_unit'].mean()))
        
        # GRÁFICO DE LINHA (MUITO MAIS CLARO QUE BOLHAS)
        # Eixo X = Data, Eixo Y = Preço, Cor = Fornecedor
        fig_comp = px.line(df_item.sort_values('data_emissao'), x='data_emissao', y='v_unit', color='nome_emit', markers=True,
                           title=f"Evolução de Preço: {item_bid}")
        fig_comp.update_layout(yaxis_tickformat="R$ ,.2f", xaxis_title="Data da Compra", yaxis_title="Preço Unitário")
        st.plotly_chart(fig_comp, use_container_width=True)

        st.write("Detalhes das Compras:")
        st.dataframe(
            df_item[['data_emissao','nome_emit','n_nf','qtd','v_unit','v_total_item']].sort_values('data_emissao', ascending=False),
            column_config={
                "data_emissao": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "v_unit": st.column_config.NumberColumn("Preço Unit.", format="R$ %.2f"),
                "v_total_item": st.column_config.NumberColumn("Total", format="R$ %.2f"),
            },
            use_container_width=True, hide_index=True
        )

# --- TAB 4: PESQUISA ---
with tab4:
    c_busca, c_cat = st.columns([3, 1])
    termo = c_busca.text_input("Buscar:", placeholder="Ex: Mangueira...")
    cat_sel = c_cat.multiselect("Categoria:", df_final['Categoria'].unique())
    
    view = df_final.copy()
    if termo: view = view[view['desc_prod'].str.contains(termo.upper())]
    if cat_sel: view = view[view['Categoria'].isin(cat_sel)]

    st.dataframe(
        view[['Categoria', 'desc_prod', 'Menor_Preco', 'Ultimo_Preco', 'Variacao_Preco', 'Ultimo_Forn', 'Ultima_Data']],
        column_config={
            "Categoria": st.column_config.TextColumn("Família", width="medium"),
            "desc_prod": st.column_config.TextColumn("Descrição", width="large"),
            "Menor_Preco": st.column_config.NumberColumn("Melhor (Hist)", format="R$ %.2f"),
            "Ultimo_Preco": st.column_config.NumberColumn("Último Pago", format="R$ %.2f"),
            "Variacao_Preco": st.column_config.ProgressColumn(
                "Var. %", 
                format="%.1f%%", 
                min_value=0, max_value=1,
                help="Variação entre o Último Pago e o Mínimo Histórico"
            ),
            "Ultima_Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY")
        },
        use_container_width=True, hide_index=True, height=600
    )
