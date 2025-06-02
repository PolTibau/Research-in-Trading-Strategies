import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import backtrader as bt
import optuna
from S_BI_EMA_optimized_strategy import MyPandasDataSentiment_BI_EMA_R, SentimentBI_EMA_Strategy_R

# --------------------------------------------------------------------
# 1. Carregar el CSV i preparar les dades en un DataFrame de pandas
# --------------------------------------------------------------------
fitxer_parquet = r'C:\Users\polti\OneDrive\Documents\FME\Trading\data\AAPL_reord.parquet'
df = pd.read_parquet(fitxer_parquet)

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
df["DailyReturn"] = df["Close"].pct_change() * 100  # Retorn diari en percentatge
print("El nombre de files amb sentiment NULL és:", df[(df["BULL"] + df["BEAR"]) == 0].shape[0])
#les files amb sentiment null, escollim un bbr de 50
df["BBr"] = df["BBr"].fillna(50)


#separar les dades en train i test fent 7/10 per train i 3/10 per test
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

#mean_price = df['close'].mean()


def run_backtest(upper_threshold, lower_threshold, long_ema_period, short_ema_period, ema_margin_pct, neutral_lower, neutral_upper):
    # 1. Crear Cerebro
    cerebro = bt.Cerebro(stdstats=False)
    
    # 2. Crear feed desde el CSV
    data = MyPandasDataSentiment_BI_EMA_R(dataname=train)
    cerebro.adddata(data)

    # 3. Añadir la estrategia
    cerebro.addstrategy(
        SentimentBI_EMA_Strategy_R,
        upper_threshold=upper_threshold,
        lower_threshold=lower_threshold,
        long_ema_period=long_ema_period,
        short_ema_period=short_ema_period,
        ema_margin_pct=ema_margin_pct,
        neutral_lower=neutral_lower,
        neutral_upper=neutral_upper,
        allow_long=True,
        allow_short=True
    )

    # 4. Broker
    cerebro.broker.setcash(100000.0)
    cerebro.broker.setcommission(commission=0.003)
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')


    # 5. Run
    results = cerebro.run(maxcpus=1)  # Usar maxcpus=1 evita overhead en multiproceso (más estable en Windows)
    strategy = results[0]

    # 6. Valor final
    final_value = cerebro.broker.getvalue()
    trades_analyzer = strategy.analyzers.trades.get_analysis()

    total_trades = trades_analyzer.total.get('closed', 0)

    return final_value, total_trades

# --------------------------------------------------------------------
def objective(trial):
    # Definir los límites de los parámetros correctamente
    up = trial.suggest_int('upper_threshold', BBr_av, BBr_max)
    low = trial.suggest_int('lower_threshold', BBr_min, up - 1)  # Asegurar que low < up - 2

    # Verificación temprana para descartar combinaciones inválidas
    if low >= up:
        return float('-1e9')

    # Definir neutral_lower con restricciones adecuadas
    nl_min = low + 1
    nl_max = up - 2
    if nl_min > nl_max:  # Ahora permitimos igualdad, pero no si nl_min > nl_max
        return float('-1e9')

    nl = trial.suggest_int('neutral_lower', nl_min, nl_max)

    # Definir neutral_upper, ahora permitimos que sea igual a neutral_lower
    nu_min = nl
    nu_max = up - 1

    if nu_min > nu_max:  # Evitamos valores inválidos
        return float('-1e9')

    nu = trial.suggest_int('neutral_upper', nu_min, nu_max)

    # Sugerencias para otros parámetros

    long_ema_period = trial.suggest_int('long_ema_period', 20, 50)
    short_ema_period = trial.suggest_int('short_ema_period', 3, 19)
    ema_margin_pct = trial.suggest_float('ema_margin_pct', 0.003, 0.01, step=0.0001)  # 1% a 5%
    # Ejecutar el backtest
    final_val, total_trades = run_backtest(up, low, long_ema_period, short_ema_period, ema_margin_pct, nl, nu)

        # Penalización: si hay pocas operaciones, reducimos el score
    if total_trades < 10:
        penalty = 0.1
    elif total_trades < 15:
        penalty = 0.3
    elif total_trades < 20:
        penalty = 0.5  # puedes ajustar este valor
    else:
        penalty = 1.0

    return final_val * penalty

# Configurar Optuna con paralelización para optimización más rápida
study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=2000)  # Ejecuta en paralelo en 4 núcleos

# Mostrar los mejores parámetros encontrados
print("\nEls millors paràmetres són:", study.best_params)
print("Valor óptimo:", study.best_value)
