# ==================== 資金費率套利機器人配置範例 ====================
# 複製此文件為 config.py 並填入你的真實配置信息
# ⚠️ 注意：config.py 文件包含敏感信息，不要上傳到公開倉庫

# ==================== API 配置區塊 ====================
# Binance 期貨 API 設定
API_KEY = "your_binance_api_key_here"           # 你的 Binance API Key
API_SECRET = "your_binance_api_secret_here"     # 你的 Binance API Secret

# Telegram 通知設定（可選，留空則不發送通知）
TELEGRAM_BOT_TOKEN = ""  # Telegram Bot Token（可選）
TELEGRAM_CHAT_ID = ""                              # Telegram Chat ID（可選）
ENABLE_TELEGRAM_NOTIFICATIONS = True                        # 是否啟用 Telegram 通知
TELEGRAM_TRADE_NOTIFICATIONS = True                         # 是否發送交易通知
TELEGRAM_ERROR_NOTIFICATIONS = True                         # 是否發送錯誤通知
TELEGRAM_SUMMARY_NOTIFICATIONS = True                       # 是否發送總結通知

# ==================== 進場配置區塊 ====================
# 基本交易設定
MAX_POSITION_SIZE = 100      # 最大倉位大小 (USDT) - 建議從小額開始測試
LEVERAGE = 10                # 槓桿倍數 (1-125)
MIN_FUNDING_RATE = 0.01      # 最小資金費率閾值 (%) - 低於此值不進場

# 進場時機設定
ENTRY_BEFORE_SECONDS = 0.2   # 結算前多少秒進場 (秒) - 激進: 0.1-0.5, 保守: 1-3
CHECK_INTERVAL = 0.1         # 主循環檢查間隔 (秒)
ENTRY_TIME_TOLERANCE = 30    # 進場時間容錯 (秒)

# 進場重試機制
MAX_ENTRY_RETRY = 0                    # 最大進場重試次數 - 0=關閉重試, 1-5=重試次數
ENTRY_RETRY_INTERVAL = 0.1             # 進場重試間隔 (秒)
ENTRY_RETRY_UNTIL_SETTLEMENT = False   # 是否重試直到結算時間

# 交易對設定
TRADING_HOURS = [0, 8, 16]            # 交易時間 (UTC) - [0, 8, 16] 表示每8小時結算
TRADING_MINUTES = [0]                 # 交易分鐘 - [0] 表示整點結算
TRADING_SYMBOLS = []                  # 指定交易幣種 - 空列表表示全部幣種
EXCLUDED_SYMBOLS = [                  # 排除的交易幣種
    'BTCDOMUSDT', 'DEFIUSDT', 'USDCUSDT'
]

# ==================== 平倉配置區塊 ====================
# 平倉時機設定
CLOSE_BEFORE_SECONDS = 0.0       # 結算前多少秒平倉 (秒) - 激進: 0.0, 保守: 1-5
CLOSE_DELAY_AFTER_ENTRY = 0      # 開倉後延遲平倉時間 (秒) - 0=立即平倉
FORCE_CLOSE_AT_SETTLEMENT = True # 是否在結算時強制平倉

# 平倉重試設定
MAX_CLOSE_RETRY = 0              # 最大平倉重試次數 - 0=關閉重試, 建議1-3
CLOSE_RETRY_INTERVAL = 0.1       # 平倉重試間隔 (秒)

# 倉位管理設定
ACCOUNT_CHECK_INTERVAL = 60          # 帳戶檢查間隔 (秒) - 正常時間每60秒一次
POSITION_TIMEOUT_SECONDS = 1         # 倉位超時時間 (秒)
ENABLE_POSITION_CLEANUP = True       # 啟用倉位清理
FORCE_CLOSE_AFTER_SECONDS = 3        # 強制平倉等待時間 (秒) - 結算後多久強制平倉
POSITION_CHECK_INTERVAL = 1          # 倉位檢查間隔 (秒) - 有持倉時的檢查頻率

# 結算後高頻檢查設定
POST_SETTLEMENT_CHECK_PERIOD = 60    # 結算後高頻檢查時間窗口 (秒) - 結算後多久內高頻檢查
POST_SETTLEMENT_CHECK_INTERVAL = 1   # 結算後檢查間隔 (秒) - 高頻檢查期間的檢查頻率

# ==================== 預設配置方案 ====================
"""
🎯 激進交易配置 (追求極限速度):
ENTRY_BEFORE_SECONDS = 0.2
CLOSE_BEFORE_SECONDS = 0.0
MAX_ENTRY_RETRY = 0
MAX_CLOSE_RETRY = 0
LEVERAGE = 20
POST_SETTLEMENT_CHECK_PERIOD = 30
POST_SETTLEMENT_CHECK_INTERVAL = 0.5


# ==================== 使用說明 ====================
"""
📋 設置步驟:
1. 複製此文件為 config.py
2. 填入你的 Binance API Key 和 Secret
3. 根據風險偏好選擇配置方案
4. 建議先用小額資金測試

⚠️ 重要提醒:
- API Key 需要開啟期貨交易和讀取權限
- 建議先在測試網測試策略
- 資金費率套利存在市場風險
- 程式碼僅供學習參考，使用時請自行承擔風險

🔗 更多信息:
- 設置教學: 參考 README.md
- Telegram 設置: 參考 TELEGRAM_SETUP.md
- 部署說明: 參考 DEPLOYMENT.md
""" 