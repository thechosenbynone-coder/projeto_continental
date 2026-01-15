import streamlit as st
import pandas as pd
from utils.formatters import format_brl, format_perc

def render_tab_negociacao(df):
    st.markdown("### 💰 Cockpit de Negociação & Savings")

    # DEFINE COLUNAS DE AGRUPAMENTO COM SEGURANÇA
    group_cols = ['desc_prod', 'Categoria']
    if 'cod_prod' in df.columns:
        group_cols.append('cod_prod')

    try:
        df_neg = df.groupby(group_cols).agg(
            Gasto_Total=('v_total_item', 'sum'),
            Qtd_Total=('qtd_real', 'sum'),
            Preco_Medio=('v_unit_real', 'mean'),
            Menor_Preco=('v_unit_real', 'min'),
            Maior_Preco=('v_unit_real', 'max'),
            Qtd_Compras=('n_nf', 'count')
        ).reset_index()
    except KeyError as e:
        st.error(f"Erro no agrupamento: {e}")
        return

    df_neg['Saving_Potencial'] = df_neg['Gasto_Total'] - (df_neg['Menor_Preco'] * df_neg['Qtd_Total'])
    
    # Volatilidade
    df_neg['Volatilidade'] = df_neg.apply(
        lambda x: (x['Maior_Preco'] - x['Menor_Preco']) / x['Menor_Preco'] if x['Menor_Preco'] > 0 else 0, axis=1
    )

    df_opps = df_neg[df_neg['Saving_Potencial'] > 10].sort_values('Saving_Potencial', ascending=False)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Potencial Economia", format_brl(df_opps['Saving_Potencial'].sum()))
    c2.metric("Oportunidades", len(df_opps))
    c3.metric("Volatilidade Média", f"{df_opps['Volatilidade'].mean()*100:.1f}%")

    st.subheader("🏆 Top Oportunidades")
    
    cols_show = ['desc_prod', 'Categoria', 'Qtd_Compras', 'Preco_Medio', 'Menor_Preco', 'Saving_Potencial']
    st.dataframe(df_opps[cols_show].head(50), use_container_width=True, hide_index=True)

    if not df_opps.empty:
        st.scatter_chart(df_opps, x='Volatilidade', y='Gasto_Total', color='Categoria', size='Saving_Potencial')
