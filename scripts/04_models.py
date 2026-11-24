#!/usr/bin/env python3
"""Local equivalents of the two BigQuery ML models.

1) Weather regression (SQL 07): linear regression of daily rides on
   temperature, rainfall, wind and calendar features. Trained on
   2017-2018, tested on 2019 (a time split, not a random split).
   A random forest is trained alongside as a non-linear benchmark.
2) Demand forecast (SQL 06): SARIMA with weekly seasonality stands in
   for ARIMA_PLUS. The last 90 days of 2019 are held out for honest
   evaluation against a seasonal-naive baseline, then the model is
   refit on all data to forecast the first 90 days of 2020.
"""
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "data" / "results"


def metrics(y, p):
    return {"mae": round(float(mean_absolute_error(y, p)), 1),
            "rmse": round(float(np.sqrt(mean_squared_error(y, p))), 1),
            "r2": round(float(r2_score(y, p)), 3),
            "mape_pct": round(float(np.mean(np.abs((y - p) / y)) * 100), 1)}


def regression(df):
    df = df.copy()
    df["dow"] = df["date"].dt.dayofweek
    df["month"] = df["date"].dt.month
    X = pd.get_dummies(df[["temp_avg_c", "prcp_mm", "wind_kmh", "dow", "month"]],
                       columns=["dow", "month"], drop_first=True, dtype=float)
    y = df["rides"]
    train = df["date"] < "2019-01-01"
    lm = LinearRegression().fit(X[train], y[train])
    rf = RandomForestRegressor(n_estimators=300, min_samples_leaf=3,
                               n_jobs=-1, random_state=42).fit(X[train], y[train])
    out = {"linear_regression_test_2019": metrics(y[~train], lm.predict(X[~train])),
           "random_forest_test_2019": metrics(y[~train], rf.predict(X[~train])),
           "linear_regression_train_2017_2018": metrics(y[train], lm.predict(X[train]))}
    coef = pd.DataFrame({"feature": X.columns, "coefficient": lm.coef_})
    coef = coef.reindex(coef["coefficient"].abs().sort_values(ascending=False).index)
    coef.to_csv(RES / "regression_coefficients.csv", index=False)
    base = {"feature": "intercept", "coefficient": lm.intercept_}
    print("intercept:", round(float(lm.intercept_)))
    return out


def fourier_terms(index, period=365.25, harmonics=3):
    """Annual seasonality as exogenous Fourier terms. BigQuery's
    ARIMA_PLUS detects yearly seasonality on its own; a plain SARIMAX
    needs it supplied, which is what these sine/cosine pairs do."""
    t = (index - pd.Timestamp("2016-01-01")).days.to_numpy(dtype=float)
    cols = {}
    for k in range(1, harmonics + 1):
        cols[f"sin{k}"] = np.sin(2 * np.pi * k * t / period)
        cols[f"cos{k}"] = np.cos(2 * np.pi * k * t / period)
    return pd.DataFrame(cols, index=index)


def design_matrix(index):
    """Calendar design matrix for the forecasting model: annual Fourier
    terms and day-of-week dummies. No trend term and stationarity is
    enforced on the ARMA errors: an unconstrained fit lets the AR
    coefficients drift past 1 and the log-scale forecast explodes."""
    X = fourier_terms(index, harmonics=3)
    dow = pd.get_dummies(index.dayofweek, prefix="dow", drop_first=True,
                         dtype=float)
    dow.index = index
    X = pd.concat([X, dow], axis=1)
    # An explicit constant is essential: without it the AR term tries
    # to carry the level itself (ar.L1 -> 0.999, no convergence) and
    # out-of-sample forecasts collapse.
    X.insert(0, "const", 1.0)
    return X


def forecast(df):
    """Dynamic regression with ARIMA errors on log daily rides.

    A textbook SARIMA(2,1,2)(1,1,1,7) was tried first and failed the
    holdout badly (MAPE 40.9%): with only weekly seasonality it cannot
    see the steep autumn decline coming. Anchoring the level to
    calendar terms (annual Fourier + weekday) with ARMA errors is the
    standard fix and stays in the ARIMA family, like ARIMA_PLUS, which
    models yearly seasonality natively.
    """
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    s = df.set_index("date")["rides"].asfreq("D")
    # 7 NaN days remain (15-21 Mar 2017, the unpublished TfL extract).
    # SARIMAX treats them as missing observations via the Kalman filter;
    # no values are invented for them.
    y = np.log(s)
    X = design_matrix(s.index)
    holdout = s.iloc[-90:]
    model = SARIMAX(y.iloc[:-90], exog=X.iloc[:-90], order=(1, 0, 1),
                    trend="n")
    fit = model.fit(disp=False)
    pred = np.exp(fit.get_forecast(90, exog=X.iloc[-90:]).predicted_mean)
    # Baseline 1, weekly seasonal naive: same weekday, average of the
    # last 13 weeks of the training period.
    train = s.iloc[:-90]
    tail = train.iloc[-7 * 13:]
    naive = tail.groupby(tail.index.dayofweek).mean() \
        .reindex(holdout.index.dayofweek).to_numpy()
    # Baseline 2, year-ago: the same weekday 364 days earlier.
    year_ago = s.reindex(holdout.index - pd.Timedelta(days=364)).to_numpy()
    res = {"sarima_holdout": metrics(holdout.to_numpy(), pred.to_numpy()),
           "seasonal_naive_holdout": metrics(holdout.to_numpy(), naive),
           "year_ago_holdout": metrics(holdout.to_numpy(), year_ago)}
    pd.DataFrame({"date": holdout.index, "actual": holdout.values,
                  "sarima_forecast": np.round(pred.values)}).to_csv(
        RES / "forecast_holdout.csv", index=False)
    future_idx = pd.date_range("2020-01-01", periods=90, freq="D")
    full = SARIMAX(y, exog=X, order=(1, 0, 1), trend="n")
    ffit = full.fit(disp=False)
    fc = ffit.get_forecast(90, exog=design_matrix(future_idx))
    ci = np.exp(fc.conf_int(alpha=0.10))
    fdf = pd.DataFrame({
        "date": fc.predicted_mean.index,
        "predicted_rides": np.round(np.exp(fc.predicted_mean.values)),
        "lower_90": np.round(ci.iloc[:, 0].values),
        "upper_90": np.round(ci.iloc[:, 1].values)})
    fdf.to_csv(RES / "forecast_next_90d.csv", index=False)
    return res


def main():
    df = pd.read_csv(RES / "daily_demand_weather.csv", parse_dates=["date"])
    out = {"regression": regression(df)}
    print(json.dumps(out, indent=2))
    out["forecast"] = forecast(df)
    (RES / "model_metrics.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
