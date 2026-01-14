import streamlit as st
import pandas as pd
import numpy as np
import random
from utils.formatters import format_brl, format_perc

# --- FUNÇÕES AUXILIARES (Lógica de Negócio do Fornecedor) ---

def gerar_dados_cadastrais(nome_fornecedor):
    """
    Gera dados de contato fictícios consistentes baseados no nome do fornecedor.
    (Para simular um CRM, já que o XML da NF não traz telefone/email).
    """
    # Usa o nome como 'seed' para que os dados sejam sempre os mesmos para o mesmo fornecedor
    random.seed(hash(nome_fornecedor))
    
    ruas = ["Av. das Indústrias", "Rodovia BR-101", "Rua da Manufatura", "Av. Brasil", "Distrito Industrial"]
    dominios = ["comercial", "vendas", "contato", "sac"]
    
    return {
        "endereco": f"{random.choice(ruas)}, {random.randint(100, 9999)} - Galpão {random.choice(['A', 'B', 'C'])}",
        "telefone": f"(11) 3{random.randint(100, 999)}-{random.randint(1000, 9999)}",
        "email": f"{random.choice(dominios)}@{nome_fornecedor.split()[0].lower()}.com.br".replace(".", "").replace(",", "")
    }

def calcular_score_fornecedor(df_fornecedor, df_mercado):
    """
    Calcula nota de 0 a 10 baseada em Competitividade de Preço e Impostos.
    """
    # 1. Score de Preço (Peso 70%)
    # Compara o preço médio do fornecedor com o MENOR preço de mercado para os mesmos itens
    itens_comuns = df_fornecedor['desc_prod'].unique()
    df_market_ref = df_mercado[df_mercado['desc_prod'].isin(itens_comuns)]
    
    if df_market_ref.empty:
        score_preco = 10 # Se for item exclusivo, ele é o rei.
    else:
        # Merge para comparar: Preço Médio DELE vs Preço Mínimo GERAL
        comparativo = df_fornecedor.groupby('desc_prod')['v_unit'].mean().reset_index()
        comparativo = comparativo.merge(df_market_ref[['desc_prod', 'Menor_Preco']], on='desc_prod')
        
        # Razão: Se ele cobra 100 e o mínimo é 80 -> Ratio 0.8. Se ele é o mínimo -> Ratio 1.0
        comparativo['ratio'] = comparativo['Menor_Preco'] / comparativo['v_unit']
        score_preco = comparativo['ratio'].mean() * 10

    # 2. Score Tributário (Peso 30%)
    # Quanto menor a carga tributária média, maior a nota (eficiência fiscal)
    taxa_media = (df_fornecedor['Imposto_Total'].sum() / df_fornecedor['v_total_item'].sum()) if df_fornecedor['v_total_item'].sum() > 0 else 0
    score_tax = (1 - taxa_media) * 10 # Ex: 30% imposto = nota 7.0
    
    nota_final = (score_preco * 0.7) + (score_tax * 0.3)
    return min(max(nota_final, 0), 10) # Garante entre 0 e 10

def definir_criticidade(df_fornecedor, gasto_total_global):
    """
    Define se é Estratégico, Tático ou Operacional.
    """
    gasto_fornecedor = df_fornecedor['v_total_item'].sum()
    share_wallet = gasto_fornecedor / gasto_total_global
    
    # Verifica se fornece itens críticos
    tem_critico = df_fornecedor['Categoria'].str.contains('CRÍTICO').any()
    
    if share_wallet > 0.10 or (tem_critico and share_wallet > 0.02):
        return "🔴 ESTRATÉGICO", "Alta dependência ou itens de risco."
    elif share_wallet > 0.05 or tem_critico:
        return "🟡 TÁTICO", "Volume relevante ou itens sensíveis."
    else:
        return "🟢 OPERACIONAL", "Fornecimento padrão."

# --- RENDERIZAÇÃO DA ABA ---

def render_tab_fornecedores(df, df_final):
    st.markdown("### 📇 Gestão de Relacionamento (SRM)")
    
    # 1. SEARCH BOX (Corrigido: Começa vazia)
    # Agrupa fornecedores e ordena por gasto (quem gasta mais aparece primeiro na lista)
    lista_f = df.groupby('nome_emit')['v_total_item'].sum().sort_values(ascending=False).index
    
    col_search, col_spacer = st.columns([1, 2])
    with col_search:
        forn_sel = st.selectbox(
            "Pesquisar Fornecedor:", 
            options=lista_f, 
            index=None, # <--- ISSO DEIXA A CAIXA VAZIA INICIALMENTE
            placeholder="Digite o nome ou selecione..."
        )

    st.divider()

    # Se nada selecionado, mostra mensagem ou visão geral
    if not forn_sel:
        st.info("👆 Selecione um fornecedor acima para acessar a ficha técnica completa.")
        return

    # --- PROCESSAMENTO DOS DADOS DO FORNECEDOR ---
    df_forn = df[df['nome_emit'] == forn_sel].copy()
    
    # Dados Cadastrais (Mock)
    cadastro = gerar_dados_cadastrais(forn_sel)
    cnpj = df_forn['cnpj_emit'].iloc[0]
    
    # Métricas
    total_gasto = df_forn['v_total_item'].sum()
    nota_score = calcular_score_fornecedor(df_forn, df_final)
    tag_criticidade, motivo_criticidade = definir_criticidade(df_forn, df['v_total_item'].sum())

    # --- LAYOUT DO CARTÃO DE VISITA (HEADER) ---
    with st.container():
        # Estilo CSS inline apenas para este bloco
        st.markdown(f"""
        <style>
            .header-forn {{
                background-color: white;
                padding: 20px;
                border-radius: 10px;
                border-left: 10px solid {'#d32f2f' if 'ESTRATÉGICO' in tag_criticidade else '#fbc02d' if 'TÁTICO' in tag_criticidade else '#388e3c'};
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .score-circle {{
                font-size: 2.5rem;
                font-weight: bold;
                color: #004280;
            }}
        </style>
        """, unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns([3, 2, 1])
        
        with c1:
            st.markdown(f"## 🏢 {forn_sel}")
            st.markdown(f"**CNPJ:** {cnpj}")
            st.markdown(f"📍 {cadastro['endereco']}")
            st.markdown(f"📞 {cadastro['telefone']} | 📧 {cadastro['email']}")
            st.caption(f"Classificação: **{tag_criticidade}** ({motivo_criticidade})")
            
        with c2:
            st.metric("Volume Total Negociado", format_brl(total_gasto))
            st.metric("Primeira Compra", df_forn['data_emissao'].min().strftime('%d/%m/%Y'))
            
        with c3:
            st.markdown("<p style='text-align:center'>Score do Fornecedor</p>", unsafe_allow_html=True)
            st.markdown(f"<div style='text-align:center; font-size: 3rem; font-weight:bold; color: #004280'>{nota_score:.1f}</div>", unsafe_allow_html=True)
            if nota_score >= 8:
                st.markdown("<p style='text-align:center; color:green'>Excelente</p>", unsafe_allow_html=True)
            elif nota_score >= 5:
                st.markdown("<p style='text-align:center; color:orange'>Regular</p>", unsafe_allow_html=True)
            else:
                st.markdown("<p style='text-align:center; color:red'>Atenção</p>", unsafe_allow_html=True)

    st.markdown("---")

    # --- HISTÓRICO DE ITENS (TABELA LIMPA) ---
    st.subheader(f"📦 Histórico de Fornecimento ({len(df_forn)} compras)")
    
    # Prepara tabela limpa
    # Agrupa por item para mostrar resumo, mas mantém detalhes da última compra
    df_history = df_forn.sort_values('data_emissao', ascending=False).copy()
    
    # Seleciona colunas úteis e renomeia
    tabela_view = df_history[[
        'data_emissao', 
        'desc_prod', 
        'v_unit', 
        'qtd', 
        'v_total_item', 
        'n_nf' # Número da Nota Fiscal é importante para rastreio
    ]].copy()
    
    # Formatação visual
    tabela_view['Preço Unit.'] = tabela_view['v_unit'].apply(format_brl)
    tabela_view['Total'] = tabela_view['v_total_item'].apply(format_brl)
    
    st.dataframe(
        tabela_view[['data_emissao', 'desc_prod', 'qtd', 'Preço Unit.', 'Total', 'n_nf']],
        column_config={
            "data_emissao": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "desc_prod": "Material / Serviço",
            "qtd": st.column_config.NumberColumn("Qtd.", format="%.2f"),
            "n_nf": "Nota Fiscal"
        },
        use_container_width=True,
        hide_index=True
    )
