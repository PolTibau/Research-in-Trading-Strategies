import os
import pandas as pd
import numpy as np
import backtrader as bt
from concurrent.futures import ProcessPoolExecutor, as_completed



# --------------------------------------------------------------------
# 1. Definir tus clases de datos personalizadas
#    (copiamos sólo las que difieren si hacen falta)
# --------------------------------------------------------------------

class MyPandasDataSentiment7(bt.feeds.PandasData):
    """
    Feed de datos que añade la línea 'bbr'.
    Ajusta los campos/columnas según tu CSV.
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

class MyPandasDataSentiment6(bt.feeds.PandasData):
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

class MyPandasDataSentiment4(bt.feeds.PandasData):
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

class MyPandasDataSentiment3(bt.feeds.PandasData):
    lines = ('bbr','daily_return',)
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

class MyPandasDataSentiment5(bt.feeds.PandasData):
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
# 2. Definir tus clases de estrategia
#    (copiamos tus 5 estrategias tal cual, solo resumidas aquí)
# --------------------------------------------------------------------

# -------- Estrategia 1 (SentimentWPR2Strategy) -------------
class WPR(bt.Indicator):
    lines = ('wpr',)
    params = (('period', 14),)

    def __init__(self):
        highest_high = bt.indicators.Highest(self.data.high, period=self.p.period)
        lowest_low = bt.indicators.Lowest(self.data.low, period=self.p.period)
        self.lines.wpr = -100 * ((highest_high - self.data.close) / (highest_high - lowest_low))
class SentimentWPR2Strategy(bt.Strategy):
    params = (
        ('upper_threshold', 54),
        ('lower_threshold', 24),
        ('wpr_period', 14),
        ('ema_period', 30),
        ('wpr_os', -80),
        ('wpr_ob', -20),
        ('ema_th', 50),
        ('neutral_lower', 26),
        ('neutral_upper', 27),
        ('allow_short', True),
        ('allow_long', True),
    )

    def __init__(self):
        self.bbr = self.datas[0].bbr
        self.wpr = WPR(self.datas[0], period=self.params.wpr_period)
        self.ema = bt.indicators.EMA(period=self.params.ema_period)
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
            trade_wpr = self.wpr[-1]  # WPR del día de la operación
            current_cash = self.broker.getvalue()  # Valor del portafoli després de l'operació
            flag = order.info.get('flag')

            if flag == 'opening_long':
                print(f"[{self.datas[0].datetime.date(0)}] **ENTRADA EN LLARG* - Preu: {order.executed.price:.2f} || BBr: {trade_bbr:.2f} || Tamany: {order.executed.size} || WPR: {trade_wpr} || Valor Actual: {current_cash:.2f} || Comissió: {order.executed.comm:.2f}")
                self.entry_price = order.executed.price
                self.entry_date = self.datas[0].datetime.date(0)
                self.trade_type = "LLARG"
                self.open_size = order.executed.size
                self.open_commission = order.executed.comm

            elif flag == 'opening_short':
                print(f"[{self.datas[0].datetime.date(0)}] **ENTRADA EN CURT** - Preu: {order.executed.price:.2f} || BBr: {trade_bbr:.2f} || Tamany: {order.executed.size} || WPR: {trade_wpr} || Valor Actual: {current_cash:.2f} || Comissió: {order.executed.comm:.2f}")
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
        wpr_now = self.wpr[0]
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

        # Entrada LARGA (100% de la cartera) i WPR < -80 (possible sobrevenda)
        if bbr_now > self.params.upper_threshold and wpr_now < self.params.wpr_os and self.ema[0] > self.params.ema_th:
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
        elif bbr_now < self.params.lower_threshold and wpr_now > self.params.wpr_ob and self.ema[0] < self.params.ema_th:
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

# -------- Estrategia 2 (SentimentWPRStrategy) -------------
class SentimentWPRStrategy(bt.Strategy):
    params = (
        ('upper_threshold', 54),
        ('lower_threshold', 24),
        ('period', 14),
        ('wpr_os', -80),
        ('wpr_ob', -20),
        ('rsi_os', 30),
        ('rsi_ob', 70),
        ('neutral_lower', 26),
        ('neutral_upper', 27),
        ('allow_short', True),
        ('allow_long', True),
    )

    def __init__(self):
        self.bbr = self.datas[0].bbr
        self.wpr = WPR(self.datas[0], period=self.params.period)
        self.rsi = bt.indicators.RSI(period=self.params.period)
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
            trade_wpr = self.wpr[-1]  # WPR del día de la operación
            current_cash = self.broker.getvalue()  # Valor del portafoli després de l'operació
            flag = order.info.get('flag')

            if flag == 'opening_long':
                print(f"[{self.datas[0].datetime.date(0)}] **ENTRADA EN LLARG* - Preu: {order.executed.price:.2f} || BBr: {trade_bbr:.2f} || Tamany: {order.executed.size} || WPR: {trade_wpr} || Valor Actual: {current_cash:.2f} || Comissió: {order.executed.comm:.2f}")
                self.entry_price = order.executed.price
                self.entry_date = self.datas[0].datetime.date(0)
                self.trade_type = "LLARG"
                self.open_size = order.executed.size
                self.open_commission = order.executed.comm

            elif flag == 'opening_short':
                print(f"[{self.datas[0].datetime.date(0)}] **ENTRADA EN CURT** - Preu: {order.executed.price:.2f} || BBr: {trade_bbr:.2f} || Tamany: {order.executed.size} || WPR: {trade_wpr} || Valor Actual: {current_cash:.2f} || Comissió: {order.executed.comm:.2f}")
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
        wpr_now = self.wpr[0]
        rsi_now = self.rsi[0]
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

        # Entrada LARGA (100% de la cartera) i WPR < -80 (possible sobrevenda)
        if bbr_now > self.params.upper_threshold and wpr_now < self.params.wpr_os and rsi_now < self.params.rsi_os:
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
        elif bbr_now < self.params.lower_threshold and wpr_now > self.params.wpr_ob and rsi_now > self.params.rsi_ob:
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

# -------- Estrategia 3 (SentimentMomentumStrategy) ---------
class SentimentMomentumStrategy1(bt.Strategy):
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

# -------- Estrategia 4 (SentimentMomentumStrategy) ---------
class SentimentMomentumStrategy2(bt.Strategy):
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

# -------- Estrategia 5 (SentimentSMIStrategy) -------------
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
class SentimentSMIStrategy(bt.Strategy):
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
# 3. Función auxiliar "run_backtest"
#    para ejecutar Cerebro con una estrategia + CSV
#    y retornar las métricas de interés.
# --------------------------------------------------------------------

def run_backtest(
    csv_path,               # ruta al CSV
    strategy_cls,           # clase de estrategia (por ej. SentimentWPR2Strategy)
    data_cls,               # clase del feed (MyPandasDataSentimentX)
    strategy_params=None,   # diccionario con parámetros para la estrategia
    commission=0.01,
    initial_cash=100000.0,
):
    """
    Lanza un backtest con la estrategia dada, su feed y parámetros.
    Retorna un diccionario con las métricas principales.
    """
    if strategy_params is None:
        strategy_params = {}

    # 1) Leemos el CSV
    df = pd.read_csv(csv_path)
    
    # IMPORTANTE:
    # Aquí podrías repetir lo que ya hacías: eliminar 'Unnamed: 0',
    # set_index, calculo bbr, etc. O lo delegas a un script previo.
    # Como ejemplo rápido (simplificado):
  # Eliminar la primera columna "Unnamed: 0" si apareix
    df.drop(df.columns[0], axis=1, inplace=True)

    # Aseguramos convertir la primera columna a datetime e index:
    df.set_index(df.columns[0], inplace=True)
    df.index = pd.to_datetime(df.index)

    # (Ejemplo) si necesitas BULL, BEAR, BBr, etc.:
    if 'positivePartscr' in df.columns and 'negativePartscr' in df.columns:
        df["BULL"] = 0.33 * (df["positivePartscr"] + df["certaintyPartscr"] + df["finhypePartscr"])
        df["BEAR"] = 0.33 * (df["negativePartscr"] + df["uncertaintyPartscr"] + df["findownPartscr"])
        df["BBr"] = 100 * df["BULL"] / (df["BULL"] + df["BEAR"])

    df["DailyReturn"] = df["Adj Close"].pct_change() * 100  # Retorn diari en percentatge

    # 2) Preparamos Cerebro
    cerebro = bt.Cerebro()
    strategy = cerebro.addstrategy(strategy_cls, **strategy_params)

    # 3) Cargamos los datos
    data = data_cls(dataname=df)  # feed que definiste
    cerebro.adddata(data)

    # 4) Configuramos broker
    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=commission)

    # 5) Añadimos analizadores para obtener métricas
    cerebro.addanalyzer(bt.analyzers.Returns,     _name='returns')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown,    _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

    # 6) Ejecutamos
    results = cerebro.run()
    final_strat = results[0]  # la estrategia

    # 7) Recopilamos métricas
    portvalue_final = cerebro.broker.getvalue()
    total_trades = getattr(final_strat, 'total_trades', 0)
    total_comm = getattr(final_strat, 'total_commission', 0)

    returns_analyzer   = final_strat.analyzers.returns.get_analysis()
    trades_analyzer    = final_strat.analyzers.trades.get_analysis()

    # Extraemos en variables cómodas
    # Retorno total (rtot) = log-return. Convertimos a % normal: (exp(...) - 1)*100
    cumret = (np.exp(returns_analyzer['rtot']) - 1) * 100 if 'rtot' in returns_analyzer else None
    annret = returns_analyzer.get('rnorm100')  # en %
    
    # Win rate
    closed_trades = trades_analyzer.get('total', {}).get('closed', 0)
    won_trades = trades_analyzer.get('won', {}).get('total', 0)
    win_rate = (won_trades / closed_trades * 100) if closed_trades else 0

    # Preparamos los resultados para devolver
    out = {
        'CSV': os.path.basename(csv_path),
        'Strategy': strategy_cls.__name__,
        'FinalPortfolioValue': portvalue_final,
        'TotalTrades': total_trades,
        'TotalCommission': total_comm,
        'CumulativeReturn_%': cumret,
        'AnnualReturn_%': annret,
        'ExcessReturn_%': annret - 2.0,  # asumiendo un 2% de retorno libre de riesgo
        'Win_%': win_rate,
    }
    print()

    return out


# --------------------------------------------------------------------
# 4. Lógica principal que lanza las 5 estrategias en paralelo
# --------------------------------------------------------------------
if __name__ == '__main__':
    # Preparamos las "tareas": (csv, clase estrategia, clase data, params)
    arxiu = r'C:\Users\polti\OneDrive\Documents\FME\Trading\dataSent\AMZN.csv'
    tasks = [
        (arxiu, SentimentWPR2Strategy, MyPandasDataSentiment7, dict(upper_threshold=55, lower_threshold=43, wpr_period=16, ema_period=45, wpr_os=-80, wpr_ob=-1, ema_th=58, neutral_lower=40, neutral_upper=81, allow_long=True, allow_short=True)),
        (arxiu, SentimentWPRStrategy, MyPandasDataSentiment6, dict(upper_threshold=72, lower_threshold=32, period=25, wpr_os=-77, wpr_ob=-18, rsi_os=36, rsi_ob=73, neutral_lower=26, neutral_upper=65, allow_long=True, allow_short=True)),
        (arxiu, SentimentMomentumStrategy1, MyPandasDataSentiment3, dict(upper_threshold=56, lower_threshold=46, neutral_lower=50, neutral_upper=53, momentum_days=3, allow_long=True, allow_short=True)),
        (arxiu, SentimentMomentumStrategy2, MyPandasDataSentiment4, dict(upper_threshold=64, lower_threshold=24, cci_upper_threshold=116, cci_lower_threshold=-136, neutral_lower=33, neutral_upper=73, sma_period=15, allow_long=True, allow_short=True)),
        (arxiu, SentimentSMIStrategy, MyPandasDataSentiment5, dict(upper_threshold=59, lower_threshold=44, pfast=4, pslow=10, period=19, smasig=8, neutral_lower=30, neutral_upper=69, allow_long=True, allow_short=True)),
    ]

    # Lanzamos en paralelo
    results_list = []
    with ProcessPoolExecutor(max_workers=7) as executor:
        futures = []
        for (csv_path, strat_cls, data_cls, params) in tasks:
            # Para cada estrategia y CSV, lanzamos un job en paralelo:
            fut = executor.submit(run_backtest, csv_path, strat_cls, data_cls, params)
            futures.append(fut)

        # Recolectamos resultados a medida que van terminando
        for fut in as_completed(futures):
            res = fut.result()  # diccionario con métricas
            results_list.append(res)

    # Imprimimos un resumen final
    print("\nResumen de Resultados:\n")
    for r in results_list:
        print(f"--- {r['Strategy']} sobre {r['CSV']} ---")
        print(f"  Valor Final  : {r['FinalPortfolioValue']:.2f}")
        print(f"  Trades       : {r['TotalTrades']}")
        print(f"  Comisión     : {r['TotalCommission']:.2f}")
        print(f"  Retorno Tot. : {r['CumulativeReturn_%']:.2f}%")
        print(f"  Retorno Anual: {r['AnnualReturn_%']:.2f}%")
        print(f"  Exceso Ret.  : {r['ExcessReturn_%']:.2f}%")
        print(f"  Win Rate     : {r['Win_%']:.2f}%")
        print("")
