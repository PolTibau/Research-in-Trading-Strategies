# =====================================================================
# BACKTEST COMPLETO
# Apple – sentiment_score → BBr (0‑100) ya calculado dentro del Parquet
# Columnas del Parquet pueden venir con mayúsculas/minúsculas variadas,
# espacios, etc.  Este script normaliza los nombres y lanza Backtrader.
#
# Requisitos:
#   pip install backtrader pandas numpy matplotlib
# =====================================================================

import pandas as pd
import numpy as np
import backtrader as bt
from statistics import mean
import os

# ---------------------------------------------------------------------
# 1. Cargar y normalizar el Parquet
# ---------------------------------------------------------------------
fitxer_parquet = r'C:\Users\polti\Downloads\lexicons\split\AAPL_trans.parquet'
df = pd.read_parquet(fitxer_parquet)

# 1.a  Normalizar todos los nombres: strip + quitar espacios + lower
def _clean(col):
    return col.strip().replace(' ', '').replace('_', '').lower()

df = df.rename(columns={c: _clean(c) for c in df.columns})

# 1.b  Renombrar a nombres estándar
target_map = {
    'open':   'Open',
    'high':   'High',
    'low':    'Low',
    'close':  'Close',
    'volume': 'Volume',
    'sentimentscore': 'BBr',
    'updownlogratio': 'UpDownLogRatio',
    'date':   'Date',

}
df = df.rename(columns={k: v for k, v in target_map.items() if k in df.columns})

# 1.c  Verificar columnas esenciales
mandatory = ['Open', 'High', 'Low', 'Close', 'BBr', 'Date']
missing = [c for c in mandatory if c not in df.columns]
if missing:
    raise KeyError(f'Faltan columnas esenciales en el Parquet: {missing}')

# 1.d  Índice de fecha
df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
df = df.set_index('Date').sort_index()

# 1.e  Volume dummy si hace falta
if 'Volume' not in df.columns:
    df['Volume'] = 0.0

# 1.f  DailyReturn en porcentaje
df['DailyReturn'] = df['Close'].pct_change() * 100

# ---------------------------------------------------------------------
# 2. Train / Test split
# ---------------------------------------------------------------------
train_size = int(len(df) * 0.70)
train = df.iloc[:train_size]
test  = df.iloc[train_size:]

# ---------------------------------------------------------------------
# 3. Feed personalizado para Backtrader
# ---------------------------------------------------------------------
class MyPandasSentiment(bt.feeds.PandasData):
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

# ---------------------------------------------------------------------
# 4. Estrategia completa (idéntica a tu versión, sin omitir nada)
# ---------------------------------------------------------------------
class NOUSentimentROC_Strategy(bt.Strategy):
    params = (
        ('upper_threshold', 70),
        ('lower_threshold', 30),
        ('mom_lb', 5),
        ('mom_avg', 0.1),
        ('ema_period', 200),
        ('atr_p', 14),
        ('sl_mul', 2.0),
        ('tp_mul', 3.0),
        ('allow_short', True),
        ('allow_long', True),
        ('momentum_days', 5),
    )

    # -------------------- inicialización -----------------------
    def __init__(self):
        self.bbr          = self.datas[0].bbr
        self.daily_return = self.datas[0].daily_return
        self.open_price   = self.datas[0].open
        self.close_price  = self.datas[0].close
        self.high_price   = self.datas[0].high
        self.low_price    = self.datas[0].low

        self.atr = bt.indicators.AverageTrueRange(period=self.params.atr_p)
        self.sma = bt.indicators.ExponentialMovingAverage(
            self.datas[0].close, period=self.params.ema_period)

        self.current_invested_fraction = 0.0
        self.entry_price = None
        self.entry_date  = None
        self.trade_type  = None
        self.total_trades = 0
        self.total_commission = 0.0
        self.open_size = 0.0
        self.open_commission = 0.0

    # -------------------- utilidades de momentum ---------------
    def momentum_avg(self, lookback, min_avg):
        if len(self.daily_return) < lookback:
            return False
        avg_ret = np.mean([self.daily_return[-i] for i in range(lookback)])
        return avg_ret > min_avg

    def momentum_contrario(self, long_position=True):
        if len(self.daily_return) < self.params.momentum_days:
            return False
        if long_position:
            return all(self.daily_return[-i] < 0 for i in range(self.params.momentum_days))
        else:
            return all(self.daily_return[-i] > 0 for i in range(self.params.momentum_days))

    def last_n_days_positive(self):
        if len(self.daily_return) < self.params.momentum_days:
            return False
        return all(self.daily_return[-i] > 0 for i in range(self.params.momentum_days))

    def last_n_days_negative(self):
        if len(self.daily_return) < self.params.momentum_days:
            return False
        return all(self.daily_return[-i] < 0 for i in range(self.params.momentum_days))

    # -------------------- gestión de órdenes -------------------
    def notify_order(self, order):
        if order.status != order.Completed:
            return

        trade_bbr   = self.bbr[0]
        trade_return = [self.daily_return[0],
                        self.daily_return[-1],
                        self.daily_return[-2]]
        flag = order.info.get('flag')

        if flag in {'opening_long', 'opening_short'}:
            self.entry_price = order.executed.price
            self.entry_date  = self.datas[0].datetime.date(0)
            self.trade_type  = 'LLARG' if flag == 'opening_long' else 'CURT'
            self.open_size   = order.executed.size
            self.open_commission = order.executed.comm
            print(f"[{self.entry_date}] {'LONG' if flag=='opening_long' else 'SHORT'} "
                  f"Open {self.entry_price:.2f}  BBr {trade_bbr:.2f}  Size {self.open_size}")
        elif flag in {'closing_long', 'closing_short', 'stop_exit'}:
            exit_price = order.executed.price
            pl = (exit_price - self.entry_price) * self.open_size \
                 if self.trade_type == 'LLARG' else \
                 (self.entry_price - exit_price) * self.open_size
            pl -= (self.open_commission + order.executed.comm)
            days = (self.datas[0].datetime.date(0) - self.entry_date).days
            print(f"[{self.datas[0].datetime.date(0)}] CLOSE "
                  f"Exit {exit_price:.2f}  P/L {pl:.2f}  Days {days}")
            self.entry_price = self.entry_date = None
            self.open_size = self.open_commission = 0.0
            self.trade_type = None

        self.total_trades += 1
        self.total_commission += order.executed.comm

    # -------------------- helper abrir posición ---------------
    def open_position_fraction(self, fraction, is_long=True):
        price = self.data.open[0]
        comm  = self.broker.getcommissioninfo(self.data).p.commission
        capital = self.broker.getvalue() * fraction * 0.9
        size = capital / (price * (1 + comm))
        if size <= 0:
            return None
        return self.buy(size=size) if is_long else self.sell(size=size)

    # -------------------- lógica de trading -------------------
    def next(self):
        bbr_now   = self.bbr[0]
        price_now = self.data.close[0]
        atr_now   = self.atr[0]
        sma_now   = self.sma[0]

        trend_up = price_now > sma_now
        pos_mom  = self.momentum_avg(self.params.mom_lb,  self.params.mom_avg)
        neg_mom  = self.momentum_avg(self.params.mom_lb, -self.params.mom_avg)

        # Salida por SL/TP dinámicos
        if self.position.size != 0 and self.entry_price is not None:
            if self.position.size > 0:  # largo
                stop = self.entry_price - self.params.sl_mul * atr_now
                tp   = self.entry_price + self.params.tp_mul * atr_now
                if price_now <= stop or price_now >= tp:
                    o = self.close()
                    if o: o.addinfo(flag='stop_exit')
                    self.current_invested_fraction = 0.0
                    return
            else:                       # corto
                stop = self.entry_price + self.params.sl_mul * atr_now
                tp   = self.entry_price - self.params.tp_mul * atr_now
                if price_now >= stop or price_now <= tp:
                    o = self.close()
                    if o: o.addinfo(flag='stop_exit')
                    self.current_invested_fraction = 0.0
                    return

        # Salida por reversión de BBr
        if self.position.size > 0 and bbr_now < self.params.lower_threshold:
            o = self.close()
            if o: o.addinfo(flag='closing_long')
            self.current_invested_fraction = 0.0
            return
        if self.position.size < 0 and bbr_now > self.params.upper_threshold:
            o = self.close()
            if o: o.addinfo(flag='closing_short')
            self.current_invested_fraction = 0.0
            return

        # Entrada largo
        if (self.params.allow_long
            and bbr_now > self.params.upper_threshold
            and pos_mom and trend_up):
            if self.current_invested_fraction < 0:
                o = self.close()
                if o: o.addinfo(flag='closing_short')
            if self.current_invested_fraction <= 0:
                o = self.open_position_fraction(1.0, is_long=True)
                if o: o.addinfo(flag='opening_long')
                self.current_invested_fraction = 1.0
            return

        # Entrada corto
        if (self.params.allow_short
            and bbr_now < self.params.lower_threshold
            and neg_mom and not trend_up):
            if self.current_invested_fraction > 0:
                o = self.close()
                if o: o.addinfo(flag='closing_long')
            if self.current_invested_fraction >= 0:
                o = self.open_position_fraction(1.0, is_long=False)
                if o: o.addinfo(flag='opening_short')
                self.current_invested_fraction = -1.0

# ---------------------------------------------------------------------
# 5. Montar y ejecutar Backtrader
# ---------------------------------------------------------------------
if __name__ == '__main__':
    cerebro = bt.Cerebro()

    cerebro.addstrategy(
        NOUSentimentROC_Strategy,
        upper_threshold=60, lower_threshold=11,
        mom_lb=10, mom_avg=0.02,
        ema_period=57, atr_p=27,
        sl_mul=3.0, tp_mul=1.9,
        allow_long=True, allow_short=True
    )

    cerebro.adddata(MyPandasSentiment(dataname=train))

    cerebro.broker.setcash(100_000)
    cerebro.broker.setcommission(commission=0.001)

    # Analyzers
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.02)
    cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name='annual')
    cerebro.addanalyzer(bt.analyzers.DrawDown,   _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='bh',
                        timeframe=bt.TimeFrame.NoTimeFrame)

    print(f"Valor inicial del portafolio: {cerebro.broker.getvalue():.2f}")
    strat = cerebro.run()[0]

    final_value = cerebro.broker.getvalue()
    strategy_ret = (final_value - 100_000) / 100_000
    sharpe    = strat.analyzers.sharpe.get_analysis()
    annual    = strat.analyzers.annual.get_analysis()
    drawdown  = strat.analyzers.drawdown.get_analysis()
    trades_an = strat.analyzers.trades.get_analysis()
    bh_series = strat.analyzers.bh.get_analysis()
    buyhold_ret = bh_series[max(bh_series.keys())]

    print(f"Valor final del portafolio: {final_value:.2f}")
    print(f"Rentabilidad estrategia: {strategy_ret:.2%}")
    print(f"Rentabilidad Buy & Hold: {buyhold_ret:.2%}")
    print(f"Sharpe Ratio (rf=2%): {sharpe.get('sharperatio', float('nan')):.2f}")
    closed = trades_an['total']['closed']
    win_rate = trades_an['won']['total'] / closed * 100 if closed else 0
    print(f"Win %: {win_rate:.2f}%")
    for yr, ret in annual.items():
        print(f"Annual Return {yr}: {ret:.2%}")
    if annual:
        avg_annual = mean(annual.values())
        excess = avg_annual - 0.02
        print(f"Average Annual Return: {avg_annual:.2%}")
        print(f"Excess Return vs 2% RF: {excess:.2%}")
    print(f"Max Drawdown: {drawdown.max.drawdown:.2f}% "
          f"(duración: {drawdown.max.len} días)")
    print(f"Total Trades: {trades_an.total.closed}")

    cerebro.plot()
