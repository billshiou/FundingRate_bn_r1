#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
簡化版平倉方法 - 只保留核心功能
"""

import time

def simplified_close_position(self):
    """簡化平倉 - 直接發送市價單"""
    if not self.current_position:
        return False
        
    symbol = self.current_position['symbol']
    direction = self.current_position['direction'] 
    quantity = self.current_position['quantity']
    
    try:
        # 簡化平倉：直接發送市價單
        side = 'SELL' if direction == 'long' else 'BUY'
        start_time = time.time()
        
        order = self.client.futures_create_order(
            symbol=symbol,
            side=side,
            type='MARKET',
            quantity=quantity,
            reduceOnly=True
        )
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        print(f"[{self.format_corrected_time()}] ✅平倉成功: {symbol} | {execution_time_ms}ms | ID:{order['orderId']}")
        
        # 清理狀態
        self.current_position = None
        self.position_open_time = None
        self.is_closing = False
        
        return True
        
    except Exception as e:
        error_time_ms = int((time.time() - start_time) * 1000)
        print(f"[{self.format_corrected_time()}] ❌平倉失敗: {symbol} - {e} | {error_time_ms}ms")
        return False

def simplified_force_close_position(self):
    """簡化強制平倉"""
    if not self.current_position:
        return False
        
    symbol = self.current_position['symbol']
    
    print(f"[{self.format_corrected_time()}] 🚨 強制平倉: {symbol}")
    
    # 先嘗試正常平倉
    success = self.close_position()
    
    if success:
        print(f"[{self.format_corrected_time()}] ✅ 強制平倉成功")
        return True
    else:
        print(f"[{self.format_corrected_time()}] ❌ 強制平倉失敗")
        # 強制清理狀態
        self.current_position = None
        self.position_open_time = None
        self.is_closing = False
        return False 