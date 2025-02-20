import pandas as pd
import backtrader as bt

# -------------------------------
# Carregar el CSV original i preparar la dada
# -------------------------------
fitxer_csv = r'C:\Users\polti\OneDrive\Documents\FME\Trading\DB.csv'
df = pd.read_csv(fitxer_csv)

# Esborrem la primera columna (la que surt com a "Unnamed: 0")
df.drop(df.columns[0], axis=1, inplace=True)

# Establim la columna "Date" com a índex i convertim a datetime
df.set_index(df.columns[0], inplace=True)
df.index = pd.to_datetime(df.index)

# -------------------------------
# Afegir les columnes calculades
# -------------------------------
# Calcular els components de Bullish i Bearish Sentiment
df["BULL"] = 0.33 * (df["positivePartscr"] + df["certaintyPartscr"] + df["finhypePartscr"])
df["BEAR"] = 0.33 * (df["negativePartscr"] + df["uncertaintyPartscr"] + df["findownPartscr"])

# Calcular la ràtio Bull-Bear (BBr)
df["BBr"] = 100 * df["BULL"] / (df["BULL"] + df["BEAR"])

# Opcional: comprovar l'ordre de columnes per assegurar-nos que BBr està com esperem
print("Columnes disponibles:", df.columns.tolist())

# -------------------------------
# Definir el feed de dades a partir del DataFrame
# Utilitzem bt.feeds.PandasData per llegir directament el DataFrame
# -------------------------------
class MyPandasDataSentiment(bt.feeds.PandasData):
    """
    Feed de dades personalitzat que afegeix la columna 'BBr' com a línia extra.
    
    Els paràmetres indiquen:
      - datetime: utilitza l'índex del DataFrame (la data)
      - open, high, low, close, volume: columnes bàsiques per a les operacions
      - bbr: columna calculada 'BBr'
      - openinterest: no s'utilitza (-1)
    """
    lines = ('bbr',)
    params = (
        ('datetime', None),       # Utilitza l'índex del DataFrame
        ('open', 'Open'),
        ('high', 'High'),
        ('low', 'Low'),
        ('close', 'Close'),
        ('volume', 'Volume'),
        ('openinterest', -1),
        ('bbr', 'BBr'),           # Assigna la columna 'BBr' a la línia 'bbr'
    )

# -------------------------------
# Estratègia basada en Sentiment Simple
# -------------------------------
class SentimentStrategy(bt.Strategy):
    params = (
        ('threshold', 55),  # Llindar de BBr
        ('allow_short', True),
    )
    
    def __init__(self):
        self.bbr = self.datas[0].bbr
        self.current_pos = 0

    def next(self):
        bbr_now = self.bbr[0]
        # Si BBr supera el llindar, obrim posició en llarg
        if bbr_now > self.params.threshold:
            if self.current_pos != 1:
                if self.current_pos == -1:
                    self.close()  # Tanquem posició curta si n'hi ha
                self.buy()
                self.current_pos = 1
        else:
            # Si no superem el llindar i permetem curt, obrim posició curta
            if self.params.allow_short:
                if self.current_pos != -1:
                    if self.current_pos == 1:
                        self.close()  # Tanquem posició llarga si n'hi ha
                    self.sell()
                    self.current_pos = -1
            else:
                # Si no permetem curt, tanquem qualsevol posició oberta
                if self.current_pos != 0:
                    self.close()
                    self.current_pos = 0

# -------------------------------
# Configurar i executar Backtrader
# -------------------------------
if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(SentimentStrategy, threshold=50, allow_short=False)

    # Afegir el feed de dades directament des del DataFrame modificat
    data = MyPandasDataSentiment(dataname=df)
    cerebro.adddata(data)

    cerebro.broker.setcash(100000.0)
    cerebro.broker.setcommission(commission=0.01)

    print('Valor inicial del Portafoli: %.2f' % cerebro.broker.getvalue())
    cerebro.run()
    print('Valor final del Portafoli: %.2f' % cerebro.broker.getvalue())

    cerebro.plot()
