import streamlit as st
from utils.formatters import format_brl

def render_tab_busca(df_final):
    st.markdown("##### 🔎 Pesquisa Geral")
    c1, c2 = st.columns([3,1])
    termo = c1.text_input("Buscar:", placeholder="Ex: Cimento, Parafuso...")
    
    cats_disp = df_final['Categoria'].unique() if not df_final.empty else []
    cat = c2.multiselect("Categoria:", cats_disp)

    if not df_final.empty:
        view = df_final.copy()
        if termo: 
            view = view[view['desc_prod'].str.contains(termo.upper()) | view['cod_prod'].str.contains(termo.upper())]
        if cat: 
            view = view[view['Categoria'].isin(cat)]

        view['Melhor Preço'] = view['Menor_Preco'].apply(format_brl)
        view['Último Pago'] = view['Ultimo_Preco'].apply(format_brl)
        view['Saving Estimado'] = view['Saving_Potencial'].apply(format_brl)

        st.dataframe(
            view[['Categoria', 'cod_prod', 'desc_prod', 'Melhor Preço', 'Último Pago', 'Saving Estimado', 'Ultimo_Forn', 'Ultima_Data']],
            column_config={"Ultima_Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY")},
            hide_index=True,
            use_container_width=True
        )
    else:
        st.warning("Nenhum dado encontrado.")
