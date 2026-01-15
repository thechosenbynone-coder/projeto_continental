import streamlit as st
import plotly.express as px
import pandas as pd

from utils.formatters import format_brl, format_perc


def _safe_col(df: pd.DataFrame, *candidates: str):
    """Retorna o primeiro nome de coluna existente no df, ou None."""
    for c in candidates:
        if c in df.columns:
            return c
    return None


def render_tab_dashboard(df: pd.DataFrame, df_final: pd.DataFrame):
    st.markdown("### 📊 Dashboard de Suprimentos")
    st.caption("Resumo executivo-operacional: onde está o gasto, onde concentra, e onde agir primeiro.")

    # -------------------------
    # KPIs (Faixa 1)
    # -------------------------
    spend_col = _safe_col(df, "v_total_item", "Total_Gasto", "Gasto")
    nf_col = _safe_col(df, "n_nf_clean", "n_nf")
    forn_col = _safe_col(df, "nome_emit", "Fornecedor", "Nome_Fornecedor")
    cat_col = _safe_col(df, "Categoria", "categoria")
    mes_col = _safe_col(df, "mes_ano", "Mes_Ano", "mesano")

    if spend_col is None:
        st.error("Não encontrei a coluna de gasto (esperado: v_total_item).")
        return

    total_spend = float(df[spend_col].sum()) if len(df) else 0.0
    nf_unicas = int(df[nf_col].nunique()) if nf_col and len(df) else 0
    forn_ativos = int(df[forn_col].nunique()) if forn_col and len(df) else 0
    itens_distintos = int(df["desc_prod"].nunique()) if "desc_prod" in df.columns and len(df) else 0

    # Saving potencial (se existir no df_final)
    saving_pot = 0.0
    if isinstance(df_final, pd.DataFrame) and "Saving_Potencial" in df_final.columns:
        saving_pot = float(df_final["Saving_Potencial"].fillna(0).sum())

    # Concentração (Top10/Top20) e Tail Spend
    top10_share = 0.0
    tail_share = 0.0
    if forn_col and len(df):
        spend_forn = df.groupby(forn_col)[spend_col].sum().sort_values(ascending=False)
        denom = float(spend_forn.sum())
        if denom > 0:
            top10_share = float(spend_forn.head(10).sum() / denom)
            top20_share = float(spend_forn.head(20).sum() / denom)
            tail_share = float(1 - top20_share)

    # KPI row
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("💰 Gasto", format_brl(total_spend))
    k2.metric("🧾 NFs", f"{nf_unicas:,}".replace(",", "."))
    k3.metric("🏢 Fornecedores", f"{forn_ativos:,}".replace(",", "."))
    k4.metric("📦 Itens", f"{itens_distintos:,}".replace(",", "."))
    k5.metric("🎯 Saving Pot.", format_brl(saving_pot))
    k6.metric("🧲 Top 10 Share", format_perc(top10_share))

    st.caption(f"Tail spend (fora Top 20 fornecedores): **{format_perc(tail_share)}**" if forn_col else "")

    st.divider()

    # -------------------------
    # Gráficos (Faixa 2)
    # -------------------------
    left, right = st.columns([1.2, 1.0])

    # (A) Composição por categoria (Treemap) - substitui o Sunburst poluído
    with left:
        st.subheader("Composição do gasto por categoria")
        if cat_col:
            df_cat = (
                df.groupby(cat_col, dropna=False)[spend_col]
                .sum()
                .reset_index()
                .sort_values(spend_col, ascending=False)
            )

            # Evita rótulos NaN
            df_cat[cat_col] = df_cat[cat_col].fillna("SEM CATEGORIA").astype(str)

            fig_tree = px.treemap(
                df_cat,
                path=[cat_col],
                values=spend_col,
            )
            fig_tree.update_layout(
                template="plotly_white",
                height=380,
                margin=dict(t=10, l=10, r=10, b=10),
            )
            st.plotly_chart(fig_tree, use_container_width=True)
        else:
            st.info("Coluna de categoria não encontrada. (Esperado: Categoria)")

    # (B) Concentração de fornecedores (ranking) - visão de prioridade
    with right:
        st.subheader("Concentração de gasto (Top fornecedores)")
        if forn_col:
            spend_forn = df.groupby(forn_col)[spend_col].sum().sort_values(ascending=False)
            view = spend_forn.head(15).reset_index()
            view.columns = ["Fornecedor", "Gasto"]
            # encurta nomes muito longos (sem perder a leitura)
            view["Fornecedor"] = view["Fornecedor"].astype(str).apply(
                lambda x: x[:42] + "…" if len(x) > 43 else x
            )
            view = view.sort_values("Gasto", ascending=True)

            fig_rank = px.bar(
                view,
                x="Gasto",
                y="Fornecedor",
                orientation="h",
                text="Gasto",
            )
            fig_rank.update_traces(texttemplate="%{text:.2s}", textposition="outside", cliponaxis=False)
            fig_rank.update_layout(
                template="plotly_white",
                height=380,
                margin=dict(t=10, l=10, r=10, b=10),
                showlegend=False,
                xaxis_title="R$",
                yaxis_title="",
            )
            st.plotly_chart(fig_rank, use_container_width=True)
        else:
            st.info("Coluna de fornecedor não encontrada. (Esperado: nome_emit)")

    st.divider()

    # -------------------------
    # Tendência (Faixa 3)
    # -------------------------
    st.subheader("📅 Tendência mensal do gasto")

    if mes_col:
        df_monthly = (
            df.groupby(mes_col)[spend_col]
            .sum()
            .reset_index()
            .sort_values(mes_col)
        )
        df_monthly.columns = ["Mes", "Gasto"]

        # Insight simples: variação do último mês vs anterior (se existir)
        insight = ""
        if len(df_monthly) >= 2:
            last = float(df_monthly["Gasto"].iloc[-1])
            prev = float(df_monthly["Gasto"].iloc[-2])
            if prev != 0:
                mom = (last / prev) - 1
                insight = f"Variação último mês vs anterior: **{format_perc(mom)}**"

        fig_trend = px.line(df_monthly, x="Mes", y="Gasto", markers=True)
        fig_trend.update_layout(
            template="plotly_white",
            height=320,
            xaxis_title="",
            yaxis_title="R$",
            margin=dict(t=10, l=10, r=10, b=10),
        )
        st.plotly_chart(fig_trend, use_container_width=True)
        if insight:
            st.caption(insight)
    else:
        st.info("Coluna de mês/ano não encontrada. (Esperado: mes_ano)")

    st.divider()

    # -------------------------
    # Ação (Faixa 4) - oportunidades
    # -------------------------
    st.subheader("🔎 Onde agir agora: Top oportunidades")
    st.caption("Itens com maior saving potencial (se disponível).")

    if isinstance(df_final, pd.DataFrame) and "Saving_Potencial" in df_final.columns:
        cols_show = []
        for c in ["desc_prod", "Categoria", "Total_Gasto", "Saving_Potencial", "Ultimo_Forn", "Ultima_Data", "Menor_Preco", "Qtd_Total"]:
            if c in df_final.columns:
                cols_show.append(c)

        view_ops = df_final.copy()
        view_ops["Saving_Potencial"] = view_ops["Saving_Potencial"].fillna(0)
        view_ops = view_ops.sort_values("Saving_Potencial", ascending=False).head(20)

        # Formata campos monetários para leitura rápida
        if "Total_Gasto" in view_ops.columns:
            view_ops["Total_Gasto"] = view_ops["Total_Gasto"].apply(format_brl)
        view_ops["Saving_Potencial"] = view_ops["Saving_Potencial"].apply(format_brl)

        st.dataframe(
            view_ops[cols_show],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Saving_Potencial não encontrado no df_final. (Verifique processamento/colunas)")
