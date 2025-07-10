#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
網絡速度測試腳本 - 診斷平倉速度問題
"""

import time
import requests
from binance.client import Client
from config import API_KEY, API_SECRET

def test_network_speed():
    """測試網絡速度和API響應時間"""
    print("=" * 60)
    print("🔍 網絡速度測試開始...")
    print("=" * 60)
    
    try:
        # 初始化客戶端
        client = Client(API_KEY, API_SECRET)
        
        # 1. 測試Ping (5次)
        print("\n📡 測試API Ping...")
        ping_times = []
        for i in range(5):
            start = time.time()
            try:
                client.ping()
                ping_time = int((time.time() - start) * 1000)
                ping_times.append(ping_time)
                print(f"   Ping {i+1}: {ping_time}ms")
            except Exception as e:
                print(f"   Ping {i+1}: 失敗 - {e}")
        
        if ping_times:
            avg_ping = sum(ping_times) / len(ping_times)
            min_ping = min(ping_times)
            max_ping = max(ping_times)
            print(f"   平均: {avg_ping:.0f}ms | 最小: {min_ping}ms | 最大: {max_ping}ms")
        
        # 2. 測試價格獲取 (5次)
        print("\n📊 測試價格獲取...")
        price_times = []
        for i in range(5):
            start = time.time()
            try:
                ticker = client.futures_symbol_ticker(symbol='BTCUSDT')
                price_time = int((time.time() - start) * 1000)
                price_times.append(price_time)
                print(f"   價格 {i+1}: {price_time}ms (價格: {ticker['price']})")
            except Exception as e:
                print(f"   價格 {i+1}: 失敗 - {e}")
        
        if price_times:
            avg_price = sum(price_times) / len(price_times)
            min_price = min(price_times)
            max_price = max(price_times)
            print(f"   平均: {avg_price:.0f}ms | 最小: {min_price}ms | 最大: {max_price}ms")
        
        # 3. 測試倉位查詢 (3次)
        print("\n👥 測試倉位查詢...")
        position_times = []
        for i in range(3):
            start = time.time()
            try:
                positions = client.futures_position_information()
                position_time = int((time.time() - start) * 1000)
                position_times.append(position_time)
                print(f"   倉位 {i+1}: {position_time}ms (共{len(positions)}個倉位)")
            except Exception as e:
                print(f"   倉位 {i+1}: 失敗 - {e}")
        
        if position_times:
            avg_position = sum(position_times) / len(position_times)
            min_position = min(position_times)
            max_position = max(position_times)
            print(f"   平均: {avg_position:.0f}ms | 最小: {min_position}ms | 最大: {max_position}ms")
        
        # 4. 測試服務器時間同步 (3次)
        print("\n⏰ 測試時間同步...")
        sync_times = []
        for i in range(3):
            start = time.time()
            try:
                server_time = client.get_server_time()
                sync_time = int((time.time() - start) * 1000)
                sync_times.append(sync_time)
                print(f"   時間同步 {i+1}: {sync_time}ms")
            except Exception as e:
                print(f"   時間同步 {i+1}: 失敗 - {e}")
        
        if sync_times:
            avg_sync = sum(sync_times) / len(sync_times)
            min_sync = min(sync_times)
            max_sync = max(sync_times)
            print(f"   平均: {avg_sync:.0f}ms | 最小: {min_sync}ms | 最大: {max_sync}ms")
        
        # 5. 綜合評估
        print("\n" + "=" * 60)
        print("📈 網絡質量評估:")
        print("=" * 60)
        
        if ping_times:
            if avg_ping < 50:
                ping_grade = "優秀"
                ping_color = "✅"
            elif avg_ping < 100:
                ping_grade = "良好"
                ping_color = "✅"
            elif avg_ping < 300:
                ping_grade = "一般"
                ping_color = "⚠️"
            else:
                ping_grade = "較差"
                ping_color = "❌"
            
            print(f"{ping_color} Ping延遲: {avg_ping:.0f}ms - {ping_grade}")
        
        if price_times:
            if avg_price < 100:
                price_grade = "優秀"
                price_color = "✅"
            elif avg_price < 200:
                price_grade = "良好"
                price_color = "✅"
            elif avg_price < 500:
                price_grade = "一般"
                price_color = "⚠️"
            else:
                price_grade = "較差"
                price_color = "❌"
            
            print(f"{price_color} 價格查詢: {avg_price:.0f}ms - {price_grade}")
        
        if position_times:
            if avg_position < 200:
                pos_grade = "優秀"
                pos_color = "✅"
            elif avg_position < 500:
                pos_grade = "良好"
                pos_color = "✅"
            elif avg_position < 1000:
                pos_grade = "一般"
                pos_color = "⚠️"
            else:
                pos_grade = "較差"
                pos_color = "❌"
            
            print(f"{pos_color} 倉位查詢: {avg_position:.0f}ms - {pos_grade}")
        
        # 6. 平倉速度預測
        print("\n🚀 平倉速度預測:")
        print("-" * 40)
        
        if ping_times and price_times:
            # 預測平倉時間 = API延遲 + 網絡延遲 + 處理時間
            predicted_close_time = avg_ping + 50  # 50ms 為處理時間
            
            if predicted_close_time < 150:
                close_grade = "超快"
                close_color = "⚡"
            elif predicted_close_time < 300:
                close_grade = "快"
                close_color = "✅"
            elif predicted_close_time < 500:
                close_grade = "中等"
                close_color = "⚠️"
            else:
                close_grade = "較慢"
                close_color = "❌"
            
            print(f"{close_color} 預期平倉時間: {predicted_close_time:.0f}ms - {close_grade}")
        
        # 7. 優化建議
        print("\n💡 優化建議:")
        print("-" * 40)
        
        if ping_times and avg_ping > 300:
            print("❌ 網絡延遲過高，建議：")
            print("   - 檢查網絡連接")
            print("   - 使用更穩定的網絡")
            print("   - 考慮更換網絡供應商")
        
        if price_times and avg_price > 500:
            print("❌ API響應慢，建議：")
            print("   - 檢查API密鑰權限")
            print("   - 減少並發請求")
            print("   - 優化請求頻率")
        
        if ping_times and avg_ping < 100:
            print("✅ 網絡狀況良好，適合高頻交易")
        
        print("\n" + "=" * 60)
        print("測試完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        print("請檢查：")
        print("1. API密鑰是否正確")
        print("2. 網絡連接是否正常")
        print("3. config.py文件是否存在")

if __name__ == "__main__":
    test_network_speed() 