import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import backtrader as bt
import optuna
from NOUS_R_optimized_strategySLTP import NOUMyPandasDataSentiment_ROC_R, NOUSentimentROC_Strategy_R

# --------------------------------------------------------------------
# 1. Carregar el CSV i preparar les dades en un DataFrame de pandas
# --------------------------------------------------------------------
fitxer_parquet = r'C:\Users\polti\OneDrive\Documents\FME\Trading\data\GOOG_reord.parquet'
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

def run_backtest(upper_threshold, lower_threshold, lookback, mom_lb, mom_avg, ma_period, atr_p, sl_mul, tp_mul):
    # 1. Crear Cerebro
    cerebro = bt.Cerebro(stdstats=False)
    
    # 2. Crear feed desde el CSV
    data = NOUMyPandasDataSentiment_ROC_R(dataname=train)
    cerebro.adddata(data)

    # 3. Añadir la estrategia
    cerebro.addstrategy(
        NOUSentimentROC_Strategy_R,
        upper_pct=upper_threshold,
        lower_pct=lower_threshold,
        lookback_thr=lookback,
        mom_lookback=mom_lb,  # ¡Aquí ojo! momentum_days es el parámetro que tenías en la función, pero ya lo sustituiste por mom_lb (corrígelo).
        mom_min_avg=mom_avg,
        sma_period=ma_period,
        atr_period=atr_p,
        sl_mult=sl_mul,
        tp_mult=tp_mul,
        allow_short=True,
        allow_long=True
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
    up = trial.suggest_int('upper_pct', 50, 85)
    low = trial.suggest_int('lower_pct', 15, min(up-10, 50))
    lookback = trial.suggest_int('lookback_thr', 50, 200)

    mom_lb = trial.suggest_int('mom_lookback', 3, 10)
    mom_avg = trial.suggest_float('mom_min_avg', 0.0, 0.3, step=0.01)
    ma_period = trial.suggest_int('sma_period', 50, 200)

    atr_p  = trial.suggest_int('atr_period', 10, 30)
    sl_mul = trial.suggest_float('sl_mult', 1.0, 4.0, step=0.1)
    tp_mul = trial.suggest_float('tp_mult', 1.0, 6.0, step=0.1)

    # Ejecutar el backtest
    final_val = run_backtest(up, low, lookback, mom_lb, mom_avg, ma_period, atr_p, sl_mul, tp_mul)

    return final_val

study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=1000)  # prueba 200 iteraciones

print()
print("Els millors paràmetres són:", study.best_params)
print("Valor óptimo:", study.best_value)
