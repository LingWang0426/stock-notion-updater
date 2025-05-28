
import os
import requests
import openai
from datetime import datetime
from notion_client import Client
import yfinance as yf

# 载入环境变量
from dotenv import load_dotenv
load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

notion = Client(auth=NOTION_TOKEN)
openai.api_key = OPENAI_API_KEY

# 获取数据库中所有股票条目
def get_stocks_from_notion():
    results = []
    response = notion.databases.query(database_id=DATABASE_ID)
    for row in response['results']:
        props = row['properties']
        name = props['Name']['title'][0]['text']['content']
        code = props['code']['rich_text'][0]['text']['content']
        market = props['market']['select']['name']
        results.append({
            "page_id": row['id'],
            "name": name,
            "code": code,
            "market": market
        })
    return results

# 获取股票数据
def get_stock_data(ticker):
    stock = yf.Ticker(ticker)
    hist = stock.history(period="1mo")
    info = stock.info
    return {
        "price": info.get("regularMarketPrice", None),
        "pe": info.get("trailingPE", None),
        "pb": info.get("priceToBook", None),
        "hist": hist
    }

# 简化版技术分析 + GPT 调用
def analyze_with_gpt(name, code, hist):
    try:
        closes = hist['Close'].dropna()
        ma5 = closes.rolling(window=5).mean().iloc[-1]
        ma20 = closes.rolling(window=20).mean().iloc[-1]
        current = closes.iloc[-1]
        macd = closes.ewm(span=12).mean() - closes.ewm(span=26).mean()
        macd_signal = macd.ewm(span=9).mean()
        macd_hist = macd - macd_signal
        prompt = f"""
请分析以下股票的技术面情况，简洁总结当前趋势，并说明是否处于低买区：

股票名称：{name}
股票代码：{code}
当前价格：{current:.2f}
5日均线：{ma5:.2f}
20日均线：{ma20:.2f}
MACD最近3日：{macd_hist[-3:].round(2).to_list()}

用简洁语言描述趋势：如“MACD金叉，短线上涨趋势明显”或“跌破20日线，建议观望”。
"""
        res = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        return res['choices'][0]['message']['content']
    except Exception as e:
        return f"分析失败：{e}"

# 更新 Notion 页面
def update_notion_page(page_id, price, pe, pb, tech_summary):
    now = datetime.now().isoformat()
    notion.pages.update(
        page_id=page_id,
        properties={
            "Price": {"number": price},
            "PE": {"number": pe if pe else 0},
            "PB": {"number": pb if pb else 0},
            "Tech Analysis": {"rich_text": [{"text": {"content": tech_summary}}]},
            "Update Status": {"checkbox": True},
            "Last Updated": {"date": {"start": now}}
        }
    )

# 主执行函数
def main():
    stocks = get_stocks_from_notion()
    for stock in stocks:
        code = stock['code']
        if stock['market'] == 'HK':
            ticker = code.replace('.HK', '') + ".HK"
        else:
            ticker = code
        print(f"处理股票：{stock['name']} ({ticker})")
        data = get_stock_data(ticker)
        tech = analyze_with_gpt(stock['name'], code, data['hist'])
        update_notion_page(stock['page_id'], data['price'], data['pe'], data['pb'], tech)

if __name__ == "__main__":
    main()
