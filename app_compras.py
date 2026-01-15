import streamlit as st
import pandas as pd
import sqlite3
import os
import re
import unicodedata
from difflib import SequenceMatcher

# --- IMPORTS ---
from styles.theme import aplicar_tema
from utils.classifiers import classificar_materiais_turbo
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
# 1) FUNÇÕES DE SUPORTE (LIMPEZA E MATCH)
# ==============================================================================

def remover_acentos(texto):
    if not isinstance(texto, str):
        return str(texto)
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join([c for c in nfkd if not unicodedata.combining(c)])

def limpar_texto_match(texto):
    if not isinstance(texto, str):
        return str(texto)
    texto = remover_acentos(texto).upper().strip()
    sufixos = [" LTDA", " S.A", " SA", " EIRELI", " ME", " EPP", " COMERCIO", " SERVICOS"]
    for s in sufixos:
        texto = texto.replace(s, "")
    return re.sub(r"[^A-Z0-9]", "", texto)

def limpar_nf_excel(valor):
    """Remove .0 e zeros à esquerda"""
    if pd.isna(valor) or valor == "":
        return ""
    s = str(valor).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return re.sub(r"\D", "", s).lstrip("0")

def calcular_similaridade(nome_xml, nome_excel):
    t_xml = limpar_texto_match(nome_xml)
    t_excel = limpar_texto_match(nome_excel)
    if t_xml == t_excel:
        return 100
    if t_excel in t_xml or t_xml in t_excel:
        return 95
    return SequenceMatcher(None, t_xml, t_excel).ratio() * 100

def carregar_arquivo_flexivel(uploaded_file):
    try:
        if uploaded_file.name.lower().endswith(".csv"):
            try:
                return pd.read_csv(uploaded_file, encoding="utf-8-sig", sep=None, engine="python")
            except Exception:
                uploaded_file.seek(0)
                return pd.read_csv(uploaded_file, sep=";", encoding="latin1")
        return pd.read_excel(uploaded_file)
    except Exception:
        return None

# ==============================================================================
# 2) CARGA DE DADOS
# ==============================================================================

@st.cache_data
def carregar_dados():
    if not os.path.exists("compras_suprimentos.db"):
        return pd.DataFrame()

    conn = sqlite3.connect("compras_suprimentos.db")
    df = pd.read_sql("SELECT * FROM base_compras", conn)
    conn.close()

    if df.empty:
        return pd.DataFrame()

    # Datas
    df["data_emissao"] = pd.to_datetime(df["data_emissao"], errors="coerce")
    df["ano"] = df["data_emissao"].dt.year
    df["mes_ano"] = df["data_emissao"].dt.strftime("%Y-%m")

    # Texto / NF
    df["desc_prod"] = df["desc_prod"].astype(str).str.upper().str.strip()
    df["n_nf_clean"] = df["n_nf"].astype(str).apply(limpar_nf_excel)

    # Colunas numéricas mínimas
    for col in ["v_total_item", "v_unit_real", "qtd_real"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Impostos (mantendo seu padrão)
    for col in ["v_icms", "v_ipi", "v_pis", "v_cofins"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["Imposto_Total"] = df[["v_icms", "v_ipi", "v_pis", "v_cofins"]].sum(axis=1)

    # Normalizações / classificações
    df = normalizar_unidades_v1(df)
    df["Categoria"] = classificar_materiais_turbo(df)
    df = validar_compliance(df)

    return df

# ==============================================================================
# 3) ENRIQUECIMENTO (DETETIVE)
# ==============================================================================

def enriquecer_dados_detetive(df_xml, df_mapa):
    try:
        df_mapa.columns = [str(c).upper().strip() for c in df_mapa.columns]

        mapa_cols = {"NF": None, "FORNECEDOR": None, "AF": None, "CC": None, "PLANO": None}
        sinonimos = {
            "NF": ["NF", "NOTA", "N_NF", "NUMERO"],
            "FORNECEDOR": ["FORNECEDOR", "NOME", "EMPRESA"],
            "AF": ["AF/AS", "AF", "AS", "PEDIDO", "OC"],
            "PLANO": ["PLANO DE CONTAS", "PLANO", "CONTA"],
            "CC": ["CC", "CENTRO", "CUSTO", "DEPARTAMENTO"],
        }

        for chave, lista_nomes in sinonimos.items():
            for col_real in df_mapa.columns:
                if any(nome == col_real or nome in col_real for nome in lista_nomes):
                    if chave == "CC" and "PLANO" in col_real:
                        continue
                    mapa_cols[chave] = col_real
                    break

        if not mapa_cols["NF"]:
            return df_xml, [], 0

        df_mapa["nf_key"] = df_mapa[mapa_cols["NF"]].apply(limpar_nf_excel)

        dict_mapa = {}
        for _, row in df_mapa.iterrows():
            nf = row["nf_key"]
            if nf:
                dict_mapa.setdefault(nf, []).append(row)

        af_list, cc_list, plano_list, status_list = [], [], [], []
        total_matches = 0

        for _, row_xml in df_xml.iterrows():
            nf_xml = row_xml["n_nf_clean"]
            forn_xml = row_xml["nome_emit"]

            candidatos = dict_mapa.get(nf_xml, [])
            melhor_candidato = None
            melhor_score = 0

            if candidatos:
                for cand in candidatos:
                    if mapa_cols["FORNECEDOR"]:
                        nome_mapa = str(cand[mapa_cols["FORNECEDOR"]])
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
                elif len(candidatos) == 1 and not mapa_cols["FORNECEDOR"]:
                    aceitar = True
                    status = "⚠️ Só NF"

            val_af = "Não Mapeado"
            val_cc = "Não Mapeado"
            val_plano = "Não Mapeado"

            if aceitar:
                total_matches += 1
                if mapa_cols["AF"]:
                    val_af = str(melhor_candidato[mapa_cols["AF"]])
                if mapa_cols["CC"]:
                    val_cc = str(melhor_candidato[mapa_cols["CC"]])
                if mapa_cols["PLANO"]:
                    val_plano = str(melhor_candidato[mapa_cols["PLANO"]])

                if str(val_af).lower() == "nan":
                    val_af = "Não Mapeado"
                if str(val_cc).lower() == "nan":
                    val_cc = "Não Mapeado"
                if str(val_plano).lower() == "nan":
                    val_plano = "Não Mapeado"

            af_list.append(val_af)
            cc_list.append(val_cc)
            plano_list.append(val_plano)
            status_list.append(status)

        df_xml["AF_MAPA"] = af_list
        df_xml["CC_MAPA"] = cc_list
        df_xml["PLANO_MAPA"] = plano_list
        df_xml["STATUS_MATCH"] = status_list

        return df_xml, ["AF_MAPA", "CC_MAPA", "PLANO_MAPA", "STATUS_MATCH"], total_matches

    except Exception as e:
        st.error(f"Erro no Detetive: {e}")
        return df_xml, [], 0

# ==============================================================================
# APP
# ==============================================================================

st.title("🏗️ Portal de Inteligência em Suprimentos")

df_full = carregar_dados()
if df_full.empty:
    st.error("Base vazia. Rode o extrator.")
    st.stop()

# Sidebar: mapas e processamento
with st.sidebar:
    st.header("🕵️ Inteligência de Negócio")
    uploaded_files = st.file_uploader(
        "Carregar Mapas (CSV/Excel)",
        type=["csv", "xlsx", "xls"],
        accept_multiple_files=True
    )

    if uploaded_files:
        df_mapa = pd.DataFrame()
        for file in uploaded_files:
            df_tmp = carregar_arquivo_flexivel(file)
            if df_tmp is not None:
                df_tmp.columns = [str(c).upper().strip() for c in df_tmp.columns]
                df_mapa = pd.concat([df_mapa, df_tmp], ignore_index=True)

        if not df_mapa.empty:
            st.success(f"{len(df_mapa)} linhas carregadas.")
            if st.button("🚀 Processar"):
                with st.spinner("Analisando..."):
                    df_full, _, matches = enriquecer_dados_detetive(df_full, df_mapa)
                    if matches > 0:
                        st.success(f"{matches} vínculos encontrados!")
                    else:
                        st.warning("Nenhum match encontrado.")

# Visão integrada (se houver mapeamento)
if "AF_MAPA" in df_full.columns:
    st.markdown("### 📊 Visão Integrada")
    df_m = df_full[df_full["AF_MAPA"] != "Não Mapeado"]
    if not df_m.empty:
        c1, c2, c3 = st.columns(3)
        # mantendo seu padrão atual (bar_chart simples)
        c1.bar_chart(df_m.groupby("CC_MAPA")["v_total_item"].sum(), horizontal=True)
        c2.bar_chart(df_m.groupby("PLANO_MAPA")["v_total_item"].sum(), horizontal=True)
        c3.metric("Cobertura", f"{(len(df_m) / len(df_full)) * 100:.1f}%")

st.divider()

# ==============================================================================
# PREPARAÇÃO DE DADOS (BENCHMARK HISTÓRICO GLOBAL + IMPACTO ANUAL)
# ==============================================================================

# 1) Filtro de ano (impacto anual)
anos = sorted(df_full["ano"].dropna().unique(), reverse=True)
ano_sel = st.pills("Ano", options=anos, default=anos[0], selection_mode="single")
if not ano_sel:
    ano_sel = anos[0]

df_ano = df_full[df_full["ano"] == ano_sel].copy()

# 2) Definição dinâmica das colunas de agrupamento
cols_agrup = ["desc_prod", "ncm", "Categoria"]
if "cod_prod" in df_full.columns:
    cols_agrup.append("cod_prod")
if "AF_MAPA" in df_full.columns:
    cols_agrup.extend(["AF_MAPA", "CC_MAPA", "PLANO_MAPA"])

cols_reais = [c for c in cols_agrup if c in df_full.columns]

# 3) Garantias de tipos
df_full["data_emissao"] = pd.to_datetime(df_full["data_emissao"], errors="coerce")
df_ano["data_emissao"] = pd.to_datetime(df_ano["data_emissao"], errors="coerce")

for c in ["v_total_item", "v_unit_real", "qtd_real"]:
    df_full[c] = pd.to_numeric(df_full[c], errors="coerce").fillna(0)
    df_ano[c] = pd.to_numeric(df_ano[c], errors="coerce").fillna(0)

# ------------------------------------------------------------------------------
# A) BENCHMARK HISTÓRICO GLOBAL (todos os anos)
#    Preco_Medio_Historico / Menor / Maior / Qtd_Compras_Hist
# ------------------------------------------------------------------------------
df_hist = (
    df_full.groupby(cols_reais, dropna=False)
    .agg(
        Preco_Medio_Historico=("v_unit_real", "mean"),
        Menor_Preco_Hist=("v_unit_real", "min"),
        Maior_Preco_Hist=("v_unit_real", "max"),
        Qtd_Compras_Hist=("v_unit_real", "count"),
    )
    .reset_index()
)

# ------------------------------------------------------------------------------
# B) ÚLTIMA COMPRA GLOBAL (mais recente no histórico inteiro)
#    Ultimo_Preco / Ultima_Data / Ultimo_Forn
# ------------------------------------------------------------------------------
df_full_sorted = df_full.sort_values("data_emissao")
df_last_global = (
    df_full_sorted.groupby(cols_reais, dropna=False)
    .tail(1)[cols_reais + ["v_unit_real", "data_emissao", "nome_emit", "qtd_real"]]
    .rename(
        columns={
            "v_unit_real": "Ultimo_Preco",
            "data_emissao": "Ultima_Data",
            "nome_emit": "Ultimo_Forn",
            "qtd_real": "Qtd_Ultima_Compra",
        }
    )
    .copy()
)

# ------------------------------------------------------------------------------
# C) IMPACTO NO ANO SELECIONADO (quantidade e gasto do ano)
# ------------------------------------------------------------------------------
df_impacto_ano = (
    df_ano.groupby(cols_reais, dropna=False)
    .agg(
        Total_Gasto_Ano=("v_total_item", "sum"),
        Qtd_Total_Ano=("qtd_real", "sum"),
        Qtd_Compras_Ano=("v_unit_real", "count"),
    )
    .reset_index()
)

# ------------------------------------------------------------------------------
# D) JUNTAR TUDO EM UM DF FINAL DE OPORTUNIDADES
# ------------------------------------------------------------------------------
df_grouped = df_impacto_ano.merge(df_hist, on=cols_reais, how="left")
df_grouped = df_grouped.merge(df_last_global, on=cols_reais, how="left")

# saneamento numérico
for c in [
    "Total_Gasto_Ano", "Qtd_Total_Ano", "Qtd_Compras_Ano",
    "Preco_Medio_Historico", "Menor_Preco_Hist", "Maior_Preco_Hist", "Qtd_Compras_Hist",
    "Ultimo_Preco", "Qtd_Ultima_Compra",
]:
    if c in df_grouped.columns:
        df_grouped[c] = pd.to_numeric(df_grouped[c], errors="coerce").fillna(0)

# ------------------------------------------------------------------------------
# E) CÁLCULO DO SAVING (se tivesse comprado ao preço médio histórico)
#    Comparando com o último preço (mais recente do histórico global)
#    Impacto medido pela quantidade do ANO selecionado
# ------------------------------------------------------------------------------
df_grouped["Saving_Equalizado"] = (
    (df_grouped["Ultimo_Preco"] - df_grouped["Preco_Medio_Historico"]) * df_grouped["Qtd_Total_Ano"]
)
df_grouped["Saving_Equalizado"] = df_grouped["Saving_Equalizado"].fillna(0).clip(lower=0)

# (Opcional) Saving idealizado, usando menor preço histórico
df_grouped["Saving_Potencial"] = (
    (df_grouped["Ultimo_Preco"] - df_grouped["Menor_Preco_Hist"]) * df_grouped["Qtd_Total_Ano"]
)
df_grouped["Saving_Potencial"] = df_grouped["Saving_Potencial"].fillna(0).clip(lower=0)

# Volatilidade histórica (ajuda a filtrar oportunidades reais)
df_grouped["Volatilidade_Hist"] = 0.0
mask = df_grouped["Menor_Preco_Hist"] > 0
df_grouped.loc[mask, "Volatilidade_Hist"] = (
    (df_grouped.loc[mask, "Maior_Preco_Hist"] - df_grouped.loc[mask, "Menor_Preco_Hist"])
    / df_grouped.loc[mask, "Menor_Preco_Hist"]
)

# ------------------------------------------------------------------------------
# F) Compatibilidade com abas existentes
#    Muitos lugares esperam colunas com nomes antigos (Total_Gasto / Qtd_Total / Menor_Preco etc).
#    Vamos criar aliases para não quebrar UI.
# ------------------------------------------------------------------------------
df_grouped["Total_Gasto"] = df_grouped["Total_Gasto_Ano"]
df_grouped["Qtd_Total"] = df_grouped["Qtd_Total_Ano"]
df_grouped["Menor_Preco"] = df_grouped["Menor_Preco_Hist"]
df_grouped["Maior_Preco"] = df_grouped["Maior_Preco_Hist"]
df_grouped["Qtd_Compras"] = df_grouped["Qtd_Compras_Ano"]

# ==============================================================================
# RENDERIZAÇÃO DAS ABAS
# ==============================================================================
tabs = st.tabs(["📌 Visão Executiva", "📊 Dashboard", "🛡️ Compliance", "📇 Fornecedores", "💰 Cockpit", "🔍 Busca"])

with tabs[0]:
    # df_ano = recorte do ano (visão do ano); df_grouped = oportunidades com benchmark global
    render_tab_exec_review(df_ano, df_grouped)

with tabs[1]:
    render_tab_dashboard(df_ano, df_grouped)

with tabs[2]:
    render_tab_compliance(df_full)

with tabs[3]:
    render_tab_fornecedores(df_full, df_grouped)

with tabs[4]:
    render_tab_negociacao(df_full)

with tabs[5]:
    render_tab_busca(df_full)
