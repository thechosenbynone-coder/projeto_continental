import streamlit as st
import pandas as pd
from utils.formatters import format_brl

def render_tab_busca(df_full):
    # Importante: Recebemos df_full (Base Completa) e não a filtrada por ano.
    
    st.markdown("### 🔍 Banco de Preços (Histórico Completo)")
    st.caption("Pesquise em todo o histórico de compras da empresa, independente do ano fiscal.")

    # 1. BARRA DE PESQUISA (Começa vazia e limpa)
    c1, c2 = st.columns([3, 1])
    
    with c1:
        termo_busca = st.text_input(
            "O que você procura?", 
            value="", # Garante que comece vazio
            placeholder="Ex: Rolamento, Cimento, Luva..."
        )
        
    with c2:
        # Filtro de categoria opcional para refinar
        cats_disponiveis = sorted(df_full['Categoria'].unique())
        filtro_cat = st.selectbox("Filtrar Categoria (Opcional)", options=["Todas"] + cats_disponiveis)

    st.divider()

    # 2. LÓGICA DE BUSCA (Só roda se tiver termo ou filtro)
    if not termo_busca and filtro_cat == "Todas":
        st.info("👈 Digite algo acima para começar a pesquisar no banco de dados.")
        return

    # Filtra a base completa
    df_result = df_full.copy()
    
    # Filtro de Texto (Case insensitive)
    if termo_busca:
        mask_desc = df_result['desc_prod'].str.contains(termo_busca.upper())
        mask_cod = df_result['cod_prod'].str.contains(termo_busca.upper())
        df_result = df_result[mask_desc | mask_cod]
    
    # Filtro de Categoria
    if filtro_cat != "Todas":
        df_result = df_result[df_result['Categoria'] == filtro_cat]

    if df_result.empty:
        st.warning("Nenhum item encontrado com esses critérios.")
        return

    # 3. CONSTRUÇÃO DA TABELA INTELIGENTE
    # Agrupamos por Produto para tirar a média e achar o "Campeão"
    
    # Primeiro, achamos quem tem o menor preço para cada item (O "Melhor Fornecedor" por preço)
    idx_min_price = df_result.groupby('desc_prod')['v_unit'].idxmin()
    df_best_suppliers = df_result.loc[idx_min_price, ['desc_prod', 'nome_emit', 'v_unit', 'data_emissao']]
    df_best_suppliers.rename(columns={
        'nome_emit': 'Melhor Fornecedor', 
        'v_unit': 'Melhor Preço',
        'data_emissao': 'Data Ref.'
    }, inplace=True)

    # Agora agrupamos as estatísticas gerais
    df_view = df_result.groupby(['desc_prod', 'Categoria', 'cod_prod']).agg(
        Preco_Medio=('v_unit', 'mean'),
        Ultimo_Preco=('v_unit', 'last'), # Assume que o df já está ordenado por data no carregamento
        Qtd_Compras=('n_nf', 'count')
    ).reset_index()

    # Juntamos as duas informações
    df_view = df_view.merge(df_best_suppliers, on='desc_prod')

    # Limita resultados para não travar (Top 100 mais comprados)
    df_view = df_view.sort_values('Qtd_Compras', ascending=False).head(100)

    # Formatação Visual
    df_view['Preço Médio'] = df_view['Preco_Medio'].apply(format_brl)
    df_view['Melhor Preço'] = df_view['Melhor Preço'].apply(format_brl)
    
    # Seleção final de colunas
    cols_to_show = [
        'Categoria', 
        'desc_prod', 
        'Preço Médio', 
        'Melhor Fornecedor', 
        'Melhor Preço', 
        'Data Ref.',
        'Qtd_Compras'
    ]

    st.dataframe(
        df_view[cols_to_show],
        column_config={
            "desc_prod": "Descrição do Material",
            "Data Ref.": st.column_config.DateColumn("Melhor Compra em", format="DD/MM/YYYY"),
            "Qtd_Compras": st.column_config.NumberColumn("Freq.", help="Quantas vezes já compramos"),
            "Melhor Fornecedor": st.column_config.TextColumn("Melhor Fornecedor (Preço)", help="Fornecedor que praticou o menor preço histórico")
        },
        use_container_width=True,
        hide_index=True
    )
