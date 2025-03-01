import pandas as pd
import numpy as np
import backtrader as bt
import optuna
import re
import os
import sys
import logging
import contextlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from S_CCI_optimized_strategy import MyPandasDataSentiment4_R, SentimentMomentumStrategy4_R
from S_R_optimized_strategy import MyPandasDataSentiment3_R, SentimentMomentumStrategy_R
from S_SMI_optimized_strategy import MyPandasDataSentiment5_R, SentimentSMIStrategy_R, SMI
from S_WPR_EMA_optimized_strategy import MyPandasDataSentiment7_R, SentimentWPR2Strategy_R, WPR
from S_WPR_RSI_optimized_strategy import MyPandasDataSentiment6_R, SentimentWPRStrategy_R, WPR

class_name_map = {
    'SentimentWPR2Strategy': 'SentimentWPR2Strategy_R',
    'SentimentWPRStrategy': 'SentimentWPRStrategy_R',
    'SentimentMomentumStrategy1': 'SentimentMomentumStrategy_R',
    'SentimentMomentumStrategy2': 'SentimentMomentumStrategy4_R',
    'SentimentSMIStrategy': 'SentimentSMIStrategy_R',
    'MyPandasDataSentiment3': 'MyPandasDataSentiment3_R',
    'MyPandasDataSentiment4': 'MyPandasDataSentiment4_R',
    'MyPandasDataSentiment5': 'MyPandasDataSentiment5_R',
    'MyPandasDataSentiment6': 'MyPandasDataSentiment6_R',
    'MyPandasDataSentiment7': 'MyPandasDataSentiment7_R',
}


def replace_params_in_line(line, best_params_dict, class_name_map):
    """
    Busca en una línea que define una tarea del tipo:
      (csv, StrategyClass, DataClass, dict(param1=valor1, param2=valor2, ...)),
    y reemplaza los valores de los parámetros si existen en best_params_dict.
    """
    # Se espera que la línea contenga algo como: dict( ... )
    m = re.search(r'\(\s*[^,]+,\s*([^,]+),\s*[^,]+,\s*dict\s*\((.+?)\)\s*\)', line)
    if m:
        raw_strat = m.group(1).strip()
        mapped_strat = class_name_map.get(raw_strat, raw_strat)
        if mapped_strat in best_params_dict:
            params_str = m.group(2)  # cadena con los parámetros dentro de dict(...)
            def repl(match):
                param = match.group(1)
                value = match.group(2)
                if param in best_params_dict[mapped_strat]:
                    new_val = best_params_dict[mapped_strat][param]
                    print(f"✅ Reemplazando {param}={value} -> {new_val} en {mapped_strat}")
                    return f"{param}={new_val}"
                else:
                    print(f"⚠️ {param} no encontrado en {mapped_strat}. No se reemplaza.")
                    return match.group(0)
            # Se aplica el reemplazo a TODOS los parámetros encontrados en la cadena
            new_params_str = re.sub(r'(\w+)\s*=\s*([^,)+]+)', repl, params_str)
            # Reconstruir la línea: se reemplaza la parte del dict( ... ) por la versión modificada
            new_line = re.sub(r'(dict\s*\().+?(\)\s*\))', r'\1' + new_params_str + r'\2', line)
            return new_line
        else:
            print(f"⚠️ {mapped_strat} no tiene parámetros optimizados en best_params_dict")
            return line
    else:
        return line

def update_multistrategy(best_params_dict):
    """
    Actualiza multistrategy.py reemplazando los valores dentro de tasks = [ ... ]
    con los valores optimizados de best_params_dict.
    """
    file_path = 'multistrategy.py'

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    print("\n🔍 DEBUG: Contenido de best_params_dict antes de actualizar multistrategy.py")
    for strat, params in best_params_dict.items():
        print(f"   {strat}: {params}")

    new_lines = []
    tasks_block = False
    for line in lines:
        if 'tasks = [' in line:
            tasks_block = True

        if tasks_block:
            if '(' in line and 'dict(' in line:
                line = replace_params_in_line(line, best_params_dict, class_name_map)
        new_lines.append(line)
        # Detecta el cierre del bloque de tareas (se asume que la línea contiene "]")
        if tasks_block and ']' in line:
            tasks_block = False

    for l in new_lines:
        if 'dict(' in l:
            print(l.strip())

    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
        f.flush() 
        os.fsync(f.fileno()) 



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
        SentimentWPRStrategy_R: {
            'upper_threshold': trial.suggest_int('upper_threshold', BBr_av, BBr_max),
            'lower_threshold': trial.suggest_int('lower_threshold', BBr_min, BBr_av),
            'wpr_os': trial.suggest_int('wpr_os', -100, -75),
            'wpr_ob': trial.suggest_int('wpr_ob', -25, 0),
            'rsi_os': trial.suggest_int('rsi_os', 25, 40),
            'rsi_ob': trial.suggest_int('rsi_ob', 60, 75),
            'period': trial.suggest_int('period', 10, 30),
        },
        SentimentWPR2Strategy_R: {
            'upper_threshold': trial.suggest_int('upper_threshold', BBr_av, BBr_max),
            'lower_threshold': trial.suggest_int('lower_threshold', BBr_min, BBr_av),
            'wpr_os': trial.suggest_int('wpr_os', -100, -75),
            'wpr_ob': trial.suggest_int('wpr_ob', -25, 0),
            'wpr_period': trial.suggest_int('wpr_period', 10, 20),
            'ema_period': trial.suggest_int('ema_period', 15, 50),
            'ema_th': trial.suggest_int('ema_th', 40, 60),
        },
        SentimentMomentumStrategy_R: {
            'upper_threshold': trial.suggest_int('upper_threshold', BBr_av, BBr_max),
            'lower_threshold': trial.suggest_int('lower_threshold', BBr_min, BBr_av),
            'neutral_lower': trial.suggest_int('neutral_lower', BBr_min, BBr_av),
            'neutral_upper': trial.suggest_int('neutral_upper', BBr_av, BBr_max),
            'momentum_days': trial.suggest_int('momentum_days', 1, 6),
        },
        SentimentMomentumStrategy4_R: {
            'upper_threshold': trial.suggest_int('upper_threshold', BBr_av, BBr_max),
            'lower_threshold': trial.suggest_int('lower_threshold', BBr_min, BBr_av),
            'cci_upper_threshold': trial.suggest_int('cci_upper_threshold', 70, 140),
            'cci_lower_threshold': trial.suggest_int('cci_lower_threshold', -140, -70),
            'neutral_lower': trial.suggest_int('neutral_lower', BBr_min, BBr_av),
            'neutral_upper': trial.suggest_int('neutral_upper', BBr_av, BBr_max),
            'sma_period': trial.suggest_int('sma_period', 10, 30),
        },
        SentimentSMIStrategy_R: {
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

def optimize_strategy(strategy_cls, data_cls, n_trials=700):
    study = optuna.create_study(direction='maximize')
    study.optimize(lambda trial: objective(trial, strategy_cls, data_cls), n_trials=n_trials)
    return strategy_cls.__name__, study.best_params, study.best_value

if __name__ == '__main__':
    tasks = [
        (SentimentWPR2Strategy_R, MyPandasDataSentiment7_R),
        (SentimentWPRStrategy_R, MyPandasDataSentiment6_R),
        (SentimentMomentumStrategy_R, MyPandasDataSentiment3_R),
        (SentimentMomentumStrategy4_R, MyPandasDataSentiment4_R),
        (SentimentSMIStrategy_R, MyPandasDataSentiment5_R)
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
