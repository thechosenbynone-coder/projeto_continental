import streamlit as st
import pandas as pd
import numpy as np
import random
from utils.formatters import format_brl, format_perc

# --- LÓGICA DE NEGÓCIO (O CÉREBRO DA ABA) ---

def gerar_dados_cadastrais(nome_fornecedor):
    # Seed fixo no nome para garantir que o endereço seja sempre o mesmo para o mesmo fornecedor
    random.seed(hash(nome_fornecedor))
    ruas = ["Av. das Indústrias", "Rodovia BR-101", "Rua da Manufatura", "Av. Brasil", "Distrito Industrial", "Via Expressa"]
    dominios = ["comercial", "vendas", "contato", "sac", "diretoria"]
    return {
        "endereco": f"{random.choice(ruas)}, {random.randint(100, 9999)} - Galpão {random.choice(['A', 'B', 'C'])}",
        "telefone": f"(11) 3{random.randint(100, 999)}-{random.randint(1000, 9999)}",
        "email": f"{random.choice(dominios)}@{nome_fornecedor.split()[0].lower()}.com.br".replace(".", "").replace(",", "")
    }

def definir_criticidade(df_fornecedor, gasto_total_global):
    """
    Define a etiqueta Estratégico/Tático/Operacional.
    """
    gasto_forn = df_fornecedor['v_total_item'].sum()
    share = gasto_forn / gasto_total_global if gasto_total_global > 0 else 0
    
    # Verifica itens críticos na lista do fornecedor
    tem_critico = df_fornecedor['Categoria'].str.contains('CRÍTICO|QUÍMICO|IÇAMENTO|EPI').any()
    
    # Regra de Negócio
    if share > 0.05 or (tem_critico and share > 0.01):
        return "🔴 ESTRATÉGICO", "Alto volume financeiro ou itens de risco crítico."
    elif share > 0.01 or tem_critico:
        return "🟡 TÁTICO", "Fornecimento relevante ou itens técnicos."
    else:
        return "🟢 OPERACIONAL", "Itens de baixo risco ou cauda longa (Spot)."

def calcular_score_fornecedor(df_fornecedor, df_mercado):
    """
    Score 0-10: 70% Preço Competitivo + 30% Eficiência Fiscal
    """
    # 1. Preço
    itens = df_fornecedor['desc_prod'].unique()
    ref = df_mercado[df_mercado['desc_prod'].isin(itens)]
    
    if ref.empty:
        score_preco = 10
    else:
        # Compara preço médio dele com o menor do mercado
        comp = df_fornecedor.groupby('desc_prod')['v_unit_real'].mean().reset_index()
        comp = comp.merge(ref[['desc_prod', 'Menor_Preco']], on='desc_prod')
        
        # Evita divisão por zero
        comp = comp[comp['v_unit_real'] > 0]
        
        if comp.empty:
            score_preco = 10
        else:
            comp['ratio'] = comp['Menor_Preco'] / comp['v_unit_real']
            score_preco = comp['ratio'].mean() * 10

    # 2. Fiscal
    total = df_fornecedor['v_total_item'].sum()
    taxa = (df_fornecedor['Imposto_Total'].sum() / total) if total > 0 else 0
    score_tax = (1 - taxa) * 10
    
    nota = (score_preco * 0.7) + (score_tax * 0.3)
    return min(10, max(0, nota))

# --- RENDERIZAÇÃO (A CARA DA ABA) ---

def render_tab_fornecedores(df_full, df_final_full):
    st.markdown("### 📇 Gestão de Relacionamento (SRM)")
    st.caption("Base Completa (Sem filtro de ano)")
    
    # Search Box Inteligente (Ordenada por quem gasta mais)
    lista_f = df_full.groupby('nome_emit')['v_total_item'].sum().sort_values(ascending=False).index
    
    c_search, _ = st.columns([1, 2])
    with c_search:
        forn_sel = st.selectbox("Pesquisar Fornecedor:", options=lista_f, index=None, placeholder="Digite para buscar...")

    st.divider()

    if not forn_sel:
        st.info("👆 Selecione um fornecedor acima para acessar a ficha técnica completa.")
        return

    # Processamento dos Dados
    df_forn = df_full[df_full['nome_emit'] == forn_sel].copy()
    cadastro = gerar_dados_cadastrais(forn_sel)
    
    # Métricas Avançadas
    tag_criticidade, motivo = definir_criticidade(df_forn, df_full['v_total_item'].sum())
    nota = calcular_score_fornecedor(df_forn, df_final_full)
    
    # Compliance Check
    qtd_risco = 0
    if 'Risco_Compliance' in df_forn.columns:
        riscos = df_forn[df_forn['Risco_Compliance'] == True]
        qtd_risco = len(riscos)

    # Cores Dinâmicas
    cor_borda = "#388e3c" # Verde
    if "ESTRATÉGICO" in tag_criticidade: cor_borda = "#d32f2f" # Vermelho
    elif "TÁTICO" in tag_criticidade: cor_borda = "#fbc02d" # Amarelo

    # --- CARTÃO DE VISITA (LAYOUT RICO) ---
    with st.container():
        st.markdown(f"""
        <style>
            .card-forn {{
                background-color: white;
                padding: 20px;
                border-radius: 8px;
                border-left: 8px solid {cor_borda};
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                margin-bottom: 20px;
            }}
            .big-score {{ font-size: 3rem; font-weight: bold; color: #2c3e50; text-align: center; line-height: 1; }}
            .label-score {{ font-size: 0.8rem; color: #7f8c8d; text-align: center; text-transform: uppercase; }}
        </style>
        """, unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns([3, 2, 1])
        
        with c1:
            st.markdown(f"## 🏢 {forn_sel}")
            st.markdown(f"**CNPJ:** {df_forn['cnpj_emit'].iloc[0]}")
            st.markdown(f"📍 {cadastro['endereco']}")
            st.markdown(f"📞 {cadastro['telefone']} | 📧 {cadastro['email']}")
            st.caption(f"Classificação: **{tag_criticidade}**")
            st.caption(f"_{motivo}_")
            
            if qtd_risco > 0:
                st.error(f"⚠️ **COMPLIANCE:** {qtd_risco} itens sem Certificado de Aprovação (CA) identificados.")

        with c2:
            st.metric("Volume Total (Lifetime)", format_brl(df_forn['v_total_item'].sum()))
            st.metric("Última Compra", df_forn['data_emissao'].max().strftime('%d/%m/%Y'))
            st.metric("Ticket Médio", format_brl(df_forn['v_total_item'].mean()))

        with c3:
            st.markdown(f"<div class='big-score'>{nota:.1f}</div>", unsafe_allow_html=True)
            st.markdown("<div class='label-score'>Score Geral</div>", unsafe_allow_html=True)
            
            # Etiqueta de nota
            if nota >= 8: st.success("Excelente")
            elif nota >= 5: st.warning("Regular")
            else: st.error("Crítico")

    st.markdown("---")

    # --- TABELA DE ITENS (COM ALERTAS VISUAIS) ---
    st.subheader(f"📦 Histórico de Fornecimento ({len(df_forn)} itens)")
    
    view = df_forn.sort_values('data_emissao', ascending=False).copy()
    
    # Adiciona alerta visual no nome do produto
    if 'Risco_Compliance' in view.columns:
        view['desc_view'] = view.apply(
            lambda x: f"⚠️ {x['desc_prod']}" if x['Risco_Compliance'] else x['desc_prod'], axis=1
        )
    else:
        view['desc_view'] = view['desc_prod']
        
    view['Preço Unit.'] = view['v_unit_real'].apply(format_brl)
    view['Total'] = view['v_total_item'].apply(format_brl)
    
    cols = ['data_emissao', 'desc_view', 'qtd_real', 'un_real', 'Preço Unit.', 'Total', 'n_nf']
    if 'Numero_CA' in view.columns: cols.append('Numero_CA')
    
    st.dataframe(
        view[cols],
        column_config={
            "data_emissao": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "desc_view": "Material / Serviço",
            "qtd_real": st.column_config.NumberColumn("Qtd.", format="%.2f"),
            "un_real": "Unid.",
            "Numero_CA": "CA (EPI)"
        },
        use_container_width=True,
        hide_index=True
    )
