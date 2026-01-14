import streamlit as st
import pandas as pd
from utils.formatters import format_brl

def render_tab_compliance(df_full):
    st.markdown("### 🛡️ Painel de Compliance e Governança")
    st.caption("Monitoramento de riscos regulatórios e documentais (Base Completa)")

    if 'Risco_Compliance' not in df_full.columns:
        st.info("Nenhum dado de compliance processado ainda.")
        return

    # Filtra apenas itens que FALHARAM na validação
    df_risco = df_full[df_full['Risco_Compliance'] == True].copy()
    df_criticos = df_full[df_full['Categoria'].str.contains('CRÍTICO|QUÍMICO|EPI|IÇAMENTO', na=False)].copy()

    # --- KPI CARDS ---
    c1, c2, c3, c4 = st.columns(4)
    
    total_gasto_risco = df_risco['v_total_item'].sum()
    qtd_itens_risco = len(df_risco)
    forn_irregulares = df_risco['nome_emit'].nunique()
    
    with c1:
        st.metric("Volume Financeiro em Risco", format_brl(total_gasto_risco))
    with c2:
        st.metric("Itens Irregulares", qtd_itens_risco)
    with c3:
        st.metric("Fornecedores Ofensores", forn_irregulares)
    with c4:
        total_critico = len(df_criticos)
        compliance_rate = ((total_critico - qtd_itens_risco) / total_critico * 100) if total_critico > 0 else 100
        st.metric("Índice de Conformidade", f"{compliance_rate:.1f}%")

    st.divider()

    # --- VISÃO 1: TOP OFENSORES ---
    c_chart, c_table = st.columns([1, 2])
    
    with c_chart:
        st.subheader("🚨 Risco por Categoria")
        if not df_risco.empty:
            risco_cat = df_risco['Categoria'].value_counts()
            st.bar_chart(risco_cat, color="#d32f2f")
        else:
            st.success("Nenhum risco detectado.")

    with c_table:
        st.subheader("📋 Top Fornecedores com Pendências")
        if not df_risco.empty:
            top_offenders = df_risco.groupby('nome_emit').agg(
                Itens_Irregulares=('desc_prod', 'count'),
                Valor_Risco=('v_total_item', 'sum'),
                Ultima_Infracao=('data_emissao', 'max')
            ).sort_values('Itens_Irregulares', ascending=False).head(10).reset_index()
            
            # Formatação manual antes de enviar para o dataframe para evitar erro de JSON
            top_offenders['Valor_Risco_Formatado'] = top_offenders['Valor_Risco'].apply(format_brl)
            top_offenders['Data_Formatada'] = top_offenders['Ultima_Infracao'].dt.strftime('%d/%m/%Y')
            
            # Garantir que max_value para a barra de progresso seja pelo menos 1
            max_pendencias = int(top_offenders['Itens_Irregulares'].max()) if not top_offenders.empty else 1

            st.dataframe(
                top_offenders[['nome_emit', 'Itens_Irregulares', 'Valor_Risco_Formatado', 'Data_Formatada']],
                column_config={
                    "nome_emit": "Fornecedor",
                    "Itens_Irregulares": st.column_config.ProgressColumn(
                        "Qtd. Pendências", 
                        format="%d", 
                        min_value=0, 
                        max_value=max_pendencias
                    ),
                    "Valor_Risco_Formatado": "Valor Total",
                    "Data_Formatada": "Última Ocorrência"
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.write("Sem pendências para listar.")

    st.markdown("---")

    # --- VISÃO 2: RELATÓRIO DE AÇÃO ---
    st.subheader("📝 Relatório de Ação (Itens para Regularização)")
    
    if not df_risco.empty:
        # Filtros
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filtro_cat = st.multiselect("Filtrar Categoria:", options=df_risco['Categoria'].unique(), key="f_cat")
        with col_f2:
            filtro_forn = st.multiselect("Filtrar Fornecedor:", options=df_risco['nome_emit'].unique(), key="f_forn")
            
        df_view = df_risco.copy()
        if filtro_cat: df_view = df_view[df_view['Categoria'].isin(filtro_cat)]
        if filtro_forn: df_view = df_view[df_view['nome_emit'].isin(filtro_forn)]
        
        # Limpeza de dados para o Dataframe (evita tipos não serializáveis)
        df_export = df_view[['data_emissao', 'nome_emit', 'n_nf', 'desc_prod', 'Categoria', 'v_unit_real']].copy()
        df_export['data_emissao'] = df_export['data_emissao'].dt.strftime('%d/%m/%Y')
        df_export['Valor'] = df_export['v_unit_real'].apply(format_brl)
        
        def definir_acao(cat):
            cat = str(cat)
            if 'EPI' in cat: return "Solicitar C.A. válido"
            if 'QUÍMICO' in cat: return "Solicitar FISPQ/Licença"
            if 'IÇAMENTO' in cat: return "Solicitar Certificado de Teste"
            return "Verificar Especificação"
            
        df_export['Ação Recomendada'] = df_export['Categoria'].apply(definir_acao)
        
        st.dataframe(
            df_export[['data_emissao', 'nome_emit', 'n_nf', 'desc_prod', 'Categoria', 'Ação Recomendada']],
            hide_index=True,
            use_container_width=True
        )
