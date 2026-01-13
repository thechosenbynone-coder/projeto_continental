import streamlit as st
import plotly.express as px
from utils.formatters import format_brl

def render_tab_negociacao(df):
    """
    Renderiza a aba de Cockpit de Negociação.
    Recebe o DataFrame principal (df) que JÁ DEVE TER a coluna 'Categoria'.
    """
    st.markdown("### 💰 Cockpit de Negociação")
    st.caption("Identificação de oportunidades baseada na volatilidade de preços.")

    # 1. PREPARAÇÃO (Agrupamento específico para esta visão)
    # Importante: O df recebido já deve ter passado pelo classificador no arquivo principal
    df_neg = df.groupby(['desc_prod', 'cod_prod', 'Categoria']).agg(
        Gasto_Total=('v_total_item', 'sum'),
        Qtd_Total=('qtd', 'sum'),
        Preco_Medio=('v_unit', 'mean'),
        Preco_Min=('v_unit', 'min'),
        Preco_Max=('v_unit', 'max'),
        Qtd_Compras=('n_nf', 'count')
    ).reset_index()

    if df_neg.empty:
        st.info("Nenhum dado disponível para análise de negociação.")
        return

    # Cálculos de Inteligência
    df_neg['Volatilidade_Preco'] = ((df_neg['Preco_Max'] - df_neg['Preco_Min']) / df_neg['Preco_Min']) * 100
    df_neg['Saving_Potencial'] = (df_neg['Preco_Medio'] - df_neg['Preco_Min']) * df_neg['Qtd_Total']

    # --- LAYOUT VISUAL ---
    col_matriz, col_kpis = st.columns([3, 1])

    with col_matriz:
        st.markdown("##### 🎯 Matriz de Ataque")
        df_plot = df_neg.fillna(0)
        fig_scatter = px.scatter(
            df_plot.sort_values('Gasto_Total', ascending=False).head(50),
            x='Gasto_Total', 
            y='Volatilidade_Preco',
            size='Saving_Potencial',
            color='Categoria',
            hover_name='desc_prod',
            log_x=True,
            height=400
        )
        fig_scatter.update_layout(
            xaxis_title="Volume Gasto (R$)",
            yaxis_title="Variação de Preço (%)",
            separators=",."
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    with col_kpis:
        st.markdown("##### 🚀 Oportunidades")
        top_saving = df_neg.sort_values('Saving_Potencial', ascending=False).head(3)
        for index, row in top_saving.iterrows():
            st.metric(
                label=f"{str(row['desc_prod'])[:15]}...",
                value=format_brl(row['Saving_Potencial']),
                delta=f"Var: {row['Volatilidade_Preco']:.1f}%"
            )

    st.divider()

    # Detalhe Tático
    st.markdown("##### 🕵️ Investigação Detalhada por Item")
    lista_ordenada = df_neg.sort_values('Saving_Potencial', ascending=False)['desc_prod'].unique()
    
    if len(lista_ordenada) > 0:
        item_investigar = st.selectbox("Selecione o material:", lista_ordenada)

        if item_investigar:
            df_hist = df[df['desc_prod'] == item_investigar].sort_values('data_emissao')
            
            c1, c2 = st.columns([2, 1])
            with c1:
                fig_line = px.line(df_hist, x='data_emissao', y='v_unit', markers=True, color='nome_emit')
                fig_line.update_layout(separators=",.", yaxis_tickformat=".2f")
                st.plotly_chart(fig_line, use_container_width=True)
                
            with c2:
                st.metric("Preço Mínimo Pago", format_brl(df_hist['v_unit'].min()))
                st.metric("Preço Máximo Pago", format_brl(df_hist['v_unit'].max()))
                
            view_hist = df_hist[['data_emissao', 'nome_emit', 'qtd', 'v_unit', 'v_total_item']].copy()
            view_hist['Unitário'] = view_hist['v_unit'].apply(format_brl)
            view_hist['Total'] = view_hist['v_total_item'].apply(format_brl)
            st.dataframe(view_hist, use_container_width=True, hide_index=True)
