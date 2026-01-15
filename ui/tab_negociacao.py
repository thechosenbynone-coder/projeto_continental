import streamlit as st
import pandas as pd
from utils.formatters import format_brl, format_perc

def render_tab_negociacao(df):
    st.markdown("### 💰 Cockpit de Negociação & Savings")
    st.caption("Identificação de oportunidades baseada na dispersão de preços históricos.")

    # 1. CÁLCULO DE OPPORTUNITIES
    # O erro estava aqui: mudamos de 'v_unit' para 'v_unit_real' e 'qtd' para 'qtd_real'
    df_neg = df.groupby(['desc_prod', 'cod_prod', 'Categoria']).agg(
        Gasto_Total=('v_total_item', 'sum'),
        Qtd_Total=('qtd_real', 'sum'),          # <--- CORRIGIDO
        Preco_Medio=('v_unit_real', 'mean'),    # <--- CORRIGIDO
        Menor_Preco=('v_unit_real', 'min'),     # <--- CORRIGIDO
        Maior_Preco=('v_unit_real', 'max'),     # <--- CORRIGIDO
        Qtd_Compras=('n_nf', 'count')
    ).reset_index()

    # Cálculo do Dinheiro na Mesa (Saving Potencial)
    # Se tivéssemos comprado tudo pelo menor preço histórico, quanto teríamos gasto?
    df_neg['Gasto_Otimizado'] = df_neg['Menor_Preco'] * df_neg['Qtd_Total']
    df_neg['Saving_Potencial'] = df_neg['Gasto_Total'] - df_neg['Gasto_Otimizado']
    
    # Cálculo de Volatilidade ((Maior - Menor) / Menor)
    # Evita divisão por zero
    df_neg['Volatilidade'] = df_neg.apply(
        lambda x: (x['Maior_Preco'] - x['Menor_Preco']) / x['Menor_Preco'] if x['Menor_Preco'] > 0 else 0, 
        axis=1
    )

    # Ordena pelas maiores oportunidades
    df_opportunities = df_neg[df_neg['Saving_Potencial'] > 10].sort_values('Saving_Potencial', ascending=False)

    # --- KPIS DE TOPO ---
    total_saving_map = df_opportunities['Saving_Potencial'].sum()
    qtd_opps = len(df_opportunities)
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Potencial Total de Economia", format_brl(total_saving_map), help="Soma da diferença entre o preço pago e o menor preço histórico de cada item.")
    with c2:
        st.metric("Itens com Oportunidade", qtd_opps, help="Quantidade de itens que possuem variação de preço significativa.")
    with c3:
        # Volatilidade Média da Carteira
        vol_media = df_opportunities['Volatilidade'].mean() * 100 if not df_opportunities.empty else 0
        st.metric("Volatilidade Média de Preços", f"{vol_media:.1f}%")

    st.divider()

    # --- TABELA DE OPORTUNIDADES (PARETO) ---
    st.subheader("🏆 Top Oportunidades de Renegociação (Pareto)")
    
    # Formatação para exibição
    df_view = df_opportunities.head(50).copy()
    
    # Criando colunas visuais
    df_view['Econ. Potencial'] = df_view['Saving_Potencial'].apply(format_brl)
    df_view['Preço Médio'] = df_view['Preco_Medio'].apply(format_brl)
    df_view['Alvo (Menor)'] = df_view['Menor_Preco'].apply(format_brl)
    df_view['Var.%'] = (df_view['Volatilidade'] * 100).map('{:.1f}%'.format)

    st.dataframe(
        df_view[['desc_prod', 'Categoria', 'Qtd_Compras', 'Preço Médio', 'Alvo (Menor)', 'Var.%', 'Econ. Potencial']],
        column_config={
            "desc_prod": st.column_config.TextColumn("Item", width="large"),
            "Qtd_Compras": st.column_config.NumberColumn("Freq.", format="%d"),
            "Econ. Potencial": st.column_config.TextColumn("Saving Est.", width="medium") # Usando TextColumn para manter formatação BRL
        },
        use_container_width=True,
        hide_index=True
    )

    # --- DETALHE GRÁFICO (SCATTER PLOT) ---
    st.subheader("📊 Dispersão: Volatilidade x Gasto")
    st.caption("Itens no topo direito são os mais críticos (Alto Gasto + Alta Variação de Preço).")
    
    if not df_opportunities.empty:
        st.scatter_chart(
            df_opportunities,
            x='Volatilidade',
            y='Gasto_Total',
            color='Categoria',
            size='Saving_Potencial',
            use_container_width=True
        )
    else:
        st.info("Sem dados suficientes para gerar gráfico de dispersão.")
