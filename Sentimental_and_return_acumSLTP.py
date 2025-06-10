import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import backtrader as bt
import matplotlib.dates as mdates
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
df["BULL"] = 0.33 * (df["positivePartscr"] + df["certaintyPartscr"] + df["finupPartscr"])
df["BEAR"] = 0.33 * (df["negativePartscr"] + df["uncertaintyPartscr"] + df["findownPartscr"])
df["BBr"] = 100 * df["BULL"] / (df["BULL"] + df["BEAR"])

df["DailyReturn"] = df["Close"].pct_change() * 100  # Retorn diari en percentatge
print("El nombre de files amb sentiment NULL és:", df[(df["BULL"] + df["BEAR"]) == 0].shape[0])

#ver el valor de bbr entre los dias 2021-10-23 y 2021-11-23
print("El valor de BBr entre 2021-10-23 y 2021-11-23 es:")
print(df.loc['2021-10-20':'2021-11-23', 'BBr'])
print(df.loc['2021-10-23':'2021-11-23', 'DailyReturn'])

# Calcular el retorn diari utilitzant la columna 'Close' (pots canviar a 'Adj Close')


train_size = int(len(df) * 0.8)
train = df.iloc[:train_size]
test = df.iloc[train_size:]

# --------------------------------------------------------------------
# 2. Definir la classe de dades personalitzada a partir de Pandas
# --------------------------------------------------------------------
class MyPandasDataSentiment_ROC(bt.feeds.PandasData):
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


class BBrPlot(bt.Indicator):
    '''Dibuja la línea BBr (%) que viene en el data feed'''
    lines = ('bbr',)
    plotinfo = dict(
        subplot=False,        # pon False si la quieres sobre el precio
        plotname='BBr (%)',
        plotymargin=0.05,
        plotyhlines=[0, 100] # líneas horizontales de zonas
    )
    def __init__(self):
        self.lines.bbr = self.data.bbr
        self.bbr_plot = BBrPlot(self.datas[0])


# --------------------------------------------------------------------
# 3. Definir l'estratègia amb escalat de posicions i parametrització dels dies de momentum
# --------------------------------------------------------------------
class SentimentROC_Strategy(bt.Strategy):
    params = (
        ('upper_threshold', 54),
        ('lower_threshold', 24),
        ('momentum_days', 20),  # Nombre de dies requerits de momentum positiu/negatiu
        ('stop_up',    4.0),
        ('stop_down',  2.0),
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
        self.lines.bbr = self.data.bbr


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
    
    def momentum_contrario(self, long_position=True):
        """
        Devuelve True si:
        · long_position=True  →  los últimos N días son negativos
        · long_position=False →  los últimos N días son positivos
        """
        if len(self.daily_return) < self.params.momentum_days:
            return False
        
        if long_position:                      # estamos largos → ¿N días negativos?
            return all(self.daily_return[-i] < 0
                       for i in range(self.params.momentum_days))
        else:                                  # estamos cortos → ¿N días positivos?
            return all(self.daily_return[-i] > 0
                       for i in range(self.params.momentum_days))



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
        
                # ───────── Take-Profit / Stop-Loss ─────────
        if self.position.size != 0 and self.entry_price is not None:
            entry_px = self.entry_price
            cur_px   = self.data.close[0]
            pct = 100.0 * (cur_px - entry_px) / entry_px
            if self.position.size < 0:          # si es corto, la señal se invierte
                pct = -pct

            if pct >= self.params.stop_up or pct <= -self.params.stop_down:
                o = self.close()                # salimos a neutro
                if o is not None:
                    o.addinfo(flag='stop_exit')
                self.current_invested_fraction = 0.0
                return                           # saltamos el resto de reglas


            # ───────── Salida inversa por BBr ─────────
        if self.position.size > 0 and bbr_now < self.params.lower_threshold:
            # Estábamos largos y el sentimiento se ha girado → cerramos
            close_order = self.close()
            if close_order is not None:
                close_order.addinfo(flag='closing_long', old_size=self.position.size)
            self.current_invested_fraction = 0.0
            return                                    # evitamos evaluar más reglas

        elif self.position.size < 0 and bbr_now > self.params.upper_threshold:
            # Estábamos cortos y el sentimiento se ha girado → cerramos
            close_order = self.close()
            if close_order is not None:
                close_order.addinfo(flag='closing_short', old_size=self.position.size)
            self.current_invested_fraction = 0.0
            return                                    # evitamos evaluar más reglas


        if self.position.size > 0 and self.momentum_contrario(long_position=True):
            #imprimim la data actual
            close_order = self.close()
            if close_order is not None:
                close_order.addinfo(flag='momentum_exit_long', old_size=self.position.size)
            self.current_invested_fraction = 0.0

            # Si se permiten cortos, abrir inmediatamente la posición contraria
            if self.params.allow_short and bbr_now < self.params.lower_threshold:
                open_order = self.open_position_fraction(1.0, is_long=False)
                if open_order is not None:
                    open_order.addinfo(flag='opening_short', open_size=0.0, open_comm=0.0)
                self.current_invested_fraction = -1.0
            return                               # evitamos evaluar el resto

        #    Si estamos cortos y ocurre momentum positivo → salir / girar
        elif self.position.size < 0 and self.momentum_contrario(long_position=False):
            close_order = self.close()
            if close_order is not None:
                close_order.addinfo(flag='momentum_exit_short', old_size=self.position.size)
            self.current_invested_fraction = 0.0

            # Si se permiten largos, abrir inmediatamente la posición contraria
            if self.params.allow_long and bbr_now > self.params.upper_threshold:
                open_order = self.open_position_fraction(1.0, is_long=True)
                if open_order is not None:
                    open_order.addinfo(flag='opening_long', open_size=0.0, open_comm=0.0)
                self.current_invested_fraction = 1.0
            return
        # # Si el valor de BBr está en la zona neutral, se cierra la posición.
        # if self.params.neutral_lower < bbr_now < self.params.neutral_upper:
        #     if self.current_invested_fraction != 0:
        #         # En lugar de self.close()
        #         if self.position.size > 0:
        #             close_order = self.close()
        #             if close_order is not None:
        #                 close_order.addinfo(flag='closing_long', old_size=self.position.size)
        #         elif self.position.size < 0:
        #             close_order = self.close()
        #             if close_order is not None:
        #                 close_order.addinfo(flag='closing_short', old_size=self.position.size)

        #         self.current_invested_fraction = 0.0
        #     return

        # Entrada LARGA (100% de la cartera) con momentum positivo
        if bbr_now > self.params.upper_threshold and positive_momentum:
            # Si no estamos ya 100% largos
            if self.current_invested_fraction == -1.0:
                close_order = self.close()
                if close_order is not None:
                    close_order.addinfo(flag='closing_short', old_size=self.position.size)

                open_order = self.open_position_fraction(1.0, is_long=True)
                if open_order is not None:
                    open_order.addinfo(flag='opening_long', open_size=0.0, open_comm=0.0)
                self.current_invested_fraction = 1.0

            elif self.current_invested_fraction == 0.0:
                open_order = self.open_position_fraction(1.0, is_long=True)
                if open_order is not None:
                    open_order.addinfo(flag='opening_long', open_size=0.0, open_comm=0.0)
                self.current_invested_fraction = 1.0

        # Entrada CORTA (100% de la cartera) con momentum negativo
        elif bbr_now < self.params.lower_threshold and negative_momentum:
            if self.params.allow_short:
                # Si no estamos ya 100% cortos
                if self.current_invested_fraction == 1.0:
                    close_order = self.close()
                    if close_order is not None:
                        close_order.addinfo(flag='closing_long', old_size=self.position.size)

                    open_order = self.open_position_fraction(1.0, is_long=False)
                    if open_order is not None:
                        open_order.addinfo(flag='opening_short', open_size=0.0, open_comm=0.0)
                    self.current_invested_fraction = -1.0

                elif self.current_invested_fraction == 0.0:
                    open_order = self.open_position_fraction(1.0, is_long=False)
                    if open_order is not None:
                        open_order.addinfo(flag='opening_short', open_size=0.0, open_comm=0.0)
                    self.current_invested_fraction = -1.0   

# --------------------------------------------------------------------
# 4. Configurar i executar Backtrader
# --------------------------------------------------------------------
if __name__ == '__main__':
    cerebro = bt.Cerebro()
    strategy = cerebro.addstrategy(
        SentimentROC_Strategy,
        upper_threshold=51, lower_threshold=0, stop_up=7.25, stop_down=9.25, momentum_days=3, allow_long=True, allow_short=True
    )
    
    data = MyPandasDataSentiment_ROC(dataname=train)
    cerebro.adddata(data)
    cerebro.broker.setcash(100000.0)
    cerebro.broker.setcommission(commission=0.001)

    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.02)
    cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name='annual')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='bh', timeframe=bt.TimeFrame.NoTimeFrame, data=data)

    
    print('Valor inicial del Portafoli: %.2f' % cerebro.broker.getvalue())
    strategies = cerebro.run()
    strategy = strategies[0]

    strategy_return = (cerebro.broker.getvalue() -
                   cerebro.broker.startingcash) / cerebro.broker.startingcash

    sharpe = strategy.analyzers.sharpe.get_analysis()
    annual = strategy.analyzers.annual.get_analysis()
    drawdown = strategy.analyzers.drawdown.get_analysis()
    trades_analyzer = strategy.analyzers.trades.get_analysis()
    bh_series = strategy.analyzers.bh.get_analysis()
    buyhold_ret = bh_series[max(bh_series.keys())]  # último valor
    print(f"Rentabilidad Buy & Hold: {buyhold_ret:.2%}")

    print(f"Rentabilidad estrategia: {strategy_return:.2%}")

    print('Valor final del Portafoli: %.2f' % cerebro.broker.getvalue())
    print(f"Nombre total d'operacions realitzades: {strategy.total_trades}")
    print(f'Total de comissions pagades: {strategy.total_commission:.2f}')

    print('Sharpe Ratio (rf=2%):', f"{sharpe.get('sharperatio', float('nan')):.2f}")

    # Win % -> se obtiene de trades_analyzer
    closed_trades = trades_analyzer['total']['closed']
    if closed_trades > 0:
        won_trades = trades_analyzer['won']['total']
        win_rate = won_trades / closed_trades * 100
    else:
        win_rate = 0
    print(f"Win %: {win_rate:.2f}%")

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

    print('Total Trades:', trades_analyzer.total.closed)
    
    cerebro.plot()
