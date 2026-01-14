import streamlit as st
import pandas as pd
import random
from utils.formatters import format_brl

def render_tab_fornecedores(df, df_final):
    st.markdown("### 📇 Gestão de Relacionamento (SRM)")
    
    # Verifica se os dados chegaram completos
    # Se isso aparecer, é porque o app_compras.py está correto
    st.caption(f"Base Total Disponível: {len(df)} transações (Histórico Completo)")

    # Search Box
    lista_f = df.groupby('nome_emit')['v_total_item'].sum().sort_values(ascending=False).index
    
    c1, _ = st.columns([1,2])
    with c1:
        forn_sel = st.selectbox("Pesquisar Fornecedor:", options=lista_f, index=None, placeholder="Digite para buscar...")

    st.divider()

    if not forn_sel:
        st.info("👆 Selecione um fornecedor acima.")
        return

    df_forn = df[df['nome_emit'] == forn_sel].copy()
    
    # Verifica Compliance
    qtd_risco = 0
    if 'Risco_Compliance' in df_forn.columns:
        riscos = df_forn[df_forn['Risco_Compliance'] == True]
        qtd_risco = len(riscos)
    
    # Score Simplificado para Teste
    nota = 8.5 # Placeholder se o cálculo falhar, mas vamos calcular:
    try:
        # Lógica de Score
        itens = df_forn['desc_prod'].unique()
        ref = df_final[df_final['desc_prod'].isin(itens)]
        if not ref.empty:
            comp = df_fornecedor_temp = df_forn.groupby('desc_prod')['v_unit_real'].mean().reset_index()
            comp = comp.merge(ref[['desc_prod', 'Menor_Preco']], on='desc_prod')
            nota = (comp['Menor_Preco'] / comp['v_unit_real']).mean() * 10
            nota = min(10, max(0, nota))
    except:
        pass

    # Layout Visual
    cor = "#d32f2f" if qtd_risco > 0 else "#388e3c"
    
    with st.container():
        st.markdown(f"""
            <div style="padding: 20px; border-left: 10px solid {cor}; background: #f8f9fa; border-radius: 5px;">
                <h2>🏢 {forn_sel}</h2>
                <p><strong>Total Gasto:</strong> {format_brl(df_forn['v_total_item'].sum())}</p>
                <p><strong>Última Compra:</strong> {df_forn['data_emissao'].max().strftime('%d/%m/%Y')}</p>
            </div>
        """, unsafe_allow_html=True)
        
        if qtd_risco > 0:
            st.error(f"⚠️ ALERTA: Encontrados {qtd_risco} itens de EPI sem Certificado de Aprovação (CA) na nota!")

    st.subheader("Histórico")
    
    # Tabela com destaque
    view = df_forn[['data_emissao', 'desc_prod', 'qtd_real', 'un_real', 'v_unit_real', 'n_nf', 'Numero_CA']].copy()
    
    # Se tiver risco, coloca um emoji no nome
    if 'Risco_Compliance' in df_forn.columns:
        mask = df_forn['Risco_Compliance'] == True
        view.loc[mask, 'desc_prod'] = "⚠️ " + view.loc[mask, 'desc_prod']

    st.dataframe(view, use_container_width=True, hide_index=True)
