import os
import sys
import logging
import contextlib
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd
import numpy as np
import backtrader as bt
import optuna
from optuna.pruners import MedianPruner   # ← tallarà trials molt dolents
from NOUS_R_optimized_strategySLTP import (
    NOUMyPandasDataSentiment_ROC_R,
    NOUSentimentROC_Strategy_R,
)
from S_R_optimized_strategySLTP import (
    MyPandasDataSentiment_ROC_R,
    SentimentROC_Strategy_R,
)
from S_BI_EMA_optimized_strategySLTP import (
    MyPandasDataSentiment_BI_EMA_R,
    SentimentBI_EMA_Strategy_R,
)
from ROC_optimized_strategySLTP import (
    noMyPandasDataSentiment_ROC_R,
    noSentimentROC_Strategy_R,
)
from BI_EMA_optimized_strategySLTP import (
    noMyPandasDataSentiment_BI_EMA_R,
    noSentimentBI_EMA_Strategy_R,
)

# ───────────────────────────────
# 1. Configuració bàsica i dades
# ───────────────────────────────
logging.getLogger('backtrader').setLevel(logging.WARNING)
logging.getLogger('optuna').setLevel(logging.WARNING)

@contextlib.contextmanager
def suppress_output():
    """Silencia prints dins del bloc (backtrader en fa força)."""
    with open(os.devnull, 'w') as fnull:
        old_stdout = sys.stdout
        try:
            sys.stdout = fnull
            yield
        finally:
            sys.stdout = old_stdout

parquet_path = r'C:\Users\polti\OneDrive\Documents\FME\Trading\data\AMZN_reord.parquet'
df = pd.read_parquet(parquet_path)

# Elimina primera columna si és Index antic
df.drop(df.columns[0], axis=1, inplace=True)
df.set_index(df.columns[0], inplace=True)
df.index = pd.to_datetime(df.index)

# Columnes sentiment
df["BULL"] = 0.33 * (df["positivePartscr"] + df["certaintyPartscr"] + df["finupPartscr"])
df["BEAR"] = 0.33 * (df["negativePartscr"] + df["uncertaintyPartscr"] + df["findownPartscr"])
df["BBr"]  = 100 * df["BULL"] / (df["BULL"] + df["BEAR"])
df["DailyReturn"] = df["Close"].pct_change() * 100

print("Files amb sentiment NULL:", df[(df["BULL"] + df["BEAR"]) == 0].shape[0])

train_size = int(len(df) * 0.7)
train = df.iloc[:train_size]

# Rangs per Optuna
BBr_max, BBr_min = int(df["BBr"].max()), int(df["BBr"].min())
BBr_av = int((BBr_min + BBr_max) // 2)

# ───────────────────────────────
# 2. Funcions de backtest i Optuna
# ───────────────────────────────
def run_backtest(strategy_cls, data_cls, strategy_params, commission):
    cerebro = bt.Cerebro(stdstats=False)
    cerebro.adddata(data_cls(dataname=train))
    cerebro.addstrategy(strategy_cls, **strategy_params)
    cerebro.broker.setcash(100_000)
    cerebro.broker.setcommission(commission=commission)

    with suppress_output():        # Backtrader és molt xerraire
        cerebro.run()
    return cerebro.broker.getvalue()

def objective(trial, commission):
    # """Funció d'Optuna per a la SentimentROC_Strategy_R."""
    # up  = trial.suggest_int('upper_threshold',  BBr_av, BBr_max)
    # low = trial.suggest_int('lower_threshold',  BBr_min, up - 2)
    # if low >= up:
    #     return -1e9  # rebutja combinació impossible

    # params = {
    #     'upper_threshold': up,
    #     'lower_threshold': low,
    #     'stop_up':    trial.suggest_float('stop_up',   1.0, 10.0, step=0.25),
    #     'stop_down':  trial.suggest_float('stop_down', 1.0, 10.0, step=0.25),
    #     'momentum_days': trial.suggest_int('momentum_days', 2, 6),
    # }
    # params = {
    #     'upper_threshold': up,
    #     'lower_threshold': low,
    #     'long_ema_period': trial.suggest_int('long_ema_period', 20, 50),
    #     'short_ema_period': trial.suggest_int('short_ema_period', 3, 19),
    #     'ema_margin_pct': trial.suggest_float('ema_margin_pct', 0.003, 0.01, step=0.0001),
    #     'stop_up': trial.suggest_float('stop_up', 1.0, 10.0, step=0.25),
    #     'stop_down': trial.suggest_float('stop_down', 1.0, 10.0, step=0.25),
    # }
    # params = {
    #     'long_ema_period': trial.suggest_int('long_ema_period', 20, 50),
    #     'short_ema_period': trial.suggest_int('short_ema_period', 3, 19),
    #     'ema_margin_pct': trial.suggest_float('ema_margin_pct', 0.003, 0.01, step=0.0001),
    #     'stop_up': trial.suggest_float('stop_up', 1.0, 10.0, step=0.25),
    #     'stop_down': trial.suggest_float('stop_down', 1.0, 10.0, step=0.25),
    # }
    params = {
        'upper_threshold':    trial.suggest_int('upper_threshold', 50, 90),
        'lower_threshold':    trial.suggest_int('lower_threshold', 10, 50),
        'mom_lb':       trial.suggest_int('mom_lb', 3, 10),
        'mom_avg':      trial.suggest_float('mom_avg', 0.0, 0.3, step=0.01),
        'ema_period':   trial.suggest_int('ema_period', 30, 80),
        'atr_p':        trial.suggest_int('atr_p', 10, 30),
        'sl_mul':       trial.suggest_float('sl_mul', 1.0, 3.0, step=0.1),
        'tp_mul':       trial.suggest_float('tp_mul', 1.0, 3.0, step=0.1),
    }

    return run_backtest(
        NOUSentimentROC_Strategy_R,
        NOUMyPandasDataSentiment_ROC_R,
        params,
        commission,
    )

def optimize_one_commission(commission, n_trials=1000):
    study = optuna.create_study(direction='maximize', sampler=optuna.samplers.TPESampler())
    study.optimize(lambda t: objective(t, commission), n_trials=n_trials)
    return commission, study.best_params, study.best_value

# ───────────────────────────────
# 3. Llançament paral·lel
# ───────────────────────────────
if __name__ == '__main__':
    commissions = [0.001, 0.001, 0.003, 0.003, 0.005, 0.005]
    n_workers   = min(len(commissions), os.cpu_count() or 1)

    results = []
    with ProcessPoolExecutor(max_workers=n_workers) as ex:
        futures = {ex.submit(optimize_one_commission, com): com for com in commissions}
        for fut in as_completed(futures):
            com, best_params, best_val = fut.result()
            results.append((com, best_params, best_val))

    # ── Resultats ──
    results.sort(key=lambda x: x[0])  # ordena per comissió
    for com, bp, val in results:
        print(f"\n▶ Comisión {com:.3%}")
        print(f"  Mejor valor cartera final: {val:,.2f}")
        for k, v in bp.items():
            print(f"    {k:<15}: {v}")
