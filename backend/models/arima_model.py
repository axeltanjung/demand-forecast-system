import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from sklearn.metrics import mean_absolute_error, mean_squared_error
import warnings
import logging

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)


class ARIMAForecaster:
    def __init__(self, order=(2, 1, 2), seasonal_order=None):
        self.order = order
        self.seasonal_order = seasonal_order
        self.models = {}
        self.results = {}

    def _prepare_series(self, df, sku_id):
        sku_data = df[df["sku_id"] == sku_id].copy()
        ts = sku_data.groupby("date")["units_sold"].sum().reset_index()
        ts["date"] = pd.to_datetime(ts["date"])
        ts = ts.set_index("date").sort_index()
        ts["units_sold"] = ts["units_sold"].interpolate(method="linear").fillna(method="bfill").fillna(0)
        return ts["units_sold"]

    def fit(self, df, sku_id):
        series = self._prepare_series(df, sku_id)
        weekly = series.resample("W").sum()
        try:
            model = ARIMA(weekly, order=self.order)
            result = model.fit()
            self.models[sku_id] = model
            self.results[sku_id] = result
            logger.info(f"ARIMA fitted for {sku_id}, AIC={result.aic:.2f}")
            return True
        except Exception as e:
            logger.error(f"ARIMA fit failed for {sku_id}: {e}")
            return False

    def predict(self, sku_id, steps=12):
        if sku_id not in self.results:
            raise ValueError(f"No fitted model for {sku_id}")
        result = self.results[sku_id]
        forecast = result.forecast(steps=steps)
        forecast = np.maximum(forecast.values, 0)
        return forecast

    def evaluate(self, df, sku_id, test_weeks=12):
        series = self._prepare_series(df, sku_id)
        weekly = series.resample("W").sum()

        train = weekly[:-test_weeks]
        test = weekly[-test_weeks:]

        try:
            model = ARIMA(train, order=self.order)
            result = model.fit()
            preds = result.forecast(steps=test_weeks)
            preds = np.maximum(preds.values, 0)
            actuals = test.values

            mae = mean_absolute_error(actuals, preds)
            rmse = np.sqrt(mean_squared_error(actuals, preds))

            return {
                "sku_id": sku_id,
                "model": "ARIMA",
                "mae": round(mae, 2),
                "rmse": round(rmse, 2),
                "actuals": actuals.tolist(),
                "predictions": preds.tolist(),
                "dates": [d.strftime("%Y-%m-%d") for d in test.index],
            }
        except Exception as e:
            logger.error(f"ARIMA eval failed for {sku_id}: {e}")
            return None
