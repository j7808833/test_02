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
import random
import base64
import numpy as np
from matplotlib.animation import FuncAnimation

# 設置 Matplotlib 背景顏色
plt.rcParams['axes.facecolor'] = 'black'  # 設置圖表區域背景顏色為黑色
plt.rcParams['figure.facecolor'] = 'black'  # 設置整個圖表背景顏色為黑色
plt.rcParams['text.color'] = 'white'  # 設置圖表文字顏色為白色
fig, ax = plt.subplots()

# 調整標註的底色為黑色
legend = ax.legend()
if legend:
    legend.get_frame().set_facecolor('black')

# Prophet 預測函數
def predict_stock(selected_stock, n_years):
    data = yf.download(selected_stock, start="2010-01-01", end=datetime.date.today().strftime("%Y-%m-%d"))
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
        ('printlog', True),  # 是否打印交易日誌
    )

    def __init__(self, **kwargs):
        self.order = None
        self.add_timer(
            when=bt.Timer.SESSION_START,
            monthdays=[self.params.investment_day],  # 每月的特定日期投資
            monthcarry=True,  # 如果特定日期不是交易日，則延至下一個交易日
        )

        # 從kwargs中獲取初始資金
        self.initial_cash = kwargs.get('initial_cash', 10000)  # 初始資金設置為10000

    def notify_timer(self, timer, when, *args, **kwargs):
        self.log('進行定期投資')
        # 獲取當前價格
        price = self.data.close[0]
        # 計算購買數量
        investment_amount = self.params.monthly_investment / price
        # 執行購買
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
                commission = cost * self.params.commission / 100  # 將百分比轉換為小數
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

        self.order = None  # 重置 order 屬性

# 以50%的機率選擇圖片連結
if random.random() < 0.5:
    image_url = 'https://raw.githubusercontent.com/j7808833/test_02/main/pic/Cyberpunk_bar_03.gif'
else:
    image_url = 'https://raw.githubusercontent.com/j7808833/test_02/main/pic/Cyberpunk_bar_02.gif'

# 顯示GIF圖片
st.markdown(f'<img src="{image_url}" style="width: 100%;">', unsafe_allow_html=True)

# Streamlit 頁面佈局
st.title('Backtest & Backtrader Bar')

# 提示用戶輸入股票代碼，並使用逗號分隔
user_input = st.text_area("請輸入股票代碼，用逗號分隔，台股請記得在最後加上.TW", "AAPL, MSFT, GOOG, AMZN, 0050.TW")

# 將用戶輸入的股票代碼轉換為列表
stocks = [stock.strip() for stock in user_input.split(",")]
st.write("您輸入的股票代碼：", stocks)

# 股票選擇器和預測年限滑塊
selected_stock = st.selectbox('選擇股票進行預測和回測', stocks)
n_years = st.slider('預測年限:', 1, 3)

# 預測和顯示結果
if st.button('運行預測'):
    # 做預測並獲取數據、預測結果和 Prophet 模型
    data, forecast, m = predict_stock(selected_stock, n_years)
    st.write('預測數據:')
    st.write(forecast)
    st.write(f'{n_years} 年的預測圖')
    fig1 = m.plot(forecast)
    
    # 調整底色
    fig1.set_facecolor('black')

    # 調整網格繪圖區顏色
    for ax in fig1.axes:
        ax.set_facecolor('black')
        ax.tick_params(axis='x', colors='white')  # 調整x軸刻度顏色為白色
        ax.tick_params(axis='y', colors='white')  # 調整y軸刻度顏色為白色
        ax.yaxis.label.set_color('white')  # 調整y軸標籤顏色為白色
        ax.xaxis.label.set_color('white')  # 調整x軸標籤顏色為白色

    # 調整數值和框線顏色
    for text in fig1.findobj(match=matplotlib.text.Text):
        text.set_color('white')

    for dot in fig1.findobj(match=matplotlib.patches.Circle):
        dot.set_edgecolor('white')  # 點的邊緣顏色
        dot.set_facecolor('white')  # 點的填充顏色

    st.pyplot(fig1)
    st.toast('Your stock has been generated!', icon='🥂')

# 添加滑塊來控制參數
initial_cash = st.slider('預算', min_value=0, max_value=10000000, step=10000, value=10000)
monthly_investment = st.slider('每月投資金額', min_value=0, max_value=50000, step=1000, value=1000)
commission = st.slider('手續費 (%)', min_value=0.0, max_value=1.0, step=0.0001, format="%.4f", value=0.001)
investment_day = st.slider('每月投資日', min_value=1, max_value=28, step=1, value=1)
n_years_backtest = st.slider('回測持續時間 (年)', min_value=1, max_value=10, step=1, value=5)

# 定義顯示結果的函數
def display_results(cash, value, initial_value, n_years):
    # 計算年回報率
    annual_return = ((value - cash) / (initial_cash - cash)) ** (1 / n_years) - 1
    annual_return *= 100  # 轉換為百分比形式
    
    st.toast('Your stock has been generated!', icon='🥂')
    col1, col2, col3 = st.columns(3)
    col1.metric("預算", f"{cash:.2f}", f"{initial_cash:.2f}", delta_color="inverse")
    col2.metric("最終價值", f"{value:.2f}", f"{initial_value:.2f}", delta_color="inverse")
    col3.metric("年回報率", f"{annual_return:.2f}%", " ", delta_color="inverse")
    return annual_return

def get_drink_name(investment_ratio, commission, annual_return):
    if investment_ratio > 0.1:
        if commission < 0.15:
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
        if commission < 0.15:
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

# 執行回測並顯示結果
if st.button('Run Backtest'):
    # 初始化 Cerebro 引擎
    cerebro = bt.Cerebro()
    cerebro.addstrategy(PeriodicInvestmentStrategy, initial_cash=initial_cash, monthly_investment=monthly_investment, commission=commission, investment_day=investment_day)

    # 添加數據
    start_date = datetime.datetime.now() - relativedelta(years=n_years_backtest)  # 根據回測年限動態計算開始時間
    data = yf.download(selected_stock,
                    start=start_date,
                    end=datetime.datetime.now())
    cerebro.adddata(bt.feeds.PandasData(dataname=data))

    # 設置初始資本
    cerebro.broker.setcash(initial_cash)

    # 設置每筆交易的手續費
    cerebro.broker.setcommission(commission=commission)

    # 執行策略
    cerebro.run()

    # 獲取初始總價值
    initial_value = cerebro.broker.get_value()

    # 獲取當前現金餘額和總價值
    cash = cerebro.broker.get_cash()
    value = cerebro.broker.get_value()

    # 顯示結果
    display_results(cash, value, initial_value, n_years_backtest)

    # 繪製結果
    fig = cerebro.plot(style='plotly')[0][0]  # 獲取 Matplotlib 圖形對象
    st.pyplot(fig)  # 將圖形嵌入到 Streamlit 頁面中
    for marker in fig.findobj(match=matplotlib.lines.Line2D):
        marker.set_markerfacecolor('black')  # 修改標記顏色
    
    # 計算投資比例
    investment_ratio = monthly_investment / initial_cash if initial_cash != 0 else float('inf')

    # 計算年化回報率
    annual_return = ((value - initial_cash) / initial_cash + 1) ** (1 / n_years_backtest) - 1
    annual_return *= 100  # 轉換為百分比形式

    # 根據投資參數查找對應的調酒名稱
    drink_name = get_drink_name(investment_ratio, commission, annual_return)
        
    # 調酒圖片 URL 字典
    drink_images = {
        "Vodka_Soda": "https://raw.githubusercontent.com/j7808833/test_02/main/pic/cocktail_01_Vodka%20Soda.jpg",
        "Vodka_Martini": "https://raw.githubusercontent.com/j7808833/test_02/main/pic/cocktail_02_Vodka%20Martini.jpg",
        "Whiskey_Sour": "https://raw.githubusercontent.com/j7808833/test_02/main/pic/cocktail_03_Whiskey%20Sour.jpg",
        "Whiskey_Neat": "https://raw.githubusercontent.com/j7808833/test_02/main/pic/cocktail_04_Whiskey%20Neat.jpg",
        "Moscow_Mule": "https://raw.githubusercontent.com/j7808833/test_02/main/pic/cocktail_05_Moscow%20Mule.jpg",
        "Bloody_Mary": "https://raw.githubusercontent.com/j7808833/test_02/main/pic/cocktail_06_Bloody%20Mary.jpg",
        "Old_Fashioned": "https://raw.githubusercontent.com/j7808833/test_02/main/pic/cocktail_07_Old%20Fashioned.jpg",
        "Manhattan": "https://raw.githubusercontent.com/j7808833/test_02/main/pic/cocktail_08_Manhattan.jpg",
        "Screwdriver": "https://raw.githubusercontent.com/j7808833/test_02/main/pic/cocktail_09_Screwdriver.jpg",
        "Vodka_Collins": "https://raw.githubusercontent.com/j7808833/test_02/main/pic/cocktail_10_Vodka%20Collins.jpg",
        "Rob_Roy": "https://raw.githubusercontent.com/j7808833/test_02/main/pic/cocktail_11_Rob%20Roy.jpg",
        "Sazerac": "https://raw.githubusercontent.com/j7808833/test_02/main/pic/cocktail_12_Sazerac.jpg",
        "Aperol_Spritz": "https://raw.githubusercontent.com/j7808833/test_02/main/pic/cocktail_13_Aperol%20Spritz.jpg",
        "Cosmopolitan": "https://raw.githubusercontent.com/j7808833/test_02/main/pic/cocktail_14_Cosmopolitan.jpg",
        "Boulevardier": "https://raw.githubusercontent.com/j7808833/test_02/main/pic/cocktail_15_Boulevardier.jpg",
        "Vieux_Carré": "https://raw.githubusercontent.com/j7808833/test_02/main/pic/cocktail_16_Vieux%20Carr%C3%A9.jpg"
    }

    st.write(f"您的投資風格對應的調酒是: {drink_name}")

    # 顯示調酒圖片
    image_url = drink_images[drink_name]
    response = requests.get(image_url)
    drink_image = Image.open(BytesIO(response.content))
    st.markdown(f'<p align="center"><img src="{image_url}" alt="{drink_name}" width="240"></p>', unsafe_allow_html=True)

    labels=['Siege', 'Initiation', 'Crowd_control', 'Wave_clear', 'Objective_damage']
    markers = [0, 1, 2, 3, 4, 5]
    str_markers = ["0", "1", "2", "3", "4", "5"]

    # 雷達圖數據
    radar_data = {
        "Vodka_Soda": [1, 1, 1, 1, 1],
        "Vodka_Martini": [2, 2, 2, 2, 1],
        "Whiskey_Sour": [3, 3, 3, 3, 1],
        "Whiskey_Neat": [4, 4, 4, 4, 1],
        "Moscow_Mule": [1, 1, 1, 1, 2],
        "Bloody_Mary": [2, 2, 2, 2, 2],
        "Old_Fashioned": [3, 3, 3, 3, 2],
        "Manhattan": [4, 4, 4, 4, 2],
        "Screwdriver": [1, 1, 1, 1, 3],
        "Vodka_Collins": [2, 2, 2, 2, 3],
        "Rob_Roy": [3, 3, 3, 3, 3],
        "Sazerac": [4, 4, 4, 4, 3],
        "Aperol_Spritz": [1, 1, 1, 1, 4],
        "Cosmopolitan": [2, 2, 2, 2, 4],
        "Boulevardier": [3, 3, 3, 3, 4],
        "Vieux_Carré": [4, 4, 4, 4, 4],
    }

    # 定義指標標籤
    attribute_labels = ['Risk', 'Returns', 'Complexity', 'Alcohol Content', 'Investment Duration']

    # 新的指標標籤
    attribute_labels_extended = [
        'Volatility', 'Maximum Drawdown', 'Historical Returns', 
        'Expense Ratio', 'Fund Size', 'Sharpe Ratio'
    ]

    def make_radar_chart(name, stats, attribute_labels):
        labels = np.array(attribute_labels[:len(stats)])
        angles = np.linspace(0, 2*np.pi, len(labels), endpoint=False).tolist()
        stats = stats + stats[:1]
        angles += angles[:1]

        fig, ax = plt.subplots(figsize=(4.8, 4.8), subplot_kw=dict(polar=True))
        ax.fill(angles, stats, color='magenta', alpha=0.25)
        ax.plot(angles, stats, color='magenta', linewidth=2)

        ax.set_yticklabels([])
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels, color='white', fontsize=10)  # 修改指標標籤顏色和字體大小

        plt.title(name, size=10, color='white', y=1.1)  # 修改標題顏色和字體大小
        st.pyplot(fig)

    # 假設回測後的結果為某些參數
    investment_ratio = 0.05
    commission = 0.01
    annual_return = 12  # 百分比

    # 根據參數查找對應的雞尾酒名稱
    def get_drink_name(investment_ratio, commission, annual_return):
        if annual_return < 5:
            if investment_ratio < 0.1:
                return "Vodka_Soda"
            else:
                return "Moscow_Mule"
        elif 5 <= annual_return < 10:
            if investment_ratio < 0.1:
                return "Vodka_Martini"
            else:
                return "Bloody_Mary"
        elif 10 <= annual_return < 15:
            if investment_ratio < 0.1:
                return "Whiskey_Sour"
            else:
                return "Old_Fashioned"
        else:
            if investment_ratio < 0.1:
                return "Whiskey_Neat"
            else:
                return "Manhattan"

    drink_name = get_drink_name(investment_ratio, commission, annual_return)

    # 顯示對應的特性和依據
    if drink_name in radar_data:
        st.write("特性：", drink_name)  # 此處暫時以飲料名稱代替
        st.write("依據：", "根據參數查找")  # 暫時以文字代替
    else:
        st.write("找不到對應的調酒信息。")

    # 顯示對應的雷達圖
    stats = radar_data[drink_name]
    make_radar_chart(drink_name, stats, attribute_labels_extended)

    # 創建畫布和坐標軸
    fig, ax = plt.subplots()

    # 定義數據
    x_data = list(range(10))
    y_data = [x**2 for x in x_data]

    # 繪製空的散點圖
    s = ax.scatter([], [])

    # 定義更新函數
    def update(frame):
        ax.clear()
        
        # 繪製當前幀的數據
        ax.scatter(x_data[:frame+1], y_data[:frame+1], c='cyan', marker='o', label='Data')
        
        # 自定義圖表（標籤、標題等）
        ax.set_xlabel('X 軸標籤')
        ax.set_ylabel('Y 軸標籤')
        ax.set_title('散點圖動畫')
        ax.legend(loc='upper left')

    # 創建動畫
    ani = FuncAnimation(fig, update, frames=len(x_data), interval=200)

    # 使用 streamlit 將動畫嵌入到網頁中
    st.pyplot(fig)
