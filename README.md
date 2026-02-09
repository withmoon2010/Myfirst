# Eternal交易状态检查

该项目包含一个脚本，用于每天检查 NSDL 网站上印度公司 Eternal（Zomato）是否出现在两个名单里：

1. 3% limit list：如果 **没有** 出现，视为通过测试。
2. Apex company list：如果 **出现**，视为通过测试。

脚本会在完成检查后发送一条消息，默认输出到控制台，也可以通过 Webhook 发送。你可以用 cron 或脚本自带的定时模式，确保每天纽约时间下午 4 点运行。

## 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 运行一次检查

```bash
python eternal_monitor.py --run-once
```

## 每天纽约时间 16:00 自动检查

脚本内置循环定时：

```bash
python eternal_monitor.py --daemon
```

或者使用 cron（推荐）：

```bash
TZ=America/New_York
0 16 * * * /path/to/python /workspace/Myfirst/eternal_monitor.py --run-once
```

## 发送消息

默认输出到控制台。如果你有 Webhook（比如 Slack/Teams），设置环境变量即可：

```bash
export WEBHOOK_URL="https://hooks.slack.com/services/..."
python eternal_monitor.py --run-once
```

或者发送到邮箱（先配置 SMTP）： 

```bash
export EMAIL_RECIPIENT="xiaopeng.zhao@tengyuepartners.com"
export SMTP_HOST="smtp.example.com"
export SMTP_PORT="587"
export SMTP_USERNAME="user@example.com"
export SMTP_PASSWORD="your-password"
export EMAIL_SENDER="alerts@example.com"
python eternal_monitor.py --run-once
```

## 可选环境变量

| 变量 | 说明 |
| --- | --- |
| `WEBHOOK_URL` | 发送消息的 webhook URL。 |
| `EMAIL_RECIPIENT` | 收件人邮箱地址（优先于 webhook，默认 `xiaopeng.zhao@tengyuepartners.com`）。 |
| `SMTP_HOST` | SMTP 服务器地址。 |
| `SMTP_PORT` | SMTP 端口，默认 587。 |
| `SMTP_USERNAME` | SMTP 用户名。 |
| `SMTP_PASSWORD` | SMTP 密码。 |
| `EMAIL_SENDER` | 发件人邮箱地址。 |
| `REPORT_DATE` | 手动指定报告日期，格式 `YYYY-MM-DD`。 |
| `REPORT_DATE_FORMAT` | 向 NSDL 提交的日期格式，默认 `%d-%m-%Y`。 |
