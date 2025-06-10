import pandas as pd
import os
import numpy as np
import matplotlib.pyplot as plt
import backtrader as bt
import optuna
from NOUS_R_optimized_strategySLTP import NOUMyPandasDataSentiment_ROC_R, NOUSentimentROC_Strategy_R

# --------------------------------------------------------------------
# 1. Carregar el CSV i preparar les dades en un DataFrame de pandas
# --------------------------------------------------------------------
fitxer_parquet = r'C:\Users\polti\OneDrive\Documents\FME\Trading\data\DB_reord.parquet'
df = pd.read_parquet(fitxer_parquet)

# Eliminar la primera columna "Unnamed: 0" si apareix
df.drop(df.columns[0], axis=1, inplace=True)

# Establir la columna "Date" (o la corresponent) com a índex i convertir a datetime
df.set_index(df.columns[0], inplace=True)
df.index = pd.to_datetime(df.index)

# Crear les columnes de BULL, BEAR i finalment la BBr
df["BULL"] = 0.33 * (df["positivePartscr"] + df["certaintyPartscr"] + df["finupPartscr"])
df["BEAR"] = 0.33 * (df["negativePartscr"] + df["uncertaintyPartscr"] + df["findownPartscr"])
df["BBr"] = 100 * df["BULL"] / (df["BULL"] + df["BEAR"])

# Calcular el retorn diari utilitzant la columna 'Close' (pots canviar a 'Adj Close')
df["DailyReturn"] = df["Close"].pct_change() * 100  # Retorn diari en percentatge
print("El nombre de files amb sentiment NULL és:", df[(df["BULL"] + df["BEAR"]) == 0].shape[0])
#les files amb sentiment null, escollim un bbr de 50
df["BBr"] = df["BBr"].fillna(50)


#separar les dades en train i test fent 1/4 per train i 3/4 per test
train_size = int(len(df) * 0.7)
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

def run_backtest(upper_threshold, lower_threshold, mom_lb, mom_avg, ema_period, atr_p, sl_mul, tp_mul):
    # 1. Crear Cerebro
    cerebro = bt.Cerebro(stdstats=False)
    
    # 2. Crear feed desde el CSV
    data = NOUMyPandasDataSentiment_ROC_R(dataname=train)
    cerebro.adddata(data)

    # 3. Añadir la estrategia
    cerebro.addstrategy(
        NOUSentimentROC_Strategy_R,
        upper_threshold=upper_threshold,
        lower_threshold=lower_threshold,
        mom_lb=mom_lb, 
        mom_avg=mom_avg,
        ema_period=ema_period,
        atr_p=atr_p,
        sl_mul=sl_mul,
        tp_mul=tp_mul,
        allow_short=True,
        allow_long=False
    )


    # 4. Broker
    cerebro.broker.setcash(100000.0)
    cerebro.broker.setcommission(commission=0.005)

    # 5. Run
    cerebro.run(maxcpus=1)  # Usar maxcpus=1 evita overhead en multiproceso (más estable en Windows)

    # 6. Valor final
    final_value = cerebro.broker.getvalue()

    return final_value

# --------------------------------------------------------------------
def objective(trial):
    # Definir los límites de los parámetros correctamente
    upper_threshold = trial.suggest_int('upper_threshold', BBr_av, BBr_max)
    lower_threshold = trial.suggest_int('lower_threshold', BBr_min, upper_threshold - 1)

    mom_lb = trial.suggest_int('mom_lb', 3, 10)
    mom_avg = trial.suggest_float('mom_avg', 0.0, 0.3, step=0.01)
    ema_period = trial.suggest_int('ema_period', 30, 80)

    atr_p  = trial.suggest_int('atr_p', 10, 30)
    sl_mul = trial.suggest_float('sl_mul', 1.0, 10.0, step=0.01)
    tp_mul = trial.suggest_float('tp_mul', 1.0, 10.0, step=0.01)

    # Ejecutar el backtest
    final_val = run_backtest(upper_threshold, lower_threshold, mom_lb, mom_avg, ema_period, atr_p, sl_mul, tp_mul)

    return final_val

study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=1000)  # prueba 200 iteraciones

print()
print("Els millors paràmetres són:", study.best_params)
print("Valor óptimo:", study.best_value)

# Imprimir en formato listo para pegar
best_params = study.best_params
formatted = (
    f"upper_threshold={best_params['upper_threshold']}, "
    f"lower_threshold={best_params['lower_threshold']}, "
    f"mom_lb={best_params['mom_lb']}, "
    f"mom_avg={best_params['mom_avg']}, "
    f"ema_period={best_params['ema_period']}, "
    f"atr_p={best_params['atr_p']}, "
    f"sl_mul={best_params['sl_mul']}, "
    f"tp_mul={best_params['tp_mul']}, "
    f"allow_long=True, allow_short=True"
)

print("\nParámetros para copiar directamente:\n", formatted)

