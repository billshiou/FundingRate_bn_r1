#!/usr/bin/env python3
"""
Telegram 通知測試腳本
用於測試收益追蹤和 Telegram 通知功能
"""

import time
from datetime import datetime
from profit_tracker import ProfitTracker

def test_telegram_notifications():
    """測試 Telegram 通知功能"""
    print("🧪 開始測試 Telegram 通知功能...")
    
    # 創建收益追蹤器
    tracker = ProfitTracker()
    
    # 測試 1: 基本消息發送
    print("\n1. 測試基本消息發送...")
    success = tracker.send_telegram_message("🧪 測試消息：Telegram 通知功能正常！")
    if success:
        print("✅ 基本消息發送成功")
    else:
        print("❌ 基本消息發送失敗")
    
    time.sleep(2)
    
    # 測試 2: 啟動通知
    print("\n2. 測試啟動通知...")
    tracker.send_start_notification()
    print("✅ 啟動通知已發送")
    
    time.sleep(2)
    
    # 測試 3: 交易通知
    print("\n3. 測試交易通知...")
    test_trade = {
        'symbol': 'BTCUSDT',
        'direction': 'long',
        'quantity': 1000,
        'entry_price': 45123.45,
        'exit_price': 45125.67,
        'pnl': 2.22,
        'funding_rate': 0.01,
        'execution_time_ms': 49
    }
    tracker.send_trade_notification(test_trade)
    print("✅ 交易通知已發送")
    
    time.sleep(2)
    
    # 測試 4: 錯誤通知
    print("\n4. 測試錯誤通知...")
    tracker.send_error_notification("測試錯誤：API 連接超時")
    print("✅ 錯誤通知已發送")
    
    time.sleep(2)
    
    # 測試 5: 停止通知
    print("\n5. 測試停止通知...")
    tracker.send_stop_notification()
    print("✅ 停止通知已發送")
    
    print("\n🎉 所有測試完成！請檢查您的 Telegram 是否收到通知。")

def test_profit_tracking():
    """測試收益追蹤功能"""
    print("\n📊 開始測試收益追蹤功能...")
    
    # 創建收益追蹤器
    tracker = ProfitTracker()
    
    # 添加一些測試交易
    test_trades = [
        {
            'symbol': 'BTCUSDT',
            'direction': 'long',
            'quantity': 1000,
            'entry_price': 45123.45,
            'exit_price': 45125.67,
            'pnl': 2.22,
            'funding_rate': 0.01,
            'execution_time_ms': 49
        },
        {
            'symbol': 'ETHUSDT',
            'direction': 'short',
            'quantity': 500,
            'entry_price': 2456.78,
            'exit_price': 2454.32,
            'pnl': 1.23,
            'funding_rate': 0.015,
            'execution_time_ms': 52
        },
        {
            'symbol': 'ADAUSDT',
            'direction': 'long',
            'quantity': 2000,
            'entry_price': 0.456,
            'exit_price': 0.454,
            'pnl': -4.0,
            'funding_rate': 0.02,
            'execution_time_ms': 45
        }
    ]
    
    # 添加交易記錄
    for i, trade in enumerate(test_trades, 1):
        print(f"\n添加交易記錄 {i}...")
        tracker.add_trade(trade)
        time.sleep(1)
    
    # 顯示統計信息
    print("\n📈 收益統計：")
    session_stats = tracker.get_session_stats()
    daily_stats = tracker.get_daily_stats()
    
    print(f"會話統計:")
    print(f"  總交易: {session_stats['total_trades']}")
    print(f"  總盈虧: {session_stats['total_pnl']:.4f} USDT")
    print(f"  勝率: {session_stats['win_rate']:.1f}%")
    print(f"  平均盈虧: {session_stats['avg_profit']:.4f} USDT")
    print(f"  最大盈利: {session_stats['max_profit']:.4f} USDT")
    print(f"  最大虧損: {session_stats['max_loss']:.4f} USDT")
    
    print(f"\n今日統計:")
    print(f"  交易次數: {daily_stats['daily_trades']}")
    print(f"  今日盈虧: {daily_stats['daily_pnl']:.4f} USDT")
    print(f"  今日勝率: {daily_stats['daily_win_rate']:.1f}%")
    
    # 測試導出 CSV
    print("\n📁 測試導出 CSV...")
    csv_file = tracker.export_trades_to_csv()
    if csv_file:
        print(f"✅ CSV 文件已導出: {csv_file}")
    else:
        print("❌ CSV 導出失敗")

def main():
    """主函數"""
    print("=" * 50)
    print("Telegram 通知和收益追蹤測試")
    print("=" * 50)
    
    try:
        # 測試 Telegram 通知
        test_telegram_notifications()
        
        # 測試收益追蹤
        test_profit_tracking()
        
        print("\n" + "=" * 50)
        print("✅ 所有測試完成！")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n❌ 測試過程中發生錯誤: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 