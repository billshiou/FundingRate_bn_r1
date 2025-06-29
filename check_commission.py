#!/usr/bin/env python3
"""
檢查幣安 API 返回的手續費數據格式
"""

from account_analyzer import AccountAnalyzer

def check_commission_format():
    """檢查手續費數據格式"""
    print("🔍 檢查幣安 API 手續費數據格式...")
    
    try:
        analyzer = AccountAnalyzer()
        
        # 獲取最近的交易記錄
        trades = analyzer.get_trade_history()
        
        if not trades:
            print("❌ 沒有找到交易記錄")
            return
        
        print(f"找到 {len(trades)} 筆交易記錄")
        print("\n手續費數據範例:")
        
        for i, trade in enumerate(trades[:3]):
            commission = trade['commission']
            realized_pnl = trade['realizedPnl']
            symbol = trade['symbol']
            side = trade['side']
            
            print(f"交易 {i+1}: {symbol} {side}")
            print(f"  手續費: {commission} (類型: {type(commission)})")
            print(f"  已實現盈虧: {realized_pnl}")
            print()
        
        # 檢查手續費的正負號
        print("📊 手續費正負號分析:")
        positive_commissions = [t for t in trades if float(t['commission']) > 0]
        negative_commissions = [t for t in trades if float(t['commission']) < 0]
        zero_commissions = [t for t in trades if float(t['commission']) == 0]
        
        print(f"正數手續費: {len(positive_commissions)} 筆")
        print(f"負數手續費: {len(negative_commissions)} 筆")
        print(f"零手續費: {len(zero_commissions)} 筆")
        
        if negative_commissions:
            print(f"\n負數手續費範例: {negative_commissions[0]['commission']}")
        if positive_commissions:
            print(f"正數手續費範例: {positive_commissions[0]['commission']}")
            
    except Exception as e:
        print(f"❌ 檢查失敗: {e}")

if __name__ == "__main__":
    check_commission_format() 