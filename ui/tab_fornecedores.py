import streamlit as st
from utils.formatters import format_brl

def render_tab_fornecedores(df, df_final):
    st.markdown("##### 📇 Ficha do Fornecedor")
    lista_f = df.groupby('nome_emit')['v_total_item'].sum().sort_values(ascending=False).index
    
    if len(lista_f) > 0:
        forn_sel = st.selectbox("Selecione:", lista_f, index=0) 
        
        if forn_sel:
            stats = df[df['nome_emit'] == forn_sel]
            dados = stats.iloc[0]
            
            st.markdown(f"""
            <div class="card-fornecedor">
                <h3 style="margin:0;">🏢 {forn_sel}</h3>
                <p style="color:#666;">CNPJ: {dados['cnpj_emit']}</p>
                <hr>
                <h2>Volume Total: {format_brl(stats['v_total_item'].sum())}</h2>
            </div>
            """, unsafe_allow_html=True)

            view_forn = df_final[df_final['desc_prod'].isin(stats['desc_prod'].unique())].copy()
            view_forn['Total'] = view_forn['Total_Gasto'].apply(format_brl)
            st.dataframe(view_forn[['cod_prod', 'desc_prod', 'Categoria', 'Total']], hide_index=True, use_container_width=True)
    else:
        st.warning("Nenhum fornecedor encontrado no período selecionado.")
