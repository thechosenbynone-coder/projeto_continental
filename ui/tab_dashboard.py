import streamlit as st
import plotly.express as px
from utils.formatters import format_brl

def render_tab_dashboard(df, df_final):
    st.markdown("### 📊 Raio-X da Operação")
    st.caption("Visão detalhada de composição de gastos e tendências temporais.")

    c_sun, c_bar = st.columns([1, 2])
    
    with c_sun:
        st.subheader("Dispersão (Top 50)")
        df_sun = df.groupby(['Categoria', 'desc_prod']).agg(Total=('v_total_item', 'sum')).reset_index()
        df_sun = df_sun.sort_values('Total', ascending=False).head(50)
        
        fig_sun = px.sunburst(
            df_sun, path=['Categoria', 'desc_prod'], values='Total',
            color='Categoria', color_discrete_sequence=px.colors.qualitative.Prism
        )
        fig_sun.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=400)
        st.plotly_chart(fig_sun, use_container_width=True)

    with c_bar:
        st.subheader("Top 10 Produtos")
        top_itens = df_final.sort_values('Total_Gasto', ascending=False).head(10).copy()
        top_itens['Nome_Curto'] = top_itens['desc_prod'].apply(lambda x: x[:30] + '...' if len(x) > 30 else x)
        
        fig_bar_h = px.bar(
            top_itens.sort_values('Total_Gasto', ascending=True), 
            x='Total_Gasto', y='Nome_Curto', orientation='h',
            color='Total_Gasto', color_continuous_scale='Blues'
        )
        fig_bar_h.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig_bar_h, use_container_width=True)

    st.divider()
    
    st.subheader("📅 Tendência Mensal")
    df_monthly = df.groupby('mes_ano').agg(Gasto=('v_total_item', 'sum')).reset_index().sort_values('mes_ano')
    fig_trend = px.area(df_monthly, x='mes_ano', y='Gasto', markers=True)
    fig_trend.update_layout(height=350, yaxis_title="R$")
    st.plotly_chart(fig_trend, use_container_width=True)
