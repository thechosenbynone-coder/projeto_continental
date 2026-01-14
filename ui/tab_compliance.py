import streamlit as st
import pandas as pd
from utils.formatters import format_brl

def render_tab_compliance(df_full):
    st.markdown("### 🛡️ Painel de Compliance e Governança")
    st.caption("Monitoramento de riscos regulatórios e documentais (Base Completa)")

    # 1. FILTRAGEM DE RISCOS
    # Pega tudo que é crítico OU tem risco de compliance marcado
    # Se 'Risco_Compliance' não existir (base nova), assume False
    if 'Risco_Compliance' not in df_full.columns:
        st.info("Nenhum dado de compliance processado ainda.")
        return

    # Filtra apenas itens que FALHARAM na validação (Ex: EPI sem CA)
    df_risco = df_full[df_full['Risco_Compliance'] == True].copy()
    
    # Filtra também itens CRÍTICOS (mesmo que estejam OK, é bom monitorar)
    df_criticos = df_full[df_full['Categoria'].str.contains('CRÍTICO|QUÍMICO|EPI|IÇAMENTO')].copy()

    # --- KPI CARDS ---
    c1, c2, c3, c4 = st.columns(4)
    
    total_gasto_risco = df_risco['v_total_item'].sum()
    qtd_itens_risco = len(df_risco)
    forn_irregulares = df_risco['nome_emit'].nunique()
    
    with c1:
        st.metric("Volume Financeiro em Risco", format_brl(total_gasto_risco), help="Total gasto em itens com pendência documental")
    with c2:
        st.metric("Itens Irregulares", qtd_itens_risco, help="Quantidade de linhas de nota fiscal com problema")
    with c3:
        st.metric("Fornecedores Ofensores", forn_irregulares, help="Quantos fornecedores entregaram itens fora do padrão")
    with c4:
        # Índice de Conformidade Geral (Baseado em itens críticos)
        total_critico = len(df_criticos)
        if total_critico > 0:
            compliance_rate = ((total_critico - qtd_itens_risco) / total_critico) * 100
            st.metric("Índice de Conformidade", f"{compliance_rate:.1f}%", delta_color="normal" if compliance_rate > 90 else "inverse")
        else:
            st.metric("Índice de Conformidade", "100%")

    st.divider()

    # --- VISÃO 1: TOP OFENSORES (QUEM COBRAR?) ---
    c_chart, c_table = st.columns([1, 2])
    
    with c_chart:
        st.subheader("🚨 Risco por Categoria")
        if not df_risco.empty:
            # Gráfico simples de barras
            risco_cat = df_risco['Categoria'].value_counts()
            st.bar_chart(risco_cat, color="#d32f2f")
        else:
            st.success("Tudo certo! Nenhum risco detectado.")

    with c_table:
        st.subheader("📋 Top Fornecedores com Pendências")
        if not df_risco.empty:
            # Agrupa por fornecedor para ver quem é o pior
            top_offenders = df_risco.groupby('nome_emit').agg(
                Itens_Irregulares=('desc_prod', 'count'),
                Valor_Risco=('v_total_item', 'sum'),
                Ultima_Infracao=('data_emissao', 'max')
            ).sort_values('Itens_Irregulares', ascending=False).head(10).reset_index()
            
            top_offenders['Valor_Risco'] = top_offenders['Valor_Risco'].apply(format_brl)
            top_offenders['Ultima_Infracao'] = top_offenders['Ultima_Infracao'].dt.strftime('%d/%m/%Y')
            
            st.dataframe(
                top_offenders,
                column_config={
                    "nome_emit": "Fornecedor",
                    "Itens_Irregulares": st.column_config.ProgressColumn("Qtd. Pendências", format="%d", min_value=0, max_value=top_offenders['Itens_Irregulares'].max()),
                    "Valor_Risco": "Valor Total",
                    "Ultima_Infracao": "Última Ocorrência"
                },
                hide_index=True,
                use_container_width=True
            )

    st.markdown("---")

    # --- VISÃO 2: RELATÓRIO DE AUDITORIA (O QUE COBRAR?) ---
    st.subheader("📝 Relatório de Ação (Itens para Regularização)")
    st.caption("Utilize esta lista para solicitar a documentação faltante (CA, FISPQ, Laudo) aos fornecedores.")
    
    if not df_risco.empty:
        # Filtros rápidos
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filtro_cat = st.multiselect("Filtrar Categoria:", options=df_risco['Categoria'].unique())
        with col_f2:
            filtro_forn = st.multiselect("Filtrar Fornecedor:", options=df_risco['nome_emit'].unique())
            
        df_view = df_risco.copy()
        if filtro_cat: df_view = df_view[df_view['Categoria'].isin(filtro_cat)]
        if filtro_forn: df_view = df_view[df_view['nome_emit'].isin(filtro_forn)]
        
        # Seleciona colunas úteis para o e-mail de cobrança
        df_export = df_view[['data_emissao', 'nome_emit', 'n_nf', 'cod_prod', 'desc_prod', 'Categoria', 'v_unit_real']].sort_values('data_emissao', ascending=False)
        
        # Formatação
        df_export['data_emissao'] = df_export['data_emissao'].dt.strftime('%d/%m/%Y')
        df_export['v_unit_real'] = df_export['v_unit_real'].apply(format_brl)
        
        # Adiciona coluna de "Ação Recomendada" baseada na categoria
        def definir_acao(cat):
            if 'EPI' in cat: return "Solicitar C.A. válido"
            if 'QUÍMICO' in cat: return "Solicitar FISPQ/Licença"
            if 'IÇAMENTO' in cat: return "Solicitar Certificado de Teste"
            return "Verificar Especificação"
            
        df_export['Ação Recomendada'] = df_export['Categoria'].apply(definir_acao)
        
        st.dataframe(
            df_export,
            column_config={
                "data_emissao": "Data Compra",
                "nome_emit": "Fornecedor",
                "n_nf": "NF",
                "desc_prod": "Descrição do Item",
                "Categoria": "Risco",
                "Ação Recomendada": st.column_config.TextColumn("Ação Necessária", width="medium")
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.balloons()
        st.success("Parabéns! Sua base não possui pendências de compliance detectadas.")
