import streamlit as st
import plotly.express as px
from utils.formatters import format_brl, format_perc

def render_tab_exec_review(df, df_final):
    st.subheader("📌 Visão Executiva")
    
    total_spend = df['v_total_item'].sum()
    imposto_total = df['Imposto_Total'].sum()
    perc_imposto = imposto_total / total_spend if total_spend > 0 else 0
    saving_total = df_final['Saving_Potencial'].sum()
    critico_spend = df_final[df_final['Categoria'].str.contains('CRÍTICO')]['Total_Gasto'].sum()

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("💰 Gasto Total", format_brl(total_spend))
    c2.metric("💸 Imposto Total", format_brl(imposto_total))
    c3.metric("📊 Carga Tributária", format_perc(perc_imposto))
    c4.metric("🎯 Saving Potencial", format_brl(saving_total))
    c5.metric("⚠️ Gasto Crítico", format_brl(critico_spend))

    # Gráfico de Tendência
    df_trend = df.groupby('mes_ano').agg(Gasto=('v_total_item','sum'), Imposto=('Imposto_Total','sum')).reset_index()
    if not df_trend.empty:
        fig = px.line(df_trend, x='mes_ano', y=['Gasto','Imposto'], markers=True)
        fig.update_layout(height=300, separators=",.", yaxis_tickformat=".2f") 
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("🧾 Análise Tributária Detalhada"):
        col1, col2 = st.columns(2)
        with col1:
            # Correção para garantir que Categoria exista no merge
            df_cat_tax = df.merge(df_final[['desc_prod','Categoria']].drop_duplicates(), on='desc_prod', how='left', suffixes=('', '_y'))
            if 'Categoria_y' in df_cat_tax.columns:
                df_cat_tax['Categoria'] = df_cat_tax['Categoria_y'].fillna(df_cat_tax['Categoria'])
            
            df_cat_tax = df_cat_tax.groupby('Categoria').agg(Gasto=('v_total_item','sum'), Imposto=('Imposto_Total','sum')).reset_index()
            df_cat_tax['% Imposto'] = df_cat_tax['Imposto'] / df_cat_tax['Gasto']
            
            fig_cat = px.bar(df_cat_tax.sort_values('% Imposto'), x='% Imposto', y='Categoria', orientation='h', text_auto='.1%')
            fig_cat.update_layout(separators=",.")
            st.plotly_chart(fig_cat, use_container_width=True)

        with col2:
            df_forn_tax = df.groupby('nome_emit').agg(Gasto=('v_total_item','sum'), Imposto=('Imposto_Total','sum')).reset_index()
            df_forn_tax['% Imposto'] = df_forn_tax['Imposto'] / df_forn_tax['Gasto']
            view_tax = df_forn_tax.sort_values('% Imposto', ascending=False).head(10).copy()
            view_tax['Gasto'] = view_tax['Gasto'].apply(format_brl)
            view_tax['Imposto'] = view_tax['Imposto'].apply(format_brl)
            view_tax['% Imposto'] = view_tax['% Imposto'].apply(format_perc)
            st.dataframe(view_tax, use_container_width=True, hide_index=True)
