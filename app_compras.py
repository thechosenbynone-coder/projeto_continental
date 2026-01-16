import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta

# Tenta aplicar tema se existir, mas não quebra se não existir
try:
    from styles.theme import aplicar_tema
    aplicar_tema()
except Exception:
    pass

st.set_page_config(page_title="Portal de Inteligência em Suprimentos (DEMO)", page_icon="🏗️", layout="wide")


# =========================
# Helpers
# =========================
def _brl(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def gerar_mock_df_ano(seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    hoje = datetime.now().date()
    meses = pd.period_range((hoje.replace(day=1) - pd.DateOffset(months=11)), periods=12, freq="M")
    mes_ano = [p.strftime("%Y-%m") for p in meses]

    categorias = ["MRO", "SERVIÇOS", "EMBALAGENS", "MAT. PRIMA", "TI", "LOGÍSTICA", "CRÍTICO - SEGURANÇA"]
    fornecedores = [
        "ALFA COMERCIAL", "BETA INDUSTRIAL", "GAMMA SERVICOS", "DELTA LOG", "OMEGA TECH",
        "NOVA EMBALAGENS", "SIGMA SUPRIMENTOS", "TAU EQUIPAMENTOS", "ZETA SOLUCOES"
    ]
    itens = [
        "LUVA NITRILICA", "FILTRO AR", "CABO REDE CAT6", "PALLET MADEIRA", "ETIQUETA ADESIVA",
        "OLEO LUBRIFICANTE", "UNIFORME EPI", "FRETE RODOVIARIO", "SERVICO MANUTENCAO"
    ]
    ncm = ["4015.19.00", "8421.39.90", "8544.42.00", "4415.20.00", "4821.10.00", "2710.19.32", "6211.33.00", "9969.99.99", "9954.00.00"]

    linhas = []
    for m in mes_ano:
        n = int(rng.integers(80, 140))
        for _ in range(n):
            i = int(rng.integers(0, len(itens)))
            f = int(rng.integers(0, len(fornecedores)))
            c = int(rng.integers(0, len(categorias)))

            qtd = float(max(1, rng.normal(20, 10)))
            preco = float(max(1, rng.normal(80, 35)))
            total = qtd * preco

            # impostos ~8% a 18% do total
            imposto = total * float(rng.uniform(0.08, 0.18))

            linhas.append({
                "mes_ano": m,
                "data_emissao": m + "-15",
                "desc_prod": itens[i],
                "ncm": ncm[i],
                "Categoria": categorias[c],
                "nome_emit": fornecedores[f],
                "qtd_real": qtd,
                "v_unit_real": preco,
                "v_total_item": total,
                "Imposto_Total": imposto,
            })

    df = pd.DataFrame(linhas)
    df["data_emissao"] = pd.to_datetime(df["data_emissao"], errors="coerce")
    df["ano"] = df["data_emissao"].dt.year
    return df


def gerar_mock_df_grouped(df_ano: pd.DataFrame, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    # Agrega por item + categoria + NCM (mock simples)
    grp = (
        df_ano.groupby(["desc_prod", "ncm", "Categoria"], dropna=False)
        .agg(
            Total_Gasto_Ano=("v_total_item", "sum"),
            Qtd_Total_Ano=("qtd_real", "sum"),
            Qtd_Compras_Ano=("v_unit_real", "count"),
            Preco_Medio_Historico=("v_unit_real", "mean"),
        )
        .reset_index()
    )

    # Mock: ultimo preco é o médio com ruído (às vezes acima)
    noise = rng.normal(1.05, 0.12, size=len(grp))
    grp["Ultimo_Preco"] = (grp["Preco_Medio_Historico"] * noise).clip(lower=1)

    # Mock: menor preço histórico
    grp["Menor_Preco_Hist"] = (grp["Preco_Medio_Historico"] * rng.uniform(0.72, 0.95, size=len(grp))).clip(lower=1)
    grp["Maior_Preco_Hist"] = (grp["Preco_Medio_Historico"] * rng.uniform(1.05, 1.55, size=len(grp))).clip(lower=1)
    grp["Qtd_Compras_Hist"] = grp["Qtd_Compras_Ano"] + rng.integers(10, 80, size=len(grp))

    # Saving equalizado (último vs média histórica) * qtd do ano
    grp["Saving_Equalizado"] = ((grp["Ultimo_Preco"] - grp["Preco_Medio_Historico"]) * grp["Qtd_Total_Ano"]).clip(lower=0)

    # Potencial (último vs menor histórico) * qtd do ano
    grp["Saving_Potencial"] = ((grp["Ultimo_Preco"] - grp["Menor_Preco_Hist"]) * grp["Qtd_Total_Ano"]).clip(lower=0)

    # Compatibilidade com telas
    grp["Total_Gasto"] = grp["Total_Gasto_Ano"]
    grp["Qtd_Total"] = grp["Qtd_Total_Ano"]
    grp["Qtd_Compras"] = grp["Qtd_Compras_Ano"]
    grp["Menor_Preco"] = grp["Menor_Preco_Hist"]
    grp["Maior_Preco"] = grp["Maior_Preco_Hist"]

    return grp


def render_sumario_demo(df_ano: pd.DataFrame, df_grouped: pd.DataFrame):
    st.markdown("## 📌 Sumário Executivo (DEMO)")
    st.caption("Dados mockados para manter o app funcionando enquanto refazemos o banco/ETL.")

    gasto_total = df_ano["v_total_item"].sum()
    imposto_total = df_ano["Imposto_Total"].sum()
    carga_trib = (imposto_total / gasto_total) if gasto_total > 0 else 0
    saving_eq = df_grouped["Saving_Equalizado"].sum()
    gasto_critico = df_ano[df_ano["Categoria"].astype(str).str.contains("CRÍTICO", na=False)]["v_total_item"].sum()

    top10_share = 0.0
    spend_forn = df_ano.groupby("nome_emit")["v_total_item"].sum().sort_values(ascending=False)
    if spend_forn.sum() > 0:
        top10_share = float(spend_forn.head(10).sum() / spend_forn.sum())

    c1, c2, c3, c4 = st.columns([1.2, 1.2, 1.2, 1])
    with c1:
        st.metric("💰 Gasto Total", _brl(gasto_total), help="Total gasto no período.")
        st.caption(f"Top 10 Share: **{top10_share*100:.1f}%**  \nⓘ Concentração do gasto nos 10 maiores fornecedores.")
    c2.metric("🎯 Oportunidade de Saving", _brl(saving_eq),
              help="Mock: (Último preço - média histórica) × volume do ano (truncado em 0).")
    c3.metric("⚠️ Gasto com Itens Críticos", _brl(gasto_critico),
              help="Mock: soma dos itens com categoria contendo 'CRÍTICO'.")
    with c4:
        st.metric("🏛️ Imposto Total", _brl(imposto_total), help="Mock: imposto total calculado sobre o gasto.")
        st.caption(f"Carga tributária: **{carga_trib*100:.1f}%**")

    st.divider()

    st.subheader("📈 Tendência mensal: Gasto x Imposto")
    df_trend = (
        df_ano.groupby("mes_ano", dropna=False)
        .agg(Gasto=("v_total_item", "sum"), Imposto=("Imposto_Total", "sum"))
        .reset_index()
        .sort_values("mes_ano")
    )
    fig_trend = px.line(df_trend, x="mes_ano", y=["Gasto", "Imposto"], markers=True)
    fig_trend.update_layout(template="plotly_white", height=360, xaxis_title="", yaxis_title="R$")
    st.plotly_chart(fig_trend, width="stretch")

    st.divider()

    left, right = st.columns(2)
    with left:
        st.subheader("Composição do gasto por categoria")
        df_cat = df_ano.groupby("Categoria")["v_total_item"].sum().reset_index().sort_values("v_total_item", ascending=False)
        fig_tree = px.treemap(df_cat, path=["Categoria"], values="v_total_item")
        fig_tree.update_layout(template="plotly_white", height=360, margin=dict(t=10, l=10, r=10, b=10))
        st.plotly_chart(fig_tree, width="stretch")

    with right:
        st.subheader("Concentração por fornecedor (Top 10)")
        df_f = df_ano.groupby("nome_emit")["v_total_item"].sum().sort_values(ascending=False).head(10).reset_index()
        df_f = df_f.sort_values("v_total_item")
        fig_rank = px.bar(df_f, x="v_total_item", y="nome_emit", orientation="h")
        fig_rank.update_layout(template="plotly_white", height=360, xaxis_title="R$", yaxis_title="", showlegend=False)
        st.plotly_chart(fig_rank, width="stretch")

    st.divider()

    st.subheader("🎯 Onde agir agora (Top 5 oportunidades)")
    ops = df_grouped.copy()
    ops = ops[ops["Saving_Equalizado"] > 10].sort_values("Saving_Equalizado", ascending=False).head(5)
    st.dataframe(
        ops[["desc_prod", "Preco_Medio_Historico", "Ultimo_Preco", "Saving_Equalizado", "Qtd_Compras"]],
        width="stretch",
        hide_index=True,
        column_config={
            "Preco_Medio_Historico": st.column_config.NumberColumn("Preço Médio Hist.", format="R$ %.2f"),
            "Ultimo_Preco": st.column_config.NumberColumn("Último Preço", format="R$ %.2f"),
            "Saving_Equalizado": st.column_config.NumberColumn("Oportunidade Saving", format="R$ %.2f"),
            "Qtd_Compras": st.column_config.NumberColumn("Qtd Compras (Ano)", format="%.0f"),
        },
    )


# =========================
# APP
# =========================
st.title("🏗️ Portal de Inteligência em Suprimentos")

with st.sidebar:
    st.header("🧪 Modo DEMO")
    st.info("Esta versão usa dados mockados para o app voltar a subir. Depois vamos migrar para um DB pré-processado.")
    ano_demo = st.selectbox("Ano (mock)", options=[2024, 2025, 2026], index=1)
    seed = st.number_input("Seed (reprodutibilidade)", min_value=1, max_value=9999, value=7, step=1)

df_ano = gerar_mock_df_ano(seed=int(seed)).copy()
df_ano = df_ano[df_ano["ano"] == int(ano_demo)].copy()
df_grouped = gerar_mock_df_grouped(df_ano, seed=int(seed) + 4)

tabs = st.tabs(["📌 Sumário Executivo", "🛡️ Compliance", "📇 Fornecedores", "💰 Cockpit", "🔍 Busca"])

with tabs[0]:
    render_sumario_demo(df_ano, df_grouped)

with tabs[1]:
    st.markdown("## 🛡️ Compliance (DEMO)")
    st.info("Mock: aqui entraremos com flags reais quando o novo DB estiver pronto.")
    st.dataframe(
        df_ano.sample(min(15, len(df_ano)))[["data_emissao", "desc_prod", "Categoria", "nome_emit", "v_total_item", "Imposto_Total"]],
        width="stretch",
        hide_index=True
    )

with tabs[2]:
    st.markdown("## 📇 Fornecedores (DEMO)")
    df_f = df_ano.groupby("nome_emit")["v_total_item"].sum().sort_values(ascending=False).reset_index()
    st.dataframe(df_f.head(20), width="stretch", hide_index=True)

with tabs[3]:
    st.markdown("## 💰 Cockpit (DEMO)")
    st.caption("Mock: oportunidades de negociação. Depois vira drilldown real por item/fornecedor/contrato.")
    ops = df_grouped.sort_values("Saving_Equalizado", ascending=False).head(20)
    st.dataframe(
        ops[["desc_prod", "Categoria", "Preco_Medio_Historico", "Ultimo_Preco", "Saving_Equalizado", "Saving_Potencial"]],
        width="stretch",
        hide_index=True,
        column_config={
            "Preco_Medio_Historico": st.column_config.NumberColumn("Preço Médio Hist.", format="R$ %.2f"),
            "Ultimo_Preco": st.column_config.NumberColumn("Último Preço", format="R$ %.2f"),
            "Saving_Equalizado": st.column_config.NumberColumn("Saving Equalizado", format="R$ %.2f"),
            "Saving_Potencial": st.column_config.NumberColumn("Saving Potencial", format="R$ %.2f"),
        },
    )

with tabs[4]:
    st.markdown("## 🔍 Busca (DEMO)")
    q = st.text_input("Pesquisar item/fornecedor/categoria", "")
    base = df_ano.copy()
    if q.strip():
        q_up = q.upper().strip()
        base = base[
            base["desc_prod"].astype(str).str.contains(q_up, na=False)
            | base["nome_emit"].astype(str).str.contains(q_up, na=False)
            | base["Categoria"].astype(str).str.contains(q_up, na=False)
        ]
    st.dataframe(
        base[["data_emissao", "desc_prod", "Categoria", "nome_emit", "qtd_real", "v_unit_real", "v_total_item"]],
        width="stretch",
        hide_index=True
    )
