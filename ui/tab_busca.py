import streamlit as st
import pandas as pd
from utils.formatters import format_brl

def render_tab_busca(df):
    st.markdown("### 🔍 Busca Avançada de Itens")
    st.caption("Pesquise em todo o histórico de compras (Base Completa).")

    # 1. FILTROS DE BUSCA
    c1, c2, c3 = st.columns([3, 1, 1])
    
    with c1:
        termo_busca = st.text_input("Digite o nome do produto, código ou aplicação:", placeholder="Ex: Rolamento, Parafuso, Luva...")
    
    with c2:
        # Filtro de Categoria (opcional)
        categorias = ["Todas"] + sorted(df['Categoria'].unique().tolist())
        cat_sel = st.selectbox("Categoria:", options=categorias)
        
    with c3:
        # Filtro de Fornecedor (opcional)
        fornecedores = ["Todos"] + sorted(df['nome_emit'].unique().tolist())
        forn_sel = st.selectbox("Fornecedor:", options=fornecedores)

    # 2. LÓGICA DE FILTRAGEM
    df_result = df.copy()

    if termo_busca:
        # Busca insensível a maiúsculas/minúsculas
        df_result = df_result[
            df_result['desc_prod'].str.contains(termo_busca, case=False, na=False) |
            df_result['cod_prod'].astype(str).str.contains(termo_busca, case=False, na=False)
        ]

    if cat_sel != "Todas":
        df_result = df_result[df_result['Categoria'] == cat_sel]

    if forn_sel != "Todos":
        df_result = df_result[df_result['nome_emit'] == forn_sel]

    # Se não houver resultados
    if df_result.empty:
        st.warning("Nenhum item encontrado com esses filtros.")
        return

    st.markdown(f"**Encontrados:** {len(df_result)} registros | **Volume Financeiro:** {format_brl(df_result['v_total_item'].sum())}")
    
    st.divider()

    # 3. VISÃO AGRUPADA (Resumo do Item)
    st.subheader("📦 Resumo por Item")
    
    # Define as chaves de agrupamento com segurança
    # Se 'cod_prod' estiver vazio ou zerado, agrupa só pela descrição
    group_cols = ['desc_prod', 'Categoria']
    if 'cod_prod' in df_result.columns:
        group_cols.append('cod_prod')

    # Agregação usando as NOVAS colunas (v_unit_real, qtd_real, u_medida)
    # Usamos a moda (valor mais comum) para a Unidade de Medida
    df_group = df_result.groupby(group_cols).agg(
        Preco_Medio=('v_unit_real', 'mean'),
        Preco_Min=('v_unit_real', 'min'),
        Preco_Max=('v_unit_real', 'max'),
        Qtd_Total=('qtd_real', 'sum'),
        Gasto_Total=('v_total_item', 'sum'),
        Qtd_Compras=('n_nf', 'count'),
        Unidade=('u_medida', lambda x: x.mode()[0] if not x.mode().empty else x.iloc[0])
    ).reset_index()

    # Formatação para exibição
    df_view = df_group.sort_values('Gasto_Total', ascending=False).copy()
    
    df_view['Preço Médio'] = df_view['Preco_Medio'].apply(format_brl)
    df_view['Menor Preço'] = df_view['Preco_Min'].apply(format_brl)
    df_view['Maior Preço'] = df_view['Preco_Max'].apply(format_brl)
    df_view['Total Gasto'] = df_view['Gasto_Total'].apply(format_brl)

    # Seleção de colunas finais
    cols_final = ['desc_prod', 'Categoria', 'Unidade', 'Qtd_Compras', 'Qtd_Total', 'Preço Médio', 'Menor Preço', 'Maior Preço', 'Total Gasto']
    if 'cod_prod' in df_view.columns:
        cols_final.insert(1, 'cod_prod')

    st.dataframe(
        df_view[cols_final],
        column_config={
            "desc_prod": "Descrição do Item",
            "cod_prod": "Cód.",
            "Qtd_Compras": st.column_config.NumberColumn("Freq.", format="%d"),
            "Qtd_Total": st.column_config.NumberColumn("Vol. Qtd", format="%.2f")
        },
        use_container_width=True,
        hide_index=True
    )

    # 4. DETALHE DOS REGISTROS (Tabela Completa)
    with st.expander("📝 Ver Detalhe de Todas as Compras (Histórico Completo)"):
        # Prepara tabela detalhada
        df_detalhe = df_result.sort_values('data_emissao', ascending=False).copy()
        
        # Formatações
        df_detalhe['Data'] = df_detalhe['data_emissao'].dt.strftime('%d/%m/%Y')
        df_detalhe['Preço Unit.'] = df_detalhe['v_unit_real'].apply(format_brl)
        df_detalhe['Total Item'] = df_detalhe['v_total_item'].apply(format_brl)
        
        # Colunas de exibição
        cols_detalhe = ['Data', 'nome_emit', 'n_nf', 'desc_prod', 'qtd_real', 'u_medida', 'Preço Unit.', 'Total Item']
        if 'cod_tributario' in df_detalhe.columns:
             cols_detalhe.append('cod_tributario')

        st.dataframe(
            df_detalhe[cols_detalhe],
            column_config={
                "nome_emit": "Fornecedor",
                "qtd_real": st.column_config.NumberColumn("Qtd", format="%.2f"),
                "u_medida": "Un.",
                "cod_tributario": "CST/CSOSN"
            },
            use_container_width=True,
            hide_index=True
        )
