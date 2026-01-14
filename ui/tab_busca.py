import streamlit as st
import pandas as pd
from utils.formatters import format_brl

def render_tab_busca(df_full):
    # Importante: Recebemos df_full (Base Completa) com colunas normalizadas (v_unit_real)
    
    st.markdown("### 🔍 Banco de Preços (Histórico Completo)")
    st.caption("Pesquise em todo o histórico de compras da empresa. Preços normalizados (CX -> UN) para equalização.")

    # 1. BARRA DE PESQUISA (Começa vazia e limpa)
    c1, c2 = st.columns([3, 1])
    
    with c1:
        termo_busca = st.text_input(
            "O que você procura?", 
            value="", # Garante que comece vazio
            placeholder="Ex: Rolamento, Cimento, Luva..."
        )
        
    with c2:
        # Filtro de categoria
        if 'Categoria' in df_full.columns:
            cats_disponiveis = sorted(df_full['Categoria'].unique())
            filtro_cat = st.selectbox("Filtrar Categoria (Opcional)", options=["Todas"] + cats_disponiveis)
        else:
            filtro_cat = "Todas"

    st.divider()

    # 2. LÓGICA DE BUSCA (Só roda se tiver termo ou filtro)
    if not termo_busca and filtro_cat == "Todas":
        st.info("👈 Digite algo acima para começar a pesquisar no banco de dados.")
        return

    # Filtra a base completa
    df_result = df_full.copy()
    
    # Filtro de Texto (Case insensitive)
    if termo_busca:
        termo = termo_busca.upper().strip()
        mask_desc = df_result['desc_prod'].str.contains(termo)
        mask_cod = df_result['cod_prod'].str.contains(termo)
        df_result = df_result[mask_desc | mask_cod]
    
    # Filtro de Categoria
    if filtro_cat != "Todas":
        df_result = df_result[df_result['Categoria'] == filtro_cat]

    if df_result.empty:
        st.warning("Nenhum item encontrado com esses critérios.")
        return

    # 3. CONSTRUÇÃO DA TABELA INTELIGENTE (EQUALIZADA)
    
    # A) Achar o Melhor Fornecedor usando PREÇO REAL (Normalizado)
    # Isso evita que o fornecedor que vendeu 1 Unidade ganhe do que vendeu 1 Caixa (se a caixa for mais barata no unitário)
    idx_min_price = df_result.groupby('desc_prod')['v_unit_real'].idxmin()
    df_best = df_result.loc[idx_min_price, ['desc_prod', 'nome_emit', 'v_unit_real', 'data_emissao']]
    df_best.rename(columns={
        'nome_emit': 'Melhor Fornecedor', 
        'v_unit_real': 'Melhor Preço (Eq.)',
        'data_emissao': 'Data Ref.'
    }, inplace=True)

    # B) Estatísticas Gerais
    df_view = df_result.groupby(['desc_prod', 'Categoria', 'cod_prod']).agg(
        Preco_Medio=('v_unit_real', 'mean'), # Média do preço REAL (convertido)
        Ultimo_Preco=('v_unit_real', 'last'), # Último preço REAL
        Unidade_Padrao=('un_real', lambda x: x.mode()[0] if not x.mode().empty else 'UN'), # Unidade mais comum
        Qtd_Compras=('n_nf', 'count')
    ).reset_index()

    # C) Merge das Informações
    df_view = df_view.merge(df_best, on='desc_prod')

    # Limita resultados para performance (Top 100 mais frequentes)
    df_view = df_view.sort_values('Qtd_Compras', ascending=False).head(100)

    # D) Formatação Visual
    df_view['Preço Médio (Eq.)'] = df_view['Preco_Medio'].apply(format_brl)
    df_view['Melhor Preço (Eq.)'] = df_view['Melhor Preço (Eq.)'].apply(format_brl)
    
    # Seleção final de colunas
    cols_to_show = [
        'Categoria', 
        'desc_prod', 
        'Unidade_Padrao',
        'Preço Médio (Eq.)', 
        'Melhor Fornecedor', 
        'Melhor Preço (Eq.)', 
        'Data Ref.',
        'Qtd_Compras'
    ]

    st.dataframe(
        df_view[cols_to_show],
        column_config={
            "desc_prod": "Descrição do Material",
            "Unidade_Padrao": st.column_config.TextColumn("Unid.", help="Unidade normalizada (ex: CX virou UN)"),
            "Preço Médio (Eq.)": st.column_config.TextColumn("Preço Médio", help="Preço equalizado para a unidade padrão"),
            "Melhor Preço (Eq.)": st.column_config.TextColumn("Melhor Preço", help="Menor preço histórico encontrado (equalizado)"),
            "Data Ref.": st.column_config.DateColumn("Melhor Compra", format="DD/MM/YYYY"),
            "Qtd_Compras": st.column_config.NumberColumn("Freq.", help="Quantas vezes já compramos")
        },
        use_container_width=True,
        hide_index=True
    )
