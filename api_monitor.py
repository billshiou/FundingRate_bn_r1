"""
API 限流與異常頻率監控腳本
監控 Binance API 的限流情況和異常頻率，提供警告和統計
"""

import time
import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict, deque
import threading
from typing import Dict, List, Optional
import requests

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/api_monitor.log'),
        logging.StreamHandler()
    ]
)

class APIMonitor:
    """API 監控器"""
    
    def __init__(self):
        self.rate_limit_errors = deque(maxlen=1000)  # 最近1000次錯誤
        self.api_errors = deque(maxlen=1000)  # 最近1000次API錯誤
        self.request_count = defaultdict(int)  # 請求計數
        self.error_count = defaultdict(int)  # 錯誤計數
        self.last_reset_time = time.time()
        
        # 監控配置
        self.rate_limit_threshold = 5  # 5分鐘內超過5次限流錯誤就警告
        self.error_threshold = 10  # 5分鐘內超過10次錯誤就警告
        self.monitoring_interval = 60  # 每60秒檢查一次
        
        # 啟動監控線程
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        logging.info("API 監控器已啟動")
    
    def record_rate_limit_error(self, endpoint: str, error_msg: str):
        """記錄限流錯誤"""
        error_info = {
            'timestamp': time.time(),
            'endpoint': endpoint,
            'error': error_msg,
            'datetime': datetime.now().isoformat()
        }
        self.rate_limit_errors.append(error_info)
        self.error_count['rate_limit'] += 1
        
        logging.warning(f"API 限流錯誤: {endpoint} - {error_msg}")
    
    def record_api_error(self, endpoint: str, error_msg: str, error_code: Optional[int] = None):
        """記錄API錯誤"""
        error_info = {
            'timestamp': time.time(),
            'endpoint': endpoint,
            'error': error_msg,
            'error_code': error_code,
            'datetime': datetime.now().isoformat()
        }
        self.api_errors.append(error_info)
        self.error_count['api_error'] += 1
        
        logging.error(f"API 錯誤: {endpoint} - {error_msg} (代碼: {error_code})")
    
    def record_request(self, endpoint: str):
        """記錄API請求"""
        self.request_count[endpoint] += 1
    
    def get_rate_limit_stats(self, minutes: int = 5) -> Dict:
        """獲取限流統計"""
        cutoff_time = time.time() - (minutes * 60)
        
        recent_errors = [
            error for error in self.rate_limit_errors 
            if error['timestamp'] > cutoff_time
        ]
        
        return {
            'total_errors': len(recent_errors),
            'endpoints': defaultdict(int),
            'time_period': f"{minutes}分鐘",
            'threshold': self.rate_limit_threshold
        }
    
    def get_api_error_stats(self, minutes: int = 5) -> Dict:
        """獲取API錯誤統計"""
        cutoff_time = time.time() - (minutes * 60)
        
        recent_errors = [
            error for error in self.api_errors 
            if error['timestamp'] > cutoff_time
        ]
        
        # 按錯誤類型分類
        error_types = defaultdict(int)
        endpoints = defaultdict(int)
        
        for error in recent_errors:
            error_types[error['error']] += 1
            endpoints[error['endpoint']] += 1
        
        return {
            'total_errors': len(recent_errors),
            'error_types': dict(error_types),
            'endpoints': dict(endpoints),
            'time_period': f"{minutes}分鐘",
            'threshold': self.error_threshold
        }
    
    def get_request_stats(self) -> Dict:
        """獲取請求統計"""
        return {
            'total_requests': sum(self.request_count.values()),
            'endpoints': dict(self.request_count),
            'since': datetime.fromtimestamp(self.last_reset_time).isoformat()
        }
    
    def check_rate_limit_warning(self) -> bool:
        """檢查是否需要限流警告"""
        stats = self.get_rate_limit_stats()
        return stats['total_errors'] >= self.rate_limit_threshold
    
    def check_error_warning(self) -> bool:
        """檢查是否需要錯誤警告"""
        stats = self.get_api_error_stats()
        return stats['total_errors'] >= self.error_threshold
    
    def _monitor_loop(self):
        """監控循環"""
        while self.monitoring:
            try:
                # 檢查限流警告
                if self.check_rate_limit_warning():
                    self._send_rate_limit_warning()
                
                # 檢查錯誤警告
                if self.check_error_warning():
                    self._send_error_warning()
                
                # 每小時重置計數器
                if time.time() - self.last_reset_time > 3600:
                    self._reset_counters()
                
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                logging.error(f"監控循環錯誤: {e}")
                time.sleep(self.monitoring_interval)
    
    def _send_rate_limit_warning(self):
        """發送限流警告"""
        stats = self.get_rate_limit_stats()
        warning_msg = f"""
🚨 API 限流警告 🚨
時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
最近{stats['time_period']}內限流錯誤: {stats['total_errors']}次
閾值: {stats['threshold']}次
建議: 檢查API使用頻率，考慮增加請求間隔
        """
        logging.warning(warning_msg)
        print(warning_msg)
    
    def _send_error_warning(self):
        """發送錯誤警告"""
        stats = self.get_api_error_stats()
        warning_msg = f"""
🚨 API 錯誤警告 🚨
時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
最近{stats['time_period']}內API錯誤: {stats['total_errors']}次
閾值: {stats['threshold']}次
錯誤類型: {json.dumps(stats['error_types'], indent=2)}
受影響端點: {json.dumps(stats['endpoints'], indent=2)}
建議: 檢查網路連接和API配置
        """
        logging.error(warning_msg)
        print(warning_msg)
    
    def _reset_counters(self):
        """重置計數器"""
        self.request_count.clear()
        self.error_count.clear()
        self.last_reset_time = time.time()
        logging.info("API 監控計數器已重置")
    
    def get_comprehensive_report(self) -> Dict:
        """獲取綜合報告"""
        return {
            'timestamp': datetime.now().isoformat(),
            'rate_limit_stats': self.get_rate_limit_stats(),
            'api_error_stats': self.get_api_error_stats(),
            'request_stats': self.get_request_stats(),
            'warnings': {
                'rate_limit_warning': self.check_rate_limit_warning(),
                'error_warning': self.check_error_warning()
            }
        }
    
    def stop(self):
        """停止監控"""
        self.monitoring = False
        logging.info("API 監控器已停止")


# 全局監控器實例
api_monitor = APIMonitor()


def monitor_api_call(func):
    """API調用監控裝飾器"""
    def wrapper(*args, **kwargs):
        try:
            # 記錄請求
            endpoint = func.__name__
            api_monitor.record_request(endpoint)
            
            # 執行函數
            result = func(*args, **kwargs)
            return result
            
        except Exception as e:
            error_msg = str(e)
            endpoint = func.__name__
            
            # 檢查是否為限流錯誤
            if any(keyword in error_msg.lower() for keyword in [
                'rate limit', 'too many requests', '429', 'quota exceeded'
            ]):
                api_monitor.record_rate_limit_error(endpoint, error_msg)
            else:
                api_monitor.record_api_error(endpoint, error_msg)
            
            raise
    
    return wrapper


# 使用示例
if __name__ == "__main__":
    # 模擬API調用
    @monitor_api_call
    def test_api_call():
        # 模擬API調用
        time.sleep(0.1)
        return "success"
    
    # 測試正常調用
    for i in range(5):
        try:
            test_api_call()
        except Exception as e:
            print(f"調用失敗: {e}")
    
    # 等待監控報告
    time.sleep(2)
    
    # 獲取報告
    report = api_monitor.get_comprehensive_report()
    print("=== API 監控報告 ===")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    
    # 停止監控
    api_monitor.stop() 