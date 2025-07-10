#!/usr/bin/env python3
"""
快速API速度测试 - 诊断5秒延迟问题
"""

import time
from binance.client import Client
from config import API_KEY, API_SECRET

def test_api_speed():
    """测试API速度"""
    print("🔍 开始API速度测试...")
    
    # 初始化客户端
    client = Client(API_KEY, API_SECRET)
    
    # 1. 测试ping
    print("\n1. 测试网络延迟...")
    ping_times = []
    for i in range(5):
        start = time.time()
        try:
            client.ping()
            ping_time = int((time.time() - start) * 1000)
            ping_times.append(ping_time)
            print(f"   Ping {i+1}: {ping_time}ms")
        except Exception as e:
            print(f"   Ping {i+1}: 失败 - {e}")
    
    avg_ping = sum(ping_times) / len(ping_times) if ping_times else 0
    print(f"   平均Ping: {avg_ping:.0f}ms")
    
    # 2. 测试价格获取
    print("\n2. 测试价格获取速度...")
    price_times = []
    for i in range(3):
        start = time.time()
        try:
            ticker = client.futures_symbol_ticker(symbol='BTCUSDT')
            price_time = int((time.time() - start) * 1000)
            price_times.append(price_time)
            print(f"   价格获取 {i+1}: {price_time}ms")
        except Exception as e:
            print(f"   价格获取 {i+1}: 失败 - {e}")
    
    avg_price = sum(price_times) / len(price_times) if price_times else 0
    print(f"   平均价格获取: {avg_price:.0f}ms")
    
    # 3. 测试订单发送速度（只测试验证，不实际发送）
    print("\n3. 测试订单验证速度...")
    order_times = []
    for i in range(3):
        start = time.time()
        try:
            # 使用测试模式的订单验证
            client.futures_account()
            order_time = int((time.time() - start) * 1000)
            order_times.append(order_time)
            print(f"   账户信息获取 {i+1}: {order_time}ms")
        except Exception as e:
            print(f"   账户信息获取 {i+1}: 失败 - {e}")
    
    avg_order = sum(order_times) / len(order_times) if order_times else 0
    print(f"   平均账户信息获取: {avg_order:.0f}ms")
    
    # 4. 分析结果
    print("\n📊 结果分析:")
    print(f"   网络延迟: {avg_ping:.0f}ms")
    print(f"   价格获取: {avg_price:.0f}ms")
    print(f"   账户信息: {avg_order:.0f}ms")
    
    # 5. 诊断建议
    print("\n💡 诊断建议:")
    
    if avg_ping > 2000:
        print("   🚨 网络延迟过高！可能是:")
        print("      - 网络连接不稳定")
        print("      - VPN影响")
        print("      - 服务器地区问题")
        print("      建议: 检查网络连接或更换网络")
    elif avg_ping > 1000:
        print("   ⚠️ 网络延迟较高，可能影响交易速度")
        print("      建议: 优化网络连接")
    else:
        print("   ✅ 网络延迟正常")
    
    if avg_price > 3000:
        print("   🚨 API调用过慢！可能是:")
        print("      - API配额限制")
        print("      - 服务器负载过高")
        print("      - 本地网络问题")
        print("      建议: 检查API配额或联系Binance")
    elif avg_price > 1000:
        print("   ⚠️ API调用较慢，可能需要优化")
    else:
        print("   ✅ API调用速度正常")
    
    # 6. 质量评估
    total_time = avg_ping + avg_price
    if total_time < 200:
        quality = "优秀"
        emoji = "🟢"
    elif total_time < 500:
        quality = "良好"
        emoji = "🟡"
    elif total_time < 1000:
        quality = "一般"
        emoji = "🟠"
    else:
        quality = "差"
        emoji = "🔴"
    
    print(f"\n{emoji} 整体网络质量: {quality}")
    print(f"   预计平仓时间: {total_time:.0f}ms")
    
    if total_time > 5000:
        print("   🚨 这可能是您遇到5秒延迟的原因！")
        print("   建议:")
        print("      1. 检查网络连接")
        print("      2. 关闭VPN或更换VPN服务器")
        print("      3. 重启路由器")
        print("      4. 联系网络服务提供商")
    elif total_time > 2000:
        print("   ⚠️ 延迟偏高，可能影响高频交易")
        print("   建议使用瞬间平仓模式")
    else:
        print("   ✅ 延迟正常，适合高频交易")

if __name__ == "__main__":
    test_api_speed() 