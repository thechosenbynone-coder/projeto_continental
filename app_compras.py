import streamlit as st
import pandas as pd
import sqlite3
import os
import re
import io
from difflib import SequenceMatcher
from unidecode import unidecode # Recomendado para remover acentos na comparação

# --- IMPORTS ---
from styles.theme import aplicar_tema
from utils.classifiers import classificar_materiais_turbo
from utils.formatters import format_brl
from utils.normalizer import normalizar_unidades_v1
from utils.compliance import validar_compliance 

# Imports das Abas
from ui.tab_exec_review import render_tab_exec_review
from ui.tab_dashboard import render_tab_dashboard
from ui.tab_fornecedores import render_tab_fornecedores
from ui.tab_negociacao import render_tab_negociacao
from ui.tab_busca import render_tab_busca
from ui.tab_compliance import render_tab_compliance

st.set_page_config(page_title="Portal de Inteligência em Suprimentos", page_icon="🏗️", layout="wide")
aplicar_tema()

# ==============================================================================
# 1. FUNÇÕES DE SUPORTE (INTELIGÊNCIA DE MATCH)
# ==============================================================================

def limpar_texto_match(texto):
    """
    Padroniza texto para comparação:
    - Remove acentos (Verão -> Verao)
    - Remove sufixos empresariais (LTDA, S.A)
    - Remove caracteres especiais
    """
    if not isinstance(texto, str): return str(texto)
    
    # Remove acentos
    texto = unidecode(texto).upper().strip()
    
    # Remove sufixos comuns que atrapalham o match
    sufixos = [' LTDA', ' S.A', ' SA', ' EIRELI', ' ME', ' EPP', ' COMERCIO', ' SERVICOS', ' INDUSTRIA', ' BRASIL']
    for s in sufixos:
        texto = texto.replace(s, '')
        
    # Mantém apenas letras e números
    return re.sub(r'[^A-Z0-9]', '', texto)

def calcular_similaridade(nome_xml, nome_excel):
    """
    Calcula se os nomes são compatíveis.
    Retorna Score de 0 a 100.
    """
    t_xml = limpar_texto_match(nome_xml)
    t_excel = limpar_texto_match(nome_excel)
    
    # 1. Match Exato pós-limpeza
    if t_xml == t_excel: return 100
    
    # 2. Match de Inclusão (ex: "JAP" está dentro de "JAP COMERCIAL")
    if t_excel in t_xml or t_xml in t_excel:
        return 95
        
    # 3. Similaridade de caracteres (Fuzzy)
    return SequenceMatcher(None, t_xml, t_excel).ratio() * 100

def carregar_arquivo_flexivel(uploaded_file):
    """Lê Excel ou CSV automaticamente."""
    try:
        if uploaded_file.name.lower().endswith('.csv'):
            # Tenta ler CSV (separa por vírgula ou ponto-e-vírgula)
            try:
                return pd.read_csv(uploaded_file, encoding='utf-8-sig') # Tenta UTF-8
            except:
                uploaded_file.seek(0)
                return pd.read_csv(uploaded_file, sep=';', encoding='latin1') # Tenta padrão Excel BR
        else:
            return pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"Erro ao ler arquivo: {e}")
        return None

# ==============================================================================
# 2. CARGA DE DADOS (XML - BANCO DE DADOS)
# ==============================================================================
@st.cache_data
def carregar_dados():
    if not os.path.exists("compras_suprimentos.db"): return pd.DataFrame()
    conn = sqlite3.connect("compras_suprimentos.db")
    df = pd.read_sql("SELECT * FROM base_compras", conn)
    conn.close()
    if df.empty: return pd.DataFrame()

    df['data_emissao'] = pd.to_datetime(df['data_emissao'])
    df['ano'] = df['data_emissao'].dt.year
    df['desc_prod'] = df['desc_prod'].astype(str).str.upper().str.strip()
    
    # Limpeza da NF do XML para cruzamento (Remove zeros à esquerda e não-numericos)
    df['n_nf_clean'] = df['n_nf'].astype(str).apply(lambda x: re.sub(r'\D', '', x).lstrip('0'))

    # Garante colunas de valor
    if 'v_total_item' not in df.columns: df['v_total_item'] = 0.0
    
    # Impostos
    for col in ['v_icms', 'v_ipi', 'v_pis', 'v_cofins']:
        if col not in df.columns: df[col] = 0.0
    df['Imposto_Total'] = df[['v_icms', 'v_ipi', 'v_pis', 'v_cofins']].sum(axis=1)

    df = normalizar_unidades_v1(df)
    df['Categoria'] = classificar_materiais_turbo(df)
    df = validar_compliance(df)
    
    return df

# ==============================================================================
# 3. ENRIQUECIMENTO DETETIVE (NF + NOME + VALOR)
# ==============================================================================
def enriquecer_dados_detetive(df_xml, df_mapa):
    """
    Cruza XML e Mapa usando lógica avançada de detetive.
    """
    try:
        # Normaliza colunas do Mapa (CSV/Excel)
        df_mapa.columns = [str(c).upper().strip() for c in df_mapa.columns]

        # --- 1. IDENTIFICAÇÃO DE COLUNAS ---
        mapa_cols = {'NF': None, 'FORNECEDOR': None, 'AF': None, 'CC': None, 'VALOR': None}
        
        sinonimos = {
            'NF': ['NF', 'NOTA', 'N_NF', 'NUMERO'],
            'FORNECEDOR': ['FORNECEDOR', 'NOME', 'EMPRESA'],
            'AF': ['AF/AS', 'AF', 'AS', 'PEDIDO', 'OC'],
            'CC': ['CC', 'CENTRO', 'CUSTO', 'PLANO DE CONTAS'], # Adicionei Plano de Contas como fallback
            'VALOR': ['VALOR', 'TOTAL', 'V.TOTAL', 'R$']
        }

        for chave, lista_nomes in sinonimos.items():
            for col_real in df_mapa.columns:
                if any(nome == col_real or nome in col_real for nome in lista_nomes):
                    # Prioridade exata
                    mapa_cols[chave] = col_real
                    break
        
        if not mapa_cols['NF']:
            st.error("❌ O arquivo precisa ter uma coluna de Nota Fiscal (NF).")
            return df_xml, []
            
        st.caption(f"Colunas Mapeadas: NF=[{mapa_cols['NF']}] | Forn=[{mapa_cols['FORNECEDOR']}] | AF=[{mapa_cols['AF']}] | CC=[{mapa_cols['CC']}]")

        # --- 2. PREPARAÇÃO DO MAPA ---
        # Cria chave limpa de NF no Mapa
        df_mapa['nf_key'] = df_mapa[mapa_cols['NF']].astype(str).apply(lambda x: re.sub(r'\D', '', x).lstrip('0'))
        
        # Cria dicionário indexado por NF (Otimização de Performance)
        # { '123': [ linha1, linha2 ] }
        dict_mapa = {}
        for idx, row in df_mapa.iterrows():
            nf = row['nf_key']
            if len(nf) > 0: # Ignora vazios
                if nf not in dict_mapa: dict_mapa[nf] = []
                dict_mapa[nf].append(row)

        # --- 3. LOOP DE DETETIVE ---
        af_list = []
        cc_list = []
        status_list = []

        total_matches = 0

        # Itera sobre cada NOTA FISCAL do XML (agrupado para não repetir processamento por item)
        # Mas precisamos preencher item a item, então iteramos o DF
        
        for idx, row_xml in df_xml.iterrows():
            nf_xml = row_xml['n_nf_clean']
            forn_xml = row_xml['nome_emit']
            valor_xml = row_xml['v_total_item'] # Valor do item (cuidado, o mapa costuma ter valor total da nota)
            
            # Busca candidatos com a mesma NF
            candidatos = dict_mapa.get(nf_xml, [])
            
            melhor_candidato = None
            melhor_score = 0
            
            if candidatos:
                for cand in candidatos:
                    score_atual = 0
                    
                    # A. Validação de Nome (Peso Alto)
                    if mapa_cols['FORNECEDOR']:
                        nome_mapa = str(cand[mapa_cols['FORNECEDOR']])
                        sim = calcular_similaridade(forn_xml, nome_mapa)
                        score_atual = sim # 0 a 100
                    else:
                        score_atual = 50 # Neutro
                    
                    # B. Validação de Valor (Desempate)
                    # Se o valor do item for igual ao valor da linha do mapa (raro, mas possível em serviços)
                    # Ou se não tivermos valor no mapa, ignoramos
                    
                    if score_atual > melhor_score:
                        melhor_score = score_atual
                        melhor_candidato = cand
            
            # --- DECISÃO FINAL ---
            # Aceitamos match se score > 45 (Nomes parecidos ou inclusos)
            # Ou se score > 0 e só tem 1 candidato na NF (Confiança na unicidade da NF)
            
            aceitar = False
            status = "Não Encontrado"
            
            if melhor_candidato is not None:
                if melhor_score > 60:
                    aceitar = True
                    status = "✅ Confirmado"
                elif len(candidatos) == 1 and melhor_score > 30: # Flexível para erros de digitação leves
                    aceitar = True
                    status = "⚠️ Aproximado"
                elif len(candidatos) == 1 and not mapa_cols['FORNECEDOR']: # Confiança cega na NF
                    aceitar = True
                    status = "⚠️ Só NF"

            val_af = "Não Mapeado"
            val_cc = "Não Mapeado"

            if aceitar:
                total_matches += 1
                if mapa_cols['AF']: val_af = str(melhor_candidato[mapa_cols['AF']])
                if mapa_cols['CC']: val_cc = str(melhor_candidato[mapa_cols['CC']])
                
                # Limpeza final dos valores
                if val_af == 'nan': val_af = "Não Mapeado"
                if val_cc == 'nan': val_cc = "Não Mapeado"

            af_list.append(val_af)
            cc_list.append(val_cc)
            status_list.append(status)

        df_xml['AF_MAPA'] = af_list
        df_xml['CC_MAPA'] = cc_list
        df_xml['STATUS_MATCH'] = status_list
        
        return df_xml, ['AF_MAPA', 'CC_MAPA', 'STATUS_MATCH'], total_matches

    except Exception as e:
        st.error(f"Erro no Detetive: {e}")
        return df_xml, [], 0

# ==============================================================================
# INTERFACE PRINCIPAL
# ==============================================================================

st.title("🏗️ Portal de Inteligência em Suprimentos")

df_full = carregar_dados()
if df_full.empty:
    st.error("Base XML vazia. Rode o extrator primeiro.")
    st.stop()

# --- SIDEBAR: UPLOAD DETETIVE ---
with st.sidebar:
    st.header("🕵️ Inteligência de Negócio")
    st.info("Carregue seus arquivos 'MAPA 2024.csv' e 'MAPA 2025.csv'.")
    
    # Upload Múltiplo (Para subir 2024 e 2025 de uma vez se quiser)
    uploaded_files = st.file_uploader("Carregar Mapas (CSV ou Excel)", type=["csv", "xlsx", "xls"], accept_multiple_files=True)
    
    cols_financeiras = []
    
    if uploaded_files:
        # Concatena todos os arquivos carregados em um único DataFrame Mestre
        df_mapa_mestre = pd.DataFrame()
        
        for file in uploaded_files:
            df_temp = carregar_arquivo_flexivel(file)
            if df_temp is not None:
                # Padroniza colunas antes de juntar
                df_temp.columns = [str(c).upper().strip() for c in df_temp.columns]
                df_mapa_mestre = pd.concat([df_mapa_mestre, df_temp], ignore_index=True)
        
        if not df_mapa_mestre.empty:
            st.success(f"{len(uploaded_files)} arquivos carregados. {len(df_mapa_mestre)} linhas de mapa.")
            
            if st.button("🚀 Processar Cruzamento"):
                with st.spinner("O Robô Detetive está analisando..."):
                    df_full, cols_financeiras, matches = enriquecer_dados_detetive(df_full, df_mapa_mestre)
                    
                    if matches > 0:
                        st.balloons()
                        st.success(f"Sucesso! {matches} linhas de compras foram vinculadas às suas AFs e Centros de Custo.")
                    else:
                        st.warning("Nenhum match encontrado. Verifique se os números das NFs nos CSVs batem com o XML.")

# --- DASHBOARD RÁPIDO DO EXCEL ---
if 'AF_MAPA' in df_full.columns:
    st.markdown("### 📊 Visão Estratégica (Dados Integrados)")
    
    df_match = df_full[df_full['AF_MAPA'] != 'Não Mapeado'].copy()
    
    if not df_match.empty:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.caption("Rateio por Centro de Custo")
            graf_cc = df_match.groupby('CC_MAPA')['v_total_item'].sum().sort_values(ascending=True)
            st.bar_chart(graf_cc, color="#2ecc71", horizontal=True)
        
        with c2:
            st.caption("Top 5 Pedidos (AFs)")
            graf_af = df_match.groupby('AF_MAPA')['v_total_item'].sum().sort_values(ascending=False).head(5)
            st.bar_chart(graf_af, color="#9b59b6", horizontal=True)
            
        with c3:
            st.caption("Qualidade do Cruzamento")
            st.metric("Itens Mapeados", f"{len(df_match)}", f"{len(df_match)/len(df_full)*100:.1f}% da base")
    
st.divider()

# --- RECALCULO GLOBAL PARA ABAS ---
group_cols = ['desc_prod', 'ncm', 'Categoria']
if 'AF_MAPA' in df_full.columns:
    group_cols.extend(['AF_MAPA', 'CC_MAPA'])

# Agrupamento Seguro (Prevenindo erros se colunas não existirem)
cols_existentes = [c for c in group_cols if c in df_full.columns]

df_grouped_full = df_full.groupby(cols_existentes).agg(
    Total_Gasto=('v_total_item', 'sum'),
    Qtd_Total=('qtd_real', 'sum'), 
    Menor_Preco=('v_unit_real', 'min') 
).reset_index()

# FUNÇÃO AUXILIAR DE FILTRO (Mantida)
def processar_filtro_ano(df_base, key_suffix):
    anos = sorted(df_base['ano'].unique(), reverse=True)
    c1, c2 = st.columns([1, 5])
    with c1: st.markdown("**Período:**")
    with c2:
        ano_sel = st.pills("Ano", options=anos, default=anos[0], label_visibility="collapsed", key=f"pills_{key_suffix}")
    
    if not ano_sel: ano_sel = anos[0]
    df_filtered = df_base[df_base['ano'] == ano_sel].copy()

    # Recalcula com colunas extras se existirem
    cols_agrup = ['desc_prod', 'ncm', 'Categoria']
    if 'AF_MAPA' in df_filtered.columns: cols_agrup.extend(['AF_MAPA', 'CC_MAPA'])
    cols_validas = [c for c in cols_agrup if c in df_filtered.columns]

    df_grouped = df_filtered.groupby(cols_validas).agg(
        Total_Gasto=('v_total_item', 'sum'),
        Qtd_Total=('qtd_real', 'sum'),
        Menor_Preco=('v_unit_real', 'min')
    ).reset_index()
    
    df_grouped['cod_prod'] = '' 

    df_last = (
        df_filtered.sort_values('data_emissao')
        .drop_duplicates(['desc_prod', 'ncm'], keep='last')
        [['desc_prod', 'ncm', 'v_unit_real', 'nome_emit', 'data_emissao']]
        .rename(columns={'v_unit_real': 'Ultimo_Preco', 'nome_emit': 'Ultimo_Forn', 'data_emissao': 'Ultima_Data'})
    )
    df_res = df_grouped.merge(df_last, on=['desc_prod', 'ncm'])
    df_res['Saving_Potencial'] = df_res['Total_Gasto'] - (df_res['Menor_Preco'] * df_res['Qtd_Total'])
    
    return df_filtered, df_res

# --- RENDERIZAÇÃO DAS ABAS ---
tabs = st.tabs(["📌 Visão Executiva", "📊 Dashboard", "🛡️ Compliance", "📇 Fornecedores", "💰 Cockpit", "🔍 Busca"])

with tabs[0]:
    df_t1, df_final_t1 = processar_filtro_ano(df_full, "tab1")
    render_tab_exec_review(df_t1, df_final_t1)

with tabs[1]:
    df_t2, df_final_t2 = processar_filtro_ano(df_full, "tab2")
    render_tab_dashboard(df_t2, df_final_t2)

with tabs[2]: render_tab_compliance(df_full)
with tabs[3]: render_tab_fornecedores(df_full, df_grouped_full)
with tabs[4]: render_tab_negociacao(df_full)
with tabs[5]: render_tab_busca(df_full)
