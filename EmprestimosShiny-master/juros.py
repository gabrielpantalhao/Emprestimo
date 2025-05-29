from shiny import App, ui, render
import pandas as pd
import numpy as np

# UI
app_ui = ui.page_fluid(
    ui.tags.head(
        ui.tags.link(rel="stylesheet", href="style.css")
    ),
    ui.div(
        ui.h1("Simulador de Empréstimo", class_="titulo")
    ),
    ui.div(
        {
            "class": "form-container"
        },
        ui.input_numeric("valor_emprestimo", "Valor do Empréstimo (R$)", 10000, min=0, step=100),
        ui.input_numeric("taxa_juros", "Taxa de Juros Mensal (%)", 2.0, min=0, step=0.1),
        ui.input_numeric("numero_parcelas", "Número de Parcelas", 12, min=1, step=1)
    ),
    ui.div(
        {"class": "output-container"},
        ui.output_table("tabela_parcelas")
    ),
    ui.div(
        {"class": "output-container"},
        ui.output_plot("grafico_parcelas")
    ),
    ui.div(
        {"class": "output-container", "style": "text-align: center"},
        ui.download_button("baixar_dados", "Baixar Tabela", class_="btn-download")
    )
)

# Função para calcular parcelas com juros compostos
def calcular_parcelas(valor, juros, n_parcelas):
    taxa = juros / 100
    if taxa == 0:
        parcela = valor / n_parcelas
    else:
        parcela = valor * (taxa * (1 + taxa) ** n_parcelas) / ((1 + taxa) ** n_parcelas - 1)

    saldo_devedor = valor
    dados = []

    for i in range(1, n_parcelas + 1):
        juros_mes = saldo_devedor * taxa
        amortizacao = parcela - juros_mes
        saldo_devedor -= amortizacao
        dados.append({
            "Parcela": i,
            "Valor Parcela (R$)": round(parcela, 2),
            "Juros (R$)": round(juros_mes, 2),
            "Amortização (R$)": round(amortizacao, 2),
            "Saldo Devedor (R$)": round(max(saldo_devedor, 0), 2)
        })

    return pd.DataFrame(dados)

# Server
def server(input, output, session):
    @output
    @render.table
    def tabela_parcelas():
        return calcular_parcelas(
            input.valor_emprestimo(),
            input.taxa_juros(),
            input.numero_parcelas()
        )

    @output
    @render.plot
    def grafico_parcelas():
        import matplotlib.pyplot as plt
        df = calcular_parcelas(
            input.valor_emprestimo(),
            input.taxa_juros(),
            input.numero_parcelas()
        )
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(df["Parcela"], df["Valor Parcela (R$)"], label="Valor Parcela", marker="o")
        ax.plot(df["Parcela"], df["Juros (R$)"], label="Juros", linestyle="--", marker="x")
        ax.plot(df["Parcela"], df["Amortização (R$)"], label="Amortização", linestyle=":", marker="s")
        ax.set_xlabel("Parcela")
        ax.set_ylabel("Valor (R$)")
        ax.set_title("Composição das Parcelas")
        ax.legend()
        ax.grid(True)
        return fig

    @session.download(filename="simulacao_parcelas.csv")
    def baixar_dados():
        df = calcular_parcelas(
            input.valor_emprestimo(),
            input.taxa_juros(),
            input.numero_parcelas()
        )
        yield df.to_csv(index=False)

app = App(app_ui, server)


app.run(port=8080)

