
import os
import requests
from datetime import datetime
from notion_client import Client
import yfinance as yf
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

notion = Client(auth=NOTION_TOKEN)
openai = OpenAI(api_key=OPENAI_API_KEY)

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

def fetch_capital_flow_from_xueqiu(code, market):
    try:
        suffix = '' if market == 'US' else ''
        url = f"https://stock.xueqiu.com/v5/stock/capital/flow.json?symbol={code}{suffix}&period=1d"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://xueqiu.com",
            "Cookie": "xq_a_token=demo"  # 可替换为真实 cookie 提升稳定性
        }
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            return "主力数据获取失败"
        data = res.json().get('data', {})
        net = data.get('net_amount_main', 0)
        main_in = data.get('buy_amount_super', 0)
        ret = f"主力净流入 {net/1e4:.2f} 万元"
        return ret
    except Exception as e:
        return f"资金流抓取失败：{e}"

def analyze_with_gpt(name, code, hist):
    try:
        closes = hist['Close'].dropna()
        if len(closes) < 20:
            return "📉 历史数据不足"
        ma5 = closes.rolling(window=5).mean().iloc[-1]
        ma20 = closes.rolling(window=20).mean().iloc[-1]
        current = closes.iloc[-1]
        prompt = f"""
请分析以下股票的技术面情况，简洁总结当前趋势，并说明是否处于低买区：
股票名称：{name}
股票代码：{code}
当前价格：{current:.2f}
5日均线：{ma5:.2f}
20日均线：{ma20:.2f}
"""
        chat = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        return chat.choices[0].message.content
    except Exception as e:
        return f"GPT 分析失败：{e}"

def update_notion_page(page_id, price, pe, pb, tech_summary, capital):
    now = datetime.now().isoformat()
    try:
        notion.pages.update(
            page_id=page_id,
            properties={
                "Price": {"number": price},
                "PE": {"number": pe if pe and pe > 0 else 0},
                "PB": {"number": pb if pb and pb > 0 else 0},
                "Tech Analysis": {"rich_text": [{"text": {"content": tech_summary[:1900]}}]},
                "Capital Flow": {"rich_text": [{"text": {"content": capital}}]},
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
            print(f"⚠️ 股票代码格式错误：{stock['name']}，已跳过")
            continue
        print(f"🔍 正在处理：{stock['name']} ({ticker})")
        try:
            data = get_stock_data(ticker)
            tech = analyze_with_gpt(stock['name'], stock['code'], data['hist'])
            capital = fetch_capital_flow_from_xueqiu(stock['code'], stock['market'])
            update_notion_page(stock['page_id'], data['price'], data['pe'], data['pb'], tech, capital)
            print(f"✅ 已更新：{stock['name']}")
        except Exception as e:
            print(f"❌ 处理失败：{stock['name']}，原因：{e}")

if __name__ == "__main__":
    main()
