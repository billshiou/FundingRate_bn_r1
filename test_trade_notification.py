#!/usr/bin/env python3
"""
測試完整的交易通知格式
展示每筆交易結束後會發送的詳細資訊
"""

import time
from datetime import datetime
from profit_tracker import ProfitTracker

def test_complete_trade_notification():
    """測試完整的交易通知"""
    print("🔍 測試完整的交易通知格式...")
    
    # 創建模擬的交易數據
    trade_data = {
        'symbol': 'BTCUSDT',
        'direction': 'long',
        'quantity': 1000,
        'entry_price': 45000.0,
        'exit_price': 45100.0,
        'pnl': 12.34,
        'funding_rate': 0.0123,
        'execution_time_ms': 150,
        'position_duration_seconds': 120,
        'entry_timestamp': int((datetime.now().timestamp() - 120) * 1000),
        'exit_timestamp': int(datetime.now().timestamp() * 1000),
        'order_id': '123456789',
        'retry_count': 0
    }
    
    # 創建收益追蹤器
    tracker = ProfitTracker()
    
    print("\n1. 即時交易通知（程式內部統計）:")
    print("-" * 50)
    message = tracker.format_trade_message(trade_data)
    print(message)
    
    print("\n2. 延遲帳戶分析通知（真實帳戶數據）:")
    print("-" * 50)
    
    # 模擬延遲的帳戶分析通知
    from config import LEVERAGE
    
    # 計算倉位和保證金資訊
    position_value = trade_data['quantity'] * trade_data['entry_price']
    margin_used = position_value / LEVERAGE
    
    # 模擬帳戶分析結果
    account_detail = {
        'symbol': 'BTCUSDT',
        'direction': 'long',
        'realized_pnl': 11.85,
        'commission': -0.45,
        'funding_fee': 0.12,
        'net_profit': 11.52,
        'entry_time': trade_data['entry_timestamp'],
        'exit_time': trade_data['exit_timestamp']
    }
    
    account_msg = (
        f"📊 <b>單筆真實收益分析</b>\n\n"
        f"<b>交易對:</b> {account_detail['symbol']}\n"
        f"<b>方向:</b> {account_detail['direction'].upper()}\n"
        f"<b>數量:</b> {trade_data['quantity']:,}\n"
        f"<b>倉位價值:</b> {position_value:.2f} USDT\n"
        f"<b>保證金:</b> {margin_used:.2f} USDT\n"
        f"<b>槓桿:</b> {LEVERAGE}x\n\n"
        f"<b>開倉時間:</b> {datetime.fromtimestamp(account_detail['entry_time']/1000).strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"<b>平倉時間:</b> {datetime.fromtimestamp(account_detail['exit_time']/1000).strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"<b>持倉時間:</b> {trade_data['position_duration_seconds']}秒\n\n"
        f"<b>程式盈虧:</b> {trade_data['pnl']:.4f} USDT\n"
        f"<b>帳戶實際盈虧:</b> {account_detail['realized_pnl']:.4f} USDT\n"
        f"<b>手續費:</b> {account_detail['commission']:.4f} USDT\n"
        f"<b>資金費:</b> {account_detail['funding_fee']:.4f} USDT\n"
        f"<b>帳戶淨利:</b> {account_detail['net_profit']:.4f} USDT\n\n"
        f"<b>差異:</b> {account_detail['net_profit'] - trade_data['pnl']:.4f} USDT"
    )
    
    print(account_msg)
    
    print("\n3. 通知流程說明:")
    print("-" * 50)
    print("✅ 每筆交易結束後會發送兩次通知:")
    print("   1. 即時通知：程式內部統計的交易結果")
    print("   2. 延遲通知：1分鐘後的真實帳戶數據分析")
    print()
    print("📋 包含的詳細資訊:")
    print("   • 交易對、方向、數量")
    print("   • 開倉價、平倉價")
    print("   • 開倉時間、平倉時間、持倉時間")
    print("   • 倉位價值、保證金、槓桿")
    print("   • 程式盈虧、帳戶實際盈虧")
    print("   • 手續費、資金費")
    print("   • 帳戶淨利、差異分析")
    print("   • 會話統計（總交易、總盈虧、勝率等）")

def main():
    """主函數"""
    print("=" * 60)
    print("完整交易通知格式測試")
    print("=" * 60)
    
    try:
        test_complete_trade_notification()
        
        print("\n" + "=" * 60)
        print("✅ 測試完成！")
        print("=" * 60)
        
        print("\n💡 實際運行時:")
        print("• 程式會自動發送這些通知到你的 Telegram")
        print("• 確保 config.py 中已正確設定 Telegram 參數")
        print("• 可以通過 NOTIFY_ON_TRADE 開關控制通知")
        
    except Exception as e:
        print(f"\n❌ 測試過程中發生錯誤: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 