import os
import sqlite3
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Portal de Inteligência em Suprimentos", page_icon="🏗️", layout="wide")

def brl(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"

def connect(db_path: str):
    return sqlite3.connect(db_path, check_same_thread=False)

def safe_numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0)

@st.cache_data(show_spinner=False)
def list_years(db_path: str):
    with connect(db_path) as con:
        df = pd.read_sql(
            "SELECT DISTINCT ano FROM fato_gastos WHERE ano IS NOT NULL ORDER BY ano DESC",
            con,
        )
    return [int(x) for x in df["ano"].dropna().tolist()]

@st.cache_data(show_spinner=False)
def load_gastos(db_path: str, ano: int):
    with connect(db_path) as con:
        gastos_tipo = pd.read_sql(
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
            params=[ano],
        )

        trend = pd.read_sql(
            """
            SELECT
              mes_ano,
              SUM(COALESCE(valor_total,0)) AS gasto,
              SUM(COALESCE(imposto_total,0)) AS imposto
            FROM fato_gastos
            WHERE ano = ? AND mes_ano IS NOT NULL
            GROUP BY mes_ano
            ORDER BY mes_ano
            """,
            con,
            params=[ano],
        )
    return gastos_tipo, trend

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
            params=[ano],
        )

    if df.empty:
        return df

    for col in ["gasto_ano", "qtd_ano", "preco_medio_hist", "menor_preco_hist", "maior_preco_hist", "ultimo_preco"]:
        if col in df.columns:
            df[col] = safe_numeric(df[col])

    df["saving_equalizado"] = ((df["ultimo_preco"] - df["preco_medio_hist"]) * df["qtd_ano"]).clip(lower=0)
    df["saving_potencial"] = ((df["ultimo_preco"] - df["menor_preco_hist"]) * df["qtd_ano"]).clip(lower=0)
    df["has_bench"] = (df["preco_medio_hist"] > 0) | (df["ultimo_preco"] > 0)

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
            params=[ano],
        )
    if df.empty:
        return df
    df["gasto"] = safe_numeric(df["gasto"])
    return df

@st.cache_data(show_spinner=False)
def load_busca(db_path: str, ano: int, limit: int = 20000):
    with connect(db_path) as con:
        df = pd.read_sql(
            f"""
            SELECT mes_ano, nome_emit, descricao, ncm, qtd, v_unit, v_total, item_key
            FROM fato_itens
            WHERE ano = ?
            LIMIT {int(limit)}
            """,
            con,
            params=[ano],
        )
    if df.empty:
        return df
    for c in ["qtd", "v_unit", "v_total"]:
        df[c] = safe_numeric(df[c])
    return df

st.title("🏗️ Portal de Inteligência em Suprimentos")
st.caption("Read-Only no banco CURATED. KPIs executivos com imposto e carga tributária.")

default_db = os.path.join("data", "curated", "suprimentos_curated.sqlite")

with st.sidebar:
    st.header("🗃️ Banco CURATED")
    db_path = st.text_input("Caminho do SQLite", value=default_db)

    st.divider()
    st.header("⚙️ Ajustes")
    topn = st.slider("Top N oportunidades (Cockpit)", 10, 300, 50, 10)
    crit_regex = st.text_input(
        "Regra de 'Crítico' (regex na descrição)",
        value=r"EPI|SEGUR|EMERG|FREIO|BOMBEIR|BLOQUEIO|NR-",
    )

if not os.path.exists(db_path):
    st.error(f"Banco não encontrado: {db_path}")
    st.stop()

anos = list_years(db_path)
if not anos:
    st.error("Não encontrei anos em fato_gastos (ano IS NOT NULL).")
    st.stop()

ano_sel = st.pills("Ano", options=anos, default=anos[0], selection_mode="single")
if not ano_sel:
    ano_sel = anos[0]
ano_sel = int(ano_sel)

gastos_tipo, trend = load_gastos(db_path, ano_sel)
itens = load_itens_agg(db_path, ano_sel)
fornecedores = load_fornecedores(db_path, ano_sel)

gasto_total = float(gastos_tipo["valor_total"].sum()) if not gastos_tipo.empty else 0.0
imposto_total = float(gastos_tipo["imposto_total"].sum()) if not gastos_tipo.empty else 0.0
carga_trib = (imposto_total / gasto_total) if gasto_total > 0 else 0.0

gasto_cte = float(gastos_tipo.loc[gastos_tipo["doc_tipo"] == "CTE", "valor_total"].sum()) if not gastos_tipo.empty else 0.0
saving_eq_total = float(itens["saving_equalizado"].sum()) if (isinstance(itens, pd.DataFrame) and not itens.empty) else 0.0

gasto_critico = 0.0
if isinstance(itens, pd.DataFrame) and not itens.empty and crit_regex.strip():
    crit_mask = itens["descricao"].astype(str).str.contains(crit_regex, case=False, na=False, regex=True)
    gasto_critico = float(itens.loc[crit_mask, "gasto_ano"].sum())

top10_share = 0.0
if isinstance(fornecedores, pd.DataFrame) and not fornecedores.empty:
    total_spend = float(fornecedores["gasto"].sum())
    if total_spend > 0:
        top10_share = float(fornecedores.head(10)["gasto"].sum() / total_spend)

tabs = st.tabs(["📌 Sumário Executivo", "📇 Fornecedores", "💰 Cockpit", "🔍 Busca"])

with tabs[0]:
    st.subheader("📌 Sumário Executivo")

    # Hierarquia: Gasto Total -> Saving -> Crítico -> Imposto (carga no texto) -> Frete
    c1, c2, c3, c4, c5 = st.columns([1.25, 1.25, 1.25, 1.15, 1])

    with c1:
        st.metric("💰 Gasto Total", brl(gasto_total), help="Total do ano (NFE + CTE + demais docs).")
        st.caption(f"Top 10 Share (NFe): **{top10_share*100:.1f}%**")

    c2.metric("🎯 Saving Potencial", brl(saving_eq_total),
              help="Saving Equalizado (compras): (Último - Média Hist.) × volume do ano, truncado em 0.")

    c3.metric("⚠️ Gasto Itens Críticos", brl(gasto_critico),
              help="Estimativa por regex na descrição. No DB definitivo vira classificação materializada.")

    with c4:
        st.metric("🏛️ Imposto Total", brl(imposto_total),
                  help="Imposto total por documento (NFe: ICMSTot/vTotTrib ou soma de tributos em ICMSTot; CTe: vICMS/vTotTrib quando disponível).")
        st.caption(f"Carga tributária: **{carga_trib*100:.1f}%**")

    c5.metric("🚚 Frete (CTe)", brl(gasto_cte), help="Total de CTe no ano (valor_total).")

    st.divider()

    st.subheader("📈 Tendência mensal: Gasto vs Imposto")
    if trend.empty:
        st.info("Sem mes_ano válido em fato_gastos para este ano.")
    else:
        fig = px.line(trend, x="mes_ano", y=["gasto", "imposto"], markers=True)
        fig.update_layout(template="plotly_white", height=360, xaxis_title="", yaxis_title="R$")
        st.plotly_chart(fig, width="stretch")

with tabs[1]:
    st.subheader("📇 Fornecedores (NFe)")
    if fornecedores.empty:
        st.info("Sem dados de fornecedores no ano selecionado.")
    else:
        st.dataframe(
            fornecedores,
            width="stretch",
            hide_index=True,
            column_config={"gasto": st.column_config.NumberColumn("Gasto", format="R$ %.2f")},
        )

with tabs[2]:
    st.subheader("💰 Cockpit (Itens)")
    if itens is None or itens.empty:
        st.info("Sem itens NFe para o ano selecionado.")
    else:
        df = itens.copy()
        df = df[df["saving_equalizado"] > 0].sort_values("saving_equalizado", ascending=False).head(int(topn))

        st.dataframe(
            df[["descricao", "ncm", "gasto_ano", "qtd_ano", "preco_medio_hist", "ultimo_preco", "saving_equalizado", "saving_potencial"]],
            width="stretch",
            hide_index=True,
            column_config={
                "gasto_ano": st.column_config.NumberColumn("Gasto Ano", format="R$ %.2f"),
                "preco_medio_hist": st.column_config.NumberColumn("Preço Médio Hist.", format="R$ %.2f"),
                "ultimo_preco": st.column_config.NumberColumn("Último Preço", format="R$ %.2f"),
                "saving_equalizado": st.column_config.NumberColumn("Saving Eq.", format="R$ %.2f"),
                "saving_potencial": st.column_config.NumberColumn("Saving Pot.", format="R$ %.2f"),
                "qtd_ano": st.column_config.NumberColumn("Qtd Ano", format="%.2f"),
            },
        )

with tabs[3]:
    st.subheader("🔍 Busca")
    df_busca = load_busca(db_path, ano_sel)
    if df_busca.empty:
        st.info("Sem dados para busca no ano selecionado.")
    else:
        q = st.text_input("Pesquisar por item/fornecedor/NCM", value="").strip()
        base = df_busca.copy()
        if q:
            q_up = q.upper()
            base = base[
                base["descricao"].astype(str).str.upper().str.contains(q_up, na=False)
                | base["nome_emit"].astype(str).str.upper().str.contains(q_up, na=False)
                | base["ncm"].astype(str).str.upper().str.contains(q_up, na=False)
            ]

        st.dataframe(
            base.sort_values("v_total", ascending=False).head(1000),
            width="stretch",
            hide_index=True,
            column_config={
                "qtd": st.column_config.NumberColumn("Qtd", format="%.2f"),
                "v_unit": st.column_config.NumberColumn("Preço Unit", format="R$ %.2f"),
                "v_total": st.column_config.NumberColumn("Total", format="R$ %.2f"),
            },
        )
