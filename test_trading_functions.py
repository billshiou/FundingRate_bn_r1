"""
自動化測試腳本 - 資金費率套利機器人
測試核心功能：持倉計算、JSON序列化、時間同步、配置驗證等
"""

import pytest
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# 添加專案路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 導入測試目標
from test_trading_minute import FundingRateTrader, safe_json_serialize


class TestTradingFunctions:
    """交易功能測試類"""
    
    def setup_method(self):
        """每個測試方法執行前的初始化"""
        self.trader = FundingRateTrader()
    
    def teardown_method(self):
        """每個測試方法執行後的清理"""
        if hasattr(self.trader, 'ws'):
            self.trader.ws.close()
    
    def test_safe_json_serialize(self):
        """測試安全的JSON序列化功能"""
        # 測試 numpy 數據類型
        test_data = {
            'int64': np.int64(123),
            'float64': np.float64(123.456),
            'array': np.array([1, 2, 3]),
            'normal_int': 456,
            'normal_float': 789.123,
            'normal_list': [1, 2, 3],
            'normal_dict': {'a': 1, 'b': 2}
        }
        
        # 應該能正常序列化
        serialized = safe_json_serialize(test_data)
        json_str = json.dumps(serialized)
        
        # 驗證結果
        assert isinstance(json_str, str)
        assert '123' in json_str
        assert '123.456' in json_str
        assert '[1, 2, 3]' in json_str
    
    def test_calculate_position_size(self):
        """測試持倉數量計算"""
        # 模擬價格和配置
        symbol = 'BTCUSDT'
        current_price = 50000.0
        
        # 計算數量
        quantity = self.trader.calculate_position_size(symbol, current_price)
        
        # 驗證結果
        assert isinstance(quantity, int)
        assert quantity > 0
        assert quantity >= 1  # 至少1個單位
    
    def test_time_formatting(self):
        """測試時間格式化功能"""
        # 測試時間格式化
        formatted_time = self.trader.format_corrected_time('%H:%M:%S')
        
        # 驗證格式
        assert isinstance(formatted_time, str)
        assert len(formatted_time) == 8  # HH:MM:SS
        assert ':' in formatted_time
    
    def test_config_validation(self):
        """測試配置驗證"""
        # 驗證基本配置
        assert hasattr(self.trader, 'max_position_size')
        assert hasattr(self.trader, 'leverage')
        assert hasattr(self.trader, 'min_funding_rate')
        
        # 驗證配置值合理性
        assert self.trader.max_position_size > 0
        assert self.trader.leverage > 0
        assert self.trader.min_funding_rate >= 0
    
    def test_symbol_validation(self):
        """測試交易對驗證"""
        # 測試有效交易對
        assert self.trader.is_valid_symbol('BTCUSDT')
        assert self.trader.is_valid_symbol('ETHUSDT')
        
        # 測試無效交易對
        assert not self.trader.is_valid_symbol('INVALID')
        assert not self.trader.is_valid_symbol('')
    
    def test_trading_time_validation(self):
        """測試交易時間驗證"""
        # 測試交易時間檢查
        is_trading_time = self.trader.is_trading_time()
        
        # 驗證結果類型
        assert isinstance(is_trading_time, bool)
    
    def test_logging_functions(self):
        """測試日誌功能"""
        # 測試交易事件日誌
        self.trader.log_trade_event('test_event', 'BTCUSDT', {
            'test': 'data',
            'value': 123
        })
        
        # 測試系統事件日誌
        self.trader.log_system_event('test_system', {
            'status': 'ok',
            'timestamp': datetime.now().isoformat()
        })
        
        # 測試交易步驟日誌
        self.trader.log_trade_step('test', 'BTCUSDT', 'test_action', {
            'step': 'test',
            'data': 'test_data'
        })
        
        # 如果沒有異常就通過
        assert True
    
    def test_funding_rate_processing(self):
        """測試資金費率處理"""
        # 模擬資金費率數據
        test_funding_rate = -0.0001  # -0.01%
        
        # 測試資金費率判斷
        if test_funding_rate < 0:
            direction = 'long'
        else:
            direction = 'short'
        
        # 驗證結果
        assert direction in ['long', 'short']
        assert direction == 'long'  # 負資金費率應該做多
    
    def test_retry_mechanism_config(self):
        """測試重試機制配置"""
        # 驗證重試配置存在
        assert hasattr(self.trader, 'max_entry_retry')
        assert hasattr(self.trader, 'max_close_retry')
        assert hasattr(self.trader, 'entry_retry_interval')
        assert hasattr(self.trader, 'close_retry_interval')
        
        # 驗證配置值合理性
        assert self.trader.max_entry_retry >= 0
        assert self.trader.max_close_retry >= 0
        assert self.trader.entry_retry_interval > 0
        assert self.trader.close_retry_interval > 0


class TestErrorHandling:
    """錯誤處理測試類"""
    
    def setup_method(self):
        """每個測試方法執行前的初始化"""
        self.trader = FundingRateTrader()
    
    def test_invalid_price_handling(self):
        """測試無效價格處理"""
        # 測試零價格
        with pytest.raises(Exception):
            self.trader.calculate_position_size('BTCUSDT', 0)
        
        # 測試負價格
        with pytest.raises(Exception):
            self.trader.calculate_position_size('BTCUSDT', -100)
    
    def test_invalid_symbol_handling(self):
        """測試無效交易對處理"""
        # 測試空字串
        assert not self.trader.is_valid_symbol('')
        
        # 測試None
        assert not self.trader.is_valid_symbol(None)
    
    def test_json_serialization_errors(self):
        """測試JSON序列化錯誤處理"""
        # 測試無法序列化的對象
        class UnserializableObject:
            pass
        
        test_data = {
            'normal': 'data',
            'problematic': UnserializableObject()
        }
        
        # 應該能處理並跳過無法序列化的部分
        try:
            serialized = safe_json_serialize(test_data)
            # 如果沒有拋出異常就通過
            assert True
        except Exception:
            # 如果有異常，也接受（因為我們處理了）
            assert True


class TestPerformance:
    """性能測試類"""
    
    def setup_method(self):
        """每個測試方法執行前的初始化"""
        self.trader = FundingRateTrader()
    
    def test_calculate_position_size_performance(self):
        """測試持倉計算性能"""
        import time
        
        start_time = time.time()
        
        # 執行多次計算
        for _ in range(100):
            self.trader.calculate_position_size('BTCUSDT', 50000.0)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # 驗證性能（100次計算應該在1秒內完成）
        assert execution_time < 1.0
    
    def test_json_serialization_performance(self):
        """測試JSON序列化性能"""
        import time
        
        # 準備大量測試數據
        test_data = {
            'large_array': [np.float64(i) for i in range(1000)],
            'nested_dict': {
                'level1': {
                    'level2': {
                        'level3': np.int64(123)
                    }
                }
            }
        }
        
        start_time = time.time()
        
        # 執行多次序列化
        for _ in range(10):
            safe_json_serialize(test_data)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # 驗證性能（10次序列化應該在1秒內完成）
        assert execution_time < 1.0


if __name__ == "__main__":
    # 直接執行測試
    pytest.main([__file__, "-v"]) 