import streamlit as st
import backtrader as bt
import yfinance as yf
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from sklearn.ensemble import RandomForestClassifier
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
import time

matplotlib.use('Agg')

# 函數：獲取股票數據
def get_stock_data(code, start_date, end_date, short_period, long_period):
    df = yf.download(code, start=start_date, end=end_date)
    if df.empty:
        st.error(f"無法下載股票代碼 {code} 的數據，請檢查股票代碼和日期範圍。")
        return None
    df = df.sort_index(ascending=True)
    df['SMA_10'] = df['Close'].rolling(window=short_period).mean()
    df['SMA_20'] = df['Close'].rolling(window=long_period).mean()
    df = df.dropna()
    return df

def create_dataset(stock_data, window_size):
    X = []
    y = []
    scaler = MinMaxScaler()
    stock_data_normalized = scaler.fit_transform(stock_data[['Close', 'SMA_10', 'SMA_20']].values)

    for i in range(len(stock_data) - window_size - 2):
        X.append(stock_data_normalized[i:i + window_size])
        if stock_data.iloc[i + window_size + 2]['Close'] > stock_data.iloc[i + window_size - 1]['Close']:
            y.append(1)
        else:
            y.append(0)

    X, y = np.array(X), np.array(y)
    return X, y, scaler

# 定義隨機森林策略
class RFStrategy(bt.Strategy):
    params = (
        ("window_size", 10),
        ("scaler", None),
        ("model", None),
        ("short_period", 10),
        ("long_period", 20),
    )

    def __init__(self):
        self.data_close = self.datas[0].close
        self.sma10 = bt.indicators.SimpleMovingAverage(self.datas[0], period=self.params.short_period)
        self.sma20 = bt.indicators.SimpleMovingAverage(self.datas[0], period=self.params.long_period)
        self.counter = 1
        self.buyprice = None
        self.buycomm = None

    def log(self, txt, dt=None):
        pass

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
            self.bar_executed = len(self)

        self.order = None

    def notify_trade(self, trade):
        pass

    def next(self):
        if self.counter < self.params.window_size:
            self.counter += 1
            return

        previous_features = [[self.data_close[-i], self.sma10[-i], self.sma20[-i]] for i in range(0, self.params.window_size)]
        X = np.array(previous_features).reshape(self.params.window_size, -1)

        print("Shape of X before scaling (Random Forest):", X.shape)

        X = self.params.scaler.transform(X)
        X = X.reshape(1, -1)  # 將 X 重新調整為 2D 數組

        prediction = self.params.model.predict(X)
        predicted_trend = prediction[0]

        if predicted_trend == 1 and not self.position:
            self.order = self.buy()
        elif predicted_trend == 0 and self.position:
            self.order = self.sell()
        elif self.position:
            if self.data_close[0] < self.buyprice * 0.9:
                self.order = self.sell()
            elif self.data_close[0] > self.buyprice * 1.5:
                self.order = self.sell()

# 函數：訓練隨機森林模型
def train_random_forest():
    global rf_model_ready, trained_rf_model, scaler
    with st.spinner("開始訓練隨機森林..."):
        stock_data = get_stock_data(symbol, start_date, end_date, short_period, long_period)
        if stock_data is None:
            return

        window_size = 10
        X, y, scaler = create_dataset(stock_data[['Close', 'SMA_10', 'SMA_20']], window_size)

        print(X.shape)

        X = X.reshape(X.shape[0], -1)

        rf_model = RandomForestClassifier(n_estimators=100, random_state=42)
        rf_model.fit(X, y)

        trained_rf_model = rf_model
        rf_model_ready = True

# 函數：運行Backtrader
def run_backtrader():
    global scaler, rf_model_ready, trained_rf_model
    with st.spinner("運行Backtrader..."):
        while not rf_model_ready:
            time.sleep(1)

        st.write("隨機森林模型加載成功。")

        stock_data = get_stock_data(symbol, start_date, end_date, short_period, long_period)
        if stock_data is None:
            return

        cerebro = bt.Cerebro()
        cerebro.broker.set_cash(initial_cash)
        cerebro.broker.setcommission(commission=commission/100)

        cerebro.addstrategy(RFStrategy, scaler=scaler, model=trained_rf_model, short_period=short_period, long_period=long_period)

        data = bt.feeds.PandasData(dataname=stock_data)
        cerebro.adddata(data)

        results = cerebro.run()

        portvalue = cerebro.broker.getvalue()
        pnl = portvalue - initial_cash
        st.write(f'最終投資組合價值: ${portvalue:.2f}')
        st.write(f'盈虧: ${pnl:.2f}')

        roi = (portvalue - initial_cash) / initial_cash * 100
        st.write(f'投資報酬率: {roi:.2f}%')

        fig = cerebro.plot(style='candlestick')[0][0]
        st.pyplot(fig)

# Streamlit 應用
st.title("隨機森林股票交易策略")

st.markdown("""

### 策略概述
這個策略使用了一個簡單的長短期移動平均線（SMA）和一個基於隨機森林（Random Forest）模型來進行股票交易。主要步驟如下：

1. **獲取股票數據**：從Yahoo Finance下載指定股票的歷史數據。
2. **計算移動平均線**：計算短期和長期的移動平均線（SMA）。
3. **創建訓練數據集**：將股票數據轉換為隨機森林模型的訓練數據集。
4. **訓練隨機森林模型**：使用訓練數據集來訓練隨機森林模型。
5. **回測策略**：使用Backtrader回測引擎來運行交易策略，並評估其表現。

### 詳細步驟
1. **獲取股票數據**
   - 使用yfinance庫從Yahoo Finance下載股票數據。
   - 計算短期和長期的移動平均線，並將其添加到數據框中。

2. **創建訓練數據集**
   - 將股票數據轉換為隨機森林模型的訓練數據集。這裡使用了MinMaxScaler進行數據標準化。
   - 根據窗口大小（window_size）創建特徵和標籤。特徵是窗口內的股票價格和移動平均線，標籤是窗口結束後的價格變動方向（上漲或下跌）。

3. **訓練隨機森林模型**
   - 定義隨機森林模型的結構，包括多個決策樹。
   - 使用訓練數據集進行模型訓練，優化模型參數。

4. **回測策略**
   - 使用Backtrader回測引擎運行交易策略。
   - 策略根據隨機森林模型的預測結果進行交易決策。如果預測價格會上漲且目前沒有持倉，則買入股票；如果預測價格會下跌且目前有持倉，則賣出股票。
   - 策略還包括止損和止盈邏輯：如果價格下跌超過10%或上漲超過50%，則賣出股票。

5. **結果展示**
   - 回測完成後，顯示最終的投資組合價值、盈虧（P/L）和投資報酬率（ROI）。
   - 使用Matplotlib繪製回測結果的K線圖，並嵌入到Streamlit應用中展示。

### 使用方法
1. 在Streamlit應用中輸入股票符號、開始日期和結束日期。
2. 調整短期和長期移動平均線的參數、交易手續費、每次交易金額和初始現金。
3. 點擊“開始回測”按鈕，系統會自動訓練隨機森林模型並運行回測策略，最終展示回測結果。

這個策略結合了技術分析（移動平均線）和機器學習（隨機森林模型）的優勢，旨在提高交易決策的準確性和收益率。
""")

symbol = st.text_input("股票代碼", "AAPL")
start_date = st.date_input("開始日期", pd.to_datetime("2020-01-01"))
end_date = st.date_input("結束日期", pd.to_datetime("today"))

short_period = st.slider("短期均線", 1, 30, 5)
long_period = st.slider("長期均線", 30, 200, 60)
commission = st.slider('交易手續費 (%)', min_value=0.0, max_value=0.5, step=0.0005, format="%.4f", value=0.001)
trade_amount = st.slider("每次交易金額", min_value=0, max_value=50000, step=1000, value=1000)
initial_cash = st.slider("初始現金", min_value=0, max_value=10000000, step=10000, value=10000)

if st.button("開始回測"):
    rf_model_ready = False
    trained_rf_model = None
    scaler = None

    train_random_forest()
    run_backtrader()