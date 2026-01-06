import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os

st.set_page_config(page_title="Gestão Suprimentos Cloud", layout="wide")

# Função para ligar ao banco que vais enviar junto
def carregar_dados():
    # Procura o arquivo na mesma pasta do script
    caminho_db = "compras_suprimentos.db"
    if not os.path.exists(caminho_db):
        st.error("Erro: Banco de dados não encontrado no servidor!")
        return pd.DataFrame()
    
    conn = sqlite3.connect(caminho_db)
    df = pd.read_sql_query("SELECT * FROM base_compras", conn)
    conn.close()
    df['data_emissao'] = pd.to_datetime(df['data_emissao'])
    return df

df = carregar_dados()

# ... (O restante do código do Dashboard que já fizemos segue aqui)
st.title("🛡️ Portal de Inteligência em Suprimentos")
st.write("Dados em nuvem para acesso remoto.")
st.dataframe(df.head())