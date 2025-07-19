#!/usr/bin/env python3
"""
資金費率套利機器人 - 快速啟動腳本 (v2.1)
提供簡單的啟動界面和配置檢查

v2.1 更新:
- API 速度優化 (3-10倍提升)
- 智能重試機制
- 併發保護和狀態重置
"""

import os
import sys
import time
from datetime import datetime

def check_config():
    """檢查配置文件"""
    print("🔍 檢查配置文件...")
    
    if not os.path.exists('config.py'):
        print("❌ 錯誤: 找不到 config.py 文件")
        print("💡 請先複製 config.example.py 為 config.py 並填入你的API信息")
        return False
    
    try:
        import config
        if not hasattr(config, 'API_KEY') or config.API_KEY == "your_api_key_here":
            print("❌ 錯誤: 請在 config.py 中填入你的 API_KEY")
            return False
        
        if not hasattr(config, 'API_SECRET') or config.API_SECRET == "your_api_secret_here":
            print("❌ 錯誤: 請在 config.py 中填入你的 API_SECRET")
            return False
        
        print("✅ 配置文件檢查通過")
        return True
        
    except ImportError as e:
        print(f"❌ 錯誤: 無法導入配置文件 - {e}")
        return False

def check_dependencies():
    """檢查依賴包"""
    print("🔍 檢查依賴包...")
    
    required_packages = [
        'ccxt', 'pandas', 'numpy', 'requests', 
        'websocket', 'binance'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ 缺少依賴包: {', '.join(missing_packages)}")
        print("💡 請執行: pip install -r requirements.txt")
        return False
    
    print("✅ 依賴包檢查通過")
    return True

def check_logs_directory():
    """檢查日誌目錄"""
    print("🔍 檢查日誌目錄...")
    
    if not os.path.exists('logs'):
        os.makedirs('logs')
        print("📁 創建日誌目錄")
    
    print("✅ 日誌目錄檢查通過")

def show_menu():
    """顯示主菜單"""
    print("\n" + "="*50)
    print("🤖 資金費率套利機器人")
    print("="*50)
    print("1. 🚀 啟動機器人")
    print("2. 🧪 運行測試")
    print("3. 📊 查看API監控")
    print("4. 📋 查看配置")
    print("5. 📖 查看日誌")
    print("6. ❌ 退出")
    print("="*50)

def show_config_summary():
    """顯示配置摘要"""
    try:
        import config
        print("\n📋 當前配置摘要:")
        print(f"   最大倉位大小: {getattr(config, 'MAX_POSITION_SIZE', 'N/A')} USDT")
        print(f"   槓桿倍數: {getattr(config, 'LEVERAGE', 'N/A')}x")
        print(f"   最小資金費率: {getattr(config, 'MIN_FUNDING_RATE', 'N/A')}%")
        print(f"   進場提前時間: {getattr(config, 'ENTRY_BEFORE_SECONDS', 'N/A')}秒")
        print(f"   平倉延遲時間: {getattr(config, 'CLOSE_AFTER_SECONDS', 'N/A')}秒")
        print(f"   最大進場重試: {getattr(config, 'MAX_ENTRY_RETRY', 'N/A')}次")
        print(f"   最大平倉重試: {getattr(config, 'MAX_CLOSE_RETRY', 'N/A')}次")
    except ImportError:
        print("❌ 無法讀取配置文件")

def show_logs():
    """顯示日誌文件"""
    log_files = []
    
    if os.path.exists('logs'):
        for file in os.listdir('logs'):
            if file.endswith('.txt') or file.endswith('.log'):
                log_files.append(file)
    
    if not log_files:
        print("📁 沒有找到日誌文件")
        return
    
    print("\n📖 可用的日誌文件:")
    for i, file in enumerate(log_files, 1):
        file_path = os.path.join('logs', file)
        size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        print(f"   {i}. {file} ({size} bytes)")
    
    try:
        choice = input("\n請選擇要查看的日誌文件 (輸入編號，或按Enter取消): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(log_files):
            selected_file = log_files[int(choice) - 1]
            file_path = os.path.join('logs', selected_file)
            
            print(f"\n📄 {selected_file} 內容 (最後20行):")
            print("-" * 50)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in lines[-20:]:
                    print(line.rstrip())
        else:
            print("❌ 無效選擇")
    except Exception as e:
        print(f"❌ 讀取日誌文件失敗: {e}")

def run_tests():
    """運行測試"""
    print("\n🧪 運行自動化測試...")
    
    if not os.path.exists('test_trading_functions.py'):
        print("❌ 找不到測試文件 test_trading_functions.py")
        return
    
    try:
        import subprocess
        result = subprocess.run([
            sys.executable, '-m', 'pytest', 
            'test_trading_functions.py', '-v'
        ], capture_output=True, text=True)
        
        print("測試結果:")
        print(result.stdout)
        
        if result.stderr:
            print("錯誤信息:")
            print(result.stderr)
            
    except Exception as e:
        print(f"❌ 運行測試失敗: {e}")

def start_bot():
    """啟動機器人"""
    print("\n🚀 啟動資金費率套利機器人...")
    
    if not os.path.exists('test_trading_minute.py'):
        print("❌ 找不到主程式文件 test_trading_minute.py")
        return
    
    try:
        print("⏰ 啟動時間:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        print("💡 按 Ctrl+C 停止機器人")
        print("-" * 50)
        
        # 導入並運行主程式
        import test_trading_minute
        trader = test_trading_minute.FundingRateTrader()
        trader.run()
        
    except KeyboardInterrupt:
        print("\n\n⏹️ 機器人已停止")
    except Exception as e:
        print(f"\n❌ 啟動失敗: {e}")

def main():
    """主函數"""
    print("🤖 歡迎使用資金費率套利機器人!")
    
    # 檢查環境
    if not check_dependencies():
        return
    
    if not check_config():
        return
    
    check_logs_directory()
    
    while True:
        show_menu()
        
        try:
            choice = input("\n請選擇操作 (1-6): ").strip()
            
            if choice == '1':
                start_bot()
            elif choice == '2':
                run_tests()
            elif choice == '3':
                print("📊 API監控功能 - 請運行 python api_monitor.py")
            elif choice == '4':
                show_config_summary()
            elif choice == '5':
                show_logs()
            elif choice == '6':
                print("👋 再見!")
                break
            else:
                print("❌ 無效選擇，請輸入 1-6")
                
        except KeyboardInterrupt:
            print("\n\n👋 再見!")
            break
        except Exception as e:
            print(f"❌ 操作失敗: {e}")

if __name__ == "__main__":
    main() 