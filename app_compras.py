import streamlit as st
import pandas as pd
import sqlite3
import os
import locale

# --- IMPORTS ---
from styles.theme import aplicar_tema
from utils.classifiers import classificar_materiais_turbo
from utils.formatters import format_brl, format_perc
from utils.normalizer import normalizar_unidades_v1
from utils.compliance import validar_compliance 

# Imports das Abas
from ui.tab_exec_review import render_tab_exec_review
from ui.tab_dashboard import render_tab_dashboard
from ui.tab_fornecedores import render_tab_fornecedores
from ui.tab_negociacao import render_tab_negociacao
from ui.tab_busca import render_tab_busca
from ui.tab_compliance import render_tab_compliance # <--- NOVO IMPORT

# 1. CONFIGURAÇÃO
st.set_page_config(
    page_title="Portal de Inteligência em Suprimentos", 
    page_icon="🏗️", 
    layout="wide"
)
aplicar_tema()

# 2. CARGA DE DADOS
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
    
    for col in ['v_icms', 'v_ipi', 'v_pis', 'v_cofins', 'v_iss']:
        if col not in df.columns: df[col] = 0.0
    df['Imposto_Total'] = df[['v_icms', 'v_ipi', 'v_pis', 'v_cofins', 'v_iss']].sum(axis=1)
    
    if 'cod_prod' not in df.columns: df['cod_prod'] = ''
    
    df = normalizar_unidades_v1(df)
    return df

df_full = carregar_dados()

if df_full.empty:
    st.error("Erro: Base vazia. Rode o extrator.py novamente.")
    st.stop()

# 3. INTELIGÊNCIA GLOBAL
df_full['Categoria'] = classificar_materiais_turbo(df_full)
df_full = validar_compliance(df_full) # Essencial para a aba de Compliance funcionar

# Pré-Cálculo Global
df_grouped_full = df_full.groupby(['desc_prod', 'ncm', 'cod_prod', 'Categoria']).agg(
    Total_Gasto=('v_total_item', 'sum'),
    Qtd_Total=('qtd_real', 'sum'), 
    Menor_Preco=('v_unit_real', 'min') 
).reset_index()

df_last_full = (
    df_full.sort_values('data_emissao')
    .drop_duplicates(['desc_prod', 'ncm', 'cod_prod'], keep='last')
    [['desc_prod', 'ncm', 'cod_prod', 'v_unit_real', 'nome_emit', 'data_emissao']]
)
df_final_full = df_grouped_full.merge(df_last_full, on=['desc_prod', 'ncm', 'cod_prod'])

# 4. FUNÇÃO AUXILIAR DE FILTRO (Pills)
def processar_filtro_ano(df_base, key_suffix):
    anos = sorted(df_base['ano'].unique(), reverse=True)
    c1, c2 = st.columns([1, 5])
    with c1: st.markdown("**Período de Análise:**")
    with c2:
        ano_sel = st.pills("Selecione o Ano", options=anos, default=anos[0], label_visibility="collapsed", key=f"pills_{key_suffix}")
    st.markdown("---")
    
    if not ano_sel: ano_sel = anos[0]
    df_filtered = df_base[df_base['ano'] == ano_sel].copy()

    df_grouped = df_filtered.groupby(['desc_prod', 'ncm', 'cod_prod', 'Categoria']).agg(
        Total_Gasto=('v_total_item', 'sum'),
        Qtd_Total=('qtd_real', 'sum'),
        Menor_Preco=('v_unit_real', 'min')
    ).reset_index()

    df_last = (
        df_filtered.sort_values('data_emissao')
        .drop_duplicates(['desc_prod', 'ncm', 'cod_prod'], keep='last')
        [['desc_prod', 'ncm', 'cod_prod', 'v_unit_real', 'nome_emit', 'data_emissao']]
        .rename(columns={'v_unit_real': 'Ultimo_Preco', 'nome_emit': 'Ultimo_Forn', 'data_emissao': 'Ultima_Data'})
    )
    df_res = df_grouped.merge(df_last, on=['desc_prod', 'ncm', 'cod_prod'])
    df_res['Saving_Potencial'] = df_res['Total_Gasto'] - (df_res['Menor_Preco'] * df_res['Qtd_Total'])
    
    return df_filtered, df_res

# 5. RENDERIZAÇÃO
st.title("🏗️ Portal de Inteligência em Suprimentos")

# Nova estrutura de Abas
abas = ["📌 Visão Executiva", "📊 Dashboard", "🛡️ Compliance", "📇 Gestão de Fornecedores", "💰 Cockpit", "🔍 Busca"]
tabs = st.tabs(abas)

# Aba 1: Executiva (Tática - Com Filtro)
with tabs[0]:
    df_t1, df_final_t1 = processar_filtro_ano(df_full, "tab1")
    render_tab_exec_review(df_t1, df_final_t1)

# Aba 2: Dashboard (Tática - Com Filtro)
with tabs[1]:
    df_t2, df_final_t2 = processar_filtro_ano(df_full, "tab2")
    render_tab_dashboard(df_t2, df_final_t2)

# Aba 3: Compliance (NOVA - Base Completa)
with tabs[2]:
    render_tab_compliance(df_full)

# Aba 4: Fornecedores (Estratégica - Base Completa)
with tabs[3]:
    render_tab_fornecedores(df_full, df_final_full)

# Aba 5: Cockpit (Estratégica - Base Completa)
with tabs[4]:
    render_tab_negociacao(df_full)

# Aba 6: Busca (Operacional - Base Completa)
with tabs[5]:
    render_tab_busca(df_full)
