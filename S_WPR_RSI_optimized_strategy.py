import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import backtrader as bt

class MyPandasDataSentiment_WPR_RSI_R(bt.feeds.PandasData):
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
        ('openinterest', -1),
        ('bbr', 'BBr'),
    )
    
# --------------------------------------------------------------------
# 3. Definir el indicador Williams %R (WPR)
# --------------------------------------------------------------------
class WPR(bt.Indicator):
    """Cálculo del Williams %R (WPR) personalizado"""
    lines = ('wpr',)  # Definir la línea del indicador
    params = (('period', 14),)  # Período ajustable

    def __init__(self):
        highest_high = bt.indicators.Highest(self.data.high, period=self.p.period)  # Máximo del periodo
        lowest_low = bt.indicators.Lowest(self.data.low, period=self.p.period)  # Mínimo del periodo

        # Fórmula del WPR
        self.lines.wpr = -100 * ((highest_high - self.data.close) / (highest_high - lowest_low))

        
# --------------------------------------------------------------------
# 3. Definir l'estratègia amb escalat de posicions i parametrització dels dies de momentum
# --------------------------------------------------------------------
class SentimentWPR_RSI_Strategy_R(bt.Strategy):
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
        wpr_now = self.wpr[0]
        rsi_now = self.rsi[0]

        # Si el valor de BBr está en la zona neutral, se cierra la posición.
        if self.params.neutral_lower < bbr_now < self.params.neutral_upper:
            if self.current_invested_fraction != 0:
                # En lugar de self.close()
                if self.position.size > 0:
                    close_order = self.close()
                    if close_order is not None:
                        close_order.addinfo(flag='closing_long', old_size=self.position.size)
                elif self.position.size < 0:
                    close_order = self.close()
                    if close_order is not None:
                        close_order.addinfo(flag='closing_short', old_size=self.position.size)

                self.current_invested_fraction = 0.0
            return

        # Entrada LARGA (100% de la cartera) con momentum positivo
        if bbr_now > self.params.upper_threshold and wpr_now < self.params.wpr_os and rsi_now < self.params.rsi_os:
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
        elif bbr_now < self.params.lower_threshold and wpr_now > self.params.wpr_ob and rsi_now > self.params.rsi_ob:
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

