# ⚡ 快速啟動指南 (v2.1)

> 5分鐘內完成機器人配置和啟動
> 
> **v2.1 新功能**: API 速度優化，3-10倍性能提升

## 🚀 超快速開始（3步驟）

### 1️⃣ **安裝**
```bash
# 克隆項目
git clone https://github.com/your-username/funding-rate-bot.git
cd funding-rate-bot

# 安裝依賴
pip install -r requirements.txt
```

### 2️⃣ **配置**
```bash
# 複製配置範例
cp config_example.py config.py

# 編輯配置（填入你的 API 金鑰）
nano config.py  # 或使用任何文字編輯器
```

**最重要的配置項目：**
```python
# 必填
API_KEY = "你的_BINANCE_API_金鑰"
API_SECRET = "你的_BINANCE_API_密鑰"

# 建議新手配置
MAX_POSITION_SIZE = 10    # 小額測試
LEVERAGE = 1              # 無槓桿
MIN_FUNDING_RATE = 0.2    # 高門檻
```

### 3️⃣ **啟動**
```bash
# 直接啟動
python test_trading_minute.py

# 或使用啟動器
python start_bot.py
```

## 📱 Telegram 通知（可選，5分鐘設置）

### 快速設置
1. **創建 Bot**：在 Telegram 找 `@BotFather`，發送 `/newbot`
2. **獲取 Token**：保存返回的 Bot Token
3. **獲取 Chat ID**：找 `@userinfobot`，發送任何消息獲得 ID
4. **填入配置**：
```python
TELEGRAM_BOT_TOKEN = "你的_BOT_TOKEN"
TELEGRAM_CHAT_ID = "你的_CHAT_ID"
```

## 🎯 配置方案（快速選擇）

### 🔰 新手保守（推薦）
```python
MAX_POSITION_SIZE = 10
LEVERAGE = 1
MIN_FUNDING_RATE = 0.3
MAX_SPREAD = 2.0
ENTRY_BEFORE_SECONDS = 1.0
CLOSE_AFTER_SECONDS = 1.0     # 平倉延遲
```

### ⚡ 進階快速
```python
MAX_POSITION_SIZE = 50
LEVERAGE = 2
MIN_FUNDING_RATE = 0.15
MAX_SPREAD = 3.0
ENTRY_BEFORE_SECONDS = 0.5
CLOSE_AFTER_SECONDS = 0.5     # 平倉延遲
```

### 🏎️ 專業極速 (v2.1 優化)
```python
MAX_POSITION_SIZE = 100
LEVERAGE = 3
MIN_FUNDING_RATE = 0.1
MAX_SPREAD = 5.0
ENTRY_BEFORE_SECONDS = 0.25
CLOSE_AFTER_SECONDS = 0.1     # 平倉延遲
```

## 🚀 v2.1 性能優化

### ⚡ API 速度提升
- **進場訂單**: 3-10倍速度提升
- **槓桿檢查**: 1-4倍速度提升  
- **倉位檢查**: 1-5倍速度提升
- **平倉訂單**: 保持極速執行

### 🛡️ 智能保護
- **超時控制**: 所有API調用1秒超時
- **自動重試**: 最多2次重試，指數退避
- **併發保護**: 防止API調用衝突
- **狀態重置**: 15秒內卡住的調用自動重置

## 🔍 快速測試

### 測試 API 連接
```bash
python -c "from test_trading_minute import FundingRateBot; bot = FundingRateBot(); print('✅ 成功' if bot.test_api_connection() else '❌ 失敗')"
```

### 測試 Telegram
```bash
python -c "from test_trading_minute import FundingRateBot; bot = FundingRateBot(); bot.send_telegram_message('🚀 測試成功！')"
```

## 📊 監控運行

### 查看日誌
```bash
# Windows
type logs\trading_log.txt

# Linux/macOS
tail -f logs/trading_log.txt
```

### 停止機器人
- 按 `Ctrl + C` 安全停止
- 機器人會先平倉再退出

## ⚠️ 重要提醒

### 🚨 開始前必讀
- **小額測試**：先用 10-20 USDT 測試
- **監控運行**：密切關注前幾小時
- **及時調整**：根據結果調整參數
- **風險管理**：永遠不要用超過承受能力的資金

### 🔒 安全檢查
- [ ] API 權限正確（只啟用讀取和期貨）
- [ ] 倉位大小合理
- [ ] 槓桿倍數保守
- [ ] config.py 已在 .gitignore 中

## 🆘 遇到問題？

### 常見解決方案
1. **API 錯誤**：檢查密鑰和權限
2. **模組未找到**：重新執行 `pip install -r requirements.txt`
3. **權限錯誤**：檢查 API 權限設置
4. **網路錯誤**：檢查網路連接和防火牆

### 獲取幫助
- 查看 [完整安裝指南](INSTALL.md)
- 查看 [詳細說明文件](README.md)
- 提交 [GitHub Issue](https://github.com/your-username/funding-rate-bot/issues)

---

## 🎉 恭喜！

你的資金費率套利機器人已經準備就緒！

記住：**先小額測試，確認穩定後再增加倉位**

祝交易順利！🚀 