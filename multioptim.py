import pandas as pd
import numpy as np
import backtrader as bt
import optuna
import os
import sys
import logging
import contextlib
from concurrent.futures import ProcessPoolExecutor, as_completed

# Importamos las estrategias y los feeds personalizados
from multistrategy import (
    MyPandasDataSentiment6, SentimentWPRStrategy,
    MyPandasDataSentiment7, SentimentWPR2Strategy,
    MyPandasDataSentiment3, SentimentMomentumStrategy1,
    MyPandasDataSentiment4, SentimentMomentumStrategy2,
    MyPandasDataSentiment5, SentimentSMIStrategy
)

#Creem una funció per actualitzar els paràmetres de les estratègies
def update_multistrategy(best_params_dict):
    """Actualiza los parámetros en multistrategy.py con los valores óptimos encontrados."""
    file_path = 'multistrategy.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    inside_params = False

    for line in lines:
        for strategy, params in best_params_dict.items():
            if f'class {strategy}' in line:
                inside_params = False  # Bandera para saber cuándo modificar
            if inside_params and "(" in line:
                param_name = line.strip().split('=')[0].strip("(')")
                if param_name in params:
                    line = f"        ('{param_name}', {params[param_name]}),\n"
            if 'params = (' in line:
                inside_params = True
            if inside_params and ')' in line:
                inside_params = False
        new_lines.append(line)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

# Evitem loggejar coses innecessàries durant l'optimització de paràmetres
logging.getLogger('backtrader').setLevel(logging.WARNING)
logging.getLogger('optuna').setLevel(logging.WARNING)

#Redirigim els loggs innecesaris a un devnull
@contextlib.contextmanager
def suppress_output():
    """Context manager para suprimir la salida estándar (print statements)."""
    with open(os.devnull, 'w') as fnull:
        old_stdout = sys.stdout
        try:
            sys.stdout = fnull
            yield
        finally:
            sys.stdout = old_stdout 

# Escollim l'stock amb el que aplicarem les estratègies
csv_path = r'C:\Users\polti\OneDrive\Documents\FME\Trading\dataSent\AMZN.csv'
df = pd.read_csv(csv_path)

df.drop(df.columns[0], axis=1, inplace=True)
df.set_index(df.columns[0], inplace=True)
df.index = pd.to_datetime(df.index)

df["BULL"] = 0.33 * (df["positivePartscr"] + df["certaintyPartscr"] + df["finhypePartscr"])
df["BEAR"] = 0.33 * (df["negativePartscr"] + df["uncertaintyPartscr"] + df["findownPartscr"])
df["BBr"] = 100 * df["BULL"] / (df["BULL"] + df["BEAR"])
df["DailyReturn"] = df["Adj Close"].pct_change() * 100
df["BBr"] = df["BBr"].fillna(50)

train_size = int(len(df) * 0.25)
train = df.iloc[:train_size]
test = df.iloc[train_size:]

BBr_max = int(df["BBr"].max())
BBr_min = int(df["BBr"].min())
BBr_av = int((df["BBr"].min() + df["BBr"].max()) // 2)

def run_backtest(strategy_cls, data_cls, strategy_params):
    cerebro = bt.Cerebro(stdstats=False)
    data = data_cls(dataname=train)
    cerebro.adddata(data)
    cerebro.addstrategy(strategy_cls, **strategy_params)
    cerebro.broker.setcash(100000.0)
    cerebro.broker.setcommission(commission=0.01)

    with suppress_output():
        cerebro.run(maxcpus=1)

    return cerebro.broker.getvalue()

def objective(trial, strategy_cls, data_cls):
    param_space = {
        SentimentWPRStrategy: {
            'upper_threshold': trial.suggest_int('upper_threshold', BBr_av, BBr_max),
            'lower_threshold': trial.suggest_int('lower_threshold', BBr_min, BBr_av),
            'wpr_os': trial.suggest_int('wpr_os', -100, -75),
            'wpr_ob': trial.suggest_int('wpr_ob', -25, 0),
            'rsi_os': trial.suggest_int('rsi_os', 25, 40),
            'rsi_ob': trial.suggest_int('rsi_ob', 60, 75),
            'period': trial.suggest_int('period', 10, 30),
        },
        SentimentWPR2Strategy: {
            'upper_threshold': trial.suggest_int('upper_threshold', BBr_av, BBr_max),
            'lower_threshold': trial.suggest_int('lower_threshold', BBr_min, BBr_av),
            'wpr_os': trial.suggest_int('wpr_os', -100, -75),
            'wpr_ob': trial.suggest_int('wpr_ob', -25, 0),
            'wpr_period': trial.suggest_int('wpr_period', 10, 20),
            'ema_period': trial.suggest_int('ema_period', 15, 50),
            'ema_th': trial.suggest_int('ema_th', 40, 60),
        },
        SentimentMomentumStrategy1: {
            'upper_threshold': trial.suggest_int('upper_threshold', BBr_av, BBr_max),
            'lower_threshold': trial.suggest_int('lower_threshold', BBr_min, BBr_av),
            'neutral_lower': trial.suggest_int('neutral_lower', BBr_min, BBr_av),
            'neutral_upper': trial.suggest_int('neutral_upper', BBr_av, BBr_max),
            'momentum_days': trial.suggest_int('momentum_days', 1, 6),
        },
        SentimentMomentumStrategy2: {
            'upper_threshold': trial.suggest_int('upper_threshold', BBr_av, BBr_max),
            'lower_threshold': trial.suggest_int('lower_threshold', BBr_min, BBr_av),
            'cci_upper_threshold': trial.suggest_int('cci_upper_threshold', 70, 140),
            'cci_lower_threshold': trial.suggest_int('cci_lower_threshold', -140, -70),
            'neutral_lower': trial.suggest_int('neutral_lower', BBr_min, BBr_av),
            'neutral_upper': trial.suggest_int('neutral_upper', BBr_av, BBr_max),
            'sma_period': trial.suggest_int('sma_period', 10, 30),
        },
        SentimentSMIStrategy: {
            'upper_threshold': trial.suggest_int('upper_threshold', BBr_av, BBr_max),
            'lower_threshold': trial.suggest_int('lower_threshold', BBr_min, BBr_av),
            'pfast': trial.suggest_int('pfast', 1, 10),
            'pslow': trial.suggest_int('pslow', 10, 20),
            'smasig': trial.suggest_int('smasig', 3, 10),
            'neutral_lower': trial.suggest_int('neutral_lower', BBr_min, BBr_av),
            'neutral_upper': trial.suggest_int('neutral_upper', BBr_av, BBr_max),
        }
    }
    return run_backtest(strategy_cls, data_cls, param_space[strategy_cls])

def optimize_strategy(strategy_cls, data_cls, n_trials=500):
    study = optuna.create_study(direction='maximize')
    study.optimize(lambda trial: objective(trial, strategy_cls, data_cls), n_trials=n_trials)
    return strategy_cls.__name__, study.best_params, study.best_value

if __name__ == '__main__':
    tasks = [
        (SentimentWPR2Strategy, MyPandasDataSentiment7),
        (SentimentWPRStrategy, MyPandasDataSentiment6),
        (SentimentMomentumStrategy1, MyPandasDataSentiment3),
        (SentimentMomentumStrategy2, MyPandasDataSentiment4),
        (SentimentSMIStrategy, MyPandasDataSentiment5)
    ]

    results_list = []
    best_params_dict = {}

    results_list = []
    with ProcessPoolExecutor(max_workers=7) as executor:
        futures = {executor.submit(optimize_strategy, strat_cls, data_cls): (strat_cls, data_cls) for strat_cls, data_cls in tasks}
        
        for future in as_completed(futures):
            strategy_name, best_params, best_value = future.result()
            results_list.append((strategy_name, best_params, best_value))
            best_params_dict[strategy_name] = best_params
        
    update_multistrategy(best_params_dict)

    for strategy_name, best_params, best_value in results_list:
        print(f"Estrategia: {strategy_name}")
        print(f"Mejores Parámetros: {best_params}")
        print(f"Valor Óptimo: {best_value}\n")
