import streamlit as st
import pandas as pd
import sqlite3
import os

# --- Configuração da Página ---
st.set_page_config(
    page_title="Sistema Paralelo Ágil - Compras",
    page_icon="📦",
    layout="wide"
)

st.title("📊 Painel de Controle: Suprimentos")
st.markdown("---")

# --- Função de Conexão com Cache (para performance) ---
def carregar_dados(query):
    # Verifica se o banco existe antes de tentar conectar
    db_file = 'compras_suprimentos.db'
    
    if not os.path.exists(db_file):
        st.error(f"Erro: O arquivo '{db_file}' não foi encontrado no repositório.")
        return None

    try:
        conn = sqlite3.connect(db_file)
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Erro ao ler o banco de dados: {e}")
        return None

# --- Criação das Abas ---
tab1, tab2, tab3 = st.tabs(["📈 Análise Geral", "🏆 Top Fornecedores", "📂 Base Bruta"])

# --- ABA 1: Visão Analítica (Sua View Principal) ---
with tab1:
    st.header("Visão Analítica de Compras")
    
    # Aqui chamamos a sua View SQL criada
    df_analitica = carregar_dados("SELECT * FROM vw_compras_analitica")
    
    if df_analitica is not None and not df_analitica.empty:
        # Filtros laterais (opcional, pega as colunas da view automaticamente)
        st.dataframe(df_analitica, use_container_width=True)
        
        # Tenta gerar métricas rápidas se houver colunas numéricas
        colunas_numericas = df_analitica.select_dtypes(include=['float', 'int']).columns
        if len(colunas_numericas) > 0:
            st.info(f"Métricas rápidas baseadas na view: {', '.join(colunas_numericas)}")
            st.line_chart(df_analitica[colunas_numericas[0]]) # Gráfico simples da primeira coluna numérica
    else:
        st.warning("A view 'vw_compras_analitica' não retornou dados ou não foi encontrada.")

# --- ABA 2: Top Fornecedores (Sua View de Ranking) ---
with tab2:
    st.header("Ranking de Fornecedores")
    
    # Chamando a segunda View
    df_fornecedores = carregar_dados("SELECT * FROM vw_top_fornecedores")
    
    if df_fornecedores is not None and not df_fornecedores.empty:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.dataframe(df_fornecedores, use_container_width=True)
        
        with col2:
            # Se a view tiver colunas de texto e número, tenta montar um gráfico de barras
            cols_num = df_fornecedores.select_dtypes(include=['float', 'int']).columns
            cols_txt = df_fornecedores.select_dtypes(include=['object']).columns
            
            if len(cols_num) > 0 and len(cols_txt) > 0:
                st.subheader("Gráfico Visual")
                st.bar_chart(df_fornecedores.set_index(cols_txt[0])[cols_num[0]])
            else:
                st.info("A view precisa de uma coluna de texto e uma numérica para gerar gráfico.")
    else:
        st.warning("A view 'vw_top_fornecedores' não retornou dados.")

# --- ABA 3: Dados Brutos (Tabela Original) ---
with tab3:
    st.header("Base Completa (Tabela Física)")
    st.caption("Dados diretos da tabela 'base_compras' para conferência.")
    
    df_bruto = carregar_dados("SELECT * FROM base_compras LIMIT 1000")
    
    if df_bruto is not None:
        st.dataframe(df_bruto)
