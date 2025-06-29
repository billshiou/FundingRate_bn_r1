#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
調試篩選邏輯 - 分析為什麼只有少數交易對符合條件
"""

import requests
import time
from config import *
from binance.client import Client

def debug_filtering():
    """詳細分析篩選過程"""
    print("=== 篩選邏輯調試分析 ===")
    
    # 1. 獲取資金費率數據
    print("1. 獲取資金費率數據...")
    try:
        response = requests.get("https://fapi.binance.com/fapi/v1/premiumIndex")
        all_rates = response.json()
        print(f"   總交易對數量: {len(all_rates)}")
    except Exception as e:
        print(f"   錯誤: {e}")
        return
    
    # 2. 分析交易對篩選
    print(f"\n2. 交易對篩選...")
    print(f"   TRADING_SYMBOLS: {TRADING_SYMBOLS}")
    print(f"   EXCLUDED_SYMBOLS: {EXCLUDED_SYMBOLS}")
    
    valid_symbols = []
    excluded_count = 0
    
    for data in all_rates:
        symbol = data['symbol']
        
        # 檢查交易對篩選邏輯
        if TRADING_SYMBOLS:
            if symbol not in TRADING_SYMBOLS:
                excluded_count += 1
                continue
        else:
            if symbol in EXCLUDED_SYMBOLS:
                excluded_count += 1
                continue
        
        valid_symbols.append({
            'symbol': symbol,
            'funding_rate': float(data['lastFundingRate']) * 100,
            'next_funding_time': data['nextFundingTime']
        })
    
    print(f"   排除的交易對: {excluded_count}")
    print(f"   有效交易對: {len(valid_symbols)}")
    
    # 3. 分析資金費率篩選
    print(f"\n3. 資金費率篩選 (閾值: {MIN_FUNDING_RATE}%)...")
    
    min_threshold = MIN_FUNDING_RATE * 0.8  # 80%閾值
    funding_passed = []
    funding_failed = 0
    
    for data in valid_symbols:
        abs_funding_rate = abs(data['funding_rate'])
        if abs_funding_rate >= min_threshold:
            funding_passed.append(data)
        else:
            funding_failed += 1
    
    print(f"   第一層篩選閾值 (80%): {min_threshold:.3f}%")
    print(f"   通過資金費率篩選: {len(funding_passed)}")
    print(f"   未通過資金費率篩選: {funding_failed}")
    
    # 顯示前10個通過資金費率篩選的
    if funding_passed:
        funding_passed.sort(key=lambda x: abs(x['funding_rate']), reverse=True)
        print(f"\n   前10個通過資金費率篩選的交易對:")
        for i, data in enumerate(funding_passed[:10]):
            print(f"     {i+1}. {data['symbol']}: {data['funding_rate']:.4f}%")
    
    # 4. 分析點差和淨收益篩選
    print(f"\n4. 點差和淨收益篩選...")
    print(f"   MAX_SPREAD: {MAX_SPREAD}%")
    print(f"   MIN_FUNDING_RATE: {MIN_FUNDING_RATE}%")
    
    # 初始化Binance客戶端來獲取點差
    try:
        client = Client(API_KEY, API_SECRET)
        print("   已連接到Binance API")
    except Exception as e:
        print(f"   API連接失敗: {e}")
        return
    
    final_passed = []
    spread_failed = 0
    net_profit_failed = 0
    api_failed = 0
    
    # 檢查前20個最有潛力的交易對
    candidates = funding_passed[:20] if len(funding_passed) >= 20 else funding_passed
    print(f"   檢查前{len(candidates)}個最有潛力的交易對的點差...")
    
    for i, data in enumerate(candidates):
        symbol = data['symbol']
        funding_rate = data['funding_rate']
        abs_funding_rate = abs(funding_rate)
        
        try:
            print(f"     {i+1}/{len(candidates)} 檢查 {symbol}...", end="")
            
            # 獲取點差
            ticker = client.futures_orderbook_ticker(symbol=symbol)
            bid_price = float(ticker['bidPrice'])
            ask_price = float(ticker['askPrice'])
            spread = ((ask_price - bid_price) / ((bid_price + ask_price) / 2)) * 100
            
            # 計算淨收益
            net_profit = abs_funding_rate - spread
            
            print(f" 資金費率:{funding_rate:.4f}% 點差:{spread:.3f}% 淨收益:{net_profit:.3f}%", end="")
            
            # 檢查點差條件
            if spread > MAX_SPREAD:
                spread_failed += 1
                print(f" ❌點差過大")
                continue
                
            # 檢查淨收益條件
            if net_profit < MIN_FUNDING_RATE:
                net_profit_failed += 1
                print(f" ❌淨收益不夠")
                continue
            
            final_passed.append({
                'symbol': symbol,
                'funding_rate': funding_rate,
                'spread': spread,
                'net_profit': net_profit,
                'next_funding_time': data['next_funding_time']
            })
            print(f" ✅通過")
            
            # 延遲避免API限制
            time.sleep(0.1)
            
        except Exception as e:
            api_failed += 1
            print(f" ❌API錯誤: {e}")
    
    # 5. 總結
    print(f"\n5. 篩選結果總結:")
    print(f"   總交易對: {len(all_rates)}")
    print(f"   交易對篩選後: {len(valid_symbols)}")
    print(f"   資金費率篩選後: {len(funding_passed)}")
    print(f"   最終通過篩選: {len(final_passed)}")
    print(f"   ")
    print(f"   失敗原因統計:")
    print(f"   - 點差過大 (>{MAX_SPREAD}%): {spread_failed}")
    print(f"   - 淨收益不夠 (<{MIN_FUNDING_RATE}%): {net_profit_failed}")
    print(f"   - API錯誤: {api_failed}")
    
    # 顯示最終通過的交易對
    if final_passed:
        print(f"\n   最終符合條件的交易對:")
        for data in final_passed:
            print(f"     {data['symbol']}: 資金費率{data['funding_rate']:.4f}% 點差{data['spread']:.3f}% 淨收益{data['net_profit']:.3f}%")
    else:
        print(f"\n   ❌ 沒有交易對符合所有條件！")

if __name__ == "__main__":
    debug_filtering() 