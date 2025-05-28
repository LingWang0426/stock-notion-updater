
import os
import requests
import openai
from datetime import datetime
from notion_client import Client
import yfinance as yf

from dotenv import load_dotenv
load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

notion = Client(auth=NOTION_TOKEN)
openai.api_key = OPENAI_API_KEY

def get_stocks_from_notion():
    results = []
    response = notion.databases.query(database_id=DATABASE_ID)
    for row in response['results']:
        props = row['properties']
        try:
            name = props['Name']['title'][0]['text']['content']
            code = props['code']['rich_text'][0]['text']['content']
            market = props['market']['select']['name']
            results.append({
                "page_id": row['id'],
                "name": name,
                "code": code.strip(),
                "market": market.strip().upper()
            })
        except Exception as e:
            print(f"⚠️ 无法解析某一行股票数据，跳过：{e}")
    return results

def get_stock_data(ticker):
    stock = yf.Ticker(ticker)
    try:
        hist = stock.history(period="1mo")
        info = stock.info
        return {
            "price": info.get("regularMarketPrice", None),
            "pe": info.get("trailingPE", None),
            "pb": info.get("priceToBook", None),
            "hist": hist
        }
    except Exception as e:
        raise RuntimeError(f"❌ 获取 {ticker} 股票数据失败：{e}")

def analyze_with_gpt(name, code, hist):
    try:
        closes = hist['Close'].dropna()
        if len(closes) < 20:
            return "📉 历史数据不足，跳过技术分析"
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
        return f"❌ GPT 分析失败：{e}"

def update_notion_page(page_id, price, pe, pb, tech_summary):
    now = datetime.now().isoformat()
    try:
        notion.pages.update(
            page_id=page_id,
            properties={
                "Price": {"number": price},
                "PE": {"number": pe if pe else 0},
                "PB": {"number": pb if pb else 0},
                "Tech Analysis": {"rich_text": [{"text": {"content": tech_summary[:1900]}}]},
                "Update Status": {"checkbox": True},
                "Last Updated": {"date": {"start": now}}
            }
        )
    except Exception as e:
        print(f"❌ 更新 Notion 页面失败：{e}")

def format_ticker(code, market):
    if market == 'HK' and code.endswith('.HK'):
        return code
    elif market == 'US':
        return code
    else:
        return None

def main():
    stocks = get_stocks_from_notion()
    for stock in stocks:
        ticker = format_ticker(stock['code'], stock['market'])
        if not ticker:
            print(f"⚠️ 股票代码格式错误或暂不支持市场：{stock['name']} ({stock['code']}, {stock['market']})，已跳过")
            continue
        print(f"🔍 正在处理：{stock['name']} ({ticker})")
        try:
            data = get_stock_data(ticker)
            tech = analyze_with_gpt(stock['name'], stock['code'], data['hist'])
            update_notion_page(stock['page_id'], data['price'], data['pe'], data['pb'], tech)
            print(f"✅ 已更新：{stock['name']}")
        except Exception as e:
            print(f"❌ 处理失败：{stock['name']} ({ticker})，原因：{e}")

if __name__ == "__main__":
    main()
