# Telegram Bot 設置指南

## 1. 創建 Telegram Bot

### 步驟 1: 找到 BotFather
1. 在 Telegram 中搜索 `@BotFather`
2. 點擊開始對話

### 步驟 2: 創建新 Bot
1. 發送 `/newbot` 命令
2. 輸入 Bot 名稱（例如：`資金費率套利機器人`）
3. 輸入 Bot 用戶名（例如：`funding_rate_bot`，必須以 `bot` 結尾）
4. 複製獲得的 Bot Token（格式：`123456789:ABCdefGHIjklMNOpqrsTUVwxyz`）

### 步驟 3: 獲取 Chat ID
1. 將您的 Bot 添加到群組或與 Bot 私聊
2. 發送一條消息給 Bot
3. 訪問：`https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. 在返回的 JSON 中找到 `chat.id` 字段

## 2. 配置 config.py

在 `config.py` 中設置以下參數：

```python
# Telegram 通知配置
TELEGRAM_BOT_TOKEN = "your_telegram_bot_token_here"  # 替換為您的 Bot Token
TELEGRAM_CHAT_ID = "your_chat_id_here"  # 替換為您的 Chat ID
ENABLE_TELEGRAM_NOTIFY = True  # 是否啟用 Telegram 通知
NOTIFY_ON_TRADE = True  # 是否在每次交易時通知
NOTIFY_ON_ERROR = True  # 是否在錯誤時通知
NOTIFY_ON_START = True  # 是否在程式啟動時通知
NOTIFY_ON_STOP = True  # 是否在程式停止時通知
```

## 3. 通知類型

### 啟動通知
```
🚀 資金費率套利機器人已啟動

啟動時間: 2024-01-15 14:30:00
正在監控資金費率機會...
```

### 交易通知
```
🟢 交易完成

交易對: BTCUSDT
方向: 📈 LONG
數量: 1,000
開倉價: 45,123.45
平倉價: 45,125.67
資金費率: 0.0100%
執行時間: 49ms
盈虧: 2.22 USDT

📊 會話統計
總交易: 5
總盈虧: 12.45 USDT
勝率: 80.0%
平均盈虧: 2.49 USDT
```

### 錯誤通知
```
⚠️ 機器人發生錯誤

錯誤訊息: API 連接超時
時間: 2024-01-15 15:45:30
```

### 停止通知
```
📈 資金費率套利機器人 - 總結報告

🕐 本次會話
總交易: 10
總盈虧: 25.67 USDT
勝率: 70.0%
平均盈虧: 2.57 USDT
最大盈利: 5.23 USDT
最大虧損: -1.45 USDT
運行時間: 2.5 小時

📅 今日統計
交易次數: 10
今日盈虧: 25.67 USDT
今日勝率: 70.0%

⏹️ 機器人已停止
停止時間: 2024-01-15 17:00:00
```

## 4. 測試通知

創建測試腳本 `test_telegram.py`：

```python
from profit_tracker import ProfitTracker

# 創建收益追蹤器
tracker = ProfitTracker()

# 測試發送消息
tracker.send_telegram_message("🧪 測試消息：Telegram 通知功能正常！")

# 測試啟動通知
tracker.send_start_notification()

# 測試交易通知
test_trade = {
    'symbol': 'BTCUSDT',
    'direction': 'long',
    'quantity': 1000,
    'entry_price': 45123.45,
    'exit_price': 45125.67,
    'pnl': 2.22,
    'funding_rate': 0.01,
    'execution_time_ms': 49
}
tracker.send_trade_notification(test_trade)
```

## 5. 常見問題

### Q: Bot Token 無效
A: 檢查 Token 是否正確複製，確保沒有多餘的空格

### Q: Chat ID 無效
A: 確保您已經與 Bot 有過對話，或者 Bot 已經加入群組

### Q: 收不到通知
A: 檢查 `ENABLE_TELEGRAM_NOTIFY` 是否設為 `True`

### Q: 通知太頻繁
A: 可以關閉某些通知類型，例如：
```python
NOTIFY_ON_TRADE = False  # 關閉交易通知
NOTIFY_ON_START = False  # 關閉啟動通知
```

## 6. 安全注意事項

1. **不要分享您的 Bot Token**，它等同於密碼
2. **定期更換 Bot Token**，如果懷疑洩露
3. **使用私聊**而不是公開群組，避免信息洩露
4. **備份 config.py**，但不要上傳到公開倉庫

## 7. 高級設置

### 群組通知
如果您想在群組中接收通知：
1. 將 Bot 添加到群組
2. 在群組中發送 `/start` 命令
3. 獲取群組的 Chat ID（通常是負數）

### 多個通知目標
可以修改代碼支持多個 Chat ID：
```python
TELEGRAM_CHAT_IDS = ["chat_id_1", "chat_id_2", "chat_id_3"]
```

### 自定義消息格式
可以修改 `profit_tracker.py` 中的消息格式函數來自定義通知內容。 