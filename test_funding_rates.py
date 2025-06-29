#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試資金費率API
"""

import requests
import pandas as pd
from datetime import datetime

def test_funding_rates():
    """測試資金費率API"""
    print("=== 測試資金費率API ===")
    
    try:
        # 獲取資金費率數據
        response = requests.get("https://fapi.binance.com/fapi/v1/premiumIndex")
        all_rates = response.json()
        
        print(f"總交易對數量: {len(all_rates)}")
        
        # 轉換為DataFrame
        rates = []
        for data in all_rates:
            rates.append({
                'symbol': data['symbol'],
                'funding_rate': float(data['lastFundingRate']) * 100,
                'next_funding_time': data['nextFundingTime']
            })
        
        df = pd.DataFrame(rates)
        df['abs_funding_rate'] = df['funding_rate'].abs()
        
        print(f"轉換為DataFrame後數量: {len(df)}")
        
        # 顯示前10個最高資金費率
        top_rates = df.nlargest(10, 'abs_funding_rate')
        print(f"\n前10個最高資金費率:")
        for _, row in top_rates.iterrows():
            next_time = datetime.fromtimestamp(row['next_funding_time'] / 1000).strftime('%H:%M:%S')
            print(f"  {row['symbol']}: {row['funding_rate']:.4f}% (結算:{next_time})")
        
        # 測試不同的門檻
        thresholds = [0.01, 0.05, 0.1, 0.2, 0.5, 1.0]
        print(f"\n不同門檻的篩選結果:")
        for threshold in thresholds:
            filtered_df = df[df['abs_funding_rate'] >= threshold]
            print(f"  門檻 {threshold}%: {len(filtered_df)} 個交易對")
        
        # 檢查是否有USDT結尾的交易對
        usdt_pairs = df[df['symbol'].str.endswith('USDT')]
        print(f"\nUSDT交易對數量: {len(usdt_pairs)}")
        
        # 顯示前5個USDT交易對的資金費率
        top_usdt = usdt_pairs.nlargest(5, 'abs_funding_rate')
        print(f"\n前5個最高資金費率的USDT交易對:")
        for _, row in top_usdt.iterrows():
            next_time = datetime.fromtimestamp(row['next_funding_time'] / 1000).strftime('%H:%M:%S')
            print(f"  {row['symbol']}: {row['funding_rate']:.4f}% (結算:{next_time})")
        
    except Exception as e:
        print(f"錯誤: {e}")

if __name__ == "__main__":
    test_funding_rates() 