import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import backtrader as bt
from common.data import csv_path, select_window

# Rows the backtest runs on: "test" (out-of-sample, default), "train" or "full".
EVALUATION_WINDOW = "test"

# --------------------------------------------------------------------
# 1. Carregar el CSV i preparar les dades en un DataFrame de pandas
# --------------------------------------------------------------------
fitxer_csv = csv_path('AAPL')
df = pd.read_csv(fitxer_csv)

# Eliminar la primera columna "Unnamed: 0" si apareix
df.drop(df.columns[0], axis=1, inplace=True)

# Establir la columna "Date" (o la corresponent) com a índex i convertir a datetime
df.set_index(df.columns[0], inplace=True)
df.index = pd.to_datetime(df.index)

# Crear les columnes de BULL, BEAR i finalment la BBr
df["BULL"] = 0.33 * (df["positivePartscr"] + df["certaintyPartscr"] + df["finhypePartscr"])
df["BEAR"] = 0.33 * (df["negativePartscr"] + df["uncertaintyPartscr"] + df["findownPartscr"])
df["BBr"] = 100 * df["BULL"] / (df["BULL"] + df["BEAR"])
df.loc[(df["BULL"] + df["BEAR"]) == 0, "BBr"] = 50  # no sentiment -> neutral 50 (0/0 gives NaN)

# Calcular el retorn diari utilitzant la columna 'Close' (pots canviar a 'Adj Close')
df["DailyReturn"] = df["Adj Close"].pct_change() * 100  # Retorn diari en percentatge

print(df[(df["BULL"] + df["BEAR"]) == 0])
print("El nombre de files amb sentiment NULL és:", df[(df["BULL"] + df["BEAR"]) == 0].shape[0])

# --------------------------------------------------------------------
# 2. Definir la classe de dades personalitzada a partir de Pandas
# --------------------------------------------------------------------
class MyPandasDataSentiment3(bt.feeds.PandasData):
    """
    Feed de dades personalitzat que inclou la línia 'bbr' 
    mapejada a la columna 'BBr' del nostre DataFrame.
    """
    lines = ('bbr',)
    params = (
        ('datetime', None),
        ('open', 'Open'),
        ('high', 'High'),
        ('low', 'Low'),
        ('close', 'Close'),
        ('volume', 'Volume'),
        ('openinterest', -1),
        ('bbr', 'BBr'),
    )

# --------------------------------------------------------------------
# 3. Definir l'estratègia amb escalat de posicions
# --------------------------------------------------------------------
class Sentiment3StatesStrategy(bt.Strategy):
    params = (
        ('upper_threshold', 65),
        ('lower_threshold', 30),
        ('neutral_lower', 45),
        ('neutral_upper', 53),
        ('allow_short', True),
    )

    def __init__(self):
        self.bbr = self.datas[0].bbr
        self.initial_cash = self.broker.getvalue()
        self.current_invested_fraction = 0.0
        self.total_trades = 0  # Comptador d'operacions
        self.total_commission = 0  # Comptador de comissions

    def notify_order(self, order):
        if order.status in [order.Completed]:
            self.total_trades += 1
            self.total_commission += order.executed.comm

    def buy_fraction(self, frac):
        value_to_invest = self.initial_cash * frac
        price = self.data.close[0]
        size = int(value_to_invest / price)
        if size > 0:
            self.buy(size=size)

    def sell_fraction(self, frac):
        value_to_invest = self.initial_cash * frac
        price = self.data.close[0]
        size = int(value_to_invest / price)
        if size > 0:
            self.sell(size=size)

    def next(self):
        bbr_now = self.bbr[0]

        if self.params.neutral_lower < bbr_now < self.params.neutral_upper:
            if self.current_invested_fraction != 0:
                self.close()
                self.current_invested_fraction = 0.0
            return

        if bbr_now > self.params.upper_threshold:
            if self.current_invested_fraction <= 0:
                self.close()
                self.current_invested_fraction = 0.0
                self.buy_fraction(0.60)  
                self.current_invested_fraction = 0.60
            else:
                if self.current_invested_fraction < 0.90:
                    self.buy_fraction(0.10)
                    self.current_invested_fraction += 0.10

        elif bbr_now < self.params.lower_threshold:
            if self.params.allow_short:
                if self.current_invested_fraction >= 0:
                    self.close()
                    self.current_invested_fraction = 0.0
                    self.sell_fraction(0.60)
                    self.current_invested_fraction = -0.60
                else:
                    if abs(self.current_invested_fraction) < 0.90:
                        self.sell_fraction(0.10)
                        self.current_invested_fraction -= 0.10
            else:
                if self.current_invested_fraction != 0:
                    self.close()
                    self.current_invested_fraction = 0.0

# --------------------------------------------------------------------
# 4. Configurar i executar Backtrader
# --------------------------------------------------------------------
if __name__ == '__main__':
    cerebro = bt.Cerebro()
    strategy = cerebro.addstrategy(
        Sentiment3StatesStrategy,
        upper_threshold=60,
        lower_threshold=35,
        allow_short=True
    )
    
    data = MyPandasDataSentiment3(dataname=select_window(df, EVALUATION_WINDOW))
    cerebro.adddata(data)
    cerebro.broker.setcash(100000.0)
    cerebro.broker.setcommission(commission=0.000)
    
    print('Valor inicial del Portafoli: %.2f' % cerebro.broker.getvalue())
    strategies = cerebro.run()
    strategy = strategies[0]
    print('Valor final del Portafoli: %.2f' % cerebro.broker.getvalue())
    print(f'Nombre total d\'operacions realitzades: {strategy.total_trades}')
    print(f'Total de comissions pagades: {strategy.total_commission:.2f}')
    
    cerebro.plot()
