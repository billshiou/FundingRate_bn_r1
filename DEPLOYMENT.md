# 部署指南

## 1. 準備工作
```bash
# 克隆專案
git clone <your-repository-url>
cd funding-rate-bot

# 安裝依賴
pip install -r requirements.txt
```

## 2. 配置
```bash
# 複製配置範例
cp config.example.py config.py

# 編輯配置文件
# 填入你的 Binance API 密鑰
```

## 3. 測試
```bash
# 運行自動化測試
python -m pytest test_trading_functions.py -v

# 或使用啟動腳本
python start_bot.py
```

## 4. 部署
```bash
# 直接運行
python test_trading_minute.py

# 或使用啟動腳本
python start_bot.py
```

## 5. 監控
```bash
# 查看API監控
python api_monitor.py

# 查看日誌
tail -f logs/trading_log.txt
```

## 6. 維護
- 定期檢查日誌文件大小
- 監控API使用情況
- 更新依賴包
- 備份配置文件
