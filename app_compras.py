import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
import locale

# =====================================================
# 1. DETECÇÃO AUTOMÁTICA DE IDIOMA
# =====================================================
lang, _ = locale.getdefaultlocale()
if lang and lang.lower().startswith('pt'):
    APP_LANG = 'pt'
else:
    APP_LANG = 'en'

TEXT = {
    'pt': {
        'title': "🏗️ Portal de Inteligência em Suprimentos",
        'period': "📅 Período de Análise",
        'select_year': "Selecione os anos fiscais",
        'exec_review': "📌 Visão Executiva",
        'total_spend': "💰 Gasto Total",
        'critical_spend': "⚠️ Gasto Crítico",
        'saving': "🎯 Oportunidade de Saving",
        'supplier_conc': "🏢 Concentração de Fornecedores",
        'price_vol': "📈 Volatilidade de Preços",
        'top3': "Top 3 fornecedores",
        'variation': "Variação >20%",
        'key_insights': "🧠 Principais Insights",
        'spend_trend': "📊 Evolução de Gastos",
        'tabs': [
            "📌 Visão Executiva",
            "📊 Dashboard",
            "📇 Cadastro & Auditoria",
            "📉 Histórico de Preços",
            "🔍 Busca Avançada"
        ]
    },
    'en': {
        'title': "🏗️ Procurement Intelligence Portal",
        'period': "📅 Analysis Period",
        'select_year': "Select fiscal years",
        'exec_review': "📌 Executive Review",
        'total_spend': "💰 Total Spend",
        'critical_spend': "⚠️ Critical Spend",
        'saving': "🎯 Saving Opportunity",
        'supplier_conc': "🏢 Supplier Concentration",
        'price_vol': "📈 Price Volatility",
        'top3': "Top 3 suppliers",
        'variation': "Variation >20%",
        'key_insights': "🧠 Key Insights",
        'spend_trend': "📊 Spend Trend",
        'tabs': [
            "📌 Executive Review",
            "📊 Dashboard",
            "📇 Supplier Profile",
            "📉 Price History",
            "🔍 Advanced Search"
        ]
    }
}

T = TEXT[APP_LANG]

# =====================================================
# 2. CONFIGURAÇÃO STREAMLIT
# =====================================================
st.set_page_config(
    page_title=T['title'],
    page_icon="🏗️",
    layout="wide"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    div[data-testid="stMetric"] {
        background-color: var(--secondary-background-color);
        border: 1px solid rgba(128,128,128,0.2);
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #004280;
    }
    
    .card-fornecedor {
        background-color: var(--secondary-background-color);
        padding: 25px;
        border-radius: 12px;
        border: 1px solid rgba(128,128,128,0.2);
        margin-bottom: 20px;
        border-top: 5px solid #004280;
    }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 3. FUNÇÕES
# =====================================================
def format_brl(v):
    if pd.isna(v): return "R$ 0,00"
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# =====================================================
# 4. CARREGAMENTO DE DADOS
# =====================================================
@st.cache_data
def carregar_dados():
    if not os.path.exists("compras_suprimentos.db"):
        return pd.DataFrame()

    conn = sqlite3.connect("compras_suprimentos.db")
    df = pd.read_sql("SELECT * FROM base_compras", conn)
    conn.close()

    df['data_emissao'] = pd.to_datetime(df['data_emissao'])
    df['ano'] = df['data_emissao'].dt.year
    df['mes_ano'] = df['data_emissao'].dt.strftime('%Y-%m')
    df['desc_prod'] = df['desc_prod'].astype(str).str.upper().str.strip()
    df['ncm'] = df['ncm'].astype(str).str.replace('.', '', regex=False)
    df['cod_prod'] = df.get('cod_prod', '').astype(str)

    # Garantir colunas de imposto
    for col in ['v_icms','v_ipi','v_pis','v_cofins','v_iss']:
        if col not in df.columns:
            df[col] = 0.0
    df['Imposto_Total'] = (
        df['v_icms'].fillna(0) +
        df['v_ipi'].fillna(0) +
        df['v_pis'].fillna(0) +
        df['v_cofins'].fillna(0) +
        df['v_iss'].fillna(0)
    )

    return df

df_full = carregar_dados()
if df_full.empty:
    st.error("⚠️ Base de dados vazia.")
    st.stop()

# =====================================================
# 5. FILTROS
# =====================================================
st.title(T['title'])

anos_disponiveis = sorted(df_full['ano'].unique())
sel_anos = st.pills(
    T['select_year'],
    options=anos_disponiveis,
    selection_mode="multi",
    default=anos_disponiveis
)

if not sel_anos:
    st.warning("Selecione pelo menos um ano.")
    st.stop()

df = df_full[df_full['ano'].isin(sel_anos)].copy()
st.divider()

# =====================================================
# 6. CLASSIFICAÇÃO DE MATERIAL
# =====================================================
def classificar_material(row):
    desc, ncm = row['desc_prod'], row['ncm']

    if ncm.startswith(('2710','3403')) or any(x in desc for x in ['OLEO','GRAXA']):
        return '🔴 QUÍMICO (CRÍTICO)'
    if any(x in desc for x in ['CABO DE ACO','MANILHA','GANCHO']):
        return '🟡 IÇAMENTO (CRÍTICO)'
    if any(x in desc for x in ['LUVA','CAPACETE','OCULOS','BOTA']):
        return '🟠 EPI (CRÍTICO)'
    if any(x in desc for x in ['TUBO','PVC','VALVULA']):
        return '💧 HIDRÁULICA'
    if any(x in desc for x in ['CABO','DISJUNTOR','FIO']):
        return '⚡ ELÉTRICA'
    if any(x in desc for x in ['CIMENTO','AREIA','ARGAMASSA','TIJOLO']):
        return '🧱 CIVIL'
    if any(x in desc for x in ['CHAVE','BROCA','MARTELO','SERRA']):
        return '🔧 FERRAMENTAS'
    return '📦 GERAL'

df_grouped = df.groupby(['desc_prod','ncm','cod_prod']).agg(
    Total_Gasto=('v_total_item','sum'),
    Qtd_Total=('qtd','sum'),
    Menor_Preco=('v_unit','min')
).reset_index()
df_grouped['Categoria'] = df_grouped.apply(classificar_material, axis=1)

df_last = df.sort_values('data_emissao').drop_duplicates(
    ['desc_prod','ncm','cod_prod'], keep='last'
)[['desc_prod','ncm','cod_prod','v_unit','nome_emit','data_emissao']]

df_last.rename(columns={
    'v_unit':'Ultimo_Preco',
    'nome_emit':'Ultimo_Forn',
    'data_emissao':'Ultima_Data'
}, inplace=True)

df_final = df_grouped.merge(df_last, on=['desc_prod','ncm','cod_prod'])
df_final['Variacao_Preco'] = (df_final['Ultimo_Preco'] - df_final['Menor_Preco']) / df_final['Menor_Preco']
df_final['Saving_Potencial'] = df_final['Total_Gasto'] - (df_final['Menor_Preco'] * df_final['Qtd_Total'])

# =====================================================
# 7. TABS
# =====================================================
tab_exec, tab_dash, tab_cad, tab_hist, tab_busca = st.tabs(T['tabs'])

# =====================================================
# 8. EXECUTIVE REVIEW
# =====================================================
with tab_exec:
    st.subheader(T['exec_review'])

    total_spend = df['v_total_item'].sum()
    imposto_total = df['Imposto_Total'].sum()
    perc_imposto = imposto_total / total_spend if total_spend > 0 else 0
    saving_total = df_final['Saving_Potencial'].sum()
    critical_spend = df_final[df_final['Categoria'].str.contains('CRÍTICO')]['Total_Gasto'].sum()

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("💰 Gasto Total", format_brl(total_spend))
    c2.metric("💸 Imposto Total", format_brl(imposto_total))
    c3.metric("📊 % Imposto", f"{perc_imposto:.1%}")
    c4.metric("🎯 Saving Potencial", format_brl(saving_total))
    c5.metric("⚠️ Gasto Crítico", format_brl(critical_spend))

    st.markdown(f"""
### 🧠 Principais Insights
- 💸 Aproximadamente **{perc_imposto:.0%}** do valor comprado corresponde a carga tributária  
- ⚠️ Itens críticos concentram **{critical_spend/total_spend:.0%}** do gasto total  
- 🎯 Economia potencial estimada em **{format_brl(saving_total)}**
""")

    df_trend = df.groupby('mes_ano').agg(Gasto=('v_total_item','sum'), Imposto=('Imposto_Total','sum')).reset_index()
    fig = px.line(df_trend, x='mes_ano', y=['Gasto','Imposto'], markers=True)
    fig.update_layout(height=300, yaxis_tickformat="R$ ,.0f", legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("🧾 Análise Tributária Detalhada"):
        col1, col2 = st.columns(2)

        with col1:
            df_cat_tax = df.merge(df_final[['desc_prod','Categoria']], on='desc_prod', how='left')
            df_cat_tax = df_cat_tax.groupby('Categoria').agg(Gasto=('v_total_item','sum'), Imposto=('Imposto_Total','sum')).reset_index()
            df_cat_tax['% Imposto'] = df_cat_tax['Imposto'] / df_cat_tax['Gasto']
            fig_cat = px.bar(df_cat_tax.sort_values('% Imposto'), x='% Imposto', y='Categoria', orientation='h')
            st.plotly_chart(fig_cat, use_container_width=True)

        with col2:
            df_forn_tax = df.groupby('nome_emit').agg(Gasto=('v_total_item','sum'), Imposto=('Imposto_Total','sum')).reset_index()
            df_forn_tax['% Imposto'] = df_forn_tax['Imposto'] / df_forn_tax['Gasto']
            st.dataframe(df_forn_tax.sort_values('% Imposto', ascending=False).head(10), use_container_width=True)

# =====================================================
# 9. DASHBOARD (mantendo todo layout original)
# =====================================================
with tab_dash:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Gasto Total (Spend)", format_brl(df['v_total_item'].sum()))
    c2.metric("Fornecedores Ativos", df['cnpj_emit'].nunique())
    c3.metric("Risco Compliance", format_brl(critical_spend))
    c4.metric("Saving Potencial", format_brl(saving_total))

    st.subheader("Evolução Financeira")
    fig_line = px.area(df.groupby('mes_ano')['v_total_item'].sum().reset_index(), x='mes_ano', y='v_total_item', markers=True)
    fig_line.update_layout(yaxis_tickformat="R$ ,.2f", xaxis_title=None, yaxis_title=None, height=250)
    st.plotly_chart(fig_line, use_container_width=True)

    st.markdown("---")
    col_abc_forn, col_abc_mat = st.columns(2)
    
    with col_abc_forn:
        st.subheader("🏆 Top Fornecedores")
        top_f = df.groupby('nome_emit')['v_total_item'].sum().nlargest(10).reset_index()
        fig_pie_f = px.pie(top_f, values='v_total_item', names='nome_emit', hole=0.6)
        fig_pie_f.update_layout(showlegend=False, margin=dict(l=20,r=20,t=20,b=20), height=300)
        fig_pie_f.update_traces(textinfo='percent+label', textposition='inside')
        st.plotly_chart(fig_pie_f, use_container_width=True)
        with st.expander("🔎 Ver valores detalhados (Fornecedores)"):
            df_view_f = top_f.copy()
            df_view_f['Total'] = df_view_f['v_total_item'].apply(format_brl)
            st.dataframe(df_view_f[['nome_emit', 'Total']], hide_index=True, use_container_width=True)
    
    with col_abc_mat:
        st.subheader("📦 Top Materiais")
        top_m = df_final.groupby('desc_prod')['Total_Gasto'].sum().nlargest(10).reset_index()
        fig_pie_m = px.pie(top_m, values='Total_Gasto', names='desc_prod', hole=0.6)
        fig_pie_m.update_layout(showlegend=False, margin=dict(l=20,r=20,t=20,b=20), height=300)
        fig_pie_m.update_traces(textinfo='percent', textposition='inside')
        st.plotly_chart(fig_pie_m, use_container_width=True)
        with st.expander("🔎 Ver valores detalhados (Materiais)"):
            df_view_m = top_m.copy()
            df_view_m['Total'] = df_view_m['Total_Gasto'].apply(format_brl)
            st.dataframe(df_view_m[['desc_prod', 'Total']], hide_index=True, use_container_width=True)

    st.markdown("---")
    st.subheader("Gastos por Família")
    fig_cat = px.pie(df_final.groupby('Categoria')['Total_Gasto'].sum().reset_index(), values='Total_Gasto', names='Categoria', hole=0.5)
    fig_cat.update_layout(height=300)
    st.plotly_chart(fig_cat, use_container_width=True)

# =====================================================
# 10. CADASTRO & AUDITORIA (mantendo funcionalidade original)
# =====================================================
with tab_cad:
    st.markdown("##### 🕵️ Ficha Cadastral")
    lista_f = df.groupby('nome_emit')['v_total_item'].sum().sort_values(ascending=False).index
    forn_sel = st.selectbox("Selecione para ver o cadastro:", lista_f, index=None, placeholder="Nome do fornecedor...")
    
    if forn_sel:
        dados = df[df['nome_emit'] == forn_sel].iloc[0]
        total = df[df['nome_emit'] == forn_sel]['v_total_item'].sum()
        
        st.markdown(f"""
        <div class="card-fornecedor">
            <h3 style="margin:0;">🏢 {forn_sel}</h3>
            <p style="color:#666;">CNPJ: {dados['cnpj_emit']}</p>
            <hr>
            <p><b>📍 Endereço:</b></p>
            <p>{dados.get('xLgr','')}, {dados.get('nro','')} - {dados.get('xBairro','')}</p>
            <p>{dados.get('xMun','')}/{dados.get('uf_emit','')} - CEP: {dados.get('cep','')}</p>
            <hr>
            <p><b>Volume Total:</b></p>
            <h2>{format_brl(total)}</h2>
        </div>
        """, unsafe_allow_html=True)

        st.write("**Produtos Fornecidos:**")
        view_forn = df_final[df_final['desc_prod'].isin(df[df['nome_emit'] == forn_sel]['desc_prod'].unique())].copy()
        view_forn['Total'] = view_forn['Total_Gasto'].apply(format_brl)
        
        st.dataframe(
            view_forn[['cod_prod', 'desc_prod', 'Categoria', 'Total']],
            column_config={"cod_prod": "Ref.", "desc_prod": "Descrição", "Categoria": "Família"},
            use_container_width=True, hide_index=True
        )

# =====================================================
# 11. HISTÓRICO DE PREÇOS
# =====================================================
with tab_hist:
    st.markdown("### 📉 Evolução de Preços")
    df_final['display_name'] = df_final['desc_prod'] + " | Ref: " + df_final['cod_prod']
    item_bid_display = st.selectbox("Selecione o Item:", df_final.sort_values('Total_Gasto', ascending=False)['display_name'].unique())
    
    if item_bid_display:
        desc_sel, cod_sel = item_bid_display.split(" | Ref: ")
        df_item = df[(df['desc_prod'] == desc_sel) & (df['cod_prod'] == cod_sel)].copy()
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Melhor Preço", format_brl(df_item['v_unit'].min()))
        m2.metric("Pior Preço", format_brl(df_item['v_unit'].max()))
        m3.metric("Média", format_brl(df_item['v_unit'].mean()))
        
        fig_comp = px.line(df_item.sort_values('data_emissao'), x='data_emissao', y='v_unit', color='nome_emit', markers=True, title=f"Histórico: {desc_sel}")
        fig_comp.update_layout(yaxis_tickformat="R$ ,.2f", xaxis_title="Data", yaxis_title="Unitário")
