#!/usr/bin/env python3
"""
Excel交易總結管理工具
提供手動導出、初始化、查看樣本等功能
"""

import os
import sys
from datetime import datetime, timedelta
from excel_exporter import ExcelTradeExporter

def show_menu():
    """顯示主選單"""
    print("\n" + "="*60)
    print("📊 Excel交易總結管理工具")
    print("="*60)
    print("1. 📝 導出今日交易總結")
    print("2. 📅 導出指定日期總結")
    print("3. 📚 導出歷史數據（初始化Excel）")
    print("4. 👀 查看Excel樣本結構")
    print("5. 📋 查看現有Excel文件")
    print("6. 🧪 生成測試數據")
    print("0. 🚪 退出")
    print("="*60)

def export_today():
    """導出今日交易總結"""
    try:
        from profit_tracker import ProfitTracker
        
        print("\n🔍 正在獲取今日交易數據...")
        tracker = ProfitTracker()
        success = tracker.export_daily_excel_summary()
        
        if success:
            print("✅ 今日交易總結已導出到Excel！")
            print("📁 文件位置: 交易總結.xlsx")
        else:
            print("❌ 導出失敗，請檢查是否有今日交易數據")
            
    except Exception as e:
        print(f"❌ 導出過程中出現錯誤: {e}")

def export_specific_date():
    """導出指定日期的交易總結"""
    try:
        print("\n📅 請輸入要導出的日期")
        date_str = input("日期格式 (YYYY-MM-DD，例如 2024-12-25): ").strip()
        
        # 驗證日期格式
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            print("❌ 日期格式錯誤，請使用 YYYY-MM-DD 格式")
            return
        
        from profit_tracker import ProfitTracker
        
        print(f"🔍 正在獲取 {date_str} 的交易數據...")
        tracker = ProfitTracker()
        success = tracker.export_daily_excel_summary(date_str)
        
        if success:
            print(f"✅ {date_str} 交易總結已導出到Excel！")
        else:
            print(f"❌ 導出失敗，請檢查 {date_str} 是否有交易數據")
            
    except Exception as e:
        print(f"❌ 導出過程中出現錯誤: {e}")

def export_historical_data():
    """導出歷史數據"""
    try:
        print("\n📚 歷史數據導出")
        days_input = input("請輸入導出天數 (預設30天): ").strip()
        
        try:
            days = int(days_input) if days_input else 30
        except ValueError:
            print("❌ 天數格式錯誤，使用預設30天")
            days = 30
        
        if days > 90:
            confirm = input(f"⚠️  您要導出 {days} 天的數據，這可能需要較長時間，是否繼續？(y/N): ")
            if confirm.lower() != 'y':
                print("❌ 操作已取消")
                return
        
        from profit_tracker import ProfitTracker
        
        print(f"🔍 正在導出最近 {days} 天的歷史數據...")
        print("⏳ 這可能需要一些時間，請耐心等待...")
        
        tracker = ProfitTracker()
        success = tracker.export_historical_excel_data(days)
        
        if success:
            print(f"✅ 最近 {days} 天的歷史數據已導出到Excel！")
            print("📁 文件位置: 交易總結.xlsx")
        else:
            print("❌ 歷史數據導出失敗")
            
    except Exception as e:
        print(f"❌ 導出過程中出現錯誤: {e}")

def show_excel_structure():
    """顯示Excel文件結構樣本"""
    print("\n" + "="*60)
    print("📋 Excel交易總結文件結構")
    print("="*60)
    
    columns = [
        ("A", "日期", "交易日期 (YYYY-MM-DD)"),
        ("B", "交易次數", "當日總交易筆數"),
        ("C", "勝率(%)", "盈利交易佔比"),
        ("D", "程式盈虧", "程式計算的理論盈虧"),
        ("E", "交易盈虧", "帳戶實際交易盈亮"),
        ("F", "資金費收入", "當日資金費率收入"),
        ("G", "正資金費", "收入部分的資金費"),
        ("H", "負資金費", "支出部分的資金費"),
        ("I", "資金費次數", "當日資金費結算次數"),
        ("J", "手續費支出", "交易手續費成本"),
        ("K", "帳戶淨利", "最終實際淨利潤"),
        ("L", "理論淨利", "程式盈虧+資金費-手續費"),
        ("M", "實際vs理論差異", "帳戶與理論的差異"),
        ("N", "資金費率收益率", "資金費/交易盈虧比例"),
        ("O", "手續費率", "手續費/交易盈虧比例")
    ]
    
    for col, name, desc in columns:
        print(f"{col:2} | {name:12} | {desc}")
    
    print("\n💡 特色功能:")
    print("• 自動按日期排序（最新在上方）")
    print("• 盈利數據顯示綠色背景，虧損顯示紅色背景")
    print("• 自動計算總計行")
    print("• 支持每日自動更新")
    print("• 同一天的數據會自動覆蓋更新")

def view_existing_excel():
    """查看現有Excel文件信息"""
    filename = "交易總結.xlsx"
    
    if not os.path.exists(filename):
        print(f"\n❌ Excel文件不存在: {filename}")
        print("💡 請先使用選項1-3導出數據")
        return
    
    try:
        import pandas as pd
        df = pd.read_excel(filename, sheet_name="每日交易總結")
        
        print(f"\n📁 Excel文件信息: {filename}")
        print(f"📊 總記錄數: {len(df)} 天")
        print(f"📅 日期範圍: {df['日期'].min()} ~ {df['日期'].max()}")
        print(f"💰 總交易次數: {df['交易次數'].sum()}")
        print(f"💰 總淨利潤: {df['帳戶淨利'].sum():.4f} USDT")
        
        print(f"\n📋 最近5天數據預覽:")
        print(df[['日期', '交易次數', '勝率(%)', '帳戶淨利']].head().to_string(index=False))
        
    except Exception as e:
        print(f"❌ 讀取Excel文件失敗: {e}")

def generate_test_data():
    """生成測試數據"""
    print("\n🧪 生成測試數據")
    confirm = input("這將創建測試用的Excel文件，是否繼續？(y/N): ")
    
    if confirm.lower() != 'y':
        print("❌ 操作已取消")
        return
    
    try:
        exporter = ExcelTradeExporter("測試交易總結.xlsx")
        
        # 生成7天的測試數據
        for i in range(7):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            
            # 隨機生成測試數據
            import random
            test_stats = {
                'daily_trades': random.randint(10, 25),
                'daily_win_rate': round(random.uniform(60, 85), 2),
                'daily_pnl': round(random.uniform(-0.05, 0.15), 4),
                'realized_pnl': round(random.uniform(-0.02, 0.08), 4),
                'total_commission': round(random.uniform(0.02, 0.06), 4),
                'total_funding': round(random.uniform(0.08, 0.20), 4),
                'positive_funding': round(random.uniform(0.10, 0.25), 4),
                'negative_funding': round(random.uniform(-0.05, -0.01), 4),
                'funding_count': random.randint(5, 12),
                'net_profit': 0  # 會自動計算
            }
            
            # 計算淨利潤
            test_stats['net_profit'] = (test_stats['realized_pnl'] + 
                                      test_stats['total_funding'] - 
                                      test_stats['total_commission'])
            
            exporter.append_daily_data(date, test_stats)
        
        print("✅ 測試數據已生成完成！")
        print("📁 文件位置: 測試交易總結.xlsx")
        
    except Exception as e:
        print(f"❌ 生成測試數據失敗: {e}")

def main():
    """主函數"""
    print("🚀 Excel交易總結管理工具啟動")
    
    while True:
        try:
            show_menu()
            choice = input("\n請選擇功能 (0-6): ").strip()
            
            if choice == '0':
                print("👋 再見！")
                break
            elif choice == '1':
                export_today()
            elif choice == '2':
                export_specific_date()
            elif choice == '3':
                export_historical_data()
            elif choice == '4':
                show_excel_structure()
            elif choice == '5':
                view_existing_excel()
            elif choice == '6':
                generate_test_data()
            else:
                print("❌ 無效選擇，請輸入 0-6")
                
            if choice != '0':
                input("\n按 Enter 繼續...")
                
        except KeyboardInterrupt:
            print("\n👋 程式已中斷，再見！")
            break
        except Exception as e:
            print(f"❌ 程式執行錯誤: {e}")
            input("按 Enter 繼續...")

if __name__ == '__main__':
    main() 