#!/usr/bin/env python3
"""
帳戶數據對比測試腳本
比較程式內部統計與實際帳戶數據的差異
"""

import time
from datetime import datetime, timedelta
from profit_tracker import ProfitTracker
from account_analyzer import AccountAnalyzer

def test_account_comparison():
    """測試帳戶數據對比功能"""
    print("🔍 開始帳戶數據對比測試...")
    
    # 創建收益追蹤器
    tracker = ProfitTracker()
    
    # 創建帳戶分析器
    analyzer = AccountAnalyzer()
    
    print("\n1. 獲取程式內部統計...")
    program_stats = tracker.get_session_stats()
    print(f"程式統計:")
    print(f"  總交易: {program_stats['total_trades']}")
    print(f"  總盈虧: {program_stats['total_pnl']:.4f} USDT")
    print(f"  勝率: {program_stats['win_rate']:.1f}%")
    
    print("\n2. 獲取帳戶實際數據...")
    try:
        account_report = analyzer.generate_comprehensive_report(days=7)
        account_summary = account_report['summary']
        print(f"帳戶數據:")
        print(f"  總收入: {account_summary['total_income']:.4f} USDT")
        print(f"  已實現盈虧: {account_summary['realized_pnl']:.4f} USDT")
        print(f"  手續費: {account_summary['total_commission']:.4f} USDT")
        print(f"  資金費率: {account_summary['total_funding']:.4f} USDT")
        print(f"  淨利潤: {account_summary['net_profit']:.4f} USDT")
        
        print("\n3. 計算差異...")
        account_total = account_summary['net_profit']
        program_total = program_stats['total_pnl']
        difference = account_total - program_total
        
        print(f"差異分析:")
        print(f"  帳戶實際: {account_total:.4f} USDT")
        print(f"  程式統計: {program_total:.4f} USDT")
        print(f"  差異: {difference:.4f} USDT")
        
        if account_total != 0:
            accuracy = (1 - abs(difference) / abs(account_total)) * 100
            print(f"  準確度: {accuracy:.1f}%")
        
        # 分析差異原因
        print(f"\n4. 差異原因分析:")
        if abs(difference) > 0.01:
            if difference > 0:
                print(f"  ✅ 帳戶收益高於程式統計 {difference:.4f} USDT")
                print(f"     可能原因:")
                print(f"     - 手續費收入")
                print(f"     - 滑點收益")
                print(f"     - 其他收入（如返傭）")
                print(f"     - 程式遺漏的交易")
            else:
                print(f"  ⚠️ 程式統計高於帳戶收益 {abs(difference):.4f} USDT")
                print(f"     可能原因:")
                print(f"     - 手續費支出")
                print(f"     - 滑點損失")
                print(f"     - 程式計算誤差")
                print(f"     - 帳戶中的其他支出")
        else:
            print(f"  ✅ 差異很小 ({difference:.4f} USDT)，統計準確")
        
        # 詳細分析
        print(f"\n5. 詳細分析:")
        
        # 資金費率分析
        funding_income = account_report['funding_income']
        print(f"  資金費率收入: {funding_income['total_funding']:.4f} USDT")
        print(f"  正資金費率: {funding_income['positive_funding']:.4f} USDT")
        print(f"  負資金費率: {funding_income['negative_funding']:.4f} USDT")
        print(f"  資金費率次數: {funding_income['funding_count']}")
        
        # 手續費分析
        print(f"  總手續費: {account_summary['total_commission']:.4f} USDT")
        
        # 按交易對分析
        if account_report['realized_pnl']['by_symbol']:
            print(f"\n  按交易對分析:")
            for symbol, data in account_report['realized_pnl']['by_symbol'].items():
                print(f"    {symbol}: {data['pnl']:.4f} USDT ({data['trades']} 筆)")
        
        return True
        
    except Exception as e:
        print(f"❌ 獲取帳戶數據失敗: {e}")
        return False

def test_telegram_comparison():
    """測試 Telegram 對比通知"""
    print("\n6. 測試 Telegram 對比通知...")
    
    tracker = ProfitTracker()
    
    try:
        # 發送對比通知
        tracker.send_account_comparison_notification(days=7)
        print("✅ Telegram 對比通知已發送")
        return True
    except Exception as e:
        print(f"❌ Telegram 通知失敗: {e}")
        return False

def test_different_time_ranges():
    """測試不同時間範圍的對比"""
    print("\n7. 測試不同時間範圍...")
    
    tracker = ProfitTracker()
    
    time_ranges = [1, 3, 7, 14, 30]  # 1天、3天、7天、14天、30天
    
    for days in time_ranges:
        print(f"\n  分析最近 {days} 天:")
        try:
            comparison = tracker.compare_with_account_data(days=days)
            
            if 'error' in comparison:
                print(f"    ❌ 失敗: {comparison['error']}")
                continue
            
            comp = comparison['comparison']
            print(f"    帳戶: {comp['account_total']:.4f} USDT")
            print(f"    程式: {comp['program_total']:.4f} USDT")
            print(f"    差異: {comp['difference']:.4f} USDT")
            print(f"    準確度: {comp['accuracy']:.1f}%")
            
        except Exception as e:
            print(f"    ❌ 錯誤: {e}")

def main():
    """主函數"""
    print("=" * 60)
    print("帳戶數據對比測試")
    print("=" * 60)
    
    try:
        # 基本對比測試
        success = test_account_comparison()
        
        if success:
            # Telegram 通知測試
            test_telegram_comparison()
            
            # 不同時間範圍測試
            test_different_time_ranges()
        
        print("\n" + "=" * 60)
        print("✅ 對比測試完成！")
        print("=" * 60)
        
        print("\n📋 建議:")
        print("1. 如果差異較大，建議檢查程式是否遺漏了交易記錄")
        print("2. 手續費和滑點是造成差異的主要原因")
        print("3. 定期運行此測試來監控程式統計的準確性")
        print("4. 可以根據對比結果調整程式的計算邏輯")
        
    except Exception as e:
        print(f"\n❌ 測試過程中發生錯誤: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 