import pandas as pd
import matplotlib.pyplot as plt
import backtrader as bt
from common.data import csv_path, select_window

# Rows the backtest runs on: "test" (out-of-sample, default), "train" or "full".
EVALUATION_WINDOW = "test"

# --------------------------------------------------------------------
# 1. Carregar el CSV i preparar les dades en un DataFrame de pandas
# --------------------------------------------------------------------
fitxer_csv = csv_path('AAPL')
#Amb AAPL obtenim balanç positiu amb [65, 30]
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

print(df[ (df["BULL"] + df["BEAR"]) == 0 ])
print("El nombre de files amb el sentiment NULL és:", df[ (df["BULL"] + df["BEAR"]) == 0 ].shape[0])

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
        ('datetime', None),       # Utilitza l'índex del DataFrame com a data
        ('open', 'Open'),         # Columna per open
        ('high', 'High'),         # Columna per high
        ('low', 'Low'),           # Columna per low
        ('close', 'Close'),       # Columna per close
        ('volume', 'Volume'),     # Columna per volume
        ('openinterest', -1),
        ('bbr', 'BBr'),           # Assignem la columna 'BBr' a la línia 'bbr'
    )

# --------------------------------------------------------------------
# 2b. Definir un Sizer que inverteixi un % del capital disponible
# --------------------------------------------------------------------
class PercentSizer(bt.Sizer):
    """
    Aquest Sizer calcula la quantitat d'unitats a comprar/vendre
    usant un percentatge fix de l'efectiu disponible.
    """
    params = (
        ('perc', 0.20),  # Percentatge de l'efectiu a invertir en cada operació
    )

    def _getsizing(self, comminfo, cash, data, isbuy):
        # Percentatge del cash que volem utilitzar
        target_cash = cash * self.params.perc
        price = data.close[0] if data.close[0] else 1
        size = int(target_cash / price)
        # Evitem problemes amb valors negatius
        return max(size, 0)

# --------------------------------------------------------------------
# 3. Definir l'estratègia amb 3 estats (compra, venda, neutre)
# --------------------------------------------------------------------
class Sentiment3StatesStrategy(bt.Strategy):
    params = (
        ('upper_threshold', 90),   # Llindar superior (sobrecompra)
        ('lower_threshold', 30),   # Llindar inferior (sobrevenda)
        ('allow_short', False),     # Permetre posicions curtes
    )

    def __init__(self):
        self.bbr = self.datas[0].bbr   # Accés a la columna BBr
        self.current_pos = 0           # 1 = llarg, -1 = curt, 0 = fora del mercat

    def next(self):
        bbr_now = self.bbr[0]

        # Si BBr supera el llindar superior → senyal de compra
        if bbr_now > self.params.upper_threshold:
            if self.current_pos != 1:
                if self.current_pos == -1:
                    self.close()  # Tancar curt si n'hi ha
                self.buy()        # El sizer decidirà quantes unitats comprar
                self.current_pos = 1

        # Si BBr baixa per sota del llindar inferior → senyal de venda (curt)
        elif bbr_now < self.params.lower_threshold:
            if self.params.allow_short:
                if self.current_pos != -1:
                    if self.current_pos == 1:
                        self.close()  # Tancar llarg si n'hi ha
                    self.sell()       # El sizer decidirà quantes unitats vendre
                    self.current_pos = -1
            else:
                # Si no permetem posicions curtes, tanquem qualsevol posició oberta
                if self.current_pos != 0:
                    self.close()
                    self.current_pos = 0

        else:
            # Estat neutre (mantenir la posició actual)
            pass

# --------------------------------------------------------------------
# 4. Configurar i executar Backtrader
# --------------------------------------------------------------------
if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Afegir estratègia amb paràmetres d'exemple
    cerebro.addstrategy(
        Sentiment3StatesStrategy, 
        upper_threshold=65, 
        lower_threshold=30, 
        allow_short=True
    )

    # Afegim el Sizer que inverteix un % del capital
    cerebro.addsizer(PercentSizer, perc=0.20)  # Ex: 20% en cada operació

    # Crear el feed de dades des del DataFrame
    data = MyPandasDataSentiment3(dataname=select_window(df, EVALUATION_WINDOW))
    cerebro.adddata(data)

    # Configurar el broker
    cerebro.broker.setcash(105000.0)
    cerebro.broker.setcommission(commission=0.001)

    print('Valor inicial del Portafoli: %.2f' % cerebro.broker.getvalue())
    cerebro.run()
    print('Valor final del Portafoli: %.2f' % cerebro.broker.getvalue())

    fig = cerebro.plot()[0][0]
    leg = fig.legend
    leg.set_bbox_to_anchor((1, 0.5))
    plt.show()