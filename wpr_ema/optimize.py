import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import backtrader as bt
import optuna
from wpr_ema.strategy import MyPandasDataSentiment7_R, SentimentWPR2Strategy_R
from common.data import csv_path

# --------------------------------------------------------------------
# 1. Carregar el CSV i preparar les dades en un DataFrame de pandas
# --------------------------------------------------------------------
fitxer_csv = csv_path('AMZN')
df = pd.read_csv(fitxer_csv)

# Eliminar la primera columna "Unnamed: 0" si apareix
df.drop(df.columns[0], axis=1, inplace=True)

# Establir la columna "Date" (o la corresponent) com a índex i convertir a datetime
df.set_index(df.columns[0], inplace=True)
df.index = pd.to_datetime(df.index)

# Crear les columnes de BULL, BEAR i finalment la BBr
df["BULL"] = 0.33 * (df["positivePartscr"] + df["certaintyPartscr"] + df["finhypePartscr"])
df["BEAR"] = 0.33 * (df["negativePartscr"] + df["uncertaintyPartscr"] + df["findownPartscr"])
df["BBr"] = 100 * df["BULL"] / (df["BULL"] + df["BEAR"])

# Calcular el retorn diari utilitzant la columna 'Close' (pots canviar a 'Adj Close')
df["DailyReturn"] = df["Adj Close"].pct_change() * 100  # Retorn diari en percentatge
print("El nombre de files amb sentiment NULL és:", df[(df["BULL"] + df["BEAR"]) == 0].shape[0])
#les files amb sentiment null, escollim un bbr de 50
df["BBr"] = df["BBr"].replace(0, 50)


#separar les dades en train i test fent 1/4 per train i 3/4 per test
train_size = int(len(df) * 0.25)
train = df.iloc[:train_size]
test = df.iloc[train_size:]
print("Train:", train.shape, "Test:", test.shape)

#veamos el maximo de la columna BBr
print("El màxim de la columna BBr és:", df["BBr"].max())
print("El mínim de la columna BBr és:", df["BBr"].min())
#la mitjana entre els dos valors és
print("La mitjana entre els dos valors és:", (df["BBr"].min()+df["BBr"].max())//2)

BBr_max = int(df["BBr"].max())
BBr_min = int(df["BBr"].min())
BBr_av = int((df["BBr"].min()+df["BBr"].max())//2)

possible_upper = range(BBr_av, BBr_max)
possible_lower = range(BBr_min, BBr_av)       
possible_neutral_lower = range(BBr_av-15, BBr_av)
possible_neutral_upper = range(BBr_av, BBr_av+15, 1)# 45, 48

def run_backtest(upper_threshold, lower_threshold, wpr_os, wpr_ob, wpr_period, ema_period, ema_th, neutral_lower, neutral_upper):
    # 1. Crear Cerebro
    cerebro = bt.Cerebro(stdstats=False)
    
    # 2. Crear feed desde el CSV
    data = MyPandasDataSentiment7_R(dataname=train)
    cerebro.adddata(data)

    # 3. Añadir la estrategia
    cerebro.addstrategy(
        SentimentWPR2Strategy_R,
        upper_threshold=upper_threshold,
        lower_threshold=lower_threshold,
        wpr_os=wpr_os,
        wpr_ob=wpr_ob,
        wpr_period=wpr_period,
        ema_period=ema_period,
        ema_th=ema_th,
        neutral_lower=neutral_lower,
        neutral_upper=neutral_upper,
        allow_long=True,
        allow_short=True
    )

    # 4. Broker
    cerebro.broker.setcash(100000.0)
    cerebro.broker.setcommission(commission=0.01)

    # 5. Run
    cerebro.run(maxcpus=1)  # Usar maxcpus=1 evita overhead en multiproceso (más estable en Windows)

    # 6. Valor final
    final_value = cerebro.broker.getvalue()

    return final_value

# --------------------------------------------------------------------
def objective(trial):
    # Definir los límites de los parámetros correctamente
    up = trial.suggest_int('upper_threshold', BBr_av, BBr_max)
    low = trial.suggest_int('lower_threshold', BBr_min, up - 2)  # Asegurar que low < up - 2

    # Verificación temprana para descartar combinaciones inválidas
    if low >= up:
        trial.report(-1e9, step=0)  # Reportar valor malo
        raise optuna.TrialPruned()  # Pruning temprano para ahorrar cómputo

    # Definir neutral_lower con restricciones adecuadas
    nl_min = low + 1
    nl_max = up - 2

    # Validación de rangos antes de sugerir valores
    if nl_min > nl_max:  # Ahora permitimos igualdad, pero no si nl_min > nl_max
        trial.report(-1e9, step=1)
        raise optuna.TrialPruned()

    nl = trial.suggest_int('neutral_lower', nl_min, nl_max)

    # Definir neutral_upper, ahora permitimos que sea igual a neutral_lower
    nu_min = nl  # Antes era nl + 1, ahora permitimos igualdad
    nu_max = up - 1

    if nu_min > nu_max:  # Evitamos valores inválidos
        trial.report(-1e9, step=2)
        raise optuna.TrialPruned()

    nu = trial.suggest_int('neutral_upper', nu_min, nu_max)

    # Sugerencias para otros parámetros
    wpr_os = trial.suggest_int('wpr_os', -100, -75)
    wpr_ob = trial.suggest_int('wpr_ob', -25, 0)
    wpr_period = trial.suggest_int('wpr_period', 10, 20)

    ema_period = trial.suggest_int('ema_period', 15, 50)
    ema_th = trial.suggest_int('ema_th', 40, 60)

    # Ejecutar el backtest
    final_val = run_backtest(up, low, wpr_os, wpr_ob, wpr_period, ema_period, ema_th, nl, nu)

    # Reportar el valor del objetivo a Optuna
    trial.report(final_val, step=3)

    # Si el rendimiento es bajo, considerar pruning
    if trial.should_prune():
        raise optuna.TrialPruned()

    return final_val

# Configurar Optuna con paralelización para optimización más rápida
study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=700, n_jobs=4)  # Ejecuta en paralelo en 4 núcleos

# Mostrar los mejores parámetros encontrados
print("\nEls millors paràmetres són:", study.best_params)
print("Valor óptimo:", study.best_value)
