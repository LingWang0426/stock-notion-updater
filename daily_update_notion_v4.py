
# daily_update_notion_v4.py
# 使用新浪财经获取港股资金数据 + OpenAI GPT 技术面分析 + 写入 Notion

import os
import requests
import yfinance as yf
from datetime import datetime
from notion_client import Client
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

notion = Client(auth=NOTION_TOKEN)
openai = OpenAI(api_key=OPENAI_API_KEY)

def get_notion_stocks():
    rows = notion.databases.query(database_id=DATABASE_ID).get("results")
    stocks = []
    for row in rows:
        props = row["properties"]
        try:
            name = props["Name"]["title"][0]["text"]["content"]
            code = props["code"]["rich_text"][0]["text"]["content"]
            market = props["market"]["select"]["name"]
            page_id = row["id"]
            stocks.append({"name": name, "code": code, "market": market, "page_id": page_id})
        except:
            continue
    return stocks

def get_price_pe_pb(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            "price": info.get("regularMarketPrice", None),
            "pe": info.get("trailingPE", None),
            "pb": info.get("priceToBook", None)
        }
    except Exception as e:
        print(f"❌ 获取 {ticker} 财务数据失败：{e}")
        return {"price": None, "pe": None, "pb": None}

def get_capital_flow_sina(code):
    try:
        if not code.endswith(".HK"):
            return "仅支持港股"
        base = code.replace(".HK", "")
        url = f"http://stock.gtimg.cn/data/index.php?appn=hkDyj&action=getDyj&c={base}"
        res = requests.get(url)
        if res.status_code != 200:
            return "资金流抓取失败"
        text = res.text
        if "v_hkDyj" in text:
            parts = text.split("~")
            net = parts[1] if len(parts) > 1 else ""
            turnover = parts[7] if len(parts) > 7 else ""
            return f"主力净流入：{net} 万港币｜成交额：{turnover} 万"
        return "资金数据为空"
    except Exception as e:
        return f"资金抓取异常：{e}"

def gpt_tech_analysis(name, code):
    try:
        content = f"请根据最近走势，用一句话分析股票【{name}】（代码：{code}）的技术面趋势，是否存在低吸机会。"
        chat = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": content}],
            temperature=0.5
        )
        return chat.choices[0].message.content.strip()
    except Exception as e:
        return f"GPT 分析失败：{e}"

def update_notion(row, result):
    try:
        notion.pages.update(page_id=row["page_id"], properties={
            "Price": {"number": result["price"] if result["price"] else 0},
            "PE": {"number": result["pe"] if result["pe"] else 0},
            "PB": {"number": result["pb"] if result["pb"] else 0},
            "Tech Analysis": {"rich_text": [{"text": {"content": result["tech"][:1900]}}]},
            "Capital Flow": {"rich_text": [{"text": {"content": result["capital"][:1900]}}]},
            "Update Status": {"checkbox": True},
            "Last Updated": {"date": {"start": datetime.utcnow().isoformat()}}
        })
    except Exception as e:
        print(f"❌ 更新 Notion 页面失败：{e}")

def format_yf_code(code, market):
    if market == "HK" and not code.endswith(".HK"):
        return code + ".HK"
    if market == "US":
        return code
    return None

def main():
    stocks = get_notion_stocks()
    for row in stocks:
        ticker = format_yf_code(row["code"], row["market"])
        if not ticker:
            print(f"⚠️ 非法代码：{row['code']}，已跳过")
            continue
        print(f"📈 更新股票：{row['name']} ({ticker})")
        try:
            data = get_price_pe_pb(ticker)
            capital = get_capital_flow_sina(row["code"]) if row["market"] == "HK" else "暂不支持"
            tech = gpt_tech_analysis(row["name"], row["code"])
            result = {
                "price": data["price"],
                "pe": data["pe"],
                "pb": data["pb"],
                "capital": capital,
                "tech": tech
            }
            update_notion(row, result)
        except Exception as e:
            print(f"❌ 更新失败：{e}")

if __name__ == "__main__":
    main()
