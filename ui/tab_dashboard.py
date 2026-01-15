import streamlit as st
import plotly.express as px
import pandas as pd


def _safe_col(df: pd.DataFrame, *candidates: str):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def render_tab_dashboard(df: pd.DataFrame, df_final: pd.DataFrame):
    st.markdown("### 📊 Dashboard de Suprimentos")
    st.caption("Radar rápido: onde está o gasto, onde concentra e um teaser de oportunidades (detalhe no Cockpit).")

    # -------------------------
    # Descobrir colunas principais
    # -------------------------
    spend_col = _safe_col(df, "v_total_item", "Total_Gasto", "Gasto")
    nf_col = _safe_col(df, "n_nf_clean", "n_nf")
    forn_col = _safe_col(df, "nome_emit", "Fornecedor", "Nome_Fornecedor")
    cat_col = _safe_col(df, "Categoria", "categoria")
    mes_col = _safe_col(df, "mes_ano", "Mes_Ano", "mesano")

    if spend_col is None:
        st.error("Não encontrei a coluna de gasto (esperado: v_total_item).")
        return

    # -------------------------
    # KPIs (Faixa 1)
    # -------------------------
    total_spend = float(df[spend_col].sum()) if len(df) else 0.0
    nf_unicas = int(df[nf_col].nunique()) if nf_col and len(df) else 0
    forn_ativos = int(df[forn_col].nunique()) if forn_col and len(df) else 0
    itens_distintos = int(df["desc_prod"].nunique()) if "desc_prod" in df.columns and len(df) else 0

    saving_pot_total = 0.0
    if isinstance(df_final, pd.DataFrame) and "Saving_Potencial" in df_final.columns:
        saving_pot_total = float(df_final["Saving_Potencial"].fillna(0).sum())

    top10_share = 0.0
    tail_share = 0.0
    if forn_col and len(df):
        spend_forn = df.groupby(forn_col)[spend_col].sum().sort_values(ascending=False)
        denom = float(spend_forn.sum())
        if denom > 0:
            top10_share = float(spend_forn.head(10).sum() / denom)
            top20_share = float(spend_forn.head(20).sum() / denom)
            tail_share = float(1 - top20_share)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("💰 Gasto", f"R$ {total_spend:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    c2.metric("🧾 NFs", f"{nf_unicas:,}".replace(",", "."))
    c3.metric("🏢 Fornecedores", f"{forn_ativos:,}".replace(",", "."))
    c4.metric("📦 Itens", f"{itens_distintos:,}".replace(",", "."))
    c5.metric("🎯 Saving Pot.", f"R$ {saving_pot_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    c6.metric("🧲 Top 10 Share", f"{top10_share*100:.1f}%")

    st.caption(f"Tail spend (fora Top 20 fornecedores): **{tail_share*100:.1f}%**" if forn_col else "")

    st.divider()

    # -------------------------
    # Gráficos (Faixa 2)
    # -------------------------
    left, right = st.columns([1.2, 1.0])

    with left:
        st.subheader("Composição do gasto por categoria")
        if cat_col:
            df_cat = (
                df.groupby(cat_col, dropna=False)[spend_col]
                .sum()
                .reset_index()
                .sort_values(spend_col, ascending=False)
            )
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

    with right:
        st.subheader("Concentração de gasto (Top fornecedores)")
        if forn_col:
            spend_forn = df.groupby(forn_col)[spend_col].sum().sort_values(ascending=False)
            view = spend_forn.head(15).reset_index()
            view.columns = ["Fornecedor", "Gasto"]
            view["Fornecedor"] = view["Fornecedor"].astype(str).apply(lambda x: x[:42] + "…" if len(x) > 43 else x)
            view = view.sort_values("Gasto", ascending=True)

            fig_rank = px.bar(view, x="Gasto", y="Fornecedor", orientation="h")
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

        insight = ""
        if len(df_monthly) >= 2:
            last = float(df_monthly["Gasto"].iloc[-1])
            prev = float(df_monthly["Gasto"].iloc[-2])
            if prev != 0:
                mom = (last / prev) - 1
                insight = f"Variação último mês vs anterior: **{mom*100:.1f}%**"

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
    # Teaser (Faixa 4) - Top 5 oportunidades (detalhe no Cockpit)
    # -------------------------
    st.subheader("🎯 Top 5 oportunidades (teaser)")
    st.caption("Detalhamento completo e filtros avançados na aba **Cockpit**.")

    if not isinstance(df_final, pd.DataFrame) or "Saving_Potencial" not in df_final.columns:
        st.info("Saving_Potencial não encontrado no df_final. (Verifique processamento/colunas)")
        return

    preferred_order = [
        "desc_prod",
        "Categoria",
        "Qtd_Total",
        "Menor_Preco",
        "Ultimo_Preco",
        "Preco_Medio",
        "Total_Gasto",
        "Saving_Potencial",
        "Ultimo_Forn",
        "Ultima_Data",
    ]
    cols_show = [c for c in preferred_order if c in df_final.columns]

    view_ops = df_final.copy()
    view_ops["Saving_Potencial"] = view_ops["Saving_Potencial"].fillna(0)

    # pega top 5, mas evita poluir com zeros se houver poucas oportunidades reais
    view_ops = view_ops.sort_values("Saving_Potencial", ascending=False)
    view_ops = view_ops.head(5)

    # Config monetária correta (mantém número como número)
    money_cfg = {
        "Total_Gasto": st.column_config.NumberColumn("Total_Gasto", format="R$ %.2f"),
        "Menor_Preco": st.column_config.NumberColumn("Menor_Preco", format="R$ %.2f"),
        "Ultimo_Preco": st.column_config.NumberColumn("Ultimo_Preco", format="R$ %.2f"),
        "Preco_Medio": st.column_config.NumberColumn("Preco_Medio", format="R$ %.2f"),
        "Saving_Potencial": st.column_config.NumberColumn("Saving_Potencial", format="R$ %.2f"),
        "Qtd_Total": st.column_config.NumberColumn("Qtd_Total", format="%.0f"),
    }

    st.dataframe(
        view_ops[cols_show],
        use_container_width=True,
        hide_index=True,
        column_config=money_cfg,
    )
