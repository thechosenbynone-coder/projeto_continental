import streamlit as st
import pandas as pd
import numpy as np
import random
from utils.formatters import format_brl, format_perc

# --- FUNÇÕES AUXILIARES ---

def gerar_dados_cadastrais(nome_fornecedor):
    random.seed(hash(nome_fornecedor))
    ruas = ["Av. das Indústrias", "Rodovia BR-101", "Rua da Manufatura", "Av. Brasil", "Distrito Industrial"]
    dominios = ["comercial", "vendas", "contato", "sac"]
    return {
        "endereco": f"{random.choice(ruas)}, {random.randint(100, 9999)} - Galpão {random.choice(['A', 'B', 'C'])}",
        "telefone": f"(11) 3{random.randint(100, 999)}-{random.randint(1000, 9999)}",
        "email": f"{random.choice(dominios)}@{nome_fornecedor.split()[0].lower()}.com.br".replace(".", "").replace(",", "")
    }

def calcular_score_fornecedor(df_fornecedor, df_mercado):
    """
    Calcula nota de 0 a 10 baseada em Competitividade de Preço e Impostos.
    """
    # 1. Score de Preço (70%)
    itens_comuns = df_fornecedor['desc_prod'].unique()
    df_ref = df_mercado[df_mercado['desc_prod'].isin(itens_comuns)]
    
    if df_ref.empty:
        score_preco = 10 
    else:
        # Compara preço médio dele com o menor preço histórico do mercado
        comp = df_fornecedor.groupby('desc_prod')['v_unit_real'].mean().reset_index()
        comp = comp.merge(df_ref[['desc_prod', 'Menor_Preco']], on='desc_prod')
        
        # Evita divisão por zero e erros de dados vazios
        comp = comp[comp['v_unit_real'] > 0]
        
        if comp.empty:
            score_preco = 10
        else:
            comp['ratio'] = comp['Menor_Preco'] / comp['v_unit_real']
            score_preco = comp['ratio'].mean() * 10

    # 2. Score Tributário (30%)
    total_v = df_fornecedor['v_total_item'].sum()
    if total_v > 0:
        taxa_media = df_fornecedor['Imposto_Total'].sum() / total_v
    else:
        taxa_media = 0
        
    score_tax = (1 - taxa_media) * 10
    
    nota = (score_preco * 0.7) + (score_tax * 0.3)
    return min(max(nota, 0), 10)

# --- RENDERIZAÇÃO DA ABA ---
def render_tab_fornecedores(df, df_final):
    st.markdown("### 📇 Gestão de Relacionamento (SRM)")
    st.caption("Base Completa de Fornecedores (Histórico Total)")
    
    # Search Box
    lista_f = df.groupby('nome_emit')['v_total_item'].sum().sort_values(ascending=False).index
    
    col_search, _ = st.columns([1, 2])
    with col_search:
        forn_sel = st.selectbox("Pesquisar Fornecedor:", options=lista_f, index=None, placeholder="Digite o nome...")

    st.divider()

    if not forn_sel:
        st.info("👆 Selecione um fornecedor acima para ver a ficha técnica.")
        return

    # Filtra dados
    df_forn = df[df['nome_emit'] == forn_sel].copy()
    cadastro = gerar_dados_cadastrais(forn_sel)
    
    # Verifica Compliance
    if 'Risco_Compliance' in df_forn.columns:
        itens_risco = df_forn[df_forn['Risco_Compliance'] == True]
        qtd_risco = len(itens_risco)
    else:
        qtd_risco = 0
        
    total_itens = len(df_forn)
    perc_risco = (qtd_risco / total_itens) * 100 if total_itens > 0 else 0
    
    status_icon = "🟢"
    cor_borda = "#388e3c"
    
    if qtd_risco > 0:
        status_icon = "🔴" if perc_risco > 10 else "🟡"
        cor_borda = "#d32f2f" if perc_risco > 10 else "#fbc02d"

    # Layout do Cartão
    with st.container():
        st.markdown(f"""
        <style>
            .header-forn {{ 
                padding: 20px; border-radius: 10px; 
                border-left: 10px solid {cor_borda}; 
                background-color: #f8f9fa; 
                box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 20px;
            }}
        </style>
        """, unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns([3, 2, 1])
        
        with c1:
            st.markdown(f"## {status_icon} {forn_sel}")
            st.markdown(f"**CNPJ:** {df_forn['cnpj_emit'].iloc[0]}")
            st.markdown(f"📍 {cadastro['endereco']}")
            st.markdown(f"📞 {cadastro['telefone']}")
            
            if qtd_risco > 0:
                st.error(f"⚠️ **ALERTA DE COMPLIANCE:** {qtd_risco} itens sem nº de CA detectados.")
            
        with c2:
            st.metric("Volume Total Negociado", format_brl(df_forn['v_total_item'].sum()))
            # MUDANÇA AQUI: Última Compra (MAX)
            st.metric("Última Compra", df_forn['data_emissao'].max().strftime('%d/%m/%Y'))
            st.metric("Total de Transações", len(df_forn))
            
        with c3:
            nota = calcular_score_fornecedor(df_forn, df_final)
            st.markdown(f"<div style='text-align:center; font-size: 3.5rem; font-weight:bold; color: #004280'>{nota:.1f}</div>", unsafe_allow_html=True)
            st.markdown("<p style='text-align:center; font-weight:bold;'>SCORE GERAL</p>", unsafe_allow_html=True)

    st.markdown("---")
    
    # Tabela
    st.subheader(f"📦 Histórico de Fornecimento ({total_itens} itens)")
    
    df_view = df_forn.sort_values('data_emissao', ascending=False).copy()
    
    if 'Risco_Compliance' in df_view.columns:
        df_view['Material'] = df_view.apply(
            lambda x: f"⚠️ {x['desc_prod']}" if x['Risco_Compliance'] else x['desc_prod'], axis=1
        )
    else:
        df_view['Material'] = df_view['desc_prod']
    
    df_view['Preço Unit.'] = df_view['v_unit_real'].apply(format_brl)
    df_view['Total'] = df_view['v_total_item'].apply(format_brl)
    
    cols = ['data_emissao', 'Material', 'qtd_real', 'un_real', 'Preço Unit.', 'Total', 'n_nf']
    if 'Numero_CA' in df_view.columns:
        cols.append('Numero_CA')
    
    st.dataframe(
        df_view[cols],
        column_config={
            "data_emissao": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "qtd_real": st.column_config.NumberColumn("Qtd.", format="%.2f"),
            "un_real": "Unid.",
            "Numero_CA": "C.A."
        },
        use_container_width=True,
        hide_index=True
    )
