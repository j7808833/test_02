import streamlit as st
import pandas as pd
import yfinance as yf
import backtrader as bt
import datetime
import matplotlib.pyplot as plt
from prophet import Prophet
from dateutil.relativedelta import relativedelta
import matplotlib
matplotlib.use('Agg')
from PIL import Image
import requests
from io import BytesIO
import streamlit as st

# Prophet预测函数
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
        ('monthly_investment', None),  # 每期投资金额
        ('commission', None),  # 手续费
        ('investment_day', None),  # 投资日
        ('printlog', True),  # 是否打印交易日志
    )

    def __init__(self, **kwargs):
        self.order = None
        self.add_timer(
            when=bt.Timer.SESSION_START,
            monthdays=[self.params.investment_day],  # 每月的特定日期投资
            monthcarry=True,  # 如果特定日期不是交易日，则延至下一个交易日
        )

        # 从kwargs中获取初始资金
        self.initial_cash = kwargs.get('initial_cash', 10000)  # 初始资金设置为10000

    def notify_timer(self, timer, when, *args, **kwargs):
        self.log('进行定期投资')
        # 获取当前价格
        price = self.data.close[0]
        # 计算购买数量
        investment_amount = self.params.monthly_investment / price
        # 执行购买
        self.order = self.buy(size=investment_amount)

    def log(self, txt, dt=None):
        ''' 日志函数 '''
        dt = dt or self.datas[0].datetime.date(0)
        if self.params.printlog:
            print('%s, %s' % (dt.isoformat(), txt))

    def notify_order(self, order):
        if order.status in [order.Completed]:
            if order.isbuy():
                cost = order.executed.price * order.executed.size
                commission = cost * self.params.commission / 100  # 将百分比转换为小数
                self.log('买入执行, 价格: %.2f, 成本: %.2f, 手续费: %.2f' %
                        (order.executed.price, cost, commission))

            elif order.issell():
                self.log('卖出执行, 价格: %.2f, 成本: %.2f, 手续费: %.2f' %
                        (order.executed.price,
                        order.executed.value,
                        order.executed.comm))

            self.bar_executed = len(self)

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('订单 取消/保证金不足/拒绝')

        self.order = None

# 從 GitHub 加載圖片
image_url = 'https://raw.githubusercontent.com/j7808833/test_02/main/Cyberpunk_bar_03.jpg'
response = requests.get(image_url)
image = Image.open(BytesIO(response.content))

# 顯示圖片
st.image(image, use_column_width=True)

# Streamlit 页面布局
st.title('Backtest with Backtrader')

# 提示用户输入股票代码，并使用逗号分隔
user_input = st.text_area("请输入股票代码，用逗号分隔，台股请记得在最后加上.TW", "AAPL, MSFT, GOOG, AMZN, 0050.TW")
# 将用户输入的股票代码转换为列表
stocks = [stock.strip() for stock in user_input.split(",")]
st.write("您输入的股票代码：", stocks)

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
n_years_backtest = st.slider('Backtest Duration (Years)', min_value=1, max_value=10, step=1, value=5)

# 定义显示结果的函数
def display_results(cash, value, initial_value, n_years):
    st.write(f"Budget: ${initial_cash:.2f}")
    st.write(f"Final Cash: ${cash:.2f}")
    st.write(f"Final Value: ${value:.2f}")

    # 计算年回报率
    annual_return = ((value - cash) / (initial_cash - cash)) ** (1 / n_years) - 1
    annual_return *= 100  # 转换为百分比形式
    st.write(f"Annual Return Rate: {annual_return:.2f}%")

# 执行回测并显示结果
if st.button('Run Backtest'):
    # 初始化 Cerebro 引擎
    cerebro = bt.Cerebro()
    cerebro.addstrategy(PeriodicInvestmentStrategy, initial_cash=initial_cash, monthly_investment=monthly_investment, commission=commission, investment_day=investment_day)

    # 添加数据
    start_date = datetime.datetime.now() - relativedelta(years=n_years_backtest)  # 根据回测年限动态计算开始时间
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

    # 获取初始总价值
    initial_value = cerebro.broker.get_value()

    # 获取当前现金余额和总价值
    cash = cerebro.broker.get_cash()
    value = cerebro.broker.get_value()

    # 显示结果
    display_results(cash, value, initial_value, n_years_backtest)

    # 绘制结果
    fig = cerebro.plot(style='plotly')[0][0]  # 获取 Matplotlib 图形对象
    st.pyplot(fig)  # 将图形嵌入到 Streamlit 页面中

# 定义投资参数和调酒名称的对应关系
def get_drink_name(investment_ratio, commission, annual_return):
    if investment_ratio < 10:
        if commission < 0.01:
            if annual_return <= 2:
                return "Vodka_Soda"
            elif annual_return <= 5:
                return "Vodka_Martini"
            elif annual_return <= 10:
                return "Whiskey_Sour"
            else:
                return "Whiskey_Neat"
        else:
            if annual_return <= 2:
                return "Moscow_Mule"
            elif annual_return <= 5:
                return "Bloody_Mary"
            elif annual_return <= 10:
                return "Old_Fashioned"
            else:
                return "Manhattan"
    else:
        if commission < 0.01:
            if annual_return <= 2:
                return "Screwdriver"
            elif annual_return <= 5:
                return "Vodka_Collins"
            elif annual_return <= 10:
                return "Rob_Roy"
            else:
                return "Sazerac"
        else:
            if annual_return <= 2:
                return "Aperol_Spritz"
            elif annual_return <= 5:
                return "Cosmopolitan"
            elif annual_return <= 10:
                return "Boulevardier"
            else:
                return "Vieux_Carré"

# 構建Streamlit應用
st.title("調酒推薦系統")

# 輸入投資參數
initial_cash = st.number_input("Initial Cash", min_value=0, value=50)
monthly_investment = st.number_input("Monthly Investment", min_value=0, value=5)
commission = st.number_input("Commission", min_value=0.0, max_value=1.0, value=0.005)
annual_return = st.number_input("Annual Return (%)", min_value=0, max_value=100, value=3)

# 計算investment_ratio
investment_ratio = initial_cash / monthly_investment if monthly_investment != 0 else float('inf')

# 根據投資參數查找對應的調酒名稱
drink_name = get_drink_name(investment_ratio, commission, annual_return)

if drink_name:
    # 根據調酒名稱設置圖片URL和名稱
    if drink_name == "Vodka_Soda":
        image_url = "https://raw.githubusercontent.com/j7808833/test_02/main/cocktail_01_Vodka%20Soda.jpg"
        drink_caption = "Vodka_Soda"
    elif drink_name == "Vodka_Martini":
        image_url = "https://raw.githubusercontent.com/j7808833/test_02/main/cocktail_02_Vodka%20Martini.jpg"
        drink_caption = "Vodka_Martini"
    elif drink_name == "Whiskey_Sour":
        image_url = "https://raw.githubusercontent.com/j7808833/test_02/main/cocktail_03_Whiskey%20Sour.jpg"
        drink_caption = "Whiskey_Sour"
    elif drink_name == "Whiskey_Neat":
        image_url = "https://raw.githubusercontent.com/j7808833/test_02/main/cocktail_04_Whiskey%20Neat.jpg"
        drink_caption = "Whiskey_Neat"
    elif drink_name == "Moscow_Mule":
        image_url = "https://raw.githubusercontent.com/j7808833/test_02/main/cocktail_05_Moscow%20Mule.jpg"
        drink_caption = "Moscow_Mule"
    elif drink_name == "Bloody_Mary":
        image_url = "https://raw.githubusercontent.com/j7808833/test_02/main/cocktail_06_Bloody%20Mary.jpg"
        drink_caption = "Bloody_Mary"
    elif drink_name == "Old_Fashioned":
        image_url = "https://raw.githubusercontent.com/j7808833/test_02/main/cocktail_07_Old%20Fashioned.jpg"
        drink_caption = "Old_Fashioned"
    elif drink_name == "Manhattan":
        image_url = "https://raw.githubusercontent.com/j7808833/test_02/main/cocktail_08_Manhattan.jpg"
        drink_caption = "Manhattan"
    elif drink_name == "Screwdriver":
        image_url = "https://raw.githubusercontent.com/j7808833/test_02/main/cocktail_09_Screwdriver.jpg"
        drink_caption = "Screwdriver"
    elif drink_name == "Vodka_Collins":
        image_url = "https://raw.githubusercontent.com/j7808833/test_02/main/cocktail_10_Vodka%20Collins.jpg"
        drink_caption = "Vodka_Collins"
    elif drink_name == "Rob_Roy":
        image_url = "https://raw.githubusercontent.com/j7808833/test_02/main/cocktail_11_Rob%20Roy.jpg"
        drink_caption = "Rob_Roy"
    elif drink_name == "Sazerac":
        image_url = "https://raw.githubusercontent.com/j7808833/test_02/main/cocktail_12_Sazerac.jpg"
        drink_caption = "Sazerac"
    elif drink_name == "Aperol_Spritz":
        image_url = "https://raw.githubusercontent.com/j7808833/test_02/main/cocktail_13_Aperol%20Spritz.jpg"
        drink_caption = "Aperol_Spritz"
    elif drink_name == "Cosmopolitan":
        image_url = "https://raw.githubusercontent.com/j7808833/test_02/main/cocktail_15_Boulevardier.jpg"
        drink_caption = "Cosmopolitan"
    elif drink_name == "Vieux_Carré":
        image_url = "https://raw.githubusercontent.com/j7808833/test_02/main/cocktail_16_Vieux%20Carr%C3%A9.jpg"
        drink_caption = "Vieux_Carré"
    else:
        image_url = ""  # Add default image URL if needed
        drink_caption = "No matching drink found"
    
    # 顯示調酒名稱和圖片
    st.write(f"調酒的名稱是：{drink_caption}")
    st.image(image_url, caption=drink_caption)
else:
    st.write("No matching drink found for the given investment parameters.")

# 定義調酒名稱和其對應的特性和依據
drinks_info = {
    "Vodka_Soda": {
        "報酬率": "低",
        "大小": "小額",
        "特性": "伏特加和蘇打水，酒精度低，口感清淡清爽。",
        "依據": "低風險，適合低回報的小額短期投資。"
    },
    "Vodka_Martini": {
        "報酬率": "中",
        "大小": "小額",
        "特性": "伏特加和乾苦艾酒，酒精度中等，口感適中，經典且稍微複雜。",
        "依據": "適合中等風險和回報的小額短期投資。"
    },
    "Whiskey_Sour": {
        "報酬率": "高",
        "大小": "小額",
        "特性": "威士忌、檸檬汁和糖漿，酒精度高，口感濃烈且有層次。",
        "依據": "對應高風險和高回報的小額短期投資。"
    },
    "Whiskey_Neat": {
        "報酬率": "極高",
        "大小": "小額",
        "特性": "純飲威士忌，酒精度非常高，口感非常濃烈直接。",
        "依據": "對應極高風險和極高回報的小額短期投資。"
    },
    "Moscow_Mule": {
        "報酬率": "低",
        "大小": "大額",
        "特性": "伏特加、薑汁啤酒和青檸汁，酒精度低，口感溫和，帶有薑味的清爽感。",
        "依據": "適合低風險且低回報的大額短期投資。"
    },
    "Bloody_Mary": {
        "報酬率": "中",
        "大小": "大額",
        "特性": "伏特加、番茄汁和各種調味料，酒精度中等，口感豐富且略帶鹹味。",
        "依據": "適合中等風險和回報的大額短期投資。"
    },
    "Old_Fashioned": {
        "報酬率": "高",
        "大小": "大額",
        "特性": "威士忌、苦味酒和糖，酒精度高，口感濃烈且複雜。",
        "依據": "適合高風險和高回報的大額短期投資。"
    },
    "Manhattan": {
        "報酬率": "極高",
        "大小": "大額",
        "特性": "威士忌、甜苦艾酒和苦味酒，酒精度非常高，口感非常濃烈複雜且富有層次。",
        "依據": "適合極高風險和極高回報的大額短期投資。"
    },
    "Screwdriver": {
        "報酬率": "低",
        "大小": "小額",
        "特性": "伏特加和橙汁，酒精度低，口感清新簡單。",
        "依據": "適合低風險低回報的小額長期投資。"
    },
    "Vodka_Collins": {
        "報酬率": "中",
        "大小": "小額",
        "特性": "伏特加、檸檬汁、糖漿和蘇打水，酒精度中等，口感清爽且略帶甜味。",
        "依據": "適合中等風險和回報的小額長期投資。"
    },
    "Rob_Roy": {
        "報酬率": "高",
        "大小": "小額",
        "特性": "威士忌、甜苦艾酒和苦味酒，酒精度高，口感濃烈且經典。",
        "依據": "適合高風險和高回報的小額長期投資。"
    },
    "Sazerac": {
        "報酬率": "極高",
        "大小": "小額",
        "特性": "威士忌、苦艾酒和苦味酒，酒精度非常高，口感非常濃烈複雜。",
        "依據": "適合極高風險和極高回報的小額長期投資。"
    },
    "Aperol_Spritz": {
        "報酬率": "低",
        "大小": "大額",
        "特性": "Aperol、蘇打水和香檳，酒精度低，口感溫和且清爽。",
        "依據": "適合低風險低回報的大額長期投資。"
    },
    "Cosmopolitan": {
    "報酬率": "中",
    "大小": "大額",
    "特性": "伏特加、柑橘利口酒、蔓越莓汁和青檸汁，酒精度中等，口感適中且帶有水果味。",
    "依據": "適合中等風險和回報的大額長期投資。"
    },
    "Boulevardier": {
    "報酬率": "高",
    "大小": "大額",
    "特性": "威士忌、甜苦艾酒和苦味酒，酒精度高，口感濃烈且複雜。",
    "依據": "適合高風險和高回報的大額長期投資。"
    },
    "Vieux_Carré": {
    "報酬率": "極高",
    "大小": "大額",
    "特性": "威士忌、干邑、甜苦艾酒和苦味酒，酒精度非常高，口感非常濃烈複雜。",
    "依據": "適合極高風險和極高回報的大額長期投資。"
    }
}


# 顯示特性和依據
if drink_name in drinks_info:
    st.write("特性：", drinks_info[drink_name]["特性"])
    st.write("依據：", drinks_info[drink_name]["依據"])
else:
    st.write("找不到對應的調酒信息。")


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

