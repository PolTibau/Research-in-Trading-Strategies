import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import backtrader as bt

class MyPandasDataSentiment_SMI_R(bt.feeds.PandasData):
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
# 3. Definir l'estratègia amb escalat de posicions i parametrització dels dies de momentum
# --------------------------------------------------------------------
class SentimentSMI_Strategy_R(bt.Strategy):
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
        if bbr_now > self.params.upper_threshold and self.smi[0] > self.signal[0] and self.smi[-1] < self.signal[-1]:
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
        elif bbr_now < self.params.lower_threshold and self.smi[0] < self.signal[0] and self.smi[-1] > self.signal[-1]:
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

