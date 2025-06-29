#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
資金費率套利機器人 - 快速設置腳本
這個腳本幫助你快速設置配置文件
"""

import os
import shutil

def setup_config():
    """設置配置文件"""
    print("🚀 資金費率套利機器人快速設置")
    print("=" * 50)
    
    # 檢查config_example.py是否存在
    if not os.path.exists('config_example.py'):
        print("❌ 錯誤: 找不到 config_example.py 文件")
        return
    
    # 檢查config.py是否已存在
    if os.path.exists('config.py'):
        overwrite = input("⚠️  config.py 已存在，是否覆蓋? (y/N): ").lower()
        if overwrite != 'y':
            print("❌ 設置已取消")
            return
    
    # 複製配置範例
    try:
        shutil.copy2('config_example.py', 'config.py')
        print("✅ 已成功複製 config_example.py 到 config.py")
    except Exception as e:
        print(f"❌ 複製失敗: {e}")
        return
    
    print("\n📋 接下來請完成以下步驟:")
    print("1. 編輯 config.py 文件")
    print("2. 填入你的 Binance API Key 和 Secret")
    print("3. 根據需要調整交易參數")
    print("4. 選擇適合的配置方案:")
    print("   - 🎯 激進: 追求極限速度")
    print("   - ⚖️  平衡: 速度與安全兼顧 (推薦)")
    print("   - 🛡️  保守: 安全優先")
    print("\n⚠️  重要提醒:")
    print("- 請確保 API Key 有期貨交易權限")
    print("- 建議先用小額資金測試")
    print("- config.py 包含敏感信息，不會上傳到 Git")
    print("\n🚀 設置完成後，運行: python test_trading_minute.py")

def main():
    setup_config()

if __name__ == "__main__":
    main() 