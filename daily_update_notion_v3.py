
# daily_update_notion_v3.py
# 功能：
# - 从东方财富获取主力资金流
# - 使用 OpenAI GPT 接口生成技术分析
# - 将结果写入 Notion 数据库
# 请确保 .env 文件中包含：NOTION_TOKEN、DATABASE_ID、OPENAI_API_KEY

import os
import requests
import openai
from notion_client import Client
from dotenv import load_dotenv
from datetime import datetime
import traceback

load_dotenv()
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}
notion = Client(auth=NOTION_TOKEN)
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

def get_notion_rows(database_id):
    try:
        rows = notion.databases.query(database_id=database_id).get("results")
        return rows
    except Exception as e:
        print(f"❌ 获取 Notion 数据失败：{e}")
        return []

def update_notion_page(page_id, properties):
    try:
        notion.pages.update(page_id=page_id, properties=properties)
        print(f"✅ 更新成功: {page_id}")
    except Exception as e:
        print(f"❌ 更新失败: {e}")

def get_capital_flow_eastmoney(stock_code):
    try:
        if stock_code.startswith("6"):
            url = f"https://push2.eastmoney.com/api/qt/stock/get?secid=1.{stock_code}"
        elif stock_code.startswith("0") or stock_code.startswith("3"):
            url = f"https://push2.eastmoney.com/api/qt/stock/get?secid=0.{stock_code}"
        else:
            return "暂不支持"
        res = requests.get(url)
        data = res.json()
        if "data" in data and data["data"]:
            netinflow = data["data"].get("rzye", None)
            if netinflow:
                return f"融资余额: {netinflow} 万元"
        return "主力资金数据暂缺"
    except Exception as e:
        return "主力资金抓取失败"

def get_tech_analysis(symbol):
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "你是专业的股票技术分析师"},
                {"role": "user", "content": f"请用一句话分析{symbol}当前的技术面走势，基于K线、均线、成交量"}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ GPT 分析失败: {e}")
        return "GPT 分析失败"

def main():
    print(f"⏱ 开始抓取：{datetime.now()}")
    rows = get_notion_rows(DATABASE_ID)
    for row in rows:
        try:
            props = row["properties"]
            page_id = row["id"]
            name = props["Name"]["title"][0]["text"]["content"]
            code = props["Code"]["rich_text"][0]["text"]["content"]

            print(f"📊 正在处理: {name} ({code})")
            capital = get_capital_flow_eastmoney(code)
            analysis = get_tech_analysis(name)

            update_notion_page(page_id, {
                "Capital Flow": {"rich_text": [{"text": {"content": capital}}]},
                "Tech Analysis": {"rich_text": [{"text": {"content": analysis}}]},
            })

        except Exception as err:
            print(f"❌ 股票处理失败: {traceback.format_exc()}")
    print(f"✅ 任务完成：{datetime.now()}")

if __name__ == "__main__":
    main()
