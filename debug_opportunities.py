#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
調試交易機會 - 檢查為什麼沒有倒計時顯示
"""

import sys
import os
import time
from datetime import datetime

# 添加當前目錄到path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 導入配置和主要類
from config import MIN_FUNDING_RATE, MAX_SPREAD, TRADING_SYMBOLS, EXCLUDED_SYMBOLS
from test_trading_minute import FundingRateTrader

def debug_opportunities():
    """調試交易機會"""
    print("=== 交易機會調試工具 ===")
    print(f"當前時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"最小資金費率閾值: {MIN_FUNDING_RATE}%")
    print(f"最大點差閾值: {MAX_SPREAD}%")
    print(f"交易幣種限制: {TRADING_SYMBOLS if TRADING_SYMBOLS else '無限制'}")
    print(f"排除幣種: {EXCLUDED_SYMBOLS}")
    print("=" * 60)
    
    # 創建交易器實例
    trader = FundingRateTrader()
    trader.sync_server_time()
    
    print("正在獲取資金費率數據...")
    
    # 等待WebSocket連接和數據更新
    time.sleep(3)
    
    if not trader.funding_rates:
        print("❌ 沒有收到資金費率數據！")
        print("可能原因：")
        print("1. WebSocket連接失敗")
        print("2. 網絡問題")
        print("3. 幣安API問題")
        return
    
    print(f"✅ 收到 {len(trader.funding_rates)} 個交易對的資金費率數據")
    print()
    
    # 分析所有潛在機會
    print("🔍 分析所有交易對...")
    opportunities = []
    failures = {
        'symbol_filter': 0,
        'low_funding': 0, 
        'high_spread': 0,
        'spread_error': 0
    }
    
    for symbol, data in trader.funding_rates.items():
        # 1. 檢查交易對篩選
        if TRADING_SYMBOLS:
            if symbol not in TRADING_SYMBOLS:
                failures['symbol_filter'] += 1
                continue
        else:
            if symbol in EXCLUDED_SYMBOLS:
                failures['symbol_filter'] += 1
                continue
        
        funding_rate = data['funding_rate']
        abs_funding_rate = abs(funding_rate)
        
        # 2. 檢查資金費率是否有潛力
        if abs_funding_rate < MIN_FUNDING_RATE * 0.8:
            failures['low_funding'] += 1
            continue
        
        # 3. 計算淨收益和點差
        try:
            net_profit, spread = trader.calculate_net_profit(symbol, funding_rate)
            
            # 檢查是否符合所有條件
            if net_profit >= MIN_FUNDING_RATE and spread <= MAX_SPREAD:
                # 符合條件的機會
                opportunities.append({
                    'symbol': symbol,
                    'funding_rate': funding_rate,
                    'net_profit': net_profit,
                    'spread': spread,
                    'next_funding_time': data['next_funding_time'],
                    'direction': 'long' if funding_rate < 0 else 'short'
                })
            else:
                # 記錄失敗原因
                if spread > MAX_SPREAD:
                    failures['high_spread'] += 1
                else:
                    failures['low_funding'] += 1
                    
        except Exception as e:
            failures['spread_error'] += 1
            print(f"❌ {symbol} 點差計算失敗: {e}")
    
    # 顯示結果
    print("\n📊 分析結果：")
    print(f"總交易對數量: {len(trader.funding_rates)}")
    print(f"符合條件的機會: {len(opportunities)}")
    print()
    
    print("❌ 不符合條件的統計：")
    print(f"  交易對篩選淘汰: {failures['symbol_filter']}")
    print(f"  資金費率太低: {failures['low_funding']}")  
    print(f"  點差太大: {failures['high_spread']}")
    print(f"  點差計算錯誤: {failures['spread_error']}")
    print()
    
    if opportunities:
        print("✅ 符合條件的機會：")
        opportunities.sort(key=lambda x: (x['next_funding_time'], -x['net_profit']))
        
        for i, opp in enumerate(opportunities[:5]):  # 顯示前5個
            next_time = datetime.fromtimestamp(opp['next_funding_time'] / 1000)
            time_to_settlement = (opp['next_funding_time'] - trader.get_corrected_time()) / 1000
            
            print(f"  {i+1}. {opp['symbol']}")
            print(f"     資金費率: {opp['funding_rate']:.4f}%")
            print(f"     點差: {opp['spread']:.3f}%")
            print(f"     淨收益: {opp['net_profit']:.3f}%")
            print(f"     方向: {opp['direction']}")
            print(f"     結算時間: {next_time.strftime('%H:%M:%S')}")
            print(f"     距離結算: {time_to_settlement/60:.1f} 分鐘")
            print()
    else:
        print("❌ 目前沒有符合條件的交易機會")
        print()
        print("📋 建議檢查：")
        print(f"1. 是否要降低最小資金費率閾值（當前: {MIN_FUNDING_RATE}%）")
        print(f"2. 是否要提高最大點差閾值（當前: {MAX_SPREAD}%）")
        print("3. 檢查網絡連接是否穩定")
        print("4. 等待更好的市場機會")
        print()
        
        # 顯示最接近的幾個機會
        print("🔍 最接近條件的機會（僅供參考）：")
        near_misses = []
        
        for symbol, data in list(trader.funding_rates.items())[:10]:  # 檢查前10個
            if TRADING_SYMBOLS and symbol not in TRADING_SYMBOLS:
                continue
            if symbol in EXCLUDED_SYMBOLS:
                continue
                
            funding_rate = data['funding_rate']
            try:
                net_profit, spread = trader.calculate_net_profit(symbol, funding_rate)
                near_misses.append({
                    'symbol': symbol,
                    'funding_rate': funding_rate,
                    'net_profit': net_profit,
                    'spread': spread,
                    'next_funding_time': data['next_funding_time']
                })
            except:
                continue
        
        # 按淨收益排序
        near_misses.sort(key=lambda x: -x['net_profit'])
        
        for i, miss in enumerate(near_misses[:3]):  # 顯示前3個
            status = ""
            if miss['net_profit'] < MIN_FUNDING_RATE:
                status += f"❌淨收益太低({miss['net_profit']:.3f}% < {MIN_FUNDING_RATE}%)"
            if miss['spread'] > MAX_SPREAD:
                status += f"❌點差太大({miss['spread']:.3f}% > {MAX_SPREAD}%)"
            
            print(f"  {i+1}. {miss['symbol']}: 淨收益{miss['net_profit']:.3f}% 點差{miss['spread']:.3f}% {status}")

if __name__ == "__main__":
    try:
        debug_opportunities()
    except KeyboardInterrupt:
        print("\n程序被用戶中斷")
    except Exception as e:
        print(f"\n調試過程中發生錯誤: {e}")
        import traceback
        traceback.print_exc() 