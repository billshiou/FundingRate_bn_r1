#!/usr/bin/env python3
"""
測試通知功能
"""

import time
from profit_tracker import ProfitTracker

def test_notifications():
    """測試啟動和停止通知"""
    print("=== 測試通知功能 ===")
    
    # 創建 ProfitTracker 實例
    tracker = ProfitTracker()
    
    print("1. 測試啟動通知...")
    try:
        tracker.send_start_notification()
        print("✅ 啟動通知發送成功")
    except Exception as e:
        print(f"❌ 啟動通知發送失敗: {e}")
    
    print("\n2. 等待 3 秒...")
    time.sleep(3)
    
    print("3. 測試停止通知...")
    try:
        tracker.send_stop_notification()
        print("✅ 停止通知發送成功")
    except Exception as e:
        print(f"❌ 停止通知發送失敗: {e}")
    
    print("\n=== 測試完成 ===")

if __name__ == "__main__":
    test_notifications() 