import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import backtrader as bt

class NOUMyPandasDataSentiment_ROC_R(bt.feeds.PandasData):
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
class NOUSentimentROC_Strategy_R(bt.Strategy):
    params = (
    ('upper_pct', 70),
    ('lower_pct', 30),
    ('lookback_thr', 126),
    ('mom_lookback', 5),
    ('mom_min_avg', 0.1),
    ('sma_period', 200),
    ('atr_period', 14),
    ('sl_mult', 2.0),
    ('tp_mult', 3.0),
    ('allow_short', True),
    ('allow_long', True),
    )

    def __init__(self):
        self.bbr = self.datas[0].bbr
        self.daily_return = self.datas[0].daily_return
        self.open_price = self.datas[0].open
        self.close_price = self.datas[0].close
        self.high_price = self.datas[0].high
        self.low_price = self.datas[0].low

        # Indicadores de volatilidad y tendencia
        self.atr = bt.indicators.AverageTrueRange(period=self.params.atr_period)
        self.sma = bt.indicators.SimpleMovingAverage(self.datas[0].close, period=self.params.sma_period)

        # Control de inversión
        self.current_invested_fraction = 0.0
        self.entry_price = None
        self.entry_date = None
        self.trade_type = None
        self.total_trades = 0
        self.total_commission = 0
        self.open_size = 0.0
        self.open_commission = 0.0
    
    def calc_dynamic_thresholds(self):
        lookback = self.params.lookback_thr
        if len(self.data) < lookback:
            return None, None
        bbr_hist = list(self.bbr.get(size=lookback))
        upper_thr = np.percentile(bbr_hist, self.params.upper_pct)
        lower_thr = np.percentile(bbr_hist, self.params.lower_pct)
        return upper_thr, lower_thr
    
    def momentum_avg(self, lookback, min_avg):
        if len(self.daily_return) < lookback:
            return False
        avg_ret = np.mean([self.daily_return[-i] for i in range(lookback)])
        return avg_ret > min_avg

    
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
    # ────────────────────────────────────────────────

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
    # Calcular los umbrales dinámicos del BBr
    upper_thr, lower_thr = self.calc_dynamic_thresholds()
    if upper_thr is None:
        return

    bbr_now = self.bbr[0]
    price_now = self.data.close[0]
    atr_now = self.atr[0]
    sma_now = self.sma[0]

    # Filtro de tendencia
    trend_up = price_now > sma_now

    # Momentum promedio
    pos_momentum = self.momentum_avg(self.params.mom_lookback, self.params.mom_min_avg)
    neg_momentum = self.momentum_avg(self.params.mom_lookback, -self.params.mom_min_avg)

    # ───────── Gestión de posiciones existentes: Stops dinámicos ATR ─────────
    if self.position.size != 0 and self.entry_price is not None:
        if self.position.size > 0:
            stop_loss = self.entry_price - self.params.sl_mult * atr_now
            take_profit = self.entry_price + self.params.tp_mult * atr_now
            if price_now <= stop_loss or price_now >= take_profit:
                close_order = self.close()
                if close_order is not None:
                    close_order.addinfo(flag='stop_exit', old_size=self.position.size)
                self.current_invested_fraction = 0.0
                return
        elif self.position.size < 0:
            stop_loss = self.entry_price + self.params.sl_mult * atr_now
            take_profit = self.entry_price - self.params.tp_mult * atr_now
            if price_now >= stop_loss or price_now <= take_profit:
                close_order = self.close()
                if close_order is not None:
                    close_order.addinfo(flag='stop_exit', old_size=self.position.size)
                self.current_invested_fraction = 0.0
                return

    # ───────── Salida por reversión de sentimiento ─────────
    if self.position.size > 0 and bbr_now < lower_thr:
        close_order = self.close()
        if close_order is not None:
            close_order.addinfo(flag='closing_long', old_size=self.position.size)
        self.current_invested_fraction = 0.0
        return

    if self.position.size < 0 and bbr_now > upper_thr:
        close_order = self.close()
        if close_order is not None:
            close_order.addinfo(flag='closing_short', old_size=self.position.size)
        self.current_invested_fraction = 0.0
        return

    # ───────── Entrada larga ─────────
    if self.params.allow_long and bbr_now > upper_thr and pos_momentum and trend_up:
        if self.current_invested_fraction < 0:
            close_order = self.close()
            if close_order is not None:
                close_order.addinfo(flag='closing_short', old_size=self.position.size)
        if self.current_invested_fraction <= 0:
            open_order = self.open_position_fraction(1.0, is_long=True)
            if open_order is not None:
                open_order.addinfo(flag='opening_long', open_size=0.0, open_comm=0.0)
            self.current_invested_fraction = 1.0
        return

    # ───────── Entrada corta ─────────
    if self.params.allow_short and bbr_now < lower_thr and neg_momentum and not trend_up:
        if self.current_invested_fraction > 0:
            close_order = self.close()
            if close_order is not None:
                close_order.addinfo(flag='closing_long', old_size=self.position.size)
        if self.current_invested_fraction >= 0:
            open_order = self.open_position_fraction(1.0, is_long=False)
            if open_order is not None:
                open_order.addinfo(flag='opening_short', open_size=0.0, open_comm=0.0)
            self.current_invested_fraction = -1.0


