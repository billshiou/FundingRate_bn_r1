# 🛠️ 安裝和配置指南 (v2.1)

> **v2.1 版本更新**: API 速度優化，智能重試機制，併發保護

## 📋 前置要求

### 💻 **系統要求**
- **作業系統**: Windows 10+、macOS 10.14+、Ubuntu 18.04+
- **Python**: 3.7 或更高版本
- **網路**: 穩定的網路連接（建議延遲 < 100ms）
- **記憶體**: 至少 512MB 可用記憶體

### 🏦 **交易所要求**
- **Binance 帳戶**: 已完成 KYC 認證
- **期貨權限**: 啟用期貨交易功能
- **API 權限**: 啟用期貨交易和讀取權限
- **最低資金**: 建議至少 50 USDT 用於測試

## 🚀 快速安裝

### 1️⃣ **下載項目**
```bash
# 克隆項目
git clone https://github.com/your-username/funding-rate-bot.git
cd funding-rate-bot

# 或直接下載 ZIP 檔案並解壓
```

### 2️⃣ **安裝 Python 依賴**
```bash
# 檢查 Python 版本
python --version

# 安裝依賴
pip install -r requirements.txt

# 如果遇到權限問題，使用：
pip install --user -r requirements.txt
```

### 3️⃣ **配置 API 金鑰**
```bash
# 複製配置範例
cp config_example.py config.py

# Windows 用戶
copy config_example.py config.py
```

## 🔑 Binance API 設置

### 📱 **創建 API 金鑰**

1. **登入 Binance**
   - 前往 [Binance](https://www.binance.com/)
   - 登入你的帳戶

2. **進入 API 管理**
   - 點擊右上角頭像
   - 選擇 "API Management"

3. **創建新的 API 金鑰**
   - 點擊 "Create API"
   - 輸入標籤名稱（例如：funding-rate-bot）
   - 完成安全驗證

4. **配置權限**
   - ✅ **Enable Reading** (必須)
   - ✅ **Enable Futures** (必須)
   - ❌ **Enable Withdraws** (不建議)

5. **IP 白名單**（推薦）
   - 添加你的服務器 IP
   - 提高安全性

### 🔐 **安全設置**
```bash
# 確保 config.py 權限正確 (Linux/macOS)
chmod 600 config.py

# Windows 用戶請確保該檔案不被其他用戶訪問
```

## ⚙️ 詳細配置

### 📝 **編輯 config.py**
```python
# === 必填項目 ===
API_KEY = "your_actual_api_key_here"
API_SECRET = "your_actual_api_secret_here"

# === Telegram 通知（可選）===
TELEGRAM_BOT_TOKEN = "your_bot_token"  # 可留空
TELEGRAM_CHAT_ID = "your_chat_id"      # 可留空
ENABLE_TELEGRAM_NOTIFY = True          # 設為 False 停用通知

# === 交易設定 ===
MAX_POSITION_SIZE = 20    # 建議新手從 10-20 開始
LEVERAGE = 2              # 建議新手使用 1-2x
MIN_FUNDING_RATE = 0.15   # 建議新手提高門檻到 0.15-0.2
MAX_SPREAD = 3.0          # 建議新手降低到 3.0

# === 時機設定 ===
ENTRY_BEFORE_SECONDS = 0.5    # 新手建議 0.5 秒
CLOSE_AFTER_SECONDS = 0.5     # 新手建議 0.5 秒平倉延遲
```

### 🎯 **配置建議**

#### 🔰 **新手配置**
```python
MAX_POSITION_SIZE = 10        # 小額測試
LEVERAGE = 1                  # 無槓桿
MIN_FUNDING_RATE = 0.2        # 高門檻
MAX_SPREAD = 2.0              # 嚴格點差
ENTRY_BEFORE_SECONDS = 1.0    # 安全進場
CLOSE_AFTER_SECONDS = 1.0     # 安全平倉延遲
```

#### ⚡ **高級配置**
```python
MAX_POSITION_SIZE = 100       # 大倉位
LEVERAGE = 3                  # 高槓桿
MIN_FUNDING_RATE = 0.1        # 標準門檻
MAX_SPREAD = 5.0              # 寬鬆點差
ENTRY_BEFORE_SECONDS = 0.25   # 精準進場
CLOSE_AFTER_SECONDS = 0.1     # 極速平倉延遲
```

## 📱 Telegram 設置（可選）

### 🤖 **創建 Telegram Bot**
1. 在 Telegram 中搜尋 `@BotFather`
2. 發送 `/start` 開始對話
3. 發送 `/newbot` 創建新機器人
4. 輸入機器人名稱（例如：My Funding Bot）
5. 輸入用戶名（例如：my_funding_bot）
6. 保存返回的 Bot Token

### 📞 **獲取 Chat ID**
1. 在 Telegram 中搜尋 `@userinfobot`
2. 發送 `/start`
3. 機器人會返回你的 Chat ID
4. 將 Chat ID 填入配置文件

### ✅ **測試通知**
```bash
# 運行測試腳本
python -c "
from test_trading_minute import FundingRateBot
bot = FundingRateBot()
bot.send_telegram_message('🚀 測試通知成功！機器人已正確配置。')
"
```

## 🧪 測試安裝

### 1️⃣ **檢查依賴**
```bash
python -c "import requests, websocket, ccxt; print('✅ 依賴安裝成功')"
```

### 2️⃣ **測試 API 連接**
```bash
python -c "
from test_trading_minute import FundingRateBot
bot = FundingRateBot()
print('✅ API 連接成功' if bot.test_api_connection() else '❌ API 連接失敗')
"
```

### 3️⃣ **測試 WebSocket**
```bash
python test_network_speed.py
```

### 4️⃣ **測試完整功能**
```bash
python start_bot.py
# 選擇 "測試模式" 進行全面測試
```

## 🚦 首次運行

### 📊 **監控模式（推薦新手）**
```bash
# 先運行監控模式，觀察市場
python start_bot.py
# 選擇 "5. 查看實時資金費率"
```

### 🔍 **模擬模式**
```bash
# 編輯 config.py，添加：
SIMULATION_MODE = True  # 模擬交易，不實際下單

# 然後運行
python test_trading_minute.py
```

### 🚀 **實盤交易**

## ⚡ v2.1 性能優化說明

### 🚀 **API 速度提升**
- **進場訂單**: 3-10倍速度提升，從平均 2-5秒 降至 0.5-1秒
- **槓桿檢查**: 1-4倍速度提升，從平均 1-2秒 降至 0.3-0.5秒
- **倉位檢查**: 1-5倍速度提升，從平均 1-3秒 降至 0.3-0.8秒
- **平倉訂單**: 保持極速執行，平均 50-100ms

### 🛡️ **智能保護機制**
- **超時控制**: 所有API調用都有1秒超時保護
- **自動重試**: 最多2次重試，使用指數退避策略 (0.5s → 1s → 2s)
- **併發保護**: 最多3個API調用同時進行，防止衝突
- **狀態重置**: 15秒內卡住的API調用自動重置

### 📊 **性能監控**
```bash
# 查看API性能日誌
tail -f logs/api_performance.log

# 查看詳細交易日誌
tail -f logs/trading_log.txt
```
```bash
# 確認配置無誤後
python test_trading_minute.py
```

## 📁 日誌檢查

### 📄 **日誌位置**
```
logs/
├── trading_log.txt          # 主要交易日誌
├── trade_analysis.txt       # 交易分析記錄
├── api_monitor.log          # API 使用記錄
└── error.log               # 錯誤日誌
```

### 👀 **即時監控**
```bash
# Linux/macOS
tail -f logs/trading_log.txt

# Windows PowerShell
Get-Content logs/trading_log.txt -Wait
```

## ❌ 常見問題

### 🔧 **安裝問題**

**Q: pip install 失敗**
```bash
# 升級 pip
python -m pip install --upgrade pip

# 使用國內鏡像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
```

**Q: ModuleNotFoundError**
```bash
# 檢查 Python 環境
which python
python --version

# 重新安裝依賴
pip uninstall -r requirements.txt -y
pip install -r requirements.txt
```

### 🔑 **API 問題**

**Q: API 連接失敗**
- 檢查 API Key 和 Secret 是否正確
- 確認啟用了期貨交易權限
- 檢查 IP 白名單設置

**Q: 權限不足錯誤**
- 確認 API 權限包含 "Enable Reading" 和 "Enable Futures"
- 檢查帳戶是否有足夠餘額

### 📱 **Telegram 問題**

**Q: Telegram 通知失敗**
```bash
# 測試 Bot Token
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getMe"

# 測試發送消息
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/sendMessage" \
     -d "chat_id=<YOUR_CHAT_ID>&text=測試消息"
```

## 🆘 獲取幫助

### 📞 **支援管道**
- **GitHub Issues**: 報告 Bug 和功能請求
- **文檔**: 查看 README.md 獲取更多信息
- **社群**: 加入 Telegram 群組討論

### 📊 **診斷工具**
```bash
# 生成診斷報告
python -c "
from test_trading_minute import FundingRateBot
bot = FundingRateBot()
bot.generate_diagnostic_report()
"
```

---

## ✅ 安裝檢查清單

- [ ] Python 3.7+ 已安裝
- [ ] 依賴包安裝成功
- [ ] Binance API 金鑰已配置
- [ ] API 權限設置正確
- [ ] config.py 文件已正確配置
- [ ] Telegram Bot 設置完成（可選）
- [ ] 測試連接成功
- [ ] 日誌目錄已創建
- [ ] 首次測試運行成功

🎉 **恭喜！你已成功安裝資金費率套利機器人！** 