import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import backtrader as bt

class MyPandasDataSentiment_BI_EMA_R(bt.feeds.PandasData):
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
class SentimentBI_EMA_Strategy_R(bt.Strategy):
    params = (
        ('upper_threshold', 54),
        ('lower_threshold', 24),
        ('wpr_period', 14),
        ('long_ema_period', 14),
        ('short_ema_period', 14),
        ('ema_margin_pct', 0.01), 
        ('stop_up', 0.01),
        ('stop_down', 0.01),
        ('allow_short', True),
        ('allow_long', True),
    )

    def __init__(self):
        self.bbr = self.datas[0].bbr
        self.long_ema = bt.indicators.EMA(period=self.params.long_ema_period)
        self.short_ema = bt.indicators.EMA(period=self.params.short_ema_period)
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
            flag = order.info.get('flag')

            if flag in ('opening_long', 'opening_short'):
                self.entry_price   = order.executed.price
                self.entry_date    = self.datas[0].datetime.date(0)
                self.open_size     = order.executed.size
                self.open_commission = order.executed.comm

            elif flag in ('closing_long', 'closing_short', 'stop_exit',
                        'closing_long_end', 'closing_short_end'):
                self.entry_price   = None
                self.entry_date    = None
                self.open_size     = 0.0
                self.open_commission = 0.0

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
        ema_gap_long = self.short_ema[0] - self.long_ema[0]
        ema_margin_long = self.long_ema[0] * self.params.ema_margin_pct

        ema_gap_short = self.long_ema[0] - self.short_ema[0]
        ema_margin_short = self.long_ema[0] * self.params.ema_margin_pct

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
                                           # saltamos el resto de reglas
            
        # # ───────── Salida inversa por BBr ─────────
        # if self.position.size > 0 and bbr_now < self.params.lower_threshold:
        #     # Estábamos largos y el sentimiento se ha girado → cerramos
        #     close_order = self.close()
        #     if close_order is not None:
        #         close_order.addinfo(flag='closing_long', old_size=self.position.size)
        #     self.current_invested_fraction = 0.0
        #                                         # evitamos evaluar más reglas

        # elif self.position.size < 0 and bbr_now > self.params.upper_threshold:
        #     # Estábamos cortos y el sentimiento se ha girado → cerramos
        #     close_order = self.close()
        #     if close_order is not None:
        #         close_order.addinfo(flag='closing_short', old_size=self.position.size)
        #     self.current_invested_fraction = 0.0
              

        # Si el valor de BBr está en la zona neutral, se cierra la posición.
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
            

        # Entrada LARGA (100% de la cartera) con momentum positivo
        if ema_gap_long > ema_margin_long: #bbr_now > self.params.upper_threshold and
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
        elif ema_gap_short > ema_margin_short: # bbr_now < self.params.lower_threshold and 
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

