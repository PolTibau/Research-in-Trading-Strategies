import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import backtrader as bt
from statistics import mean

# --------------------------------------------------------------------
# 1. Carregar el CSV i preparar les dades en un DataFrame de pandas
# --------------------------------------------------------------------
fitxer_parquet = r'C:\Users\polti\OneDrive\Documents\FME\Trading\data\AAPL_reord.parquet'
df = pd.read_parquet(fitxer_parquet)

# Eliminar la primera columna "Unnamed: 0" si apareix
df.drop(df.columns[0], axis=1, inplace=True)

# Establir la columna "Date" (o la corresponent) com a índex i convertir a datetime
df.set_index(df.columns[0], inplace=True)
df.index = pd.to_datetime(df.index)

# Crear les columnes de BULL, BEAR i finalment la BBr
df["BULL"] = 0.33 * (df["positivePartscr"] + df["certaintyPartscr"] + df["finhypePartscr"])
df["BEAR"] = 0.33 * (df["negativePartscr"] + df["uncertaintyPartscr"] + df["findownPartscr"])
df["BBr"] = 100 * df["BULL"] / (df["BULL"] + df["BEAR"])

print("El nombre de files amb sentiment NULL és:", df[(df["BULL"] + df["BEAR"]) == 0].shape[0])

train_size = int(len(df) * 0.7)
train = df.iloc[:train_size]
test = df.iloc[train_size:]

# --------------------------------------------------------------------
# 2. Definir la classe de dades personalitzada a partir de Pandas
# --------------------------------------------------------------------
class MyPandasDataSentiment_CCI(bt.feeds.PandasData):
    """
    Feed de dades personalitzat que inclou les línies:
      - 'bbr' (BBr)
    """
    lines = ('bbr',)
    params = (
        ('datetime', None),
        ('open', 'Open'),
        ('high', 'High'),
        ('low', 'Low'),
        ('close', 'Close'),
        ('volume', 'Volume'),
        ('bbr', 'BBr'),
    )

# --------------------------------------------------------------------
# 3. Definir l'estratègia amb escalat de posicions i parametrització dels dies de momentum
# --------------------------------------------------------------------
class SentimentCCI_Strategy(bt.Strategy):
    params = (
        ('upper_threshold', 54),
        ('lower_threshold', 24),
        ('cci_upper_threshold', 100),
        ('cci_lower_threshold', -100),
        ('neutral_lower', 26),
        ('neutral_upper', 27),
        ('sma_period', 2),  # Nombre de dies requerits de momentum positiu/negatiu
        ('allow_short', True),
        ('allow_long', True),
    )

    def __init__(self):
        self.bbr = self.datas[0].bbr
        self.cci = bt.indicators.CCI(self.datas[0], period=self.params.sma_period)  # Calculamos el CCI aquí
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
            trade_cci = self.cci[0]  # CCI del día de la operación
            current_cash = self.broker.getvalue()  # Valor del portafoli després de l'operació
            flag = order.info.get('flag')

            if flag == 'opening_long':
                print(f"[{self.datas[0].datetime.date(0)}] **ENTRADA EN LLARG* - Preu: {order.executed.price:.2f} || BBr: {trade_bbr:.2f} || Tamany: {order.executed.size} || CCI: {trade_cci}% || Valor Actual: {current_cash:.2f} || Comissió: {order.executed.comm:.2f}")
                self.entry_price = order.executed.price
                self.entry_date = self.datas[0].datetime.date(0)
                self.trade_type = "LLARG"
                self.open_size = order.executed.size
                self.open_commission = order.executed.comm

            elif flag == 'opening_short':
                print(f"[{self.datas[0].datetime.date(0)}] **ENTRADA EN CURT** - Preu: {order.executed.price:.2f} || BBr: {trade_bbr:.2f} || Tamany: {order.executed.size} || CCI: {trade_cci}% || Valor Actual: {current_cash:.2f} || Comissió: {order.executed.comm:.2f}")
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

    def next(self):
        bbr_now = self.bbr[0]
        cci_now = self.cci[0]
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
        if bbr_now > self.params.upper_threshold and self.params.cci_upper_threshold < cci_now:
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
        elif bbr_now < self.params.lower_threshold and self.params.cci_lower_threshold > cci_now:
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
        SentimentCCI_Strategy,
        upper_threshold=55, lower_threshold=14, cci_upper_threshold=78, cci_lower_threshold=-87, neutral_lower=22, neutral_upper=23, sma_period=17, allow_long=True, allow_short=True
    )
    
    data = MyPandasDataSentiment_CCI(dataname=test)
    cerebro.adddata(data)
    cerebro.broker.setcash(100000.0)
    cerebro.broker.setcommission(commission=0.001)
    
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.02)
    cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name='annual')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    
    print('Valor inicial del Portafoli: %.2f' % cerebro.broker.getvalue())
    strategies = cerebro.run()
    strategy = strategies[0]

    sharpe = strategy.analyzers.sharpe.get_analysis()
    annual = strategy.analyzers.annual.get_analysis()
    drawdown = strategy.analyzers.drawdown.get_analysis()
    trades = strategy.analyzers.trades.get_analysis()

    print('Valor final del Portafoli: %.2f' % cerebro.broker.getvalue())
    print(f"Nombre total d'operacions realitzades: {strategy.total_trades}")
    print(f'Total de comissions pagades: {strategy.total_commission:.2f}')

    print('Sharpe Ratio (rf=2%):', f"{sharpe.get('sharperatio', float('nan')):.2f}")

    # Individuales por año (opcional)
    for year, ret in annual.items():
        print(f"Annual Return {year}:", f"{ret:.2%}")

    # Promedio global
    annual_returns = list(annual.values())
    if annual_returns:
        avg_annual_return = mean(annual_returns)
        excess_return = avg_annual_return - 0.02
        print('Average Annual Return:', f"{avg_annual_return:.2%}")
        print('Excess Return (vs 2% RF):', f"{excess_return:.2%}")


    print('Max Drawdown:', f"{drawdown.max.drawdown:.2f}%")
    print('Max Drawdown Duration (days):', drawdown.max.len)

    print('Total Trades:', trades.total.closed)
    
    cerebro.plot()
