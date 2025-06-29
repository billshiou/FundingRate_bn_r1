#!/usr/bin/env python3
"""
專案清理腳本
清理不需要的文件，整理專案結構
"""

import os
import shutil
import sys

def cleanup_files():
    """清理不需要的文件"""
    print("🧹 開始清理專案...")
    
    # 要刪除的文件列表
    files_to_delete = [
        'funding_rate_trader_bn.py',  # 舊版本
        'funding_rate_monitor_bn.py', # 舊版本
        'test_binance_funding.py',    # 測試文件
        'main.py',                    # 舊主程式
        'README_async_improvements.md', # 舊文檔
        'push.bat',                   # 舊腳本
    ]
    
    # 要刪除的目錄列表
    dirs_to_delete = [
        'src/',                       # 舊目錄結構
        'utils/',                     # 舊目錄結構
        'risk/',                      # 舊目錄結構
        'strategies/',                # 舊目錄結構
        'exchanges/',                 # 舊目錄結構
        'config/',                    # 舊目錄結構
        '__pycache__/',               # Python緩存
        '.venv/',                     # 虛擬環境（如果存在）
    ]
    
    # 刪除文件
    for file in files_to_delete:
        if os.path.exists(file):
            try:
                os.remove(file)
                print(f"✅ 已刪除: {file}")
            except Exception as e:
                print(f"❌ 刪除失敗 {file}: {e}")
    
    # 刪除目錄
    for dir_path in dirs_to_delete:
        if os.path.exists(dir_path):
            try:
                shutil.rmtree(dir_path)
                print(f"✅ 已刪除目錄: {dir_path}")
            except Exception as e:
                print(f"❌ 刪除目錄失敗 {dir_path}: {e}")

def create_final_structure():
    """創建最終的專案結構"""
    print("\n📁 創建最終專案結構...")
    
    # 確保logs目錄存在
    if not os.path.exists('logs'):
        os.makedirs('logs')
        print("✅ 創建 logs/ 目錄")
    
    # 創建空的 __init__.py 文件
    init_files = ['logs/__init__.py']
    
    for init_file in init_files:
        if not os.path.exists(init_file):
            with open(init_file, 'w') as f:
                f.write('# 自動生成的 __init__.py 文件\n')
            print(f"✅ 創建: {init_file}")

def show_final_structure():
    """顯示最終的專案結構"""
    print("\n📋 最終專案結構:")
    print("=" * 50)
    
    structure = """
funding-rate-bot/
├── test_trading_minute.py      # 主程式
├── config.py                   # 配置文件 (包含API密鑰)
├── config.example.py           # 配置範例
├── requirements.txt            # 依賴包
├── README.md                   # 說明文件
├── LICENSE                     # 授權文件
├── .gitignore                  # Git忽略文件
├── pytest.ini                 # 測試配置
├── start_bot.py               # 快速啟動腳本
├── test_trading_functions.py   # 自動化測試
├── api_monitor.py              # API監控
└── logs/                       # 日誌目錄
    ├── __init__.py
    ├── trading_log.txt         # 交易日誌
    └── api_monitor.log         # API監控日誌
"""
    
    print(structure)

def check_git_status():
    """檢查Git狀態"""
    print("\n🔍 檢查Git狀態...")
    
    if not os.path.exists('.git'):
        print("⚠️  警告: 這不是一個Git倉庫")
        print("💡 建議: git init 初始化倉庫")
        return
    
    try:
        import subprocess
        result = subprocess.run(['git', 'status', '--porcelain'], 
                              capture_output=True, text=True)
        
        if result.stdout.strip():
            print("📝 有未提交的更改:")
            for line in result.stdout.strip().split('\n'):
                if line:
                    print(f"   {line}")
        else:
            print("✅ 工作目錄乾淨")
            
    except Exception as e:
        print(f"❌ 檢查Git狀態失敗: {e}")

def create_deployment_guide():
    """創建部署指南"""
    print("\n📝 創建部署指南...")
    
    guide_content = """# 部署指南

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
"""
    
    with open('DEPLOYMENT.md', 'w', encoding='utf-8') as f:
        f.write(guide_content)
    
    print("✅ 創建 DEPLOYMENT.md")

def main():
    """主函數"""
    print("🤖 資金費率套利機器人 - 專案清理工具")
    print("=" * 50)
    
    # 確認操作
    confirm = input("⚠️  這將刪除一些舊文件，確定繼續嗎? (y/N): ").strip().lower()
    if confirm != 'y':
        print("❌ 操作已取消")
        return
    
    # 執行清理
    cleanup_files()
    create_final_structure()
    show_final_structure()
    check_git_status()
    create_deployment_guide()
    
    print("\n🎉 專案清理完成!")
    print("\n📋 下一步:")
    print("1. 檢查 config.py 中的API配置")
    print("2. 運行 python start_bot.py 測試")
    print("3. 提交到Git: git add . && git commit -m 'v1.0.0'")
    print("4. 推送到GitHub: git push origin main")

if __name__ == "__main__":
    main() 