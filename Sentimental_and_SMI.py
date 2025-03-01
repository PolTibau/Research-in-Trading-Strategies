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

print("El nombre de files amb sentiment NULL és:", df[(df["BULL"] + df["BEAR"]) == 0].shape[0])

# --------------------------------------------------------------------
# 2. Definir la classe de dades personalitzada a partir de Pandas
# --------------------------------------------------------------------
class MyPandasDataSentiment_SMI(bt.feeds.PandasData):
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
# 3. Definir el indicador Stochastic Momentum Index (SMI)
# --------------------------------------------------------------------
class SMI(bt.Indicator):
    """Cálculo del Stochastic Momentum Index (SMI) personalizado"""
    lines = ('smi', 'smasig')  # Definir las líneas del indicador
    params = (('period', 14), ('pfast', 3), ('pslow', 3), ('smasig', 3))  # Parámetros ajustables

    def __init__(self):
        high_low_mean = (self.data.high + self.data.low) / 2  # Precio medio (High + Low) / 2
        hl_range = self.data.high - self.data.low  # Rango de precios (High - Low)
        
        # Suavizado rápido y lento del precio medio
        smi_fast = bt.indicators.EMA(high_low_mean - self.data.close, period=self.p.pfast)
        smi_slow = bt.indicators.EMA(smi_fast, period=self.p.pslow)

        # Cálculo del SMI
        self.lines.smi = 100 * smi_slow / bt.indicators.EMA(hl_range, period=self.p.pslow)

        # Línea de señal del SMI
        self.lines.smasig = bt.indicators.EMA(self.lines.smi, period=self.p.smasig)


# --------------------------------------------------------------------
# 4. Definir l'estratègia 
# --------------------------------------------------------------------
class SentimentSMI_Strategy(bt.Strategy):
    params = (
        ('upper_threshold', 54),
        ('lower_threshold', 24),
        ('pfast', 3),
        ('pslow', 3),
        ('smasig', 5),
        ('period', 14),
        ('neutral_lower', 26),
        ('neutral_upper', 27),
        ('allow_short', True),
        ('allow_long', True),
    )

    def __init__(self):
        self.bbr = self.datas[0].bbr
        self.smi = SMI(self.datas[0], period=self.params.period, pfast=self.params.pfast, pslow=self.params.pslow, smasig=self.params.smasig)
        self.signal = self.smi.smasig
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
            trade_bbr = self.bbr[-1]  # BBr del día de la operación
            signal = self.signal[0]
            trade_smi = self.smi[0]
            current_cash = self.broker.getvalue()  # Valor del portafoli després de l'operació
            flag = order.info.get('flag')

            if flag == 'opening_long':
                print(f"[{self.datas[0].datetime.date(0)}] **ENTRADA EN LLARG* - Preu: {order.executed.price:.2f} || BBr: {trade_bbr:.2f} || Tamany: {order.executed.size} || SMI: {trade_smi}% || Signal: {signal} || Valor Actual: {current_cash:.2f} || Comissió: {order.executed.comm:.2f}")
                self.entry_price = order.executed.price
                self.entry_date = self.datas[0].datetime.date(0)
                self.trade_type = "LLARG"
                self.open_size = order.executed.size
                self.open_commission = order.executed.comm

            elif flag == 'opening_short':
                print(f"[{self.datas[0].datetime.date(0)}] **ENTRADA EN CURT** - Preu: {order.executed.price:.2f} || BBr: {trade_bbr:.2f} || Tamany: {order.executed.size} || SMI: {trade_smi}% || Signal: {signal} || Valor Actual: {current_cash:.2f} || Comissió: {order.executed.comm:.2f}")
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
                profit_loss = (exit_price - self.entry_price) * open_size - (open_comm + close_comm)

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
                profit_loss = (exit_price - self.entry_price) * open_size - (open_comm + close_comm)

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
        #comprem si el SMI creua per sobre de la linia de senyal

        bbr_now = self.bbr[0]
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
        if bbr_now > self.params.upper_threshold and self.smi[0] > self.signal[0] and self.smi[-1] < self.signal[-1]:
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
        elif bbr_now < self.params.lower_threshold and self.smi[0] < self.signal[0] and self.smi[-1] > self.signal[-1]:
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
# 5. Configurar i executar Backtrader
# --------------------------------------------------------------------
if __name__ == '__main__':
    cerebro = bt.Cerebro()
    strategy = cerebro.addstrategy(
        SentimentSMI_Strategy,
        upper_threshold=53,
        lower_threshold=27,
        pfast=7,
        pslow=8,
        period=18,
        smasig=4,
        neutral_lower=41,
        neutral_upper=41,
        allow_long=True,
        allow_short=True
    )
    

    data = MyPandasDataSentiment_SMI(dataname=df)
    cerebro.adddata(data)
    cerebro.broker.setcash(100000.0)
    cerebro.broker.setcommission(commission=0.01)

    #mètriques de valor final del portafoli
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    
    print('Valor inicial del Portafoli: %.2f' % cerebro.broker.getvalue())
    strategies = cerebro.run()
    strategy = strategies[0]
    print('Valor final del Portafoli: %.2f' % cerebro.broker.getvalue())
    print(f"Nombre total d'operacions realitzades: {strategy.total_trades}")
    print(f'Total de comissions pagades: {strategy.total_commission:.2f}')
    print()

    returns_analyzer = strategy.analyzers.returns.get_analysis()
    sharpe_analyzer = strategy.analyzers.sharpe.get_analysis()
    drawdown_analyzer = strategy.analyzers.drawdown.get_analysis()
    trades_analyzer = strategy.analyzers.trades.get_analysis()

    # Cumulative Return (returns_analyzer['rtot'] = retorno total)
    cumulative_return = (np.exp(returns_analyzer['rtot'])-1) * 100  # lo multiplicamos por 100 para %
    print(f"Cumulative Return: {cumulative_return:.2f}%")

    # Annual Return (returns_analyzer['rnorm100'] = retorno anualizado en %)
    annual_return = returns_analyzer['rnorm100']
    print(f"Annual Return: {annual_return:.2f}%")

    # Sharpe Ratio (sharpe_analyzer['sharperatio'])
    sharpe_ratio = sharpe_analyzer['sharperatio']
    print(f"Annual Sharpe Ratio: {sharpe_ratio:.2f}")

    # Win % -> se obtiene de trades_analyzer
    closed_trades = trades_analyzer['total']['closed']
    if closed_trades > 0:
        won_trades = trades_analyzer['won']['total']
        win_rate = won_trades / closed_trades * 100
    else:
        win_rate = 0
    print(f"Win %: {win_rate:.2f}%")

    # Maximum Drawdown
    max_dd = drawdown_analyzer['max']['drawdown']  # en porcentaje
    print(f"Maximum Drawdown: {max_dd:.2f}%")

    # Max Length Drawdown
    max_len_dd = drawdown_analyzer['max']['len']
    print(f"Max Length Drawdown (days): {max_len_dd}")

    # Excess Returns (si defines una tasa libre de riesgo, p.e. 2%)
    risk_free = 0.02
    excess_return = annual_return - (risk_free * 100)
    print(f"Excess Return vs {risk_free*100:.2f}%: {excess_return:.2f}%")
    
    cerebro.plot()
