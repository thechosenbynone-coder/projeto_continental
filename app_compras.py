import streamlit as st
import pandas as pd
import sqlite3
import os
import re
import io
import unicodedata 
from difflib import SequenceMatcher

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
# 1. FUNÇÕES DE SUPORTE (LIMPEZA E MATCH)
# ==============================================================================

def remover_acentos(texto):
    """Remove acentos de forma nativa."""
    if not isinstance(texto, str): return str(texto)
    nfkd = unicodedata.normalize('NFKD', texto)
    return "".join([c for c in nfkd if not unicodedata.combining(c)])

def limpar_texto_match(texto):
    """Padroniza texto para comparação (Upper, sem acento, sem sufixo)."""
    if not isinstance(texto, str): return str(texto)
    texto = remover_acentos(texto).upper().strip()
    sufixos = [' LTDA', ' S.A', ' SA', ' EIRELI', ' ME', ' EPP', ' COMERCIO', ' SERVICOS', ' INDUSTRIA', ' BRASIL']
    for s in sufixos:
        texto = texto.replace(s, '')
    return re.sub(r'[^A-Z0-9]', '', texto)

def limpar_nf_excel(valor):
    """
    CORREÇÃO CRÍTICA: Trata o erro de float do Excel (ex: 123.0 virar 1230).
    """
    if pd.isna(valor) or valor == '':
        return ""
    
    # Converte para string
    s = str(valor).strip()
    
    # Se terminar em .0, remove (ex: '102648.0' -> '102648')
    if s.endswith('.0'):
        s = s[:-2]
        
    # Remove tudo que não é dígito e zeros à esquerda
    s = re.sub(r'\D', '', s).lstrip('0')
    return s

def calcular_similaridade(nome_xml, nome_excel):
    """Score de 0 a 100."""
    t_xml = limpar_texto_match(nome_xml)
    t_excel = limpar_texto_match(nome_excel)
    if t_xml == t_excel: return 100
    if t_excel in t_xml or t_xml in t_excel: return 95
    return SequenceMatcher(None, t_xml, t_excel).ratio() * 100

def carregar_arquivo_flexivel(uploaded_file):
    """Lê Excel ou CSV (UTF-8 ou Latin1)."""
    try:
        if uploaded_file.name.lower().endswith('.csv'):
            try:
                # Tenta padrão universal
                return pd.read_csv(uploaded_file, encoding='utf-8-sig', sep=None, engine='python')
            except:
                # Tenta padrão Excel Brasileiro (ponto e vírgula, latin1)
                uploaded_file.seek(0)
                return pd.read_csv(uploaded_file, sep=';', encoding='latin1')
        else:
            return pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"Erro ao ler arquivo {uploaded_file.name}: {e}")
        return None

# ==============================================================================
# 2. CARGA DE DADOS (XML)
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
    # CORREÇÃO: Coluna Mes_Ano reintegrada
    df['mes_ano'] = df['data_emissao'].dt.strftime('%Y-%m')
    
    df['desc_prod'] = df['desc_prod'].astype(str).str.upper().str.strip()
    
    # Limpeza da NF do XML
    df['n_nf_clean'] = df['n_nf'].astype(str).apply(limpar_nf_excel)

    if 'v_total_item' not in df.columns: df['v_total_item'] = 0.0
    for col in ['v_icms', 'v_ipi', 'v_pis', 'v_cofins']:
        if col not in df.columns: df[col] = 0.0
    df['Imposto_Total'] = df[['v_icms', 'v_ipi', 'v_pis', 'v_cofins']].sum(axis=1)

    df = normalizar_unidades_v1(df)
    df['Categoria'] = classificar_materiais_turbo(df)
    df = validar_compliance(df)
    
    return df

# ==============================================================================
# 3. ENRIQUECIMENTO DETETIVE (CORRIGIDO)
# ==============================================================================
def enriquecer_dados_detetive(df_xml, df_mapa):
    try:
        df_mapa.columns = [str(c).upper().strip() for c in df_mapa.columns]

        # Mapeamento com PLANO DE CONTAS separado
        mapa_cols = {'NF': None, 'FORNECEDOR': None, 'AF': None, 'CC': None, 'PLANO': None}
        sinonimos = {
            'NF': ['NF', 'NOTA', 'N_NF', 'NUMERO'],
            'FORNECEDOR': ['FORNECEDOR', 'NOME', 'EMPRESA'],
            'AF': ['AF/AS', 'AF', 'AS', 'PEDIDO', 'OC'],
            'PLANO': ['PLANO DE CONTAS', 'PLANO', 'CONTA'],
            'CC': ['CC', 'CENTRO', 'CUSTO', 'DEPARTAMENTO']
        }

        # Identifica colunas
        for chave, lista_nomes in sinonimos.items():
            for col_real in df_mapa.columns:
                # Lógica: Se achou "PLANO DE CONTAS", não deixa o "CC" pegar ele depois
                if any(nome == col_real or nome in col_real for nome in lista_nomes):
                    if chave == 'CC' and 'PLANO' in col_real: continue # Evita confusão
                    mapa_cols[chave] = col_real
                    break
        
        if not mapa_cols['NF']:
            st.error("❌ Coluna NF não encontrada nos arquivos.")
            return df_xml, [], 0

        # Cria chave limpa com a CORREÇÃO DO FLOAT
        df_mapa['nf_key'] = df_mapa[mapa_cols['NF']].apply(limpar_nf_excel)
        
        # Dicionário Indexado
        dict_mapa = {}
        for idx, row in df_mapa.iterrows():
            nf = row['nf_key']
            if nf:
                if nf not in dict_mapa: dict_mapa[nf] = []
                dict_mapa[nf].append(row)

        # Loop de Cruzamento
        af_list = []
        cc_list = []
        plano_list = []
        status_list = []
        total_matches = 0

        for idx, row_xml in df_xml.iterrows():
            nf_xml = row_xml['n_nf_clean']
            forn_xml = row_xml['nome_emit']
            
            candidatos = dict_mapa.get(nf_xml, [])
            melhor_candidato = None
            melhor_score = 0
            
            if candidatos:
                for cand in candidatos:
                    score = 0
                    if mapa_cols['FORNECEDOR']:
                        nome_mapa = str(cand[mapa_cols['FORNECEDOR']])
                        score = calcular_similaridade(forn_xml, nome_mapa)
                    else:
                        score = 50 
                    
                    if score > melhor_score:
                        melhor_score = score
                        melhor_candidato = cand
            
            aceitar = False
            status = "Não Encontrado"
            
            if melhor_candidato is not None:
                if melhor_score > 60:
                    aceitar = True
                    status = "✅ Confirmado"
                elif len(candidatos) == 1 and melhor_score > 30:
                    aceitar = True
                    status = "⚠️ Aproximado"
                elif len(candidatos) == 1 and not mapa_cols['FORNECEDOR']:
                    aceitar = True
                    status = "⚠️ Só NF"

            val_af = "Não Mapeado"
            val_cc = "Não Mapeado"
            val_plano = "Não Mapeado"

            if aceitar:
                total_matches += 1
                if mapa_cols['AF']: val_af = str(melhor_candidato[mapa_cols['AF']])
                if mapa_cols['CC']: val_cc = str(melhor_candidato[mapa_cols['CC']])
                if mapa_cols['PLANO']: val_plano = str(melhor_candidato[mapa_cols['PLANO']])
                
                # Limpa 'nan' do pandas
                if val_af.lower() == 'nan': val_af = "Não Mapeado"
                if val_cc.lower() == 'nan': val_cc = "Não Mapeado"
                if val_plano.lower() == 'nan': val_plano = "Não Mapeado"

            af_list.append(val_af)
            cc_list.append(val_cc)
            plano_list.append(val_plano)
            status_list.append(status)

        df_xml['AF_MAPA'] = af_list
        df_xml['CC_MAPA'] = cc_list
        df_xml['PLANO_MAPA'] = plano_list
        df_xml['STATUS_MATCH'] = status_list
        
        cols_retorno = ['AF_MAPA', 'CC_MAPA', 'PLANO_MAPA', 'STATUS_MATCH']
        return df_xml, cols_retorno, total_matches

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

with st.sidebar:
    st.header("🕵️ Inteligência de Negócio")
    st.info("Suba os arquivos 'MAPA 2024' e 'MAPA 2025' juntos.")
    
    uploaded_files = st.file_uploader("Carregar Mapas (CSV/Excel)", type=["csv", "xlsx", "xls"], accept_multiple_files=True)
    
    if uploaded_files:
        df_mapa_mestre = pd.DataFrame()
        for file in uploaded_files:
            df_temp = carregar_arquivo_flexivel(file)
            if df_temp is not None:
                # Normaliza colunas antes de concatenar
                df_temp.columns = [str(c).upper().strip() for c in df_temp.columns]
                df_mapa_mestre = pd.concat([df_mapa_mestre, df_temp], ignore_index=True)
        
        if not df_mapa_mestre.empty:
            st.success(f"{len(df_mapa_mestre)} linhas carregadas.")
            if st.button("🚀 Processar Cruzamento"):
                with st.spinner("Analisando NFs, Nomes e Planos de Conta..."):
                    df_full, cols_fin, matches = enriquecer_dados_detetive(df_full, df_mapa_mestre)
                    if matches > 0:
                        st.balloons()
                        st.success(f"Sucesso! {matches} notas vinculadas.")
                    else:
                        st.warning("Nenhum match encontrado. Verifique se os CSVs estão corretos.")

# --- DASHBOARD DE ENRIQUECIMENTO ---
if 'AF_MAPA' in df_full.columns:
    st.markdown("### 📊 Visão Estratégica Integrada")
    df_match = df_full[df_full['AF_MAPA'] != 'Não Mapeado'].copy()
    
    if not df_match.empty:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.caption("Gasto por Centro de Custo")
            graf_cc = df_match.groupby('CC_MAPA')['v_total_item'].sum().sort_values(ascending=True)
            st.bar_chart(graf_cc, color="#2ecc71", horizontal=True)
        with c2:
            st.caption("Gasto por Plano de Contas")
            graf_pl = df_match.groupby('PLANO_MAPA')['v_total_item'].sum().sort_values(ascending=True)
            st.bar_chart(graf_pl, color="#3498db", horizontal=True)
        with c3:
            st.metric("Itens Mapeados", f"{len(df_match)}", f"{(len(df_match)/len(df_full))*100:.1f}% Cobertura")

st.divider()

# --- PREPARAÇÃO DE DADOS PARA ABAS ---
group_cols = ['desc_prod', 'ncm', 'Categoria']
if 'AF_MAPA' in df_full.columns:
    group_cols.extend(['AF_MAPA', 'CC_MAPA', 'PLANO_MAPA'])

cols_validas = [c for c in group_cols if c in df_full.columns]

# Agrupamento Global (Full)
df_grouped_full = df_full.groupby(cols_validas).agg(
    Total_Gasto=('v_total_item', 'sum'),
    Qtd_Total=('qtd_real', 'sum'), 
    Menor_Preco=('v_unit_real', 'min') 
).reset_index()

# FILTRO AUXILIAR
def processar_filtro_ano(df_base, key_suffix):
    anos = sorted(df_base['ano'].unique(), reverse=True)
    c1, c2 = st.columns([1, 5])
    with c1: st.markdown("**Período:**")
    with c2:
        ano_sel = st.pills("Ano", options=anos, default=anos[0], label_visibility="collapsed", key=f"pills_{key_suffix}")
    
    if not ano_sel: ano_sel = anos[0]
    df_filtered = df_base[df_base['ano'] == ano_sel].copy()

    # Agrupamento Filtrado
    cols_agrup = ['desc_prod', 'ncm', 'Categoria']
    if 'AF_MAPA' in df_filtered.columns: 
        cols_agrup.extend(['AF_MAPA', 'CC_MAPA', 'PLANO_MAPA'])
    cols_validas_filt = [c for c in cols_agrup if c in df_filtered.columns]

    df_grouped = df_filtered.groupby(cols_validas_filt).agg(
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

# --- ABAS ---
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
