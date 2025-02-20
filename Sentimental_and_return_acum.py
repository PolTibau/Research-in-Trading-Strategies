import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import backtrader as bt

# --------------------------------------------------------------------
# 1. Carregar el CSV i preparar les dades en un DataFrame de pandas
# --------------------------------------------------------------------
fitxer_csv = r'C:\Users\polti\OneDrive\Documents\FME\Trading\dataSent\AAPL.csv'
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

# Calcular el retorn diari utilitzant la columna 'Close' (pots canviar a 'Adj Close')
df["DailyReturn"] = df["Adj Close"].pct_change() * 100  # Retorn diari en percentatge
print("El nombre de files amb sentiment NULL és:", df[(df["BULL"] + df["BEAR"]) == 0].shape[0])

# --------------------------------------------------------------------
# 2. Definir la classe de dades personalitzada a partir de Pandas
# --------------------------------------------------------------------
class MyPandasDataSentiment3(bt.feeds.PandasData):
    """
    Feed de dades personalitzat que inclou les línies:
      - 'bbr' (BBr)
      - 'daily_return' (Retorn diari)
    """
    lines = ('bbr', 'daily_return',)
    params = (
        ('datetime', None),
        ('open', 'Open'),
        ('high', 'High'),
        ('low', 'Low'),
        ('close', 'Close'),
        ('volume', 'Volume'),
        ('openinterest', -1),
        ('bbr', 'BBr'),
        ('daily_return', 'DailyReturn'),
    )

# --------------------------------------------------------------------
# 3. Definir l'estratègia amb escalat de posicions i parametrització dels dies de momentum
# --------------------------------------------------------------------
class SentimentMomentumStrategy(bt.Strategy):
    params = (
        ('upper_threshold', 54),
        ('lower_threshold', 24),
        ('neutral_lower', 26),
        ('neutral_upper', 27),
        ('momentum_days', 2),  # Nombre de dies requerits de momentum positiu/negatiu
        ('allow_short', True),
        ('allow_long', True),
    )

    def __init__(self):
        self.bbr = self.datas[0].bbr
        self.daily_return = self.datas[0].daily_return
        self.open_price = self.datas[0].open  # Precio de Open para entrar y salir
        self.initial_cash = self.broker.getvalue()
        self.current_invested_fraction = 0.0
        self.entry_price = None
        self.entry_date = None
        self.trade_type = None
        self.commission_in_this_trade = 0.0
        self.total_trades = 0
        self.total_commission = 0
        self.last_date = self.data.datetime.date(-1)


    def notify_order(self, order):
        if order.status in [order.Completed]:
            trade_bbr = self.bbr[0]  # BBr del día de la operación
            trade_return = [self.daily_return[0], self.daily_return[-1], self.daily_return[-2]]  # Daily Return del día de la operación
            current_cash = self.broker.getvalue()  # Valor del portafoli després de l'operació
            flag = order.info.get('flag')

            if flag == 'opening_long':
                print(f"[{self.datas[0].datetime.date(0)}] **ENTRADA EN LLARG* - Preu: {order.executed.price:.2f} || BBr: {trade_bbr:.2f} || Tamany: {order.executed.size} || Daily Return: {trade_return}% || Valor Actual: {current_cash:.2f} || Comissió: {order.executed.comm:.2f}")
                self.entry_price = order.executed.price
                self.entry_date = self.datas[0].datetime.date(0)
                self.trade_type = "LLARG"
                self.open_size = order.executed.size
                self.open_commission = order.executed.comm

            elif flag == 'opening_short':
                print(f"[{self.datas[0].datetime.date(0)}] **ENTRADA EN CURT** - Preu: {order.executed.price:.2f} || BBr: {trade_bbr:.2f} || Tamany: {order.executed.size} || Daily Return: {trade_return}% || Valor Actual: {current_cash:.2f} || Comissió: {order.executed.comm:.2f}")
                self.entry_price = order.executed.price
                self.entry_date = self.datas[0].datetime.date(0)
                self.trade_type = "CURT"
                self.open_size = order.executed.size
                self.open_commission = order.executed.comm
            
            elif flag == 'closing_long':
                exit_price = order.executed.price  # Se cierra al Open del siguiente día
                open_size = self.open_size
                open_comm = self.open_commission
                close_comm = order.executed.comm
                profit_loss = (exit_price - self.entry_price) * open_size - (open_comm + close_comm)

                days_in_trade = (self.datas[0].datetime.date(0) - self.entry_date).days

                print(f"[{self.datas[0].datetime.date(0)}] **SORTIDA DE LLARG** - Preu: {order.executed.price:.2f} || BBr: {trade_bbr:.2f} || Tamany: {order.executed.size} || Beneficis: {profit_loss:.2f} || Dies de l'operació: {days_in_trade} || Comissió: {order.executed.comm:.2f}")
                self.trade_type = "SORTIDA LLARG"
                self.entry_price = None
                self.entry_date = None
                self.open_size = 0.0
                self.open_commission = 0.0
            
            elif flag == 'closing_short':
                exit_price = order.executed.price  # Se cierra al Open del siguiente día
                open_size = self.open_size
                open_comm = self.open_commission
                close_comm = order.executed.comm
                profit_loss = (self.entry_price - exit_price) * open_size - (open_comm + close_comm)

                days_in_trade = (self.datas[0].datetime.date(0) - self.entry_date).days

                print(f"[{self.datas[0].datetime.date(0)}] **SORTIDA DE CURT** - Preu: {order.executed.price:.2f} || BBr: {trade_bbr:.2f} || Tamany: {order.executed.size} || Beneficis: {profit_loss:.2f} || Dies de l'operació: {days_in_trade} || Comissió: {order.executed.comm:.2f}") 
                self.trade_type = "SORTIDA CURT"
                self.entry_price = None
                self.entry_date = None
                self.open_size = 0.0
                self.open_commission = 0.0

            elif flag == 'closing_long_end':
                exit_price = order.executed.price  # Se cierra al Open del siguiente día
                open_size = self.open_size
                open_comm = self.open_commission
                close_comm = order.executed.comm
                profit_loss = (exit_price - self.entry_price) * open_size - (open_comm + close_comm)

                days_in_trade = (self.datas[0].datetime.date(0) - self.entry_date).days

                print(f"[{self.datas[0].datetime.date(0)}] **SORTIDA DE LLARG FINAL** - Preu: {order.executed.price:.2f} || BBr: {trade_bbr:.2f} || Tamany: {order.executed.size} || Beneficis: {profit_loss:.2f} || Dies de l'operació: {days_in_trade} || Comissió: {order.executed.comm:.2f}")
                self.trade_type = "SORTIDA LLARG FINAL"
                self.entry_price = None
                self.entry_date = None
                self.open_size = 0.0
                self.open_commission = 0.0
            
            elif flag == 'closing_short_end':
                exit_price = order.executed.price  # Se cierra al Open del siguiente día
                open_size = self.open_size
                open_comm = self.open_commission
                close_comm = order.executed.comm
                profit_loss = (self.entry_price - exit_price) * open_size - (open_comm + close_comm)

                days_in_trade = (self.datas[0].datetime.date(0) - self.entry_date).days

                print(f"[{self.datas[0].datetime.date(0)}] **SORTIDA DE CURT FINAL** - Preu: {order.executed.price:.2f} || BBr: {trade_bbr:.2f} || Tamany: {order.executed.size} || Beneficis: {profit_loss:.2f} || Dies de l'operació: {days_in_trade} || Comissió: {order.executed.comm:.2f}")
                self.trade_type = "SORTIDA CURT FINAL"
                self.entry_price = None
                self.entry_date = None
                self.open_size = 0.0
                self.open_commission = 0.0
            
            self.commission_in_this_trade = order.executed.comm
            self.total_trades += 1
            self.total_commission += order.executed.comm

    def open_position_fraction(self, fraction, is_long=True):

        price = self.data.open[0]
        comission = self.broker.getcommissioninfo(self.data).p.commission

        # Ajustamos la inversión (ej. 0.9 para dejar un 10% de colchón)
        capital_a_invertir = self.broker.getvalue() * fraction * 0.9

        size = capital_a_invertir / (price * (1 + comission))

        if size > 0:
            if is_long:
                order = self.buy(size=size)
            else:
                order = self.sell(size=size)
            return order

        return None

    def last_n_days_positive(self):
        """Verifica si los últimos N días han sido todos positivos en retorno."""
        if len(self.daily_return) < self.params.momentum_days:
            return False
        return all(self.daily_return[-i] > 0 for i in range(self.params.momentum_days))

    def last_n_days_negative(self):
        """Verifica si los últimos N días han sido todos negativos en retorno."""
        if len(self.daily_return) < self.params.momentum_days:
            return False
        return all(self.daily_return[-i] < 0 for i in range(self.params.momentum_days))

    def next(self):
        bbr_now = self.bbr[0]
        positive_momentum = self.last_n_days_positive()
        negative_momentum = self.last_n_days_negative()
        current_date = self.data.datetime.date(0)

        if current_date == self.last_date:
            if self.position.size > 0:
                close_order = self.close()
                close_order.addinfo(flag='closing_long_end', old_size=self.position.size)
            elif self.position.size < 0:
                close_order = self.close()
                close_order.addinfo(flag='closing_short_end', old_size=self.position.size)

        # Si el valor de BBr está en la zona neutral, se cierra la posición.
        if self.params.neutral_lower < bbr_now < self.params.neutral_upper:
            if self.current_invested_fraction != 0:
                # En lugar de self.close()
                if self.position.size > 0:
                    close_order = self.close()
                    close_order.addinfo(flag='closing_long', old_size=self.position.size)
                elif self.position.size < 0:
                    close_order = self.close()
                    close_order.addinfo(flag='closing_short', old_size=self.position.size)

                self.current_invested_fraction = 0.0
            return

        # Entrada LARGA (100% de la cartera) con momentum positivo
        if bbr_now > self.params.upper_threshold and positive_momentum:
            # Si no estamos ya 100% largos
            if self.current_invested_fraction == -1.0:
                close_order = self.close()
                close_order.addinfo(flag='closing_short', old_size=self.position.size)

                open_order = self.open_position_fraction(1.0, is_long=True)
                open_order.addinfo(flag='opening_long', open_size=0.0, open_comm=0.0)
                self.current_invested_fraction = 1.0

            elif self.current_invested_fraction == 0.0:
                open_order = self.open_position_fraction(1.0, is_long=True)
                open_order.addinfo(flag='opening_long', open_size=0.0, open_comm=0.0)
                self.current_invested_fraction = 1.0

        # Entrada CORTA (100% de la cartera) con momentum negativo
        elif bbr_now < self.params.lower_threshold and negative_momentum:
            if self.params.allow_short:
                # Si no estamos ya 100% cortos
                if self.current_invested_fraction == 1.0:
                    close_order = self.close()
                    close_order.addinfo(flag='closing_long', old_size=self.position.size)

                    open_order = self.open_position_fraction(1.0, is_long=False)
                    open_order.addinfo(flag='opening_short', open_size=0.0, open_comm=0.0)
                    self.current_invested_fraction = -1.0

                elif self.current_invested_fraction == 0.0:
                    open_order = self.open_position_fraction(1.0, is_long=False)
                    open_order.addinfo(flag='opening_short', open_size=0.0, open_comm=0.0)
                    self.current_invested_fraction = -1.0   

# --------------------------------------------------------------------
# 4. Configurar i executar Backtrader
# --------------------------------------------------------------------
if __name__ == '__main__':
    cerebro = bt.Cerebro()
    strategy = cerebro.addstrategy(
        SentimentMomentumStrategy,
        upper_threshold=54,
        lower_threshold=24,
        neutral_lower=26,
        neutral_upper=27,
        momentum_days=2,
        allow_long=True,
        allow_short=True
    )
    
    data = MyPandasDataSentiment3(dataname=df)
    cerebro.adddata(data)
    cerebro.broker.setcash(100000.0)
    cerebro.broker.setcommission(commission=0.01)
    
    print('Valor inicial del Portafoli: %.2f' % cerebro.broker.getvalue())
    strategies = cerebro.run()
    strategy = strategies[0]
    print('Valor final del Portafoli: %.2f' % cerebro.broker.getvalue())
    print(f"Nombre total d'operacions realitzades: {strategy.total_trades}")
    print(f'Total de comissions pagades: {strategy.total_commission:.2f}')
    
    cerebro.plot()
