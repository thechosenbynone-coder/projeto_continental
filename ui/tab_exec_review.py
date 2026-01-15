import streamlit as st
import plotly.express as px
import pandas as pd


def _brl(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"


def render_tab_exec_review(df_ano: pd.DataFrame, df_grouped: pd.DataFrame):
    st.markdown("## 📌 Sumário Executivo")
    st.caption("Visão consolidada para decisão: estado atual, oportunidades, riscos e direcionamento.")

    # ==============================
    # KPIs – FAIXA 1 (HIERARQUIA)
    # ==============================
    gasto_total = df_ano["v_total_item"].sum() if "v_total_item" in df_ano.columns else 0
    imposto_total = df_ano["Imposto_Total"].sum() if "Imposto_Total" in df_ano.columns else 0
    carga_tributaria = (imposto_total / gasto_total) if gasto_total > 0 else 0

    saving_equalizado = (
        df_grouped["Saving_Equalizado"].sum()
        if isinstance(df_grouped, pd.DataFrame) and "Saving_Equalizado" in df_grouped.columns
        else 0
    )

    gasto_critico = 0
    if "Categoria" in df_ano.columns:
        gasto_critico = df_ano[
            df_ano["Categoria"].astype(str).str.contains("CRÍTICO", na=False)
        ]["v_total_item"].sum()

    # Top 10 Share (concentração)
    top10_share = 0.0
    if "nome_emit" in df_ano.columns and gasto_total > 0:
        spend_forn = df_ano.groupby("nome_emit")["v_total_item"].sum().sort_values(ascending=False)
        if float(spend_forn.sum()) > 0:
            top10_share = float(spend_forn.head(10).sum() / float(spend_forn.sum()))

    c1, c2, c3, c4 = st.columns([1.2, 1.2, 1.2, 1])

    with c1:
        st.metric(
            "💰 Gasto Total",
            _brl(gasto_total),
            help=(
                "Valor total gasto no período selecionado. "
                "Representa o impacto financeiro direto das compras realizadas."
            ),
        )
        st.caption(
            f"Top 10 Share: **{top10_share*100:.1f}%**  \n"
            "ⓘ Percentual do gasto concentrado nos 10 maiores fornecedores."
        )

    c2.metric(
        "🎯 Oportunidade de Saving",
        _brl(saving_equalizado),
        help=(
            "Estimativa de economia baseada na equalização do preço da última compra "
            "em relação ao preço médio histórico do item, considerando o volume do período."
        ),
    )

    c3.metric(
        "⚠️ Gasto com Itens Críticos",
        _brl(gasto_critico),
        help=(
            "Total gasto em itens classificados como críticos "
            "(impacto operacional, segurança, compliance ou continuidade)."
        ),
    )

    with c4:
        st.metric(
            "🏛️ Imposto Total",
            _brl(imposto_total),
            help=(
                "Total de impostos incidentes sobre as compras do período "
                "(ICMS, IPI, PIS, COFINS, conforme disponibilidade dos dados)."
            ),
        )
        st.caption(
            f"Carga tributária: **{carga_tributaria*100:.1f}%**  \n"
            "ⓘ Percentual dos impostos em relação ao gasto total."
        )

    st.divider()

    # ==============================
    # TENDÊNCIA – FAIXA 2
    # ==============================
    st.subheader("📈 Tendência mensal: Gasto x Imposto")

    if "mes_ano" in df_ano.columns:
        df_trend = (
            df_ano.groupby("mes_ano", dropna=False)
            .agg(
                Gasto=("v_total_item", "sum"),
                Imposto=("Imposto_Total", "sum") if "Imposto_Total" in df_ano.columns else ("v_total_item", "sum"),
            )
            .reset_index()
            .sort_values("mes_ano")
        )

        fig_trend = px.line(
            df_trend,
            x="mes_ano",
            y=["Gasto", "Imposto"],
            markers=True,
        )
        fig_trend.update_layout(
            template="plotly_white",
            height=360,
            xaxis_title="",
            yaxis_title="R$",
            legend_title_text="",
        )

        st.plotly_chart(fig_trend, use_container_width=True)

        if len(df_trend) >= 2:
            last = float(df_trend.iloc[-1]["Gasto"])
            prev = float(df_trend.iloc[-2]["Gasto"])
            if prev > 0:
                mom = (last / prev - 1) * 100
                st.caption(f"Variação do último mês vs anterior: **{mom:.1f}%**")

    st.divider()

    # ==============================
    # EXPLICAÇÃO DO GASTO – FAIXA 3
    # ==============================
    left, right = st.columns(2)

    with left:
        st.subheader("Composição do gasto por categoria")
        if "Categoria" in df_ano.columns:
            df_cat = (
                df_ano.groupby("Categoria")["v_total_item"]
                .sum()
                .reset_index()
                .sort_values("v_total_item", ascending=False)
            )

            fig_tree = px.treemap(
                df_cat,
                path=["Categoria"],
                values="v_total_item",
            )
            fig_tree.update_layout(
                template="plotly_white",
                height=360,
                margin=dict(t=10, l=10, r=10, b=10),
            )
            st.plotly_chart(fig_tree, use_container_width=True)

    with right:
        st.subheader("Concentração por fornecedor (Top 10)")
        if "nome_emit" in df_ano.columns:
            df_forn = (
                df_ano.groupby("nome_emit")["v_total_item"]
                .sum()
                .sort_values(ascending=False)
                .head(10)
                .reset_index()
            )
            df_forn = df_forn.sort_values("v_total_item")

            fig_rank = px.bar(
                df_forn,
                x="v_total_item",
                y="nome_emit",
                orientation="h",
            )
            fig_rank.update_layout(
                template="plotly_white",
                height=360,
                xaxis_title="R$",
                yaxis_title="",
                showlegend=False,
            )
            st.plotly_chart(fig_rank, use_container_width=True)

    st.divider()

    # ==============================
    # AÇÃO GUIADA – FAIXA 4
    # ==============================
    st.subheader("🎯 Onde agir agora (Top 5 oportunidades)")
    st.caption(
        "Oportunidades baseadas na comparação entre o último preço pago "
        "e o preço médio histórico do item. Detalhamento completo no Cockpit."
    )

    if not isinstance(df_grouped, pd.DataFrame) or "Saving_Equalizado" not in df_grouped.columns:
        st.info("Saving equalizado não disponível.")
        return

    ops = df_grouped.copy()
    ops["Saving_Equalizado"] = pd.to_numeric(ops["Saving_Equalizado"], errors="coerce").fillna(0)
    ops = ops[ops["Saving_Equalizado"] > 10].sort_values("Saving_Equalizado", ascending=False).head(5)

    if ops.empty:
        st.info("Nenhuma oportunidade relevante encontrada neste recorte.")
        return

    cols_show = [
        c
        for c in [
            "desc_prod",
            "Preco_Medio_Historico",
            "Ultimo_Preco",
            "Saving_Equalizado",
            "Qtd_Compras",
        ]
        if c in ops.columns
    ]

    st.dataframe(
        ops[cols_show],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Preco_Medio_Historico": st.column_config.NumberColumn("Preço Médio Hist.", format="R$ %.2f"),
            "Ultimo_Preco": st.column_config.NumberColumn("Último Preço", format="R$ %.2f"),
            "Saving_Equalizado": st.column_config.NumberColumn("Oportunidade Saving", format="R$ %.2f"),
            "Qtd_Compras": st.column_config.NumberColumn("Qtd Compras", format="%.0f"),
        },
    )
