import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import yfinance as yf
import backtrader as bt
import datetime
import matplotlib.pyplot as plt
from prophet import Prophet
from dateutil.relativedelta import relativedelta
import matplotlib
matplotlib.use('Agg')

# Prophet預測函數
def predict_stock(selected_stock, n_years):
    data = yf.download(selected_stock, start="2015-01-01", end=datetime.datetime.now().strftime("%Y-%m-%d"))
    data.reset_index(inplace=True)

    df_train = data[['Date', 'Close']]
    df_train = df_train.rename(columns={"Date": "ds", "Close": "y"})

    m = Prophet()
    m.fit(df_train)
    future = m.make_future_dataframe(periods=n_years * 365)
    forecast = m.predict(future)

    return data, forecast, m

class PeriodicInvestmentStrategy(bt.Strategy):
    params = (
        ('monthly_investment', None),  # 每期投資金額
        ('commission', None),  # 手續費
        ('investment_day', None),  # 投資日
        ('printlog', True),  # 是否打印交易日志
    )

    def __init__(self, **kwargs):
        self.order = None
        self.add_timer(
            when=bt.Timer.SESSION_START,
            monthdays=[self.params.investment_day],  # 每月的特定日期投资
            monthcarry=True,  # 如果特定日期不是交易日，則延至下一個交易日
        )

        # 从kwargs中获取初始资金
        self.initial_cash = kwargs.get('initial_cash', 10000)  # 初始資金設置為10000

    def notify_timer(self, timer, when, *args, **kwargs):
        self.log('進行定期投資')
        # 获取当前价格
        price = self.data.close[0]
        # 计算购买数量
        investment_amount = self.params.monthly_investment / price
        # 执行购买
        self.order = self.buy(size=investment_amount)

    def log(self, txt, dt=None):
        ''' 日誌函數 '''
        dt = dt or self.datas[0].datetime.date(0)
        if self.params.printlog:
            print('%s, %s' % (dt.isoformat(), txt))

    def notify_order(self, order):
        if order.status in [order.Completed]:
            if order.isbuy():
                cost = order.executed.price * order.executed.size
                commission = cost * self.params.commission / 100  # 将百分比转换为小数
                self.log('買入執行, 價格: %.2f, 成本: %.2f, 手續費: %.2f' %
                        (order.executed.price, cost, commission))

            elif order.issell():
                self.log('賣出執行, 價格: %.2f, 成本: %.2f, 手續費: %.2f' %
                        (order.executed.price,
                        order.executed.value,
                        order.executed.comm))

            self.bar_executed = len(self)

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('訂單 取消/保證金不足/拒絕')

        self.order = None


# Streamlit 页面布局
st.title('Backtest with Backtrader')

# 提示用戶輸入股票代碼，並使用逗號分隔
user_input = st.text_area("請輸入股票代碼，用逗號分隔，台股請記得在最後加上.TW", "AAPL, MSFT, GOOG, AMZN, 0050.TW")
# 將用戶輸入的股票代碼轉換為列表
stocks = [stock.strip() for stock in user_input.split(",")]
st.write("您輸入的股票代碼：", stocks)

# 股票选择器和预测年限滑块
selected_stock = st.selectbox('Select stock for prediction and backtest', stocks)
n_years = st.slider('Years of prediction:', 1, 10)

# 预测和显示结果
if st.button('Run Prediction'):
    # 做预测并获取数据、预测结果和 Prophet 模型
    data, forecast, m = predict_stock(selected_stock, n_years)
    st.write('Forecast data:')
    st.write(forecast)

    st.write(f'Forecast plot for {n_years} years')
    fig1 = m.plot(forecast)
    st.pyplot(fig1)

# 添加滑块来控制参数
initial_cash = st.slider('Budget', min_value=0, max_value=10000000, step=10000, value=10000)
monthly_investment = st.slider('Monthly Investment Amount', min_value=0, max_value=50000, step=1000, value=1000)
commission = st.slider('Commission Fee (%)', min_value=0.0, max_value=1.0, step=0.0001, format="%.4f", value=0.001)
investment_day = st.slider('Investment Day of Month', min_value=1, max_value=28, step=1, value=1)
n_years = st.slider('Backtest Duration (Years)', min_value=1, max_value=10, step=1, value=5)

# 执行回测并显示结果
if st.button('Run Backtest'):
    
    # 定义显示结果的函数
    def display_results(cash, value, initial_value, n_years):
        st.write(f"Budget: ${initial_cash:.2f}")
        st.write(f"Final Cash: ${cash:.2f}")
        st.write(f"Final Value: ${value:.2f}")
        
        # 计算年回报率
        annual_return = ((value - cash) / (initial_cash - cash)) ** (1 / n_years) - 1
        annual_return *= 100  # 转换为百分比形式
        st.write(f"Annual Return Rate: {annual_return:.2f}%")

    # 初始化 Cerebro 引擎
    cerebro = bt.Cerebro()
    cerebro.addstrategy(PeriodicInvestmentStrategy, initial_cash=initial_cash, monthly_investment=monthly_investment, commission=commission, investment_day=investment_day)

    # 添加数据
    start_date = datetime.datetime.now() - relativedelta(years=n_years)  # 根据回测年限动态计算开始时间
    data = yf.download(selected_stock,
                    start=start_date,
                    end=datetime.datetime.now())
    cerebro.adddata(bt.feeds.PandasData(dataname=data))

    # 设置初始资本
    cerebro.broker.setcash(initial_cash)

    # 设置每笔交易的手续费
    cerebro.broker.setcommission(commission=commission)

    # 执行策略
    cerebro.run()

    # 绘制结果
    fig = cerebro.plot(style='plotly')[0][0]  # 获取 Matplotlib 图形对象
    st.pyplot(fig)  # 将图形嵌入到 Streamlit 页面中


    # 获取初始总价值
    initial_value = cerebro.broker.get_value()

    # 获取当前现金余额和总价值
    cash = cerebro.broker.get_cash()
    value = cerebro.broker.get_value()

    # 显示结果
    display_results(cash, value, initial_value, n_years)

# Coze 聊天機器人的嵌入 URL
coze_bot_url = "https://www.coze.com/store/bot/7355203240146829328?bot_id=true"

# HTML 內容
html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        /* 聊天按鈕樣式 */
        .chat-button {{
        position: fixed;
        top: 20px;
        right: 20px;
        background-color: #0084ff;
        color: white;
        border: none;
        border-radius: 50%;
        width: 60px;
        height: 60px;
        font-size: 30px;
        text-align: center;
        cursor: pointer;
        z-index: 1000;
       }}     


        /* 聊天框樣式 */
        .chat-popup {{
            display: none;
            position: fixed;
            bottom: 80px;
            right: 20px;
            border: 3px solid #f1f1f1;
            z-index: 1000;
        }}

        .chat-popup iframe {{
            width: 400px;
            height: 500px;
            border: none;
        }}
    </style>
</head>
<body>

<!-- 聊天按鈕 -->
<button class="chat-button" onclick="toggleChat()">💬</button>

<!-- 聊天框 -->
<div class="chat-popup" id="chatPopup">
    <iframe src="{coze_bot_url}"></iframe>
</div>

<script>
    function toggleChat() {{
        var chatPopup = document.getElementById('chatPopup');
        if (chatPopup.style.display === 'none' || chatPopup.style.display === '') {{
            chatPopup.style.display = 'block';
        }} else {{
            chatPopup.style.display = 'none';
        }}
    }}
</script>

</body>
</html>
"""

# 將 HTML 嵌入 Streamlit 應用
components.html(html_content, height=700)

