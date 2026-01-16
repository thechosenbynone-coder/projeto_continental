import os
import sqlite3
import re
import unicodedata
from difflib import SequenceMatcher

import pandas as pd
import streamlit as st
import plotly.express as px

# =========================
# Config
# =========================
st.set_page_config(
    page_title="Portal de Inteligência em Suprimentos",
    page_icon="🏗️",
    layout="wide"
)

# =========================
# Helpers
# =========================
def brl(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def pct(v):
    try:
        return f"{float(v)*100:.1f}%".replace(".", ",")
    except Exception:
        return "0,0%"


def connect(db_path: str):
    return sqlite3.connect(db_path, check_same_thread=False)


def safe_numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0)


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
        name = uploaded_file.name.lower()
        if name.endswith(".csv"):
            try:
                return pd.read_csv(uploaded_file, encoding="utf-8-sig", sep=None, engine="python")
            except Exception:
                uploaded_file.seek(0)
                return pd.read_csv(uploaded_file, sep=";", encoding="latin1")
        return pd.read_excel(uploaded_file)
    except Exception:
        return None


def classificar_categoria_simples(desc: str, ncm: str) -> str:
    d = (desc or "").upper()
    n = (ncm or "").strip()

    # heurística por palavras
    if any(k in d for k in ["FRETE", "TRANSPORTE", "LOGIST", "CTE"]):
        return "Logística"
    if any(k in d for k in ["EPI", "CAPACETE", "LUVA", "OCULOS", "BOTA", "PROTETOR", "MASCARA"]):
        return "EPI / Segurança"
    if any(k in d for k in ["PARAFUS", "PORCA", "ARRUELA", "ABRACADEIRA", "FIXADOR"]):
        return "Fixadores"
    if any(k in d for k in ["ROLAMENTO", "CORREIA", "MANCAL", "ENGRENAGEM"]):
        return "Mecânica"
    if any(k in d for k in ["CABO", "DISJUNTOR", "SENSOR", "INVERSOR", "MOTOR", "CONTATOR"]):
        return "Elétrica / Automação"
    if any(k in d for k in ["OLEO", "GRAXA", "LUBRIFIC"]):
        return "Lubrificantes"
    if any(k in d for k in ["LIMPEZA", "DETERGENTE", "SABAO", "DESENGRAXANTE"]):
        return "Limpeza"
    if any(k in d for k in ["SERVICO", "SERVIÇO", "MANUTENCAO", "MANUTENÇÃO", "INSTALACAO", "INSTALAÇÃO"]):
        return "Serviços"

    # fallback por NCM (bem leve)
    if n.startswith("84") or n.startswith("85"):
        return "Máquinas / Elétrica"
    if n.startswith("73"):
        return "Metais / Ferragens"
    if n.startswith("40"):
        return "Borracha"
    if n.startswith("39"):
        return "Plásticos"

    return "Outros"


# =========================
# SQL loaders (CURATED)
# =========================
@st.cache_data(show_spinner=False)
def curated_has_column(db_path: str, table: str, col: str) -> bool:
    try:
        with connect(db_path) as con:
            info = pd.read_sql(f"PRAGMA table_info({table})", con)
        return col in info["name"].tolist()
    except Exception:
        return False


@st.cache_data(show_spinner=False)
def list_years_curated(db_path: str):
    with connect(db_path) as con:
        df = pd.read_sql(
            "SELECT DISTINCT ano FROM fato_gastos WHERE ano IS NOT NULL ORDER BY ano DESC",
            con
        )
    return [int(x) for x in df["ano"].dropna().tolist()]


@st.cache_data(show_spinner=False)
def load_kpis_gastos(db_path: str, ano: int):
    has_imp = curated_has_column(db_path, "fato_gastos", "imposto_total")
    with connect(db_path) as con:
        if has_imp:
            df = pd.read_sql(
                """
                SELECT
                  doc_tipo,
                  SUM(COALESCE(valor_total,0)) AS valor_total,
                  SUM(COALESCE(imposto_total,0)) AS imposto_total
                FROM fato_gastos
                WHERE ano = ?
                GROUP BY doc_tipo
                """,
                con,
                params=[ano]
            )
        else:
            df = pd.read_sql(
                """
                SELECT
                  doc_tipo,
                  SUM(COALESCE(valor_total,0)) AS valor_total
                FROM fato_gastos
                WHERE ano = ?
                GROUP BY doc_tipo
                """,
                con,
                params=[ano]
            )
            df["imposto_total"] = 0.0

        trend = pd.read_sql(
            """
            SELECT
              mes_ano,
              SUM(COALESCE(valor_total,0)) AS gasto
            FROM fato_gastos
            WHERE ano = ? AND mes_ano IS NOT NULL
            GROUP BY mes_ano
            ORDER BY mes_ano
            """,
            con,
            params=[ano]
        )

        if has_imp:
            trend_imp = pd.read_sql(
                """
                SELECT
                  mes_ano,
                  SUM(COALESCE(imposto_total,0)) AS imposto
                FROM fato_gastos
                WHERE ano = ? AND mes_ano IS NOT NULL
                GROUP BY mes_ano
                ORDER BY mes_ano
                """,
                con,
                params=[ano]
            )
        else:
            trend_imp = trend.copy()
            trend_imp["imposto"] = 0.0

    return df, trend, trend_imp, has_imp


@st.cache_data(show_spinner=False)
def load_itens_agg(db_path: str, ano: int):
    with connect(db_path) as con:
        df = pd.read_sql(
            """
            SELECT
              i.item_key,
              i.descricao,
              i.ncm,
              SUM(COALESCE(i.v_total,0)) AS gasto_ano,
              SUM(COALESCE(i.qtd,0))     AS qtd_ano,
              AVG(NULLIF(i.v_unit,0))    AS preco_medio_ano,

              b.preco_medio_hist,
              b.menor_preco_hist,
              b.maior_preco_hist,
              b.ultimo_preco,
              b.ultima_data,
              b.ultimo_fornecedor
            FROM fato_itens i
            LEFT JOIN bench_item b ON b.item_key = i.item_key
            WHERE i.ano = ?
            GROUP BY
              i.item_key, i.descricao, i.ncm,
              b.preco_medio_hist, b.menor_preco_hist, b.maior_preco_hist,
              b.ultimo_preco, b.ultima_data, b.ultimo_fornecedor
            """,
            con,
            params=[ano]
        )

    if df.empty:
        return df

    for c in ["gasto_ano", "qtd_ano", "preco_medio_ano", "preco_medio_hist", "menor_preco_hist", "maior_preco_hist", "ultimo_preco"]:
        if c in df.columns:
            df[c] = safe_numeric(df[c])

    # Savings
    df["saving_equalizado"] = ((df["ultimo_preco"] - df["preco_medio_hist"]) * df["qtd_ano"]).clip(lower=0)
    df["saving_potencial"] = ((df["ultimo_preco"] - df["menor_preco_hist"]) * df["qtd_ano"]).clip(lower=0)

    # Categoria (recriando o que você tinha antes, mesmo que heurístico)
    df["Categoria"] = df.apply(lambda r: classificar_categoria_simples(r.get("descricao"), r.get("ncm")), axis=1)

    return df


@st.cache_data(show_spinner=False)
def load_fornecedores(db_path: str, ano: int):
    with connect(db_path) as con:
        df = pd.read_sql(
            """
            SELECT
              nome_emit,
              COUNT(DISTINCT item_key) AS itens_distintos,
              SUM(COALESCE(v_total,0)) AS gasto
            FROM fato_itens
            WHERE ano = ?
            GROUP BY nome_emit
            ORDER BY gasto DESC
            """,
            con,
            params=[ano]
        )
    if df.empty:
        return df
    df["gasto"] = safe_numeric(df["gasto"])
    return df


@st.cache_data(show_spinner=False)
def load_linhas_para_busca(db_path: str, ano: int, limit: int = 30000):
    # Busca é a única que “puxa linhas”
    with connect(db_path) as con:
        df = pd.read_sql(
            f"""
            SELECT
              mes_ano, nome_emit, descricao, ncm, unidade, qtd, v_unit, v_total, item_key
            FROM fato_itens
            WHERE ano = ?
            LIMIT {int(limit)}
            """,
            con,
            params=[ano]
        )
    if df.empty:
        return df
    for c in ["qtd", "v_unit", "v_total"]:
        if c in df.columns:
            df[c] = safe_numeric(df[c])
    return df


@st.cache_data(show_spinner=False)
def load_hist_item_mes(db_path: str, ano: int, item_key: str):
    with connect(db_path) as con:
        df = pd.read_sql(
            """
            SELECT
              mes_ano,
              nome_emit,
              AVG(NULLIF(v_unit,0)) AS preco_medio,
              SUM(COALESCE(qtd,0)) AS qtd,
              SUM(COALESCE(v_total,0)) AS gasto
            FROM fato_itens
            WHERE ano = ? AND item_key = ? AND mes_ano IS NOT NULL
            GROUP BY mes_ano, nome_emit
            ORDER BY mes_ano
            """,
            con,
            params=[ano, item_key]
        )
    if df.empty:
        return df
    for c in ["preco_medio", "qtd", "gasto"]:
        df[c] = safe_numeric(df[c])
    return df


# =========================
# Optional RAW “detetive”
# =========================
@st.cache_data(show_spinner=False)
def raw_available(raw_db_path: str) -> bool:
    return os.path.exists(raw_db_path)


@st.cache_data(show_spinner=False)
def raw_has_table(raw_db_path: str, table: str) -> bool:
    try:
        with connect(raw_db_path) as con:
            df = pd.read_sql(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                con,
                params=[table]
            )
        return not df.empty
    except Exception:
        return False


@st.cache_data(show_spinner=False)
def raw_get_docs_nf_for_detetive(raw_db_path: str, ano: int):
    """
    Puxa um índice mínimo para detetive:
    doc_id, n_nf, chave, nome_emit, data_emissao, valor_total
    """
    if not raw_has_table(raw_db_path, "raw_documentos"):
        return pd.DataFrame()

    with connect(raw_db_path) as con:
        df = pd.read_sql(
            """
            SELECT
              doc_id,
              doc_tipo,
              n_nf,
              chave,
              nome_emit,
              data_emissao,
              valor_total
            FROM raw_documentos
            """,
            con
        )

    if df.empty:
        return df

    df["data_emissao"] = pd.to_datetime(df["data_emissao"], errors="coerce")
    df["ano"] = df["data_emissao"].dt.year
    df = df[df["ano"] == ano].copy()

    # normaliza n_nf para match
    if "n_nf" in df.columns:
        df["n_nf_clean"] = df["n_nf"].astype(str).apply(limpar_nf_excel)
    else:
        df["n_nf_clean"] = ""

    return df


def enriquecer_detetive(df_docs_raw: pd.DataFrame, df_mapa: pd.DataFrame):
    """
    Gera uma tabela de match por NF (e, se houver, fornecedor).
    Não altera o banco. É um “painel de inteligência”, como antes.
    """
    if df_docs_raw.empty or df_mapa.empty:
        return pd.DataFrame(), 0

    df_mapa = df_mapa.copy()
    df_mapa.columns = [str(c).upper().strip() for c in df_mapa.columns]

    # tenta achar colunas
    mapa_cols = {"NF": None, "FORNECEDOR": None, "AF": None, "CC": None, "PLANO": None}
    sinonimos = {
        "NF": ["NF", "NOTA", "N_NF", "NUMERO"],
        "FORNECEDOR": ["FORNECEDOR", "NOME", "EMPRESA"],
        "AF": ["AF/AS", "AF", "AS", "PEDIDO", "OC"],
        "PLANO": ["PLANO DE CONTAS", "PLANO", "CONTA"],
        "CC": ["CC", "CENTRO", "CUSTO", "DEPARTAMENTO"],
    }
    for chave, lista in sinonimos.items():
        for col_real in df_mapa.columns:
            if any(nome == col_real or nome in col_real for nome in lista):
                if chave == "CC" and "PLANO" in col_real:
                    continue
                mapa_cols[chave] = col_real
                break

    if not mapa_cols["NF"]:
        return pd.DataFrame(), 0

    df_mapa["nf_key"] = df_mapa[mapa_cols["NF"]].apply(limpar_nf_excel)

    # índice por NF
    dict_mapa = {}
    for _, row in df_mapa.iterrows():
        nf = row.get("nf_key", "")
        if nf:
            dict_mapa.setdefault(nf, []).append(row)

    out_rows = []
    total_matches = 0

    for _, r in df_docs_raw.iterrows():
        nf_xml = str(r.get("n_nf_clean") or "")
        forn_xml = str(r.get("nome_emit") or "")

        candidatos = dict_mapa.get(nf_xml, [])
        melhor = None
        melhor_score = 0

        if candidatos:
            for cand in candidatos:
                score = 50
                if mapa_cols["FORNECEDOR"]:
                    nome_mapa = str(cand.get(mapa_cols["FORNECEDOR"], ""))
                    score = calcular_similaridade(forn_xml, nome_mapa)

                if score > melhor_score:
                    melhor_score = score
                    melhor = cand

        status = "Não Encontrado"
        aceitar = False

        if melhor is not None:
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
                val_af = str(melhor.get(mapa_cols["AF"], "Não Mapeado"))
            if mapa_cols["CC"]:
                val_cc = str(melhor.get(mapa_cols["CC"], "Não Mapeado"))
            if mapa_cols["PLANO"]:
                val_plano = str(melhor.get(mapa_cols["PLANO"], "Não Mapeado"))

        out_rows.append({
            "NF": nf_xml,
            "Fornecedor_XML": forn_xml,
            "Valor_Doc": r.get("valor_total", 0.0),
            "Status": status,
            "AF_MAPA": val_af,
            "CC_MAPA": val_cc,
            "PLANO_MAPA": val_plano,
            "Score": float(melhor_score),
        })

    df_out = pd.DataFrame(out_rows)
    return df_out, total_matches


# =========================
# Sidebar
# =========================
st.title("🏗️ Portal de Inteligência em Suprimentos")

default_curated = os.path.join("data", "curated", "suprimentos_curated.sqlite")
default_raw = os.path.join("data", "raw", "suprimentos_raw.sqlite")

with st.sidebar:
    st.header("🗃️ Fonte de Dados")
    curated_db = st.text_input("DB CURATED (SQLite)", value=default_curated)
    raw_db = st.text_input("DB RAW (opcional, p/ Detetive)", value=default_raw)

    if not os.path.exists(curated_db):
        st.error("DB curated não encontrado no caminho informado.")
        st.stop()

    st.divider()
    st.header("⚙️ Filtros")
    anos = list_years_curated(curated_db)
    if not anos:
        st.error("Não encontrei anos em fato_gastos.")
        st.stop()

    ano_sel = st.selectbox("Ano", anos, index=0)

    topn = st.slider("Top N (tabelas)", 10, 300, 50, 10)

    crit_regex = st.text_input(
        "Criticidade (regex na descrição)",
        value=r"EPI|SEGUR|EMERG|FREIO|BOMBEIR|BLOQUEIO|NR-",
        help="Enquanto criticidade não é uma dimensão no DB definitivo, usamos regra por descrição."
    )

    st.divider()
    st.header("🕵️ Detetive (Mapa NF/AF/CC/Plano)")
    uploaded_files = st.file_uploader(
        "Carregar Mapas (CSV/Excel)",
        type=["csv", "xlsx", "xls"],
        accept_multiple_files=True
    )
    run_detetive = st.button("🚀 Processar Detetive", use_container_width=True)


# =========================
# Load core datasets
# =========================
gastos_tipo, trend_gasto, trend_imp, has_imp = load_kpis_gastos(curated_db, int(ano_sel))
itens = load_itens_agg(curated_db, int(ano_sel))
fornecedores = load_fornecedores(curated_db, int(ano_sel))

gasto_total = float(gastos_tipo["valor_total"].sum()) if not gastos_tipo.empty else 0.0
imposto_total = float(gastos_tipo["imposto_total"].sum()) if (not gastos_tipo.empty and "imposto_total" in gastos_tipo.columns) else 0.0
carga_trib = (imposto_total / gasto_total) if gasto_total > 0 else 0.0

gasto_cte = float(gastos_tipo.loc[gastos_tipo["doc_tipo"] == "CTE", "valor_total"].sum()) if not gastos_tipo.empty else 0.0
gasto_nfe = float(gastos_tipo.loc[gastos_tipo["doc_tipo"] == "NFE", "valor_total"].sum()) if not gastos_tipo.empty else 0.0
gasto_unknown = float(gastos_tipo.loc[gastos_tipo["doc_tipo"] == "UNKNOWN", "valor_total"].sum()) if not gastos_tipo.empty else 0.0

saving_eq_total = float(itens["saving_equalizado"].sum()) if (isinstance(itens, pd.DataFrame) and not itens.empty) else 0.0
saving_pot_total = float(itens["saving_potencial"].sum()) if (isinstance(itens, pd.DataFrame) and not itens.empty) else 0.0

gasto_critico = 0.0
if isinstance(itens, pd.DataFrame) and not itens.empty and crit_regex.strip():
    crit_mask = itens["descricao"].astype(str).str.contains(crit_regex, case=False, na=False, regex=True)
    gasto_critico = float(itens.loc[crit_mask, "gasto_ano"].sum())

top10_share = 0.0
if isinstance(fornecedores, pd.DataFrame) and not fornecedores.empty:
    total_spend = float(fornecedores["gasto"].sum())
    if total_spend > 0:
        top10_share = float(fornecedores.head(10)["gasto"].sum() / total_spend)

# =========================
# Detetive (runs on demand)
# =========================
df_det = pd.DataFrame()
det_matches = 0

if run_detetive and uploaded_files:
    if raw_available(raw_db) and raw_has_table(raw_db, "raw_documentos"):
        df_mapa = pd.DataFrame()
        for f in uploaded_files:
            df_t = carregar_arquivo_flexivel(f)
            if df_t is not None and not df_t.empty:
                df_t.columns = [str(c).upper().strip() for c in df_t.columns]
                df_mapa = pd.concat([df_mapa, df_t], ignore_index=True)

        if df_mapa.empty:
            st.warning("Nenhum mapa válido carregado.")
        else:
            with st.spinner("Rodando Detetive (RAW → Mapa)..."):
                df_docs_raw = raw_get_docs_nf_for_detetive(raw_db, int(ano_sel))
                df_det, det_matches = enriquecer_detetive(df_docs_raw, df_mapa)
    else:
        st.warning(
            "DB RAW não encontrado (ou sem tabela raw_documentos). "
            "O Detetive depende do RAW para ler NF/chave. "
            "Sem isso, o restante do portal funciona normalmente."
        )

# =========================
# Tabs (restauradas)
# =========================
tabs = st.tabs(["📌 Visão Executiva", "📊 Dashboard", "🛡️ Compliance", "📇 Fornecedores", "💰 Cockpit", "🔍 Busca"])

# ---------------------------------------------------------
# 1) Visão Executiva
# ---------------------------------------------------------
with tabs[0]:
    st.subheader("📌 Visão Executiva")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Gasto Total", brl(gasto_total), help="NFe + CTe + demais documentos no curated.")
    c2.metric("🎯 Saving Potencial (Equalizado)", brl(saving_eq_total), help="(Último preço - Média histórica) × volume do ano (>=0).")
    c3.metric("⚠️ Gasto com Itens Críticos", brl(gasto_critico), help="Regra por regex na descrição (temporário).")
    if has_imp:
        c4.metric("🏛️ Imposto Total", brl(imposto_total), help="Imposto por documento no curated.")
        st.caption(f"Carga tributária estimada: **{pct(carga_trib)}**  |  Frete (CTe): **{brl(gasto_cte)}**  |  UNKNOWN: **{brl(gasto_unknown)}**")
    else:
        c4.metric("🚚 Frete (CTe)", brl(gasto_cte), help="Total de CTe no ano (valor_total).")
        st.caption("Imposto ainda não materializado no seu curated atual (se quiser, eu ajusto o ETL para garantir).")

    st.divider()

    # Tendência
    colA, colB = st.columns(2)
    with colA:
        st.markdown("#### 📈 Tendência mensal de gasto")
        if trend_gasto.empty:
            st.info("Sem dados mensais (mes_ano nulo).")
        else:
            fig = px.line(trend_gasto, x="mes_ano", y="gasto", markers=True)
            fig.update_layout(template="plotly_white", height=320, xaxis_title="", yaxis_title="R$")
            st.plotly_chart(fig, width="stretch")

    with colB:
        st.markdown("#### 🏛️ Tendência mensal de imposto")
        if (not has_imp) or trend_imp.empty:
            st.info("Sem imposto no curated (ou sem mes_ano).")
        else:
            fig = px.line(trend_imp, x="mes_ano", y="imposto", markers=True)
            fig.update_layout(template="plotly_white", height=320, xaxis_title="", yaxis_title="R$")
            st.plotly_chart(fig, width="stretch")

    st.divider()

    # Top fornecedores e categorias
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🏢 Top fornecedores (NFe - itens)")
        if fornecedores.empty:
            st.info("Sem fornecedores para o ano selecionado.")
        else:
            df_f = fornecedores.head(10).copy().sort_values("gasto")
            fig = px.bar(df_f, x="gasto", y="nome_emit", orientation="h")
            fig.update_layout(template="plotly_white", height=360, xaxis_title="R$", yaxis_title="")
            st.plotly_chart(fig, width="stretch")
            st.caption(f"Concentração Top 10: **{pct(top10_share)}**")

    with col2:
        st.markdown("#### 🧩 Gasto por categoria (heurística)")
        if itens.empty:
            st.info("Sem itens para o ano selecionado.")
        else:
            df_cat = itens.groupby("Categoria", dropna=False)["gasto_ano"].sum().sort_values(ascending=False).reset_index()
            fig = px.bar(df_cat.head(12), x="Categoria", y="gasto_ano")
            fig.update_layout(template="plotly_white", height=360, xaxis_title="", yaxis_title="R$")
            st.plotly_chart(fig, width="stretch")

    # Detetive output
    if not df_det.empty:
        st.divider()
        st.markdown("### 🕵️ Visão Integrada (Detetive)")
        st.success(f"{det_matches} vínculos encontrados no ano {ano_sel}.")
        st.dataframe(
            df_det.sort_values(["Status", "Valor_Doc"], ascending=[True, False]).head(500),
            width="stretch",
            hide_index=True,
            column_config={
                "Valor_Doc": st.column_config.NumberColumn("Valor Doc", format="R$ %.2f"),
                "Score": st.column_config.NumberColumn("Score", format="%.1f"),
            }
        )

# ---------------------------------------------------------
# 2) Dashboard (mais gráfico, menos “solto”)
# ---------------------------------------------------------
with tabs[1]:
    st.subheader("📊 Dashboard")

    if itens.empty:
        st.info("Sem itens para o ano selecionado.")
    else:
        # Pareto de itens
        st.markdown("#### 🧠 Pareto de Itens (gasto acumulado)")
        df_p = itens[["item_key", "descricao", "gasto_ano"]].copy()
        df_p = df_p.sort_values("gasto_ano", ascending=False)
        df_p["pct_acum"] = df_p["gasto_ano"].cumsum() / max(df_p["gasto_ano"].sum(), 1e-9)
        df_p["rank"] = range(1, len(df_p) + 1)

        col1, col2 = st.columns(2)
        with col1:
            fig = px.line(df_p.head(300), x="rank", y="pct_acum", markers=False)
            fig.update_layout(template="plotly_white", height=320, xaxis_title="Itens (rank)", yaxis_title="% acumulado")
            st.plotly_chart(fig, width="stretch")
            st.caption("Quanto mais rápido a curva sobe, mais concentrado é o gasto em poucos itens.")

        with col2:
            st.markdown("#### 🎯 Itens com maior saving (Equalizado)")
            ops = itens.sort_values("saving_equalizado", ascending=False).head(int(topn))
            st.dataframe(
                ops[["descricao", "ncm", "gasto_ano", "qtd_ano", "ultimo_preco", "preco_medio_hist", "saving_equalizado"]],
                width="stretch",
                hide_index=True,
                column_config={
                    "gasto_ano": st.column_config.NumberColumn("Gasto Ano", format="R$ %.2f"),
                    "ultimo_preco": st.column_config.NumberColumn("Último", format="R$ %.2f"),
                    "preco_medio_hist": st.column_config.NumberColumn("Média Hist.", format="R$ %.2f"),
                    "saving_equalizado": st.column_config.NumberColumn("Saving Eq.", format="R$ %.2f"),
                    "qtd_ano": st.column_config.NumberColumn("Qtd", format="%.2f"),
                }
            )

        st.divider()

        # Dashboard de fornecedores
        st.markdown("#### 🏢 Fornecedores: gasto x itens distintos")
        if not fornecedores.empty:
            df_sc = fornecedores.copy()
            fig = px.scatter(df_sc, x="itens_distintos", y="gasto", hover_name="nome_emit")
            fig.update_layout(template="plotly_white", height=360, xaxis_title="Itens distintos", yaxis_title="R$")
            st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------
# 3) Compliance (reconstruído com regras úteis no curated)
# ---------------------------------------------------------
with tabs[2]:
    st.subheader("🛡️ Compliance (reconstruído)")

    # Compliance aqui é “regras de sanidade” baseadas no que temos no curated.
    # Depois você materializa isso no DB definitivo, mas aqui não fica vazio.

    issues = []

    # Doc UNKNOWN
    if gasto_unknown > 0:
        issues.append(("Documentos UNKNOWN", "Existem documentos não classificados no ingest.", gasto_unknown))

    # Itens sem NCM
    if not itens.empty:
        sem_ncm = itens[itens["ncm"].astype(str).str.strip().eq("")]["gasto_ano"].sum()
        if sem_ncm > 0:
            issues.append(("Itens sem NCM", "NCM ausente prejudica classificação fiscal e análise.", float(sem_ncm)))

        # preços “zero”
        preco_zero = itens[(itens["ultimo_preco"] <= 0) | (itens["preco_medio_hist"] <= 0)]["gasto_ano"].sum()
        if preco_zero > 0:
            issues.append(("Benchmark fraco", "Itens sem preço histórico/último preço no benchmark.", float(preco_zero)))

        # outliers simples: último preço muito acima da média
        out = itens[(itens["preco_medio_hist"] > 0) & (itens["ultimo_preco"] > 2.5 * itens["preco_medio_hist"])]
        out_g = float(out["gasto_ano"].sum()) if not out.empty else 0.0
        if out_g > 0:
            issues.append(("Possíveis outliers de preço", "Último preço > 2,5x média histórica.", out_g))

    if not issues:
        st.success("Sem alertas relevantes com as regras atuais (curated).")
    else:
        df_iss = pd.DataFrame(issues, columns=["Tema", "Descrição", "Impacto (R$)"])
        st.dataframe(
            df_iss.sort_values("Impacto (R$)", ascending=False),
            width="stretch",
            hide_index=True,
            column_config={"Impacto (R$)": st.column_config.NumberColumn("Impacto (R$)", format="R$ %.2f")}
        )

    st.divider()
    st.markdown("#### 🔍 Lista rápida de casos (amostras)")

    if not itens.empty:
        st.markdown("**Top itens sem NCM:**")
        df1 = itens[itens["ncm"].astype(str).str.strip().eq("")].sort_values("gasto_ano", ascending=False).head(20)
        st.dataframe(df1[["descricao", "gasto_ano", "qtd_ano"]], width="stretch", hide_index=True,
                     column_config={"gasto_ano": st.column_config.NumberColumn("Gasto", format="R$ %.2f"),
                                    "qtd_ano": st.column_config.NumberColumn("Qtd", format="%.2f")})

        st.markdown("**Top outliers (último preço vs média):**")
        df2 = itens[(itens["preco_medio_hist"] > 0) & (itens["ultimo_preco"] > 2.5 * itens["preco_medio_hist"])]\
                .sort_values("saving_potencial", ascending=False).head(20)
        st.dataframe(
            df2[["descricao", "ultimo_preco", "preco_medio_hist", "gasto_ano", "saving_potencial"]],
            width="stretch",
            hide_index=True,
            column_config={
                "ultimo_preco": st.column_config.NumberColumn("Último", format="R$ %.2f"),
                "preco_medio_hist": st.column_config.NumberColumn("Média Hist.", format="R$ %.2f"),
                "gasto_ano": st.column_config.NumberColumn("Gasto", format="R$ %.2f"),
                "saving_potencial": st.column_config.NumberColumn("Saving Pot.", format="R$ %.2f"),
            }
        )

# ---------------------------------------------------------
# 4) Fornecedores (volta a ter “massa”)
# ---------------------------------------------------------
with tabs[3]:
    st.subheader("📇 Fornecedores")

    if fornecedores.empty:
        st.info("Sem fornecedores para o ano selecionado.")
    else:
        col1, col2 = st.columns([1.2, 1])
        with col1:
            st.markdown("#### Ranking por gasto")
            st.dataframe(
                fornecedores.head(200),
                width="stretch",
                hide_index=True,
                column_config={"gasto": st.column_config.NumberColumn("Gasto", format="R$ %.2f")}
            )
        with col2:
            st.markdown("#### Concentração")
            total = float(fornecedores["gasto"].sum())
            top20 = float(fornecedores.head(20)["gasto"].sum())
            st.metric("Top 10 Share", pct(top10_share))
            st.metric("Top 20 Share", pct(top20 / total if total > 0 else 0))
            st.metric("Qtd. fornecedores", f"{len(fornecedores)}")

# ---------------------------------------------------------
# 5) Cockpit (com gráfico de histórico por item)
# ---------------------------------------------------------
with tabs[4]:
    st.subheader("💰 Cockpit de Negociação (Itens)")

    if itens.empty:
        st.info("Sem itens para o ano selecionado.")
    else:
        colf1, colf2, colf3 = st.columns([1.2, 1, 1])
        min_saving = colf1.number_input("Saving mínimo (R$)", min_value=0.0, value=1000.0, step=500.0)
        categoria = colf2.selectbox("Categoria", ["(Todas)"] + sorted(itens["Categoria"].dropna().unique().tolist()))
        ordem = colf3.selectbox("Ordenar por", ["Saving Equalizado", "Saving Potencial", "Gasto Ano"], index=0)

        df = itens.copy()
        df = df[df["saving_equalizado"] >= float(min_saving)]

        if categoria != "(Todas)":
            df = df[df["Categoria"] == categoria]

        if ordem == "Saving Potencial":
            df = df.sort_values("saving_potencial", ascending=False)
        elif ordem == "Gasto Ano":
            df = df.sort_values("gasto_ano", ascending=False)
        else:
            df = df.sort_values("saving_equalizado", ascending=False)

        df_view = df.head(int(topn)).copy()

        st.dataframe(
            df_view[
                ["descricao", "ncm", "Categoria", "gasto_ano", "qtd_ano", "ultimo_preco", "preco_medio_hist",
                 "menor_preco_hist", "saving_equalizado", "saving_potencial", "ultimo_fornecedor", "ultima_data"]
            ],
            width="stretch",
            hide_index=True,
            column_config={
                "gasto_ano": st.column_config.NumberColumn("Gasto Ano", format="R$ %.2f"),
                "qtd_ano": st.column_config.NumberColumn("Qtd Ano", format="%.2f"),
                "ultimo_preco": st.column_config.NumberColumn("Último", format="R$ %.2f"),
                "preco_medio_hist": st.column_config.NumberColumn("Média Hist.", format="R$ %.2f"),
                "menor_preco_hist": st.column_config.NumberColumn("Menor Hist.", format="R$ %.2f"),
                "saving_equalizado": st.column_config.NumberColumn("Saving Eq.", format="R$ %.2f"),
                "saving_potencial": st.column_config.NumberColumn("Saving Pot.", format="R$ %.2f"),
            }
        )

        st.divider()
        st.markdown("#### 📉 Histórico do item (por mês e fornecedor)")

        # seletor de item
        if not df_view.empty:
            options = df_view[["item_key", "descricao"]].copy()
            options["label"] = options["descricao"].str.slice(0, 80) + "  •  " + options["item_key"].str.slice(0, 18)
            sel = st.selectbox("Escolha um item para ver evolução de preço", options["label"].tolist())

            sel_key = None
            if sel:
                sel_key = options.loc[options["label"] == sel, "item_key"].iloc[0]

            if sel_key:
                hist = load_hist_item_mes(curated_db, int(ano_sel), sel_key)
                if hist.empty:
                    st.info("Sem histórico mensal para esse item no ano.")
                else:
                    fig = px.line(hist, x="mes_ano", y="preco_medio", color="nome_emit", markers=True)
                    fig.update_layout(template="plotly_white", height=380, xaxis_title="", yaxis_title="Preço médio (R$)")
                    st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------
# 6) Busca (volta a ter “linha”)
# ---------------------------------------------------------
with tabs[5]:
    st.subheader("🔍 Busca")

    df_busca = load_linhas_para_busca(curated_db, int(ano_sel))
    if df_busca.empty:
        st.info("Sem linhas para busca no ano selecionado.")
    else:
        q = st.text_input("Pesquisar por item / fornecedor / NCM", value="").strip()
        base = df_busca.copy()

        if q:
            q_up = q.upper()
            base = base[
                base["descricao"].astype(str).str.upper().str.contains(q_up, na=False)
                | base["nome_emit"].astype(str).str.upper().str.contains(q_up, na=False)
                | base["ncm"].astype(str).str.upper().str.contains(q_up, na=False)
            ]

        st.dataframe(
            base.sort_values("v_total", ascending=False).head(2000),
            width="stretch",
            hide_index=True,
            column_config={
                "qtd": st.column_config.NumberColumn("Qtd", format="%.2f"),
                "v_unit": st.column_config.NumberColumn("Preço Unit", format="R$ %.2f"),
                "v_total": st.column_config.NumberColumn("Total", format="R$ %.2f"),
            }
        )

        st.caption("Dica: use busca por NCM (ex: 4015) ou parte do nome do fornecedor.")
