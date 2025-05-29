from shiny import App, ui, render, reactive
import pandas as pd
from shiny.types import FileInfo
import plotly.graph_objs as go
from shinywidgets import output_widget, render_widget
import shinywidgets

# Fontes alternativas (mocks)
def obter_taxa_juros_bcb():
    return 2.0  # mock para testes offline

def obter_ipca_bcb():
    return 0.004  # mock para testes offline

def sugerir_parcelas(P, i, renda, percent_renda):
    if renda <= 0 or percent_renda <= 0:
        return 1
    max_parcela = renda * (percent_renda / 100)
    n_sugerido = 1
    for n in range(1, 85):
        if i == 0:
            parcela = P / n
        else:
            parcela = P * (i * (1 + i)**n) / ((1 + i)**n - 1)
        if parcela <= max_parcela:
            n_sugerido = n
        else:
            break
    return n_sugerido

def calcular_quitacao_antecipada(P, i, n, meses_restantes):
    if meses_restantes >= n:
        return P
    if i == 0:
        return P * (meses_restantes / n)
    parcela = P * (i * (1 + i)**n) / ((1 + i)**n - 1)
    saldo = parcela * ((1 - (1 + i)**-(meses_restantes)) / i)
    return round(saldo, 2)

def comparar_custos(P, i, prazos=[6, 12, 24, 36]):
    dados = []
    for n in prazos:
        if i == 0:
            parcela = P / n
            total = parcela * n
        else:
            parcela = P * (i * (1 + i)**n) / ((1 + i)**n - 1)
            total = parcela * n
        dados.append({"Parcelas": n, "Parcela Mensal (R$)": round(parcela, 2), "Total Pago (R$)": round(total, 2)})
    return pd.DataFrame(dados)

app_ui = ui.page_fluid(
    ui.include_css("style.css"),

    # Adiciona FontAwesome CDN para usar os ícones
    ui.tags.head(
        ui.tags.link(
            rel="stylesheet",
            href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"
        )
    ),

    ui.tags.script("""
        function toggleTheme() {
            document.body.classList.toggle('dark');
            document.body.classList.toggle('light');
        }
    """),
    ui.tags.script("""
        document.addEventListener("DOMContentLoaded", function() {
            document.body.classList.add("dark");
        });
    """),

    # Logo com ícone FontAwesome dentro de div .logo
    ui.div(
        ui.tags.i(class_="fas fa-money-bill-wave fa-3x", title="Logo Empréstimo"),
    class_="logo"
),



    ui.h2("Simulador de Empréstimo com Parcelas", class_="titulo"),
    ui.tags.button("Alternar Tema", class_="toggle-theme", onclick="toggleTheme()"),

    ui.div(
        ui.input_numeric("valor", "Valor do empréstimo (R$)", 1000, min=1),
        ui.input_select("fonte_juros", "Fonte da taxa de juros", choices=["Manual", "Banco Central"]),
        ui.output_ui("juros_ui"),
        ui.input_numeric("renda", "Renda mensal (R$)", 3000, min=1),
        ui.input_numeric("percent_renda", "Percentual máximo para parcela (%)", 30, min=1, max=100),
        ui.input_numeric("parcelas", "Número de parcelas (meses)", 12, min=1, max=84),
        ui.input_numeric("meses_restantes", "Meses restantes para quitação", 6, min=1),
        class_="form-container"
    ),

    ui.hr(),

    ui.div(ui.output_text("sugestao_parcelas"), class_="resultado"),
    ui.div(ui.output_text("total_pago"), class_="resultado"),
    ui.div(ui.output_text("valor_quitacao"), class_="resultado"),

    ui.hr(),

    ui.div(
        ui.output_table("tabela_parcelas"),
        output_widget("grafico_divida"),
        class_="output-container"
    ),

    ui.div(
        ui.output_table("tabela_comparacao"),
        output_widget("grafico_comparacao"),
        class_="output-container"
    ),

    ui.div(
        ui.download_button("download_csv", ui.HTML('<i class="fas fa-file-csv"></i> Baixar Tabela como CSV'), class_="btn-download")
    )
)

def server(input, output, session):
    @output
    @render.ui
    def juros_ui():
        fonte = input.fonte_juros()
        if fonte == "Manual":
            return ui.input_numeric("juros", "Taxa de juros mensal (%)", value=obter_taxa_juros_bcb(), min=0, step=0.1)
        else:
            taxa_bcb = obter_taxa_juros_bcb()
            return ui.div(ui.tags.strong(f"Taxa de juros mensal obtida do Banco Central: {taxa_bcb:.2f}%"))

    @reactive.Calc
    def tabela():
        P = input.valor()
        if input.fonte_juros() == "Manual":
            juros_percent = input.juros() or obter_taxa_juros_bcb()
        else:
            juros_percent = obter_taxa_juros_bcb()
        n = input.parcelas()
        i = juros_percent / 100
        ipca = obter_ipca_bcb()

        if P <= 0 or n <= 0 or i < 0:
            return pd.DataFrame({"Erro": ["Entradas inválidas"]})

        dados = []
        if i == 0:
            parcela = P / n
            for mes in range(1, n + 1):
                saldo = P - parcela * mes
                parcela_real = parcela / ((1 + ipca) ** mes)
                dados.append({
                    "Mês": mes,
                    "Parcela (R$)": round(parcela, 2),
                    "Parcela Real (R$)": round(parcela_real, 2),
                    "Dívida Restante (R$)": max(0, round(saldo, 2))
                })
        else:
            parcela = P * (i * (1 + i)**n) / ((1 + i)**n - 1)
            saldo_restante = P
            for mes in range(1, n + 1):
                juros_mes = saldo_restante * i
                amortizacao = parcela - juros_mes
                saldo_restante -= amortizacao
                parcela_real = parcela / ((1 + ipca) ** mes)
                dados.append({
                    "Mês": mes,
                    "Parcela (R$)": round(parcela, 2),
                    "Parcela Real (R$)": round(parcela_real, 2),
                    "Dívida Restante (R$)": max(0, round(saldo_restante, 2))
                })
        return pd.DataFrame(dados)

    @output
    @render.table
    def tabela_parcelas():
        return tabela()

    @output
    @render.text
    def total_pago():
        df = tabela()
        if "Erro" in df.columns:
            return "Erro: Verifique as entradas."
        total = df["Parcela (R$)"].sum()
        return f"Total pago ao final: R$ {total:.2f}"

    @output
    @render.text
    def sugestao_parcelas():
        P = input.valor()
        juros_percent = input.juros() if input.fonte_juros() == "Manual" else obter_taxa_juros_bcb()
        renda = input.renda()
        percent_renda = input.percent_renda()
        n_sugerido = sugerir_parcelas(P, juros_percent / 100, renda, percent_renda)
        return f"Sugestão: {n_sugerido} parcelas para manter a parcela dentro de {percent_renda}% da sua renda."

    @output
    @render.text
    def valor_quitacao():
        P = input.valor()
        juros_percent = input.juros() if input.fonte_juros() == "Manual" else obter_taxa_juros_bcb()
        i = juros_percent / 100
        n = input.parcelas()
        meses_restantes = input.meses_restantes()
        valor = calcular_quitacao_antecipada(P, i, n, meses_restantes)
        return f"Valor para quitação antecipada: R$ {valor:.2f}"

    @output
    @render.table
    def tabela_comparacao():
        P = input.valor()
        juros_percent = input.juros() if input.fonte_juros() == "Manual" else obter_taxa_juros_bcb()
        i = juros_percent / 100
        return comparar_custos(P, i)

    @render_widget
    def grafico_divida():
        df = tabela()
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["Mês"], y=df["Dívida Restante (R$)"], fill='tozeroy', mode='lines+markers',
            name="Dívida Restante", line=dict(color='indianred')
        ))
        fig.update_layout(
            title="Evolução da Dívida",
            xaxis_title="Mês",
            yaxis_title="R$",
            template='plotly_white',
            height=400
        )
        return fig

    @render_widget
    def grafico_comparacao():
        P = input.valor()
        juros_percent = input.juros() if input.fonte_juros() == "Manual" else obter_taxa_juros_bcb()
        i = juros_percent / 100
        prazos = [6, 12, 24, 36]
        fig = go.Figure()

        for n in prazos:
            saldo_restante = P
            saldos = []
            for mes in range(1, n + 1):
                if i == 0:
                    parcela = P / n
                    saldo = P - parcela * mes
                else:
                    parcela = P * (i * (1 + i)**n) / ((1 + i)**n - 1)
                    juros_mes = saldo_restante * i
                    amortizacao = parcela - juros_mes
                    saldo_restante -= amortizacao
                    saldo = saldo_restante
                saldos.append(max(0, round(saldo, 2)))

            fig.add_trace(go.Scatter(
                x=list(range(1, n + 1)), y=saldos, mode='lines+markers', name=f"{n} meses"
            ))

        fig.update_layout(
            title="Comparativo de Dívida por Prazo",
            xaxis_title="Mês",
            yaxis_title="R$",
            template='plotly_white',
            height=400
        )
        return fig

    @output
    @render.download(filename="tabela_parcelas.csv")
    def download_csv():
        df = tabela()
        if "Erro" in df.columns:
            return
        return df.to_csv(index=False)

app = App(app_ui, server)

if __name__ == "__main__":
    app.run(port=8080)
