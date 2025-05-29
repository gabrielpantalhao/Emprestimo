from shiny import App, ui, render, reactive
import pandas as pd
import math
import matplotlib.pyplot as plt
from bcb import sgs
import io

# Função para buscar taxa de juros do BCB (código 20749: empréstimo pessoal não consignado)
def obter_taxa_juros_bcb():
    try:
        taxa = sgs.get({'TaxaJuros': 20749}, last=1)
        return taxa['TaxaJuros'].iloc[0] / 12
    except:
        return 2.0

# Função para buscar IPCA (código 433: IPCA variação mensal)
def obter_ipca_bcb():
    try:
        ipca = sgs.get({'IPCA': 433}, last=12)
        return ipca['IPCA'].mean() / 100
    except:
        return 0.004

# Sugestão de parcelas baseado na renda
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

# Cálculo de quitação antecipada
def calcular_quitacao_antecipada(P, i, n, meses_restantes):
    if meses_restantes >= n:
        return P
    if i == 0:
        return P * (meses_restantes / n)
    else:
        parcela = P * (i * (1 + i)**n) / ((1 + i)**n - 1)
        saldo = parcela * ((1 - (1 + i)**-(meses_restantes)) / i)
        return round(saldo, 2)


# Comparação de prazos
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

# Interface do usuário com CSS
app_ui = ui.page_fluid(
    ui.include_css("style.css"),
    ui.h2("Simulador de Empréstimo com Parcelas", class_="titulo"),

    ui.div(
        ui.input_numeric("valor", "Valor do empréstimo (R$)", 1000, min=1),
        ui.input_select("fonte_juros", "Fonte da taxa de juros", choices=["Manual", "Banco Central"]),
        ui.output_ui("juros_ui"),  # Container dinâmico para input ou texto da taxa de juros
        ui.input_numeric("renda", "Renda mensal (R$)", 3000, min=1),
        ui.input_numeric("percent_renda", "Percentual máximo para parcela (%)", 30, min=1, max=100),
        ui.input_numeric("parcelas", "Número de parcelas (meses)", 12, min=1, max=84),
        ui.input_numeric("meses_restantes", "Meses restantes para quitação", 6, min=1),
        class_="form-container"
    ),

    ui.hr(),
    ui.output_text("sugestao_parcelas"),
    ui.output_text("total_pago"),
    ui.output_text("valor_quitacao"),
    ui.hr(),

    ui.div(
        ui.output_table("tabela_parcelas"),
        ui.output_plot("grafico_divida"),
        class_="output-container"
    ),

    ui.div(
        ui.output_table("tabela_comparacao"),
        ui.output_plot("grafico_comparacao"),
        class_="output-container"
    ),

    ui.download_button("download_csv", "Baixar Tabela como CSV", class_="btn-download")
)

# Servidor
def server(input, output, session):
    @output
    @render.ui
    def juros_ui():
        fonte = input.fonte_juros()
        if fonte == "Manual":
            # Input numérico para taxa de juros mensal
            return ui.input_numeric("juros", "Taxa de juros mensal (%)", value=obter_taxa_juros_bcb(), min=0, step=0.1)
        else:
            # Texto mostrando taxa puxada da API
            taxa_bcb = obter_taxa_juros_bcb()
            return ui.div(
                ui.tags.strong(f"Taxa de juros mensal obtida do Banco Central: {taxa_bcb:.2f}%")
            )

    @reactive.Calc
    def tabela():
        P = input.valor()
        # Usar juros conforme escolha do usuário
        if input.fonte_juros() == "Manual":
            juros_percent = input.juros()
            if juros_percent is None:
                juros_percent = obter_taxa_juros_bcb()
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
        if input.fonte_juros() == "Manual":
            juros_percent = input.juros()
            if juros_percent is None:
                juros_percent = obter_taxa_juros_bcb()
        else:
            juros_percent = obter_taxa_juros_bcb()
        renda = input.renda()
        percent_renda = input.percent_renda()
        n_sugerido = sugerir_parcelas(P, juros_percent / 100, renda, percent_renda)
        return f"Sugestão: {n_sugerido} parcelas para manter a parcela dentro de {percent_renda}% da sua renda."

    @output
    @render.text
    def valor_quitacao():
        P = input.valor()
        if input.fonte_juros() == "Manual":
            juros_percent = input.juros()
            if juros_percent is None:
                juros_percent = obter_taxa_juros_bcb()
        else:
            juros_percent = obter_taxa_juros_bcb()
        i = juros_percent / 100
        n = input.parcelas()
        meses_restantes = input.meses_restantes()
        valor = calcular_quitacao_antecipada(P, i, n, meses_restantes)
        return f"Valor para quitação antecipada: R$ {valor:.2f}"

    @output
    @render.table
    def tabela_comparacao():
        P = input.valor()
        if input.fonte_juros() == "Manual":
            juros_percent = input.juros()
            if juros_percent is None:
                juros_percent = obter_taxa_juros_bcb()
        else:
            juros_percent = obter_taxa_juros_bcb()
        i = juros_percent / 100
        return comparar_custos(P, i)

    @output
    @render.plot
    def grafico_divida():
        df = tabela()
        if "Erro" in df.columns:
            return
        plt.figure(figsize=(8, 4))
        plt.plot(df["Mês"], df["Dívida Restante (R$)"], marker='o', color='darkred')
        plt.title("Evolução da Dívida")
        plt.xlabel("Mês")
        plt.ylabel("Dívida Restante (R$)")
        plt.grid(True)
        plt.tight_layout()
        return plt.gcf()

    @output
    @render.plot
    def grafico_comparacao():
        P = input.valor()
        if input.fonte_juros() == "Manual":
            juros_percent = input.juros()
            if juros_percent is None:
                juros_percent = obter_taxa_juros_bcb()
        else:
            juros_percent = obter_taxa_juros_bcb()
        i = juros_percent / 100
        prazos = [6, 12, 24, 36]

        plt.figure(figsize=(10, 6))
        for n in prazos:
            dados = []
            saldo_restante = P
            for mes in range(1, n + 1):
                if i == 0:
                    parcela = P / n
                    saldo = P - parcela * mes
                else:
                    parcela = P * (i * (1 + i)**n) / ((1 + i)**n - 1)
                    juros_mes = saldo_restante * i
                    amortizacao = parcela - juros_mes
                    saldo_restante -= amortizacao
                dados.append(max(0, round(saldo_restante, 2)))
            plt.plot(range(1, n + 1), dados, marker='o', label=f"{n} parcelas")

        plt.title("Comparação da Dívida por Prazo")
        plt.xlabel("Mês")
        plt.ylabel("Dívida Restante (R$)")
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        return plt.gcf()

    @output
    @render.download(filename="tabela_parcelas.csv")
    def download_csv():
        df = tabela()
        if "Erro" in df.columns:
            return
        with io.StringIO() as csv_buffer:
            df.to_csv(csv_buffer, index=False)
            return csv_buffer.getvalue()

# Criar e rodar o app
app = App(app_ui, server)
app.run(port=8080)
