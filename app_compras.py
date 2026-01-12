import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
import locale

# =====================================================
# 1. CONFIGURAÇÕES INICIAIS
# =====================================================
st.set_page_config(
    page_title="Portal de Inteligência em Suprimentos",
    page_icon="🏗️",
    layout="wide"
)

# Detecta idioma (ou força PT-BR se preferir)
lang, _ = locale.getdefaultlocale()
APP_LANG = 'pt' if lang and lang.lower().startswith('pt') else 'en'

TEXT = {
    'pt': {
        'title': "🏗️ Portal de Inteligência em Suprimentos",
        'period': "📅 Período de Análise",
        'select_year': "Selecione os anos fiscais",
        'exec_review': "📌 Visão Executiva",
        'total_spend': "💰 Gasto Total",
        'tabs': ["📌 Visão Executiva", "📊 Dashboard", "📇 Gestão de Fornecedores", "📉 Histórico de Preços", "🔍 Busca Avançada"]
    },
    'en': {
        'title': "🏗️ Procurement Intelligence Portal",
        'period': "📅 Analysis Period",
        'select_year': "Select fiscal years",
        'exec_review': "📌 Executive Review",
        'total_spend': "💰 Total Spend",
        'tabs': ["📌 Executive Review", "📊 Dashboard", "📇 Vendor Management", "📉 Price History", "🔍 Advanced Search"]
    }
}
T = TEXT[APP_LANG]

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
# 2. FUNÇÕES DE FORMATAÇÃO (O SEGREDO DO R$)
# =====================================================
def format_brl(v):
    """Converte float para string R$ 1.000,00"""
    if pd.isna(v): return "R$ 0,00"
    try:
        # Formata padrão US (1,234.56)
        val = f"{float(v):,.2f}"
        # Inverte os caracteres para BR (1.234,56)
        return f"R$ {val.replace(',', 'X').replace('.', ',').replace('X', '.')}"
    except:
        return str(v)

def format_perc(v):
    """Converte 0.35 para 35,0%"""
    if pd.isna(v): return "0,0%"
    try:
        val = f"{float(v)*100:.1f}"
        return f"{val.replace('.', ',')}%"
    except:
        return str(v)

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
    
    # Garante que colunas existem
    cols_imposto = ['v_icms','v_ipi','v_pis','v_cofins','v_iss']
    for col in cols_imposto:
        if col not in df.columns: df[col] = 0.0
            
    df['Imposto_Total'] = df[cols_imposto].sum(axis=1)
    
    # Garante cod_prod como string para filtros
    if 'cod_prod' not in df.columns: df['cod_prod'] = ''
    df['cod_prod'] = df['cod_prod'].astype(str)

    return df

df_full = carregar_dados()
if df_full.empty:
    st.error("⚠️ Base de dados vazia. Rode o extrator V9 primeiro.")
    st.stop()

# =====================================================
# 4. FILTROS
# =====================================================
st.title(T['title'])

anos_disponiveis = sorted(df_full['ano'].unique())
sel_anos = st.pills(T['select_year'], options=anos_disponiveis, selection_mode="multi", default=anos_disponiveis)
if not sel_anos: st.stop()

df = df_full[df_full['ano'].isin(sel_anos)].copy()
st.divider()

# =====================================================
# 5. CLASSIFICAÇÃO E AGRUPAMENTO
# =====================================================
def classificar_material(row):
    desc, ncm = row['desc_prod'], row['ncm']
    if ncm.startswith(('2710','3403')) or any(x in desc for x in ['OLEO','GRAXA']): return '🔴 QUÍMICO (CRÍTICO)'
    if any(x in desc for x in ['CABO DE ACO','MANILHA']): return '🟡 IÇAMENTO (CRÍTICO)'
    if any(x in desc for x in ['LUVA','CAPACETE','BOTA']): return '🟠 EPI (CRÍTICO)'
    if any(x in desc for x in ['TUBO','VALVULA']): return '💧 HIDRÁULICA'
    if any(x in desc for x in ['CABO','DISJUNTOR']): return '⚡ ELÉTRICA'
    if any(x in desc for x in ['CIMENTO','AREIA']): return '🧱 CIVIL'
    if any(x in desc for x in ['CHAVE','BROCA']): return '🔧 FERRAMENTAS'
    return '📦 GERAL'

df_grouped = df.groupby(['desc_prod','ncm','cod_prod']).agg(
    Total_Gasto=('v_total_item','sum'),
    Qtd_Total=('qtd','sum'),
    Menor_Preco=('v_unit','min')
).reset_index()

df_grouped['Categoria'] = df_grouped.apply(classificar_material, axis=1)

df_last = df.sort_values('data_emissao').drop_duplicates(['desc_prod','ncm','cod_prod'], keep='last')[['desc_prod','ncm','cod_prod','v_unit','nome_emit','data_emissao']]
df_last.rename(columns={'v_unit':'Ultimo_Preco', 'nome_emit':'Ultimo_Forn', 'data_emissao':'Ultima_Data'}, inplace=True)

df_final = df_grouped.merge(df_last, on=['desc_prod','ncm','cod_prod'])
df_final['Variacao_Preco'] = (df_final['Ultimo_Preco'] - df_final['Menor_Preco']) / df_final['Menor_Preco']
df_final['Saving_Potencial'] = df_final['Total_Gasto'] - (df_final['Menor_Preco'] * df_final['Qtd_Total'])

# =====================================================
# 6. INTERFACE (TABS)
# =====================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs(T['tabs'])

# --- TAB 1: EXECUTIVE REVIEW ---
with tab1:
    st.subheader(T['exec_review'])
    
    total_spend = df['v_total_item'].sum()
    imposto_total = df['Imposto_Total'].sum()
    perc_imposto = imposto_total / total_spend if total_spend > 0 else 0
    saving_total = df_final['Saving_Potencial'].sum()
    critico_spend = df_final[df_final['Categoria'].str.contains('CRÍTICO')]['Total_Gasto'].sum()

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("💰 Gasto Total", format_brl(total_spend))
    c2.metric("💸 Imposto Total", format_brl(imposto_total))
    c3.metric("📊 Carga Tributária", format_perc(perc_imposto))
    c4.metric("🎯 Saving Potencial", format_brl(saving_total))
    c5.metric("⚠️ Gasto Crítico", format_brl(critico_spend))

    # Gráfico de Tendência (Com separador BR)
    df_trend = df.groupby('mes_ano').agg(Gasto=('v_total_item','sum'), Imposto=('Imposto_Total','sum')).reset_index()
    fig = px.line(df_trend, x='mes_ano', y=['Gasto','Imposto'], markers=True)
    # AQUI ESTÁ O TRUQUE DO PLOTLY PARA BRASIL: separators=",."
    fig.update_layout(height=300, separators=",.", yaxis_tickformat=".2f") 
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("🧾 Análise Tributária Detalhada (Tabelas Corrigidas)"):
        col1, col2 = st.columns(2)
        with col1:
            df_cat_tax = df.merge(df_final[['desc_prod','Categoria']], on='desc_prod', how='left')
            df_cat_tax = df_cat_tax.groupby('Categoria').agg(Gasto=('v_total_item','sum'), Imposto=('Imposto_Total','sum')).reset_index()
            df_cat_tax['% Imposto'] = df_cat_tax['Imposto'] / df_cat_tax['Gasto']
            
            fig_cat = px.bar(df_cat_tax.sort_values('% Imposto'), x='% Imposto', y='Categoria', orientation='h', text_auto='.1%')
            fig_cat.update_layout(separators=",.")
            st.plotly_chart(fig_cat, use_container_width=True)

        with col2:
            # Tabela Formatada Corretamente
            df_forn_tax = df.groupby('nome_emit').agg(Gasto=('v_total_item','sum'), Imposto=('Imposto_Total','sum')).reset_index()
            df_forn_tax['% Imposto'] = df_forn_tax['Imposto'] / df_forn_tax['Gasto']
            
            # CRIANDO VERSÃO VISUAL (STRING)
            view_tax = df_forn_tax.sort_values('% Imposto', ascending=False).head(10).copy()
            view_tax['Gasto'] = view_tax['Gasto'].apply(format_brl)
            view_tax['Imposto'] = view_tax['Imposto'].apply(format_brl)
            view_tax['% Imposto'] = view_tax['% Imposto'].apply(format_perc)
            
            st.dataframe(view_tax, use_container_width=True, hide_index=True)

# --- TAB 2: DASHBOARD ---
with tab2:
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Gasto Total", format_brl(total_spend))
    c2.metric("Fornecedores", df['cnpj_emit'].nunique())
    c3.metric("Risco", format_brl(critico_spend))
    c4.metric("Saving", format_brl(saving_total))

    st.markdown("---")
    col_abc_f, col_abc_m = st.columns(2)

    with col_abc_f:
        st.subheader("🏆 Top Fornecedores")
        top_f = df.groupby('nome_emit')['v_total_item'].sum().nlargest(10).reset_index()
        fig_pie_f = px.pie(top_f, values='v_total_item', names='nome_emit', hole=0.6)
        fig_pie_f.update_layout(height=300, separators=",.")
        fig_pie_f.update_traces(textinfo='percent+label', textposition='inside')
        st.plotly_chart(fig_pie_f, use_container_width=True)
        
        with st.expander("🔎 Ver Valores (R$)"):
            view_f = top_f.copy()
            view_f['Total'] = view_f['v_total_item'].apply(format_brl)
            st.dataframe(view_f[['nome_emit','Total']], hide_index=True, use_container_width=True)

    with col_abc_m:
        st.subheader("📦 Top Materiais")
        top_m = df_final.groupby('desc_prod')['Total_Gasto'].sum().nlargest(10).reset_index()
        fig_pie_m = px.pie(top_m, values='Total_Gasto', names='desc_prod', hole=0.6)
        fig_pie_m.update_layout(height=300, separators=",.")
        fig_pie_m.update_traces(textinfo='percent', textposition='inside')
        st.plotly_chart(fig_pie_m, use_container_width=True)
        
        with st.expander("🔎 Ver Valores (R$)"):
            view_m = top_m.copy()
            view_m['Total'] = view_m['Total_Gasto'].apply(format_brl)
            st.dataframe(view_m[['desc_prod','Total']], hide_index=True, use_container_width=True)

# --- TAB 3: GESTÃO (VENDOR LIST) ---
with tab3:
    st.markdown("##### 📇 Ficha do Fornecedor")
    lista_f = df.groupby('nome_emit')['v_total_item'].sum().sort_values(ascending=False).index
    forn_sel = st.selectbox("Selecione:", lista_f, index=None)

    if forn_sel:
        stats = df[df['nome_emit'] == forn_sel]
        dados = stats.iloc[0]
        
        st.markdown(f"""
        <div class="card-fornecedor">
            <h3 style="margin:0;">🏢 {forn_sel}</h3>
            <p style="color:#666;">CNPJ: {dados['cnpj_emit']}</p>
            <hr>
            <h2>Volume Total: {format_brl(stats['v_total_item'].sum())}</h2>
        </div>
        """, unsafe_allow_html=True)

        view_forn = df_final[df_final['desc_prod'].isin(stats['desc_prod'].unique())].copy()
        view_forn['Total'] = view_forn['Total_Gasto'].apply(format_brl)
        st.dataframe(view_forn[['cod_prod', 'desc_prod', 'Categoria', 'Total']], hide_index=True, use_container_width=True)

# --- TAB 4: PREÇOS ---
with tab4:
    st.markdown("### 📉 Evolução de Preços")
    df_final['display'] = df_final['desc_prod'] + " | Ref: " + df_final['cod_prod']
    item_sel = st.selectbox("Item:", df_final.sort_values('Total_Gasto', ascending=False)['display'].unique())

    if item_sel:
        desc, cod = item_sel.split(" | Ref: ")
        df_item = df[(df['desc_prod'] == desc) & (df['cod_prod'] == cod)].copy()

        m1, m2, m3 = st.columns(3)
        m1.metric("Mínimo", format_brl(df_item['v_unit'].min()))
        m2.metric("Máximo", format_brl(df_item['v_unit'].max()))
        m3.metric("Média", format_brl(df_item['v_unit'].mean()))

        fig_line = px.line(df_item.sort_values('data_emissao'), x='data_emissao', y='v_unit', color='nome_emit', markers=True)
        fig_line.update_layout(separators=",.", yaxis_tickformat=".2f")
        st.plotly_chart(fig_line, use_container_width=True)
        
        # Tabela Formatada
        view_item = df_item[['data_emissao','nome_emit','n_nf','qtd','v_unit','v_total_item']].sort_values('data_emissao', ascending=False).copy()
        view_item['Unitário'] = view_item['v_unit'].apply(format_brl)
        view_item['Total'] = view_item['v_total_item'].apply(format_brl)
        
        st.dataframe(view_item[['data_emissao','nome_emit','n_nf','qtd','Unitário','Total']], hide_index=True, use_container_width=True)

# --- TAB 5: BUSCA AVANÇADA ---
with tab5:
    st.markdown("##### 🔎 Pesquisa Geral")
    c1, c2 = st.columns([3,1])
    termo = c1.text_input("Buscar:", placeholder="Ex: Cimento, Parafuso...")
    cat = c2.multiselect("Categoria:", df_final['Categoria'].unique())

    view = df_final.copy()
    if termo: 
        view = view[view['desc_prod'].str.contains(termo.upper()) | view['cod_prod'].str.contains(termo.upper())]
    if cat: 
        view = view[view['Categoria'].isin(cat)]

    # Formatação Final para Exibição
    view['Melhor Preço'] = view['Menor_Preco'].apply(format_brl)
    view['Último Pago'] = view['Ultimo_Preco'].apply(format_brl)
    view['Saving Estimado'] = view['Saving_Potencial'].apply(format_brl)

    st.dataframe(
        view[['Categoria', 'cod_prod', 'desc_prod', 'Melhor Preço', 'Último Pago', 'Saving Estimado', 'Ultimo_Forn', 'Ultima_Data']],
        column_config={"Ultima_Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY")},
        hide_index=True,
        use_container_width=True
    )