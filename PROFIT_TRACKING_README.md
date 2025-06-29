# 收益追蹤和 Telegram 通知功能

## 功能概述

您的資金費率套利機器人現在已經整合了完整的收益追蹤和 Telegram 通知功能！

### 🎯 主要功能

1. **自動收益追蹤** - 記錄每筆交易的詳細信息
2. **實時統計分析** - 會話統計、日統計、勝率分析
3. **Telegram 通知** - 即時推送重要消息
4. **歷史數據保存** - 自動保存交易記錄到 JSON 文件
5. **CSV 導出** - 支持導出交易記錄進行進一步分析

## 📊 收益統計功能

### 會話統計
- **總交易次數** - 本次運行期間的交易總數
- **總盈虧** - 累計盈虧金額
- **勝率** - 盈利交易佔比
- **平均盈虧** - 每筆交易的平均盈虧
- **最大盈利/虧損** - 單筆最大盈虧記錄
- **運行時間** - 程式運行時長

### 日統計
- **今日交易次數** - 當日完成的交易數
- **今日盈虧** - 當日累計盈虧
- **今日勝率** - 當日盈利交易佔比

## 📱 Telegram 通知類型

### 1. 啟動通知
```
🚀 資金費率套利機器人已啟動

啟動時間: 2024-01-15 14:30:00
正在監控資金費率機會...
```

### 2. 交易通知
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

### 3. 錯誤通知
```
⚠️ 機器人發生錯誤

錯誤訊息: API 連接超時
時間: 2024-01-15 15:45:30
```

### 4. 停止通知（包含完整統計）
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

## ⚙️ 配置說明

### config.py 中的 Telegram 設定

```python
# Telegram 通知配置
TELEGRAM_BOT_TOKEN = "your_telegram_bot_token_here"  # 您的 Bot Token
TELEGRAM_CHAT_ID = "your_chat_id_here"  # 您的 Chat ID
ENABLE_TELEGRAM_NOTIFY = True  # 是否啟用 Telegram 通知
NOTIFY_ON_TRADE = True  # 是否在每次交易時通知
NOTIFY_ON_ERROR = True  # 是否在錯誤時通知
NOTIFY_ON_START = True  # 是否在程式啟動時通知
NOTIFY_ON_STOP = True  # 是否在程式停止時通知
```

### 通知開關控制

您可以靈活控制各種通知：

```python
# 只接收錯誤通知
NOTIFY_ON_TRADE = False
NOTIFY_ON_START = False
NOTIFY_ON_STOP = False
NOTIFY_ON_ERROR = True

# 只接收重要通知
NOTIFY_ON_TRADE = True
NOTIFY_ON_START = True
NOTIFY_ON_STOP = True
NOTIFY_ON_ERROR = True
```

## 📁 數據文件

### 自動生成的文件

1. **trade_history.json** - 交易歷史記錄
   - 自動保存每筆交易
   - 程式重啟時自動載入
   - 包含完整的交易詳情

2. **trades_YYYYMMDD_HHMMSS.csv** - CSV 導出文件
   - 可選導出功能
   - 便於 Excel 分析
   - 包含所有交易字段

### 文件格式示例

**trade_history.json:**
```json
[
  {
    "symbol": "BTCUSDT",
    "direction": "long",
    "quantity": 1000,
    "entry_price": 45123.45,
    "exit_price": 45125.67,
    "pnl": 2.22,
    "funding_rate": 0.01,
    "execution_time_ms": 49,
    "position_duration_seconds": 120,
    "retry_count": 0,
    "order_id": "123456789",
    "timestamp": "2024-01-15T14:30:00.123456",
    "session_id": "2024-01-15T14:00:00.000000"
  }
]
```

## 🧪 測試功能

### 運行測試腳本

```bash
python test_telegram.py
```

這個腳本會：
1. 測試所有 Telegram 通知類型
2. 模擬交易記錄
3. 顯示統計信息
4. 測試 CSV 導出功能

### 手動測試

```python
from profit_tracker import ProfitTracker

# 創建追蹤器
tracker = ProfitTracker()

# 發送測試消息
tracker.send_telegram_message("測試消息")

# 查看統計
stats = tracker.get_session_stats()
print(f"總交易: {stats['total_trades']}")
print(f"總盈虧: {stats['total_pnl']:.4f} USDT")
```

## 🔧 高級功能

### 自定義消息格式

您可以修改 `profit_tracker.py` 中的消息格式函數：

```python
def format_trade_message(self, trade_data: Dict) -> str:
    # 自定義您的消息格式
    message = f"🎯 新交易: {trade_data['symbol']}"
    message += f"\n盈虧: {trade_data['pnl']:.4f} USDT"
    return message
```

### 多個通知目標

可以修改代碼支持多個 Chat ID：

```python
TELEGRAM_CHAT_IDS = ["chat_id_1", "chat_id_2", "chat_id_3"]

# 在 send_telegram_message 中循環發送
for chat_id in TELEGRAM_CHAT_IDS:
    # 發送消息到每個目標
```

## 📈 使用建議

### 1. 監控重點
- **勝率** - 理想情況下應保持在 60% 以上
- **平均盈虧** - 正數表示整體盈利
- **最大虧損** - 關注風險控制
- **執行時間** - 越短越好，表示效率高

### 2. 風險管理
- 設置合理的 `MAX_POSITION_SIZE`
- 監控 `max_loss` 避免大額虧損
- 定期檢查 `win_rate` 確保策略有效

### 3. 優化建議
- 根據統計調整 `MIN_FUNDING_RATE`
- 優化 `CLOSE_DELAY_AFTER_ENTRY` 設定
- 分析哪些交易對表現最好

## 🚀 開始使用

1. **設置 Telegram Bot** - 參考 `TELEGRAM_SETUP.md`
2. **配置 config.py** - 填入您的 Bot Token 和 Chat ID
3. **測試通知** - 運行 `python test_telegram.py`
4. **啟動機器人** - 運行 `python test_trading_minute.py`

現在您的資金費率套利機器人已經具備了完整的收益追蹤和通知功能！🎉 