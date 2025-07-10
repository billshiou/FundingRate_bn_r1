#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebSocket 穩定性測試腳本
用於測試 WebSocket 連接優化效果
"""

import time
import json
import websocket
import threading
from datetime import datetime

class WebSocketStabilityTester:
    def __init__(self):
        self.ws = None
        self.ws_thread = None
        self.reconnect_count = 0
        self.message_count = 0
        self.error_count = 0
        self.start_time = time.time()
        self.last_message_time = time.time()
        self.connection_times = []
        self.errors = []
        self.running = False
        
    def log(self, message):
        """添加時間戳的日誌"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] {message}")
    
    def on_message(self, ws, message):
        """處理消息"""
        self.message_count += 1
        self.last_message_time = time.time()
        
        # 每100條消息記錄一次
        if self.message_count % 100 == 0:
            self.log(f"📊 已接收 {self.message_count} 條消息")
    
    def on_error(self, ws, error):
        """處理錯誤"""
        self.error_count += 1
        error_str = str(error)
        self.errors.append({
            'time': time.time(),
            'error': error_str,
            'type': self._classify_error(error_str)
        })
        self.log(f"❌ 錯誤 #{self.error_count}: {error}")
    
    def _classify_error(self, error_str):
        """分類錯誤類型"""
        if "ping/pong timed out" in error_str:
            return "ping_timeout"
        elif "Connection" in error_str:
            return "connection_error"
        elif "Network" in error_str:
            return "network_error"
        else:
            return "unknown_error"
    
    def on_close(self, ws, close_status_code, close_msg):
        """處理關閉"""
        self.log(f"🔌 連接關閉 - 狀態碼: {close_status_code}, 訊息: {close_msg}")
        
        if self.running:
            self.reconnect_count += 1
            self.log(f"🔄 準備重連 (第{self.reconnect_count}次)")
            time.sleep(5)  # 5秒後重連
            self.connect()
    
    def on_open(self, ws):
        """連接開啟"""
        connection_time = time.time() - self.start_time
        self.connection_times.append(connection_time)
        self.log(f"✅ 連接開啟 - 用時: {connection_time:.2f}秒")
        
        # 發送訂閱請求
        self.log("📡 發送訂閱請求...")
    
    def connect(self):
        """建立 WebSocket 連接"""
        try:
            self.log("🔄 正在建立 WebSocket 連接...")
            
            # 使用幣安期貨的標記價格流
            stream_url = "wss://fstream.binance.com/ws/!markPrice@arr"
            
            self.ws = websocket.WebSocketApp(
                stream_url,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
                on_open=self.on_open
            )
            
            # 啟動 WebSocket 連接 - 使用優化後的參數
            self.ws_thread = threading.Thread(target=lambda: self.ws.run_forever(
                ping_interval=30,      # 30秒心跳
                ping_timeout=20,       # 20秒超時
                reconnect=5            # 5秒重連間隔
            ))
            self.ws_thread.daemon = True
            self.ws_thread.start()
            
        except Exception as e:
            self.log(f"❌ 連接失敗: {e}")
    
    def start_test(self, duration_minutes=10):
        """開始測試"""
        self.running = True
        self.start_time = time.time()
        
        self.log("=" * 60)
        self.log(f"🧪 WebSocket 穩定性測試開始 - 持續 {duration_minutes} 分鐘")
        self.log("=" * 60)
        
        # 建立連接
        self.connect()
        
        # 等待測試時間
        test_duration = duration_minutes * 60
        end_time = time.time() + test_duration
        
        try:
            while time.time() < end_time and self.running:
                time.sleep(1)
                
                # 檢查是否有消息超時
                if time.time() - self.last_message_time > 60:
                    self.log("⚠️ 60秒內未收到消息，可能連接有問題")
                    self.last_message_time = time.time()
                
        except KeyboardInterrupt:
            self.log("🛑 測試被用戶中斷")
        
        self.stop_test()
    
    def stop_test(self):
        """停止測試"""
        self.running = False
        
        if self.ws:
            self.ws.close()
        
        # 生成測試報告
        self.generate_report()
    
    def generate_report(self):
        """生成測試報告"""
        test_duration = time.time() - self.start_time
        
        self.log("\n" + "=" * 60)
        self.log("📊 WebSocket 穩定性測試報告")
        self.log("=" * 60)
        
        self.log(f"⏱️ 測試時長: {test_duration:.1f} 秒 ({test_duration/60:.1f} 分鐘)")
        self.log(f"📨 接收消息: {self.message_count} 條")
        self.log(f"🔄 重連次數: {self.reconnect_count} 次")
        self.log(f"❌ 錯誤次數: {self.error_count} 次")
        
        if self.message_count > 0:
            message_rate = self.message_count / test_duration
            self.log(f"📈 消息速率: {message_rate:.1f} 條/秒")
        
        if self.connection_times:
            avg_connection_time = sum(self.connection_times) / len(self.connection_times)
            self.log(f"⚡ 平均連接時間: {avg_connection_time:.2f} 秒")
        
        # 錯誤分析
        if self.errors:
            self.log("\n🔍 錯誤分析:")
            error_types = {}
            for error in self.errors:
                error_type = error['type']
                error_types[error_type] = error_types.get(error_type, 0) + 1
            
            for error_type, count in error_types.items():
                self.log(f"   {error_type}: {count} 次")
        
        # 穩定性評估
        if self.reconnect_count == 0:
            stability_grade = "優秀"
            stability_emoji = "🟢"
        elif self.reconnect_count <= 2:
            stability_grade = "良好"
            stability_emoji = "🟡"
        elif self.reconnect_count <= 5:
            stability_grade = "中等"
            stability_emoji = "🟠"
        else:
            stability_grade = "需要改進"
            stability_emoji = "🔴"
        
        self.log(f"\n{stability_emoji} 穩定性評級: {stability_grade}")
        
        # 建議
        if self.reconnect_count > 3:
            self.log("\n💡 建議:")
            self.log("   - 檢查網絡連接穩定性")
            self.log("   - 考慮增加重連間隔")
            self.log("   - 檢查防火牆設置")
        
        self.log("\n" + "=" * 60)

if __name__ == "__main__":
    tester = WebSocketStabilityTester()
    
    # 開始5分鐘測試
    tester.start_test(duration_minutes=5) 