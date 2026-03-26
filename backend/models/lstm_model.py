import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error
import logging

logger = logging.getLogger(__name__)


class DemandDataset(Dataset):
    def __init__(self, sequences, targets):
        self.sequences = torch.FloatTensor(sequences)
        self.targets = torch.FloatTensor(targets)

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, idx):
        return self.sequences[idx], self.targets[idx]


class LSTMModel(nn.Module):
    def __init__(self, input_size, hidden_size=64, num_layers=2, dropout=0.2, forecast_horizon=12):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.forecast_horizon = forecast_horizon

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
        )
        self.attention = nn.Sequential(
            nn.Linear(hidden_size, hidden_size),
            nn.Tanh(),
            nn.Linear(hidden_size, 1),
        )
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, forecast_horizon),
        )

    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        attn_weights = torch.softmax(self.attention(lstm_out), dim=1)
        context = (lstm_out * attn_weights).sum(dim=1)
        output = self.fc(context)
        return output


class LSTMForecaster:
    def __init__(self, lookback=24, forecast_horizon=12, hidden_size=64,
                 num_layers=2, epochs=50, batch_size=32, lr=0.001):
        self.lookback = lookback
        self.forecast_horizon = forecast_horizon
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.epochs = epochs
        self.batch_size = batch_size
        self.lr = lr
        self.models = {}
        self.scalers = {}
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def _prepare_features(self, df, sku_id, ext_features=None):
        sku_data = df[df["sku_id"] == sku_id].copy()
        ts = sku_data.groupby("date").agg({
            "units_sold": "sum",
            "price": "mean",
            "promotion_flag": "max",
        }).reset_index()
        ts["date"] = pd.to_datetime(ts["date"])
        ts = ts.set_index("date").sort_index()
        ts["units_sold"] = ts["units_sold"].interpolate().fillna(0)

        weekly = ts.resample("W").agg({
            "units_sold": "sum",
            "price": "mean",
            "promotion_flag": "max",
        })

        if ext_features is not None:
            ext = ext_features.copy()
            ext["date"] = pd.to_datetime(ext["date"])
            ext = ext.set_index("date").resample("W").mean()
            weekly = weekly.join(ext, how="left")

        weekly = weekly.fillna(0)

        weekly["lag_1"] = weekly["units_sold"].shift(1)
        weekly["lag_4"] = weekly["units_sold"].shift(4)
        weekly["rolling_mean_4"] = weekly["units_sold"].rolling(4).mean()
        weekly["rolling_std_4"] = weekly["units_sold"].rolling(4).std()
        weekly["month"] = weekly.index.month / 12.0
        weekly["week_of_year"] = weekly.index.isocalendar().week.values / 52.0

        weekly = weekly.dropna()
        return weekly

    def _create_sequences(self, data, target_col_idx=0):
        sequences, targets = [], []
        for i in range(len(data) - self.lookback - self.forecast_horizon + 1):
            seq = data[i : i + self.lookback]
            tgt = data[i + self.lookback : i + self.lookback + self.forecast_horizon, target_col_idx]
            sequences.append(seq)
            targets.append(tgt)
        return np.array(sequences), np.array(targets)

    def fit(self, df, sku_id, ext_features=None):
        weekly = self._prepare_features(df, sku_id, ext_features)
        values = weekly.values.astype(np.float32)

        scaler = MinMaxScaler()
        scaled = scaler.fit_transform(values)
        self.scalers[sku_id] = scaler

        sequences, targets = self._create_sequences(scaled)
        if len(sequences) < 10:
            logger.warning(f"Not enough data for LSTM training on {sku_id}")
            return False

        dataset = DemandDataset(sequences, targets)
        loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)

        input_size = sequences.shape[2]
        model = LSTMModel(
            input_size=input_size,
            hidden_size=self.hidden_size,
            num_layers=self.num_layers,
            forecast_horizon=self.forecast_horizon,
        ).to(self.device)

        optimizer = torch.optim.Adam(model.parameters(), lr=self.lr)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)
        criterion = nn.HuberLoss()

        model.train()
        for epoch in range(self.epochs):
            total_loss = 0
            for batch_x, batch_y in loader:
                batch_x, batch_y = batch_x.to(self.device), batch_y.to(self.device)
                optimizer.zero_grad()
                output = model(batch_x)
                loss = criterion(output, batch_y)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                total_loss += loss.item()
            avg_loss = total_loss / len(loader)
            scheduler.step(avg_loss)

        self.models[sku_id] = model
        logger.info(f"LSTM fitted for {sku_id}, final loss={avg_loss:.4f}")
        return True

    def predict(self, df, sku_id, ext_features=None):
        if sku_id not in self.models:
            raise ValueError(f"No fitted model for {sku_id}")

        weekly = self._prepare_features(df, sku_id, ext_features)
        values = weekly.values.astype(np.float32)
        scaler = self.scalers[sku_id]
        scaled = scaler.fit_transform(values)

        last_seq = scaled[-self.lookback:]
        last_seq = torch.FloatTensor(last_seq).unsqueeze(0).to(self.device)

        model = self.models[sku_id]
        model.eval()
        with torch.no_grad():
            pred_scaled = model(last_seq).cpu().numpy()[0]

        dummy = np.zeros((len(pred_scaled), values.shape[1]))
        dummy[:, 0] = pred_scaled
        pred_unscaled = scaler.inverse_transform(dummy)[:, 0]
        pred_unscaled = np.maximum(pred_unscaled, 0)
        return pred_unscaled

    def evaluate(self, df, sku_id, ext_features=None):
        weekly = self._prepare_features(df, sku_id, ext_features)
        values = weekly.values.astype(np.float32)

        test_size = self.forecast_horizon
        train_values = values[:-test_size]
        test_actuals = values[-test_size:, 0]

        scaler = MinMaxScaler()
        scaled_train = scaler.fit_transform(train_values)
        self.scalers[sku_id] = scaler

        sequences, targets = self._create_sequences(scaled_train)
        if len(sequences) < 5:
            return None

        dataset = DemandDataset(sequences, targets)
        loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)

        input_size = sequences.shape[2]
        model = LSTMModel(
            input_size=input_size,
            hidden_size=self.hidden_size,
            num_layers=self.num_layers,
            forecast_horizon=self.forecast_horizon,
        ).to(self.device)

        optimizer = torch.optim.Adam(model.parameters(), lr=self.lr)
        criterion = nn.HuberLoss()

        model.train()
        for _ in range(self.epochs):
            for batch_x, batch_y in loader:
                batch_x, batch_y = batch_x.to(self.device), batch_y.to(self.device)
                optimizer.zero_grad()
                loss = criterion(model(batch_x), batch_y)
                loss.backward()
                optimizer.step()

        model.eval()
        last_seq = scaled_train[-self.lookback:]
        last_seq = torch.FloatTensor(last_seq).unsqueeze(0).to(self.device)
        with torch.no_grad():
            pred_scaled = model(last_seq).cpu().numpy()[0]

        dummy = np.zeros((len(pred_scaled), train_values.shape[1]))
        dummy[:, 0] = pred_scaled
        preds = scaler.inverse_transform(dummy)[:, 0]
        preds = np.maximum(preds, 0)

        mae = mean_absolute_error(test_actuals, preds)
        rmse = np.sqrt(mean_squared_error(test_actuals, preds))

        test_dates = weekly.index[-test_size:]

        self.models[sku_id] = model
        return {
            "sku_id": sku_id,
            "model": "LSTM",
            "mae": round(mae, 2),
            "rmse": round(rmse, 2),
            "actuals": test_actuals.tolist(),
            "predictions": preds.tolist(),
            "dates": [d.strftime("%Y-%m-%d") for d in test_dates],
        }
