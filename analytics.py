import pandas as pd
import numpy as np

class BMSAnalytics:
    def __init__(self, filename="battery_master_log.csv"):
        try:
            self.df = pd.read_csv(filename)
            self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
        except Exception:
            self.df = pd.DataFrame()

    def analyze(self):
        if self.df.empty or len(self.df) < 2:
            return self._empty_metrics()

        latest = self.df.iloc[-1]
        
        # 1. State of Health (SoH)
        soh = (latest['energy_full_wh'] / latest['energy_design_wh']) * 100
        
        # 2. Discharge Efficiency (How steady is the voltage under load?)
        # Higher variation under constant load = higher internal resistance
        rolling_v = self.df['voltage_v'].rolling(window=5).std()
        v_stability = 100 - (rolling_v.mean() * 10) # Proxy metric
        
        # 3. Comprehensive Health Score (Weighted)
        # Factors: SoH (60%), Cycles (20%), Thermal History (20%)
        cycle_penalty = min(20, (latest['cycles'] / 1000) * 20)
        temp_penalty = 20 if self.df['temp_c'].max() > 45 else 0
        health_score = (soh * 0.6) + (20 - cycle_penalty) + (20 - temp_penalty)

        # 4. Discharge Trend Prediction
        # Simple linear regression on the last 10 samples of PCT
        recent = self.df.tail(10)
        y = recent['pct'].values
        x = np.arange(len(y)).reshape(-1, 1)
        from sklearn.linear_model import LinearRegression
        model = LinearRegression().fit(x, y)
        slope = model.coef_[0] # % change per interval

        # 5. Recommendations Logic
        recs = []
        if latest['temp_c'] > 40: recs.append("Critical: Thermal throttling advised. High temp reduces lifespan.")
        if soh < 80: recs.append("Battery reaching End-of-Life (SoH < 80%). Consider replacement.")
        if slope < -0.5: recs.append("Rapid Discharge: Heavy background processes detected.")

        return {
            "SoH (%)": round(soh, 2),
            "Health Score": int(health_score),
            "Discharge Rate": round(slope, 3),
            "Stability Index": round(v_stability, 2),
            "Cycle Count": int(latest['cycles']),
            "Recommendations": recs
        }

    def _empty_metrics(self):
        return {"SoH (%)": 0, "Health Score": 0, "Discharge Rate": 0, 
                "Stability Index": 0, "Cycle Count": 0, "Recommendations": ["Waiting for data..."]}