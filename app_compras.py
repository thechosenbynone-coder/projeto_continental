import streamlit as st
import sqlite3
import pandas as pd

# ---------------- CONFIGURAÇÕES ----------------
DB_NAME = "compras_suprimentos.db"

st.set_page_config(
    page_title="Plataforma de Compras",
    layout="wide",
    page_icon="📊"
)

# ---------------- FUNÇÕES ----------------
def conectar_db():
    return sqlite3.connect(DB_NAME)

def carregar_view(nome_view):
    conn = conectar_db()
    df = pd.read_sql(f"SELECT * FROM {nome_view}", conn)
    conn.close()
    return df

# ---------------- SIDEBAR ----------------
st.sidebar.title("📌 Navegação")

pagina = st.sidebar.radio(
    "Selecione a visão:",
    (
        "📊 Resumo Executivo",
        "📦 Compras Analítica",
        "💰 Impostos",
        "🏭 Fornecedores"
    )
)

# ---------------- RESUMO EXECUTIVO ----------------
if pagina == "📊 Resumo Executivo":
    st.title("📊 Resumo Executivo")

    df_compras = carregar_view("vw_compras_analitica")
    df_impostos = carregar_view("vw_nf_impostos")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "💵 Valor Total Compras",
            f"R$ {df_compras['valor_total'].sum():,.2f}"
        )

    with col2:
        st.metric(
            "📦 Total de Itens",
            f"{df_compras.shape[0]:,}"
        )

    with col3:
        st.metric(
            "🧾 Total de Notas",
            df_compras['n_nf'].nunique()
        )

    with col4:
        st.metric(
            "💰 Impostos Totais",
            f"R$ {df_impostos['valor_imposto'].sum():,.2f}"
        )

    st.divider()

    st.subheader("📌 Top 5 Fornecedores")
    df_top = carregar_view("vw_top_fornecedores")
    st.dataframe(df_top.head(5), use_container_width=True)

# ---------------- COMPRAS ANALÍTICA ----------------
elif pagina == "📦 Compras Analítica":
    st.title("📦 Compras Analítica")

    df_compras = carregar_view("vw_compras_analitica")

    st.dataframe(
        df_compras,
        use_container_width=True,
        height=600
    )

# ---------------- IMPOSTOS ----------------
elif pagina == "💰 Impostos":
    st.title("💰 Análise de Impostos")

    df_impostos = carregar_view("vw_nf_impostos")

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "💰 Total de Impostos",
            f"R$ {df_impostos['valor_imposto'].sum():,.2f}"
        )

    with col2:
        st.metric(
            "🧾 Total de NFs",
            df_impostos['chave_acesso'].nunique()
        )

    st.divider()

    st.dataframe(
        df_impostos,
        use_container_width=True,
        height=600
    )

# ---------------- FORNECEDORES ----------------
elif pagina == "🏭 Fornecedores":
    st.title("🏭 Fornecedores")

    df_fornecedores = carregar_view("vw_top_fornecedores")

    st.dataframe(
        df_fornecedores,
        use_container_width=True,
        height=600
    )
