
# Notion 股票自动分析机器人

本项目用于自动更新你的 Notion 股票观察表格，包含价格、PE、PB、技术面解读等内容。

## 功能
- 每天自动抓取港股 / 美股数据
- 自动调用 ChatGPT 分析技术趋势
- 自动写入 Notion 表格

## 使用方法

### 1. 新建 GitHub 仓库并上传本项目代码
将所有文件上传后解压到你的仓库中。

### 2. 设置 GitHub Secrets
进入 Settings → Secrets and variables → Actions，添加以下变量：

- `NOTION_TOKEN`：你的 Notion integration token
- `DATABASE_ID`：你的数据库 ID
- `OPENAI_API_KEY`：你的 OpenAI API key

### 3. 自动运行
每天北京时间 08:00 自动运行（或手动点击 Run workflow）。

---
