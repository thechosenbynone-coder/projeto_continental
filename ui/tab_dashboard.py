import streamlit as st
import plotly.express as px
import pandas as pd
from utils.formatters import format_brl

def render_tab_dashboard(df, df_final):
    st.markdown("### 📊 Raio-X da Operação")
    st.caption("Visão detalhada de composição de gastos e tendências temporais.")

    # ===================================================
    # LINHA 1: ONDE ESTÁ O DINHEIRO? (TREEMAP)
    # ===================================================
    # O Treemap é excelente para mostrar hierarquia (Categoria > Produto)
    # Mostra instantaneamente onde está a maior "fatia" do orçamento.
    
    st.subheader("Mapa de Calor de Gastos (Hierarquia)")
    
    # Prepara dados para o Treemap
    # Agrupa por Categoria e Produto para criar a hierarquia
    df_tree = df.groupby(['Categoria', 'desc_prod']).agg(
        Total=('v_total_item', 'sum')
    ).reset_index()
    
    # Filtra para não poluir visualmente (apenas itens relevantes)
    # Mostra apenas produtos que representam algo relevante ou top 50
    df_tree = df_tree.sort_values('Total', ascending=False).head(50)

    fig_tree = px.treemap(
        df_tree, 
        path=[px.Constant("Gasto Total"), 'Categoria', 'desc_prod'], 
        values='Total',
        color='Categoria', # Colore por categoria para diferenciar
        color_discrete_sequence=px.colors.qualitative.Prism,
        hover_data={'Total':':.2f'}
    )
    
    fig_tree.update_traces(
        textinfo="label+value+percent parent", # Mostra nome, valor e % da categoria
        root_color="lightgrey"
    )
    fig_tree.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=450)
    st.plotly_chart(fig_tree, use_container_width=True)

    st.divider()

    # ===================================================
    # LINHA 2: QUANDO GASTAMOS? (EVOLUÇÃO TEMPORAL)
    # ===================================================
    col_time, col_pareto = st.columns([2, 1])

    with col_time:
        st.subheader("📅 Tendência Mensal de Gasto")
        
        # Agrupa por Mês
        df_monthly = df.groupby('mes_ano').agg(
            Gasto=('v_total_item', 'sum'),
            Qtd_Notas=('n_nf', 'count')
        ).reset_index()
        
        # Gráfico de Barras com Linha de Tendência (Média)
        fig_bar = px.bar(
            df_monthly, 
            x='mes_ano', 
            y='Gasto',
            text_auto='.2s', # Formata valor resumido (10k, 1M)
            title="Evolução do Budget Utilizado"
        )
        
        # Adiciona linha de média móvel ou média fixa para referência
        media_gasto = df_monthly['Gasto'].mean()
        fig_bar.add_hline(y=media_gasto, line_dash="dot", annotation_text="Média Mensal", annotation_position="top left", line_color="red")
        
        fig_bar.update_layout(xaxis_title="Mês", yaxis_title="Valor Gasto (R$)", separators=",.")
        fig_bar.update_traces(marker_color='#004280') # Cor corporativa
        st.plotly_chart(fig_bar, use_container_width=True)

    # ===================================================
    # LINHA 3: CURVA ABC (PARETO) - QUEM É RELEVANTE?
    # ===================================================
    with col_pareto:
        st.subheader("📈 Curva ABC (Materiais)")
        
        # Cálculo de Pareto
        df_abc = df_final.sort_values('Total_Gasto', ascending=False)
        df_abc['Acumulado'] = df_abc['Total_Gasto'].cumsum()
        df_abc['Perc_Acumulado'] = (df_abc['Acumulado'] / df_abc['Total_Gasto'].sum()) * 100
        
        # Classificação ABC
        def classificar_abc(perc):
            if perc <= 80: return 'A (80% Valor)'
            if perc <= 95: return 'B (15% Valor)'
            return 'C (5% Valor)'
            
        df_abc['Classe'] = df_abc['Perc_Acumulado'].apply(classificar_abc)
        
        # Resumo da Classe A
        qtd_a = df_abc[df_abc['Classe'].str.contains('A')].shape[0]
        total_itens = df_abc.shape[0]
        
        st.info(f"💡 **Insight:** Apenas **{qtd_a} itens** representam 80% de todo o gasto da empresa.")
        
        # Gráfico de Pizza simples da Classe ABC
        fig_abc = px.pie(
            df_abc, 
            names='Classe', 
            values='Total_Gasto',
            hole=0.4,
            color_discrete_sequence=['#004280', '#0073e6', '#99c2ff'] # Tons de azul
        )
        fig_abc.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300)
        st.plotly_chart(fig_abc, use_container_width=True)
