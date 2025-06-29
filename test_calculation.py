#!/usr/bin/env python3
"""
測試淨利潤計算公式
驗證：該次交易盈虧 - 手續費用 + 資金費 = 該次利潤
"""

def test_profit_calculation():
    """測試利潤計算公式"""
    print("🔍 測試淨利潤計算公式...")
    print("公式: 該次交易盈虧 - 手續費用 + 資金費 = 該次利潤")
    print()
    
    # 測試案例1：你提供的例子
    print("📊 測試案例1（你提供的例子）:")
    realized_pnl = 11.8500  # 帳戶實際盈虧
    commission = -0.4500    # 手續費（負數表示支出）
    funding_fee = 0.1200    # 資金費
    
    # 計算淨利潤
    net_profit = realized_pnl + funding_fee - commission
    
    print(f"帳戶實際盈虧: {realized_pnl:.4f} USDT")
    print(f"手續費: {commission:.4f} USDT")
    print(f"資金費: {funding_fee:.4f} USDT")
    print(f"計算結果: {realized_pnl:.4f} + {funding_fee:.4f} - ({commission:.4f}) = {net_profit:.4f} USDT")
    print(f"顯示的帳戶淨利: 11.5200 USDT")
    print(f"差異: {net_profit - 11.5200:.4f} USDT")
    print()
    
    # 測試案例2：其他情況
    print("📊 測試案例2（盈利情況）:")
    realized_pnl2 = 5.00
    commission2 = -0.30
    funding_fee2 = 0.15
    
    net_profit2 = realized_pnl2 + funding_fee2 - commission2
    
    print(f"帳戶實際盈虧: {realized_pnl2:.4f} USDT")
    print(f"手續費: {commission2:.4f} USDT")
    print(f"資金費: {funding_fee2:.4f} USDT")
    print(f"計算結果: {realized_pnl2:.4f} + {funding_fee2:.4f} - ({commission2:.4f}) = {net_profit2:.4f} USDT")
    print()
    
    # 測試案例3：虧損情況
    print("📊 測試案例3（虧損情況）:")
    realized_pnl3 = -3.00
    commission3 = -0.25
    funding_fee3 = 0.10
    
    net_profit3 = realized_pnl3 + funding_fee3 - commission3
    
    print(f"帳戶實際盈虧: {realized_pnl3:.4f} USDT")
    print(f"手續費: {commission3:.4f} USDT")
    print(f"資金費: {funding_fee3:.4f} USDT")
    print(f"計算結果: {realized_pnl3:.4f} + {funding_fee3:.4f} - ({commission3:.4f}) = {net_profit3:.4f} USDT")
    print()
    
    # 總結
    print("📋 計算公式總結:")
    print("✅ 正確公式: 已實現盈虧 + 資金費 - 手續費 = 淨利潤")
    print("❌ 錯誤公式: 總收入 - 手續費 = 淨利潤")
    print()
    print("💡 說明:")
    print("• 已實現盈虧：交易本身的盈虧")
    print("• 手續費：交易手續費（通常是負數，表示支出）")
    print("• 資金費：資金費率收入（可能是正數或負數）")
    print("• 淨利潤：最終的實際收益")

def test_account_analyzer_calculation():
    """測試帳戶分析器的計算"""
    print("\n" + "="*50)
    print("測試帳戶分析器的計算邏輯")
    print("="*50)
    
    try:
        from account_analyzer import AccountAnalyzer
        
        analyzer = AccountAnalyzer()
        
        # 測試按時間範圍分析
        print("測試按時間範圍分析...")
        comparison = analyzer.compare_program_vs_account_by_period()
        
        if 'error' not in comparison:
            print("✅ 計算邏輯測試成功")
            print(f"程式總盈虧: {comparison['program_total_pnl']:.4f} USDT")
            print(f"帳戶淨利: {comparison['account_net_profit']:.4f} USDT")
            print(f"帳戶已實現盈虧: {comparison['account_total_pnl']:.4f} USDT")
            print(f"帳戶手續費: {comparison['account_total_commission']:.4f} USDT")
            print(f"帳戶資金費: {comparison['account_total_funding']:.4f} USDT")
            
            # 驗證計算
            calculated_net = comparison['account_total_pnl'] + comparison['account_total_funding'] - comparison['account_total_commission']
            print(f"計算的淨利: {calculated_net:.4f} USDT")
            print(f"顯示的淨利: {comparison['account_net_profit']:.4f} USDT")
            print(f"計算是否正確: {'✅' if abs(calculated_net - comparison['account_net_profit']) < 0.0001 else '❌'}")
        else:
            print(f"❌ 測試失敗: {comparison['error']}")
            
    except Exception as e:
        print(f"❌ 測試過程中發生錯誤: {e}")

def main():
    """主函數"""
    print("=" * 60)
    print("淨利潤計算公式驗證")
    print("=" * 60)
    
    test_profit_calculation()
    test_account_analyzer_calculation()
    
    print("\n" + "=" * 60)
    print("✅ 測試完成！")
    print("=" * 60)

if __name__ == "__main__":
    main() 