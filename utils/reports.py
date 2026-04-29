import io

import matplotlib.pyplot as plt
import pandas as pd


def _format_currency(value):
    formatted = f"R$ {float(value):,.2f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def generate_expense_pie_chart(transactions):
    if not transactions:
        return None

    df = pd.DataFrame(transactions)
    expenses = df[df["type"] == "expense"]

    if expenses.empty:
        return None

    expenses = expenses.copy()
    expenses["amount"] = expenses["amount"].astype(float)
    expenses["category"] = expenses["category"].fillna("sem categoria")
    category_totals = expenses.groupby("category")["amount"].sum().sort_values(ascending=False)
    total = category_totals.sum()

    colors = [
        "#2563eb",
        "#16a34a",
        "#f97316",
        "#dc2626",
        "#7c3aed",
        "#0891b2",
        "#ca8a04",
        "#db2777",
    ]

    fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=160)
    wedges, _, autotexts = ax.pie(
        category_totals,
        labels=None,
        colors=colors[: len(category_totals)],
        autopct=lambda pct: f"{pct:.1f}%" if pct >= 3 else "",
        startangle=90,
        pctdistance=0.78,
        wedgeprops={"width": 0.42, "edgecolor": "white", "linewidth": 2},
        textprops={"fontsize": 9, "color": "#111827"},
    )

    for text in autotexts:
        text.set_fontweight("bold")

    ax.text(
        0,
        0.06,
        "Gastos",
        ha="center",
        va="center",
        fontsize=10,
        color="#475569",
        fontweight="bold",
    )
    ax.text(
        0,
        -0.08,
        _format_currency(total),
        ha="center",
        va="center",
        fontsize=11,
        color="#0f172a",
        fontweight="bold",
    )

    legend_labels = [
        f"{category} - {_format_currency(amount)}"
        for category, amount in category_totals.items()
    ]
    ax.legend(
        wedges,
        legend_labels,
        title="Categorias",
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        frameon=False,
        fontsize=8.5,
        title_fontsize=9.5,
    )

    ax.set_title("Distribuição de gastos por categoria", fontsize=12, fontweight="bold", pad=12)
    ax.set_aspect("equal")

    img_buf = io.BytesIO()
    fig.savefig(img_buf, format="png", bbox_inches="tight", facecolor="white")
    img_buf.seek(0)
    plt.close(fig)

    return img_buf
