import streamlit as st
import pandas as pd
import sqlite3
import os
import re
import unicodedata
from difflib import SequenceMatcher

from styles.theme import aplicar_tema
from utils.classifiers import classificar_materiais_turbo
from utils.normalizer import normalizar_unidades_v1
from utils.compliance import validar_compliance

from ui.tab_exec_review import render_tab_exec_review
from ui.tab_fornecedores import render_tab_fornecedores
from ui.tab_negociacao import render_tab_negociacao
from ui.tab_busca import render_tab_busca
from ui.tab_compliance import render_tab_compliance

st.set_page_config(page_title="Portal de Inteligência em Suprimentos", page_icon="🏗️", layout="wide")
aplicar_tema()

# =========================
# Helpers
# =========================

def _db_mtime(path="compras_suprimentos.db") -> float:
    try:
        return os.path.getmtime(path)
    except Exception:
        return 0.0

def limpar_nf_excel(valor):
    if pd.isna(valor) or valor == "":
        return ""
    s = str(valor).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return re.sub(r"\D", "", s).lstrip("0")

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

# =========================
# Load base (limit columns to reduce RAM)
# =========================

@st.cache_data(show_spinner=False)
def carregar_dados(_db_stamp: float) -> pd.DataFrame:
    if not os.path.exists("compras_suprimentos.db"):
        return pd.DataFrame()

    conn = sqlite3.connect("compras_suprimentos.db")

    # 🔥 IMPORTANT: read only what app needs to start
    # (other tabs can still work with this set; if any needs extra, we add later)
    cols = [
        "data_emissao", "n_nf", "nome_emit", "desc_prod", "ncm", "cod_prod",
        "v_total_item", "v_unit_real", "qtd_real",
        "v_icms", "v_ipi", "v_pis", "v_cofins"
    ]

    # Build SELECT safely: keep only columns that exist
    # SQLite pragma table_info
    info = pd.read_sql("PRAGMA table_info(base_compras)", conn)
    existing = set(info["name"].tolist())
    cols_ok = [c for c in cols if c in existing]

    if not cols_ok:
        # fallback
        df = pd.read_sql("SELECT * FROM base_compras", conn)
    else:
        df = pd.read_sql(f"SELECT {', '.join(cols_ok)} FROM base_compras", conn)

    conn.close()

    if df.empty:
        return pd.DataFrame()

    # core transforms
    df["data_emissao"] = pd.to_datetime(df.get("data_emissao"), errors="coerce")
    df["ano"] = df["data_emissao"].dt.year
    df["mes_ano"] = df["data_emissao"].dt.strftime("%Y-%m")

    if "desc_prod" in df.columns:
        df["desc_prod"] = df["desc_prod"].astype(str).str.upper().str.strip()
    if "n_nf" in df.columns:
        df["n_nf_clean"] = df["n_nf"].astype(str).apply(limpar_nf_excel)
    else:
        df["n_nf_clean"] = ""

    for col in ["v_total_item", "v_unit_real", "qtd_real"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    for col in ["v_icms", "v_ipi", "v_pis", "v_cofins"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["Imposto_Total"] = df[["v_icms", "v_ipi", "v_pis", "v_cofins"]].sum(axis=1)

    # keep your pipeline
    df = normalizar_unidades_v1(df)
    df["Categoria"] = classificar_materiais_turbo(df)
    df = validar_compliance(df)

    # reduce RAM
    for c in ["nome_emit", "Categoria", "ncm", "cod_prod", "desc_prod", "mes_ano", "ano"]:
        if c in df.columns:
            try:
                df[c] = df[c].astype("category")
            except Exception:
                pass

    return df

# =========================
# Detetive (optional)
# =========================

def enriquecer_dados_detetive(df_xml: pd.DataFrame, df_mapa: pd.DataFrame):
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

        df_xml = df_xml.copy()
        if "n_nf_clean" not in df_xml.columns:
            df_xml["n_nf_clean"] = df_xml.get("n_nf", "").astype(str).apply(limpar_nf_excel)
        if "nome_emit" not in df_xml.columns:
            df_xml["nome_emit"] = "N/D"

        af_list, cc_list, plano_list, status_list = [], [], [], []
        total_matches = 0

        for _, row_xml in df_xml.iterrows():
            nf_xml = row_xml["n_nf_clean"]
            forn_xml = row_xml["nome_emit"]

            candidatos = dict_mapa.get(nf_xml, [])
            melhor_candidato = None
            melhor_score = 0

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
        st.exception(e)
        return df_xml, [], 0

# =========================
# Fast year aggregation (always safe)
# =========================

@st.cache_data(show_spinner=False)
def agg_ano(_db_stamp: float, data_version: int, ano_sel: int, cols_ano: tuple, df_full_work: pd.DataFrame):
    keys = list(cols_ano)
    df_ano = df_full_work[df_full_work["ano"] == ano_sel].copy()

    df_impacto = (
        df_ano.groupby(keys, dropna=False, observed=False)
        .agg(
            Total_Gasto_Ano=("v_total_item", "sum"),
            Qtd_Total_Ano=("qtd_real", "sum"),
            Qtd_Compras_Ano=("v_unit_real", "count"),
        )
        .reset_index()
    )
    return df_ano, df_impacto

# =========================
# Heavy global benchmark (ON DEMAND)
# =========================

@st.cache_data(show_spinner=False)
def benchmark_global(_db_stamp: float, data_version: int, item_key: str, df_full_work: pd.DataFrame):
    """
    Benchmark global por item_key (bem mais leve que usar várias chaves).
    """
    if item_key not in df_full_work.columns:
        raise ValueError(f"Coluna item_key '{item_key}' não existe na base.")

    base = df_full_work.dropna(subset=["data_emissao"]).copy()

    # stats por item (reduz cardinalidade e RAM)
    hist = (
        df_full_work.groupby([item_key], dropna=False, observed=False)
        .agg(
            Preco_Medio_Historico=("v_unit_real", "mean"),
            Menor_Preco_Hist=("v_unit_real", "min"),
            Maior_Preco_Hist=("v_unit_real", "max"),
            Qtd_Compras_Hist=("v_unit_real", "count"),
        )
        .reset_index()
    )

    if base.empty:
        last = hist[[item_key]].copy()
        last["Ultimo_Preco"] = 0.0
        last["Ultima_Data"] = pd.NaT
        last["Ultimo_Forn"] = ""
        return hist, last

    idx = base.groupby([item_key], dropna=False, observed=False)["data_emissao"].idxmax()
    last = base.loc[idx, [item_key, "v_unit_real", "data_emissao", "nome_emit"]].copy()
    last = last.rename(
        columns={
            "v_unit_real": "Ultimo_Preco",
            "data_emissao": "Ultima_Data",
            "nome_emit": "Ultimo_Forn",
        }
    )

    return hist, last

# =========================
# APP
# =========================

st.title("🏗️ Portal de Inteligência em Suprimentos")

db_stamp = _db_mtime()
df_full = carregar_dados(db_stamp)

if df_full.empty:
    st.error("Base vazia. Rode o extrator.")
    st.stop()

# dataset de trabalho
if "df_full_work" not in st.session_state:
    st.session_state.df_full_work = df_full.copy()
if "data_version" not in st.session_state:
    st.session_state.data_version = 0
if "last_db_stamp" not in st.session_state:
    st.session_state.last_db_stamp = db_stamp

if st.session_state.last_db_stamp != db_stamp:
    st.session_state.df_full_work = df_full.copy()
    st.session_state.data_version += 1
    st.session_state.last_db_stamp = db_stamp

df_full_work = st.session_state.df_full_work

with st.sidebar:
    st.header("⚙️ Performance")
    st.caption("No Cloud, histórico global pesado pode matar o processo. Aqui ele roda sob demanda.")
    calc_global = st.button("🧠 Calcular histórico global agora (benchmark)")

    st.header("🕵️ Inteligência de Negócio")
    uploaded_files = st.file_uploader("Carregar Mapas (CSV/Excel)", type=["csv", "xlsx", "xls"], accept_multiple_files=True)

    if uploaded_files:
        df_mapa = pd.DataFrame()
        for file in uploaded_files:
            df_tmp = carregar_arquivo_flexivel(file)
            if df_tmp is not None:
                df_tmp.columns = [str(c).upper().strip() for c in df_tmp.columns]
                df_mapa = pd.concat([df_mapa, df_tmp], ignore_index=True)

        if not df_mapa.empty:
            st.success(f"{len(df_mapa)} linhas carregadas.")
            if st.button("🚀 Processar Detetive"):
                with st.spinner("Executando Detetive..."):
                    df_enriched, _, matches = enriquecer_dados_detetive(df_full_work, df_mapa)
                    st.session_state.df_full_work = df_enriched
                    st.session_state.data_version += 1
                    df_full_work = st.session_state.df_full_work
                    st.success(f"Matches: {matches}")

st.divider()

# Ano
anos = sorted(pd.Series(df_full_work["ano"]).dropna().unique(), reverse=True)
ano_sel = st.pills("Ano", options=anos, default=anos[0], selection_mode="single")
if not ano_sel:
    ano_sel = anos[0]

# Chaves do ano (pra Sumário e visões)
cols_ano = ["Categoria"]
if "desc_prod" in df_full_work.columns:
    cols_ano.insert(0, "desc_prod")
if "ncm" in df_full_work.columns:
    cols_ano.append("ncm")
if "cod_prod" in df_full_work.columns:
    cols_ano.append("cod_prod")
if "AF_MAPA" in df_full_work.columns:
    cols_ano.extend(["AF_MAPA", "CC_MAPA", "PLANO_MAPA"])

cols_ano = [c for c in cols_ano if c in df_full_work.columns]
if not cols_ano:
    cols_ano = ["desc_prod"] if "desc_prod" in df_full_work.columns else ["Categoria"]

# Agregação leve do ano (sempre roda)
with st.spinner("Preparando recorte do ano..."):
    df_ano, df_impacto = agg_ano(db_stamp, st.session_state.data_version, ano_sel, tuple(cols_ano), df_full_work)

# Define item_key para benchmark (reduz cardinalidade)
item_key = "cod_prod" if "cod_prod" in df_full_work.columns else "desc_prod"

# df_grouped: começa com impacto do ano
df_grouped = df_impacto.copy()

# Se usuário pedir histórico global, calcula e adiciona Saving_Equalizado
if calc_global:
    with st.spinner("Calculando benchmark global (pode demorar no Cloud)..."):
        hist, last = benchmark_global(db_stamp, st.session_state.data_version, item_key, df_full_work)

    # merge benchmark pelo item_key
    df_grouped = df_grouped.merge(hist, on=item_key, how="left")
    df_grouped = df_grouped.merge(last, on=item_key, how="left")

    # saneamento
    for c in ["Preco_Medio_Historico", "Ultimo_Preco", "Qtd_Total_Ano"]:
        if c in df_grouped.columns:
            df_grouped[c] = pd.to_numeric(df_grouped[c], errors="coerce").fillna(0)

    df_grouped["Saving_Equalizado"] = (
        (df_grouped.get("Ultimo_Preco", 0) - df_grouped.get("Preco_Medio_Historico", 0))
        * df_grouped.get("Qtd_Total_Ano", 0)
    ).fillna(0).clip(lower=0)
else:
    # sem benchmark global: não quebra e deixa o app abrir
    if "Saving_Equalizado" not in df_grouped.columns:
        df_grouped["Saving_Equalizado"] = 0.0

# compat com outras telas
df_grouped["Total_Gasto"] = df_grouped.get("Total_Gasto_Ano", 0)
df_grouped["Qtd_Total"] = df_grouped.get("Qtd_Total_Ano", 0)
df_grouped["Qtd_Compras"] = df_grouped.get("Qtd_Compras_Ano", 0)

tabs = st.tabs(["📌 Sumário Executivo", "🛡️ Compliance", "📇 Fornecedores", "💰 Cockpit", "🔍 Busca"])

with tabs[0]:
    render_tab_exec_review(df_ano, df_grouped)

with tabs[1]:
    render_tab_compliance(df_full_work)

with tabs[2]:
    render_tab_fornecedores(df_full_work, df_grouped)

with tabs[3]:
    render_tab_negociacao(df_full_work)

with tabs[4]:
    render_tab_busca(df_full_work)
