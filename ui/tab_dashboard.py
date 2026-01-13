import streamlit as st
import plotly.express as px
from utils.formatters import format_brl

def render_tab_dashboard(df, df_final):
    total_spend = df['v_total_item'].sum()
    critico_spend = df_final[df_final['Categoria'].str.contains('CRÍTICO')]['Total_Gasto'].sum()
    saving_total = df_final['Saving_Potencial'].sum()

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Gasto Total", format_brl(total_spend))
    c2.metric("Fornecedores", df['cnpj_emit'].nunique())
    c3.metric("Risco", format_brl(critico_spend))
    c4.metric("Saving", format_brl(saving_total))

    st.markdown("---")
    col_abc_f, col_abc_m = st.columns(2)

    with col_abc_f:
        st.subheader("🏆 Top Fornecedores")
        top_f = df.groupby('nome_emit')['v_total_item'].sum().nlargest(10).reset_index()
        fig_pie_f = px.pie(top_f, values='v_total_item', names='nome_emit', hole=0.6)
        fig_pie_f.update_layout(height=300, separators=",.")
        fig_pie_f.update_traces(textinfo='percent+label', textposition='inside')
        st.plotly_chart(fig_pie_f, use_container_width=True)

    with col_abc_m:
        st.subheader("📦 Top Materiais")
        top_m = df_final.groupby('desc_prod')['Total_Gasto'].sum().nlargest(10).reset_index()
        fig_pie_m = px.pie(top_m, values='Total_Gasto', names='desc_prod', hole=0.6)
        fig_pie_m.update_layout(height=300, separators=",.")
        fig_pie_m.update_traces(textinfo='percent', textposition='inside')
        st.plotly_chart(fig_pie_m, use_container_width=True)
