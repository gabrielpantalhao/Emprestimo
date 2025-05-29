from shiny import App, ui, render, reactive
import pandas as pd
import math
import matplotlib.pyplot as plt


app_ui = ui.page_fluid(
    ui.h2("Simulador de Empréstimo com Parcelas"),
    
    ui.input_numeric("valor", "Valor do empréstimo (R$)", 1000, min=1),
    ui.input_numeric("juros", "Taxa de juros mensal (%)", 2, min=0),
    ui.input_numeric("parcelas", "Número de parcelas (meses)", 12, min=1),
    
    ui.hr(),
    ui.output_table("tabela_parcelas"),
    ui.output_text("total_pago"),
    ui.output_plot("grafico_divida")
)


def server(input, output, session):
    

    @reactive.Calc
    def tabela():
        P = input.valor()                
        juros_percent = input.juros()     
        n = input.parcelas()              

        i = juros_percent / 100           

        dados = []

        if i == 0:
       
            parcela = P / n
            for mes in range(1, n + 1):
                saldo = P - parcela * mes
                dados.append({"Mês": mes, "Parcela (R$)": round(parcela, 2), "Dívida Restante (R$)": max(0, round(saldo, 2))})
        else:
   
            parcela = P * (i * (1 + i)**n) / ((1 + i)**n - 1)
            saldo_restante = P
            for mes in range(1, n + 1):
                juros_mes = saldo_restante * i
                amortizacao = parcela - juros_mes
                saldo_restante -= amortizacao
                dados.append({"Mês": mes, "Parcela (R$)": round(parcela, 2), "Dívida Restante (R$)": max(0, round(saldo_restante, 2))})
        
        return pd.DataFrame(dados)


    @output
    @render.table
    def tabela_parcelas():
        return tabela()


    @output
    @render.text
    def total_pago():
        df = tabela()
        total = df["Parcela (R$)"].sum()
        return f"Total pago ao final: R$ {total:.2f}"

  
    @output
    @render.plot
    def grafico_divida():
        df = tabela()
        plt.figure(figsize=(8, 4))
        plt.plot(df["Mês"], df["Dívida Restante (R$)"], marker='o', color='darkred')
        plt.title("Evolução da Dívida")
        plt.xlabel("Mês")
        plt.ylabel("Dívida Restante (R$)")
        plt.grid(True)
        plt.tight_layout()


app = App(app_ui, server)


app.run(port=8080)

