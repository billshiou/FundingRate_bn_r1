#!/usr/bin/env python3
"""
Telegram 連接測試
"""

import requests
import time

def test_telegram_connection():
    print("=== Telegram 連接測試 ===")
    
    # 配置
    bot_token = "8096406724:AAFtECyb-c0reDIdt8FOa-MujlowiJlyoZE"
    chat_id = "1009372117"
    
    try:
        # 測試 1: 基本網路連接
        print("\n1. 測試基本網路連接...")
        response = requests.get("https://www.google.com", timeout=5)
        print(f"✅ Google 連接成功: 狀態碼 {response.status_code}")
        
        # 測試 2: Telegram API 連接
        print("\n2. 測試 Telegram API 連接...")
        url = f"https://api.telegram.org/bot{bot_token}/getMe"
        response = requests.get(url, timeout=10)
        print(f"Telegram API 連接結果: 狀態碼 {response.status_code}")
        print(f"響應內容: {response.text}")
        
        if response.status_code == 200:
            print("✅ Telegram API 連接成功")
        else:
            print("❌ Telegram API 連接失敗")
            return False
        
        # 測試 3: 發送簡單消息
        print("\n3. 發送測試消息...")
        test_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        test_data = {
            'chat_id': chat_id,
            'text': f'🔧 網路連接測試消息\n時間: {time.strftime("%Y-%m-%d %H:%M:%S")}',
            'parse_mode': 'HTML'
        }
        
        print(f"發送請求到: {test_url}")
        print(f"消息內容: {test_data['text']}")
        
        response = requests.post(test_url, data=test_data, timeout=10)
        print(f"發送結果: 狀態碼 {response.status_code}")
        print(f"響應內容: {response.text}")
        
        if response.status_code == 200:
            print("✅ 測試消息發送成功！")
            return True
        else:
            print("❌ 測試消息發送失敗")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ 請求超時")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ 連接錯誤")
        return False
    except Exception as e:
        print(f"❌ 其他錯誤: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("開始 Telegram 連接測試...")
    success = test_telegram_connection()
    
    if success:
        print("\n🎉 所有測試通過！Telegram 通知功能正常。")
    else:
        print("\n💥 測試失敗！請檢查網路連接和 Telegram 配置。")
    
    print("\n測試完成。") 