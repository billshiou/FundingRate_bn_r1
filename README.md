# 資金費率套利機器人 (Funding Rate Arbitrage Bot)

一個基於 Binance 期貨的資金費率套利自動交易機器人，能夠自動監控資金費率差異並執行套利交易。

## 🚀 功能特色

### 核心功能
- **自動資金費率監控**: 實時監控所有交易對的資金費率
- **智能套利執行**: 自動識別套利機會並執行交易
- **多重安全保障**: 三重平倉機制確保資金安全
- **精確時間同步**: 與 Binance 服務器時間同步，確保準確執行

### 風控機制
- **倉位管理**: 可配置最大倉位大小和槓桿倍數
- **重試機制**: 進場和平倉失敗自動重試
- **超時清理**: 自動清理超時倉位
- **定期檢查**: 定期檢查持倉狀態和帳戶餘額

### 監控與日誌
- **詳細日誌**: 完整的交易軌跡和系統事件記錄
- **日誌輪轉**: 自動管理日誌文件大小和清理
- **API監控**: 監控API限流和異常頻率
- **自動化測試**: 完整的單元測試覆蓋

## 📋 系統要求

- Python 3.8+
- Binance 期貨帳戶
- API Key 和 Secret Key

## 🛠️ 安裝步驟

### 1. 克隆專案
```bash
git clone <your-repository-url>
cd funding-rate-bot
```

### 2. 安裝依賴
```bash
pip install -r requirements.txt
```

### 3. 配置API

#### 方法一：使用設置腳本 (推薦)
```bash
python setup.py
```

#### 方法二：手動複製
```bash
cp config_example.py config.py
```

然後編輯 `config.py` 文件，填入你的 Binance API 信息：
```python
API_KEY = "your_api_key_here"
API_SECRET = "your_api_secret_here"
```

⚠️ **重要**: `config.py` 包含敏感信息，已在 `.gitignore` 中排除，不會上傳到 GitHub

### 4. 調整配置
根據你的需求調整 `config.py` 中的其他參數：
- `MAX_POSITION_SIZE`: 最大倉位大小 (USDT)
- `LEVERAGE`: 槓桿倍數
- `MIN_FUNDING_RATE`: 最小資金費率閾值
- `ENTRY_BEFORE_SECONDS`: 進場提前時間
- `CLOSE_BEFORE_SECONDS`: 平倉提前時間

## 🚀 使用方法

### 啟動機器人
```bash
python test_trading_minute.py
```

### 運行測試
```bash
# 運行所有測試
pytest test_trading_functions.py -v

# 運行特定測試
pytest test_trading_functions.py::TestTradingFunctions::test_calculate_position_size -v
```

### 監控API狀態
```bash
python api_monitor.py
```

## 📊 配置說明

### 預設配置方案

機器人提供三種預設配置方案，你可以根據自己的風險偏好選擇：

#### 🎯 激進交易配置 (追求極限速度)
```python
ENTRY_BEFORE_SECONDS = 0.2
CLOSE_BEFORE_SECONDS = 0.0
MAX_ENTRY_RETRY = 0
MAX_CLOSE_RETRY = 0
LEVERAGE = 20
POST_SETTLEMENT_CHECK_PERIOD = 30
POST_SETTLEMENT_CHECK_INTERVAL = 0.5
```
**特點**: 最高速度，最低延遲，適合有經驗的用戶

#### ⚖️ 平衡配置 (速度與安全兼顧)
```python
ENTRY_BEFORE_SECONDS = 1.0
CLOSE_BEFORE_SECONDS = 0.5
MAX_ENTRY_RETRY = 2
MAX_CLOSE_RETRY = 2
LEVERAGE = 10
POST_SETTLEMENT_CHECK_PERIOD = 60
POST_SETTLEMENT_CHECK_INTERVAL = 1
```
**特點**: 平衡風險與收益，推薦新手使用

#### 🛡️ 保守配置 (安全優先)
```python
ENTRY_BEFORE_SECONDS = 2.0
CLOSE_BEFORE_SECONDS = 1.0
MAX_ENTRY_RETRY = 3
MAX_CLOSE_RETRY = 3
LEVERAGE = 5
POST_SETTLEMENT_CHECK_PERIOD = 120
POST_SETTLEMENT_CHECK_INTERVAL = 2
```
**特點**: 最高安全性，適合保守的投資者

### 交易配置
```python
# 基本交易配置
MAX_POSITION_SIZE = 50      # 單次最大保證金 (USDT)
LEVERAGE = 4                # 槓桿倍數
MIN_FUNDING_RATE = 0.2      # 最小資金費率 (%)

# 時間配置
ENTRY_BEFORE_SECONDS = 0.2  # 進場提前時間 (秒)
CLOSE_BEFORE_SECONDS = 0.1  # 平倉提前時間 (秒)
CHECK_INTERVAL = 0.1        # 主循環檢查間隔 (秒)
```

### 重試配置
```python
# 進場重試
MAX_ENTRY_RETRY = 0         # 最大進場重試次數
ENTRY_RETRY_INTERVAL = 0.2  # 進場重試間隔 (秒)

# 平倉重試
MAX_CLOSE_RETRY = 3         # 最大平倉重試次數
CLOSE_RETRY_INTERVAL = 0.2  # 平倉重試間隔 (秒)
```

### 風控配置
```python
# 持倉管理
MAX_HOLDING_TIME = 0.7      # 最大持倉時間 (秒)
POSITION_TIMEOUT_SECONDS = 3 # 倉位超時時間 (秒)

# 交易時間
TRADING_HOURS = list(range(24))    # 24小時交易
TRADING_MINUTES = list(range(60))  # 每分鐘交易
```

## 📁 專案結構

```
funding-rate-bot/
├── test_trading_minute.py      # 主程式
├── config.py                   # 配置文件 (請勿上傳)
├── config_example.py           # 配置範例文件
├── setup.py                    # 快速設置腳本
├── requirements.txt            # 依賴包
├── README.md                   # 說明文件
├── test_trading_functions.py   # 自動化測試
├── api_monitor.py              # API監控
├── logs/                       # 日誌目錄
│   ├── trading_log.txt         # 交易日誌
│   └── api_monitor.log         # API監控日誌
└── .gitignore                  # Git忽略文件
```

## 🔧 核心功能詳解

### 1. 資金費率套利策略
機器人會監控所有交易對的資金費率，當發現資金費率差異超過設定閾值時：
- 負資金費率：做多該交易對
- 正資金費率：做空該交易對
- 在結算前平倉，獲取資金費率收益

### 2. 三重平倉機制
1. **主要機制**: 開倉成功後延遲平倉，快速鎖定收益
2. **備份機制**: 如果延遲平倉失敗，結算前再次平倉
3. **強制機制**: 如果備份平倉也失敗，結算後強制平倉

### 3. 時間同步
- 定期與 Binance 服務器時間同步
- 確保交易時間的準確性
- 避免因時間偏差導致的交易失誤

### 4. 日誌系統
- 結構化 JSON 格式日誌
- 自動日誌輪轉和清理
- 詳細的交易步驟記錄
- 系統狀態監控

## 🧪 測試覆蓋

### 功能測試
- 持倉數量計算
- JSON序列化處理
- 時間格式化
- 配置驗證
- 交易對驗證
- 日誌功能

### 錯誤處理測試
- 無效價格處理
- 無效交易對處理
- JSON序列化錯誤處理

### 性能測試
- 持倉計算性能
- JSON序列化性能

## 📈 監控與警報

### API監控
- 限流錯誤監控
- API錯誤頻率統計
- 自動警告機制
- 請求統計報告

### 系統監控
- 持倉狀態檢查
- 帳戶餘額監控
- 網路連接狀態
- WebSocket連接狀態

## ⚠️ 風險警告

1. **資金風險**: 期貨交易存在資金損失風險，請謹慎使用
2. **API風險**: 請妥善保管API密鑰，不要泄露給他人
3. **市場風險**: 資金費率套利受市場波動影響
4. **技術風險**: 程式可能存在bug，建議先在測試環境驗證

## 🤝 貢獻指南

1. Fork 本專案
2. 創建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 開啟 Pull Request

## 📝 更新日誌

### v1.0.0 (2025-06-22)
- 初始版本發布
- 基本資金費率套利功能
- 三重平倉機制
- 完整日誌系統
- 自動化測試
- API監控功能

## 📄 授權

本專案採用 MIT 授權 - 查看 [LICENSE](LICENSE) 文件了解詳情

## 📞 聯繫方式

如有問題或建議，請通過以下方式聯繫：
- 提交 Issue
- 發送 Email
- 開啟 Pull Request

---

**免責聲明**: 本軟體僅供學習和研究使用，使用者需自行承擔使用風險。作者不對任何投資損失負責。