import streamlit as st
import plotly.express as px
from utils.formatters import format_brl

def render_tab_dashboard(df, df_final):
    st.markdown("### 📊 Raio-X da Operação")
    st.caption("Visão detalhada de composição de gastos e tendências temporais.")

    # ===================================================
    # LINHA 1: HIERARQUIA VISUAL (SUNBURST - O SUBSTITUTO DO TREEMAP)
    # ===================================================
    # O Sunburst é mais "limpo" que o Treemap pois esconde rótulos pequenos automaticamente.
    # Ele permite clicar no centro para "mergulhar" nos dados (Drill-down).
    
    c_sun, c_bar = st.columns([1, 2])
    
    with c_sun:
        st.subheader("Dispersão por Categoria")
        st.caption("Clique nas fatias para expandir.")
        
        # Agrupa para o gráfico solar
        df_sun = df.groupby(['Categoria', 'desc_prod']).agg(Total=('v_total_item', 'sum')).reset_index()
        
        fig_sun = px.sunburst(
            df_sun,
            path=['Categoria', 'desc_prod'],
            values='Total',
            color='Categoria',
            color_discrete_sequence=px.colors.qualitative.Prism
        )
        fig_sun.update_traces(textinfo="label+percent parent")
        fig_sun.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=400)
        st.plotly_chart(fig_sun, use_container_width=True)

    # ===================================================
    # LINHA 2: O REI DA LEITURA (BARRAS HORIZONTAIS)
    # ===================================================
    with c_bar:
        st.subheader("Top 10 Produtos (Maior Gasto)")
        st.caption("Ranking absoluto dos itens mais representativos.")
        
        # Pega os Top 10 itens globais
        top_itens = df_final.sort_values('Total_Gasto', ascending=False).head(10).copy()
        
        # Truque para encurtar nomes gigantes no gráfico
        top_itens['Nome_Curto'] = top_itens['desc_prod'].apply(lambda x: x[:30] + '...' if len(x) > 30 else x)
        
        fig_bar_h = px.bar(
            top_itens.sort_values('Total_Gasto', ascending=True), # Ordena para o maior ficar em cima
            x='Total_Gasto',
            y='Nome_Curto',
            orientation='h', # Horizontal é melhor para ler no celular
            text='Total_Gasto',
            color='Total_Gasto',
            color_continuous_scale='Blues'
        )
        
        fig_bar_h.update_traces(texttemplate='%{text:.2s}', textposition='outside')
        fig_bar_h.update_layout(
            yaxis_title=None, 
            xaxis_title=None, 
            showlegend=False,
            height=400,
            margin=dict(l=0, r=0, t=0, b=0)
        )
        st.plotly_chart(fig_bar_h, use_container_width=True)

    st.divider()

    # ===================================================
    # LINHA 3: TENDÊNCIA E PARETO (MANTIDOS POIS SÃO BONS)
    # ===================================================
    col_time, col_pareto = st.columns([2, 1])

    with col_time:
        st.subheader("📅 Tendência Mensal")
        df_monthly = df.groupby('mes_ano').agg(Gasto=('v_total_item', 'sum')).reset_index()
        
        fig_trend = px.area( # Área fica mais bonito que barra para tendência
            df_monthly, 
            x='mes_ano', 
            y='Gasto',
            markers=True
        )
        fig_trend.update_traces(line_color='#004280', fill_color='rgba(0, 66, 128, 0.1)')
        fig_trend.update_layout(height=350, margin=dict(l=0, r=0, t=20, b=0), yaxis_title="R$")
        st.plotly_chart(fig_trend, use_container_width=True)

    with col_pareto:
        st.subheader("📊 Classificação ABC")
        
        # Recalcula Pareto
        df_abc = df_final.sort_values('Total_Gasto', ascending=False)
        df_abc['Acumulado'] = df_abc['Total_Gasto'].cumsum()
        total = df_abc['Total_Gasto'].sum()
        
        # Separa Classe A (80%)
        classe_a = df_abc[df_abc['Acumulado'] <= total * 0.80]
        qtd_a = len(classe_a)
        
        st.metric("Itens Classe A", f"{qtd_a}", delta="Representam 80% do Gasto")
        st.progress(0.80) # Barra de progresso visual
        st.caption("Foque sua negociação nestes itens.")
