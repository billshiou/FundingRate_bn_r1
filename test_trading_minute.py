import ccxt
import pandas as pd
from datetime import datetime, timedelta
import time
import pytz
from typing import Dict, Optional
import logging
from logging.handlers import RotatingFileHandler
import requests
import websocket
import json
import threading
import os
import sys
import signal
from config import API_KEY, API_SECRET, MAX_POSITION_SIZE, LEVERAGE, MIN_FUNDING_RATE, MAX_SPREAD, ENTRY_BEFORE_SECONDS, CHECK_INTERVAL, ENTRY_TIME_TOLERANCE, CLOSE_BEFORE_SECONDS, CLOSE_AFTER_SECONDS, CLOSE_DELAY_AFTER_ENTRY, MAX_CLOSE_RETRY, TRADING_HOURS, TRADING_MINUTES, TRADING_SYMBOLS, EXCLUDED_SYMBOLS, MAX_ENTRY_RETRY, ENTRY_RETRY_INTERVAL, ENTRY_RETRY_UNTIL_SETTLEMENT, CLOSE_RETRY_INTERVAL, FORCE_CLOSE_AT_SETTLEMENT, ACCOUNT_CHECK_INTERVAL, POSITION_TIMEOUT_SECONDS, ENABLE_POSITION_CLEANUP, FORCE_CLOSE_AFTER_SECONDS, POSITION_CHECK_INTERVAL
import traceback
from binance.client import Client
from binance.exceptions import BinanceAPIException
import hmac
import hashlib
from urllib.parse import urlencode
import numpy as np
from profit_tracker import ProfitTracker

# 全局變量，用於信號處理
trader_instance = None

def safe_json_serialize(obj):
    """安全的JSON序列化，處理numpy數據類型"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: safe_json_serialize(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [safe_json_serialize(item) for item in obj]
    else:
        return obj

def signal_handler(signum, frame):
    """信號處理函數 - 處理Ctrl+C等關閉信號"""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 收到關閉信號 {signum}，正在優雅關閉...")
    
    if trader_instance:
        try:
            # 刷新所有緩存的記錄
            if hasattr(trader_instance, '_analysis_buffer'):
                trader_instance._flush_analysis_buffer()
                
            if trader_instance.current_position:
                print(f"[{trader_instance.format_corrected_time()}] 發現持倉，嘗試清理...")
                trader_instance.force_close_position()
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 清理持倉失敗: {e}")
        
        # 發送關閉通知
        try:
            trader_instance.profit_tracker.send_stop_notification()
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 發送關閉通知失敗: {e}")
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 程式關閉完成")
    sys.exit(0)

# 設置日誌 - 使用輪轉文件處理器
def setup_logging():
    """設置日誌系統，包含文件輪轉"""
    # 創建日誌目錄
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 設置日誌格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # 創建輪轉文件處理器
    # maxBytes: 每個文件最大 5MB
    # backupCount: 保留 7 個備份文件 (總共約 35MB)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'trading_log.txt'),
        maxBytes=5*1024*1024,  # 5MB
        backupCount=7,         # 保留7個備份
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    
    # 控制台處理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # 設置根日誌器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    return logging.getLogger(__name__)

# 初始化日誌
logger = setup_logging()

def cleanup_old_logs(log_dir='logs', max_days=30):
    """清理超過指定天數的日誌文件"""
    try:
        if not os.path.exists(log_dir):
            return
            
        current_time = time.time()
        max_age = max_days * 24 * 3600  # 轉換為秒
        
        for filename in os.listdir(log_dir):
            filepath = os.path.join(log_dir, filename)
            if os.path.isfile(filepath):
                file_age = current_time - os.path.getmtime(filepath)
                if file_age > max_age:
                    os.remove(filepath)
                    print(f"已刪除舊日誌文件: {filename}")
    except Exception as e:
        print(f"清理日誌文件時出錯: {e}")

def get_log_stats(log_dir='logs'):
    """獲取日誌文件統計信息"""
    try:
        if not os.path.exists(log_dir):
            return "日誌目錄不存在"
            
        total_size = 0
        file_count = 0
        file_info = []
        
        for filename in os.listdir(log_dir):
            if filename.endswith('.txt'):
                filepath = os.path.join(log_dir, filename)
                if os.path.isfile(filepath):
                    size = os.path.getsize(filepath)
                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                    total_size += size
                    file_count += 1
                    file_info.append({
                        'name': filename,
                        'size': size,
                        'modified': mtime
                    })
        
        # 按修改時間排序
        file_info.sort(key=lambda x: x['modified'], reverse=True)
        
        stats = f"日誌統計:\n"
        stats += f"文件數量: {file_count}\n"
        stats += f"總大小: {total_size / (1024*1024):.2f} MB\n"
        stats += f"文件列表:\n"
        
        for file in file_info:
            stats += f"  {file['name']}: {file['size'] / 1024:.1f} KB ({file['modified'].strftime('%Y-%m-%d %H:%M')})\n"
            
        return stats
        
    except Exception as e:
        return f"獲取日誌統計時出錯: {e}"

class FundingRateTrader:
    def __init__(self):
        # 配置API客戶端超時設置
        self.client = Client(
            API_KEY, 
            API_SECRET,
            requests_params={
                'timeout': 10,  # 設置10秒超時
                'verify': True,  # 啟用SSL驗證
                'pool_connections': 10,  # 連接池大小
                'pool_maxsize': 10,  # 最大連接數
                'max_retries': 3,  # 最大重試次數
                'backoff_factor': 0.3  # 重試間隔因子
            }
        )
        self.max_position_size = MAX_POSITION_SIZE
        self.leverage = LEVERAGE
        self.min_funding_rate = MIN_FUNDING_RATE
        self.max_spread = MAX_SPREAD
        self.entry_before_seconds = ENTRY_BEFORE_SECONDS
        self.check_interval = CHECK_INTERVAL  # 主循環檢查間隔
        self.funding_rate_threshold = MIN_FUNDING_RATE
        self.entry_time_tolerance = ENTRY_TIME_TOLERANCE  # 進場時間容差（毫秒）
        self.close_before_seconds = CLOSE_BEFORE_SECONDS
        self.close_after_seconds = CLOSE_AFTER_SECONDS  # 結算後平倉時間 (主要平倉邏輯)
        self.close_delay_after_entry = CLOSE_DELAY_AFTER_ENTRY  # 開倉成功後延遲平倉時間
        self.current_position = None
        self.position_open_time = None
        self.funding_rates = {}  # 儲存資金費率數據
        self.book_tickers = {}   # 儲存買賣價數據 (來自WebSocket)
        self.ws = None
        self.ws_thread = None
        self.running = False
        # 配置CCXT交易所實例也添加超時設置
        self.exchange = ccxt.binance({
            'apiKey': API_KEY,
            'secret': API_SECRET,
            'enableRateLimit': True,
            'timeout': 10000,  # 10秒超時（毫秒）
            'options': {
                'defaultType': 'future',
            },
            'headers': {
                'User-Agent': 'FundingRateBot/1.0'
            }
        })
        self.logger = self._setup_logger()
        # 新增：防止重複進場的鎖定機制
        self.entry_locked_until = 0  # 鎖定到哪個時間點
        self.last_funding_time = 0   # 記錄最後處理的結算時間
        # 新增：倉位檢查延遲機制
        self.position_check_delay_until = 0  # 倉位檢查延遲到哪個時間點
        # 新增：訂單狀態追蹤
        self.pending_order = None    # 待確認的訂單
        self.order_status = None     # 訂單狀態
        # 新增：平倉狀態追蹤
        self.is_closing = False      # 是否正在平倉
        # 新增：時間同步相關
        self.time_offset = 0         # 本地時間與服務器時間的差值
        self.last_sync_time = 0      # 上次同步時間
        self.sync_interval = 300     # 每5分鐘同步一次時間
        # 添加詳細時間記錄
        self.entry_timestamps = {}
        self.close_timestamps = {}
        
        # 新增：重試機制相關變量
        self.max_entry_retry = MAX_ENTRY_RETRY  # 最大進場重試次數
        self.entry_retry_interval = ENTRY_RETRY_INTERVAL  # 進場重試間隔
        self.entry_retry_until_settlement = ENTRY_RETRY_UNTIL_SETTLEMENT  # 是否在結算前持續重試進場
        self.entry_retry_count = 0  # 當前進場重試次數
        self.entry_retry_start_time = 0  # 進場重試開始時間
        self.entry_retry_settlement_time = 0  # 進場重試的結算時間
        
        self.max_close_retry = MAX_CLOSE_RETRY  # 最大平倉重試次數
        self.close_retry_interval = CLOSE_RETRY_INTERVAL  # 平倉重試間隔
        self.force_close_at_settlement = FORCE_CLOSE_AT_SETTLEMENT  # 結算時強制平倉
        self.force_close_after_seconds = FORCE_CLOSE_AFTER_SECONDS  # 強制平倉時間（結算後N秒）
        self.close_retry_count = 0  # 當前平倉重試次數
        self.close_retry_start_time = 0  # 平倉重試開始時間
        
        # 新增：定期檢查帳戶和清理超時倉位
        self.account_check_interval = ACCOUNT_CHECK_INTERVAL  # 帳戶檢查間隔（秒）
        self.position_timeout_seconds = POSITION_TIMEOUT_SECONDS  # 倉位超時時間（秒）
        self.enable_position_cleanup = ENABLE_POSITION_CLEANUP  # 是否啟用倉位清理
        self.last_account_check_time = 0  # 上次帳戶檢查時間
        self.position_check_interval = POSITION_CHECK_INTERVAL  # 持倉檢查間隔
        
        # 初始化收益追蹤器
        self.profit_tracker = ProfitTracker()
        
        # 設置每日Excel導出
        try:
            self.profit_tracker.setup_daily_excel_export()
        except Exception as e:
            print(f"[{self.format_corrected_time()}] Excel導出設置失敗: {e}")
        
        # 初始化點差緩存 - 按需精準更新策略
        self._spread_cache = {}                    # 存儲每個交易對的點差
        self._spread_cache_time = {}               # 存儲每個交易對的更新時間
        self._spread_update_in_progress = False    # 批量更新進度標志（保留兼容性）
        
        # 🔒 併發保護機制
        self.api_call_lock = threading.Lock()  # API調用鎖定
        self.retry_state_lock = threading.Lock()  # 重試狀態鎖定
        self.is_api_calling = False  # API調用狀態
        self.api_call_start_time = 0  # API調用開始時間
        self.max_api_call_duration = 15  # 最大API調用時間（秒）
        self.concurrent_api_calls = 0  # 當前併發API調用數
        self.max_concurrent_api_calls = 1  # 最大併發API調用數
        
        # 🎯 確定當前平倉模式 (用於顯示)
        self._close_method_display = self._determine_close_method_display()

    def _determine_close_method_display(self):
        """確定平倉模式的顯示文字"""
        # 根據配置判斷平倉方法
        if hasattr(self, 'max_close_retry') and self.max_close_retry == 0:
            return "🚨極簡平倉(立即)"
        elif hasattr(self, 'close_after_seconds') and self.close_after_seconds <= 0.05:
            return "🚨極簡平倉(立即)"
        elif hasattr(self, 'close_after_seconds') and self.close_after_seconds <= 0.1:
            return f"⚡超極速平倉(+{self.close_after_seconds}s)"
        else:
            return f"📋完整平倉(+{self.close_after_seconds}s)"

    def _setup_logger(self):
        """設置日誌 - 使用全域日誌器，避免重複"""
        # 直接使用全域設置的日誌器，不再重複設置
        return logging.getLogger('FundingRateTrader')

    def is_trading_time(self) -> bool:
        """檢查是否在交易時間內 - 測試版本：每分鐘都允許交易"""
        now = datetime.utcnow()
        # 測試版本：每分鐘都允許交易，但仍然檢查小時設定
        return now.hour in TRADING_HOURS

    def is_valid_symbol(self, symbol: str) -> bool:
        """檢查是否為有效的交易幣種"""
        # 如果有設定特定交易幣種，只交易這些幣種
        if TRADING_SYMBOLS:
            return symbol in TRADING_SYMBOLS
        # 否則排除指定的幣種
        return symbol not in EXCLUDED_SYMBOLS

    def subscribe(self):
        """訂閱 WebSocket - !markPrice@arr 自動推送資金費率數據"""
        # !markPrice@arr 會自動推送所有合約的資金費率和標記價格數據
        # 無需額外訂閱操作
        print(f"[{self.format_corrected_time()}] WebSocket 已連接到 !markPrice@arr，自動接收資金費率數據")

    def on_message(self, ws, message):
        """處理 WebSocket 消息 - 處理資金費率數據"""
        try:
            data = json.loads(message)
            
            # 檢查是否是訂閱確認消息
            if 'result' in data and data['result'] is None:
                print(f"[{self.format_corrected_time()}] WebSocket 已連接，自動接收標記價格數據")
                return
            
            # 處理資金費率數據（標準格式）
            if isinstance(data, list):
                updated_count = 0
                for item in data:
                    symbol = item['s']
                    if self.is_valid_symbol(symbol):
                        funding_rate = float(item['r']) * 100  # 轉換為百分比
                        mark_price = float(item['p'])  # 標記價格
                        next_funding_time = item['T']
                        
                        # 更新資金費率數據
                        self.funding_rates[symbol] = {
                            'funding_rate': funding_rate,
                            'mark_price': mark_price,
                            'next_funding_time': next_funding_time,
                            'last_update': self.get_corrected_time()
                        }
                        updated_count += 1
                
                # 只在有更新時顯示（減少輸出頻率）
                if updated_count > 0 and (not hasattr(self, '_last_funding_display') or time.time() - self._last_funding_display >= 30):
                    total_symbols = len(self.funding_rates)
                    spread_stats = self.get_spread_stats()
                    cache_count = len(self._spread_cache) if hasattr(self, '_spread_cache') else 0
                    stats_msg = f"WebSocket: 更新{updated_count}個資金費率，總計{total_symbols}個交易對 | 點差緩存: {cache_count}個"
                    if spread_stats and spread_stats['total_requests'] > 0:
                        stats_msg += f" | 60秒API調用: {spread_stats['api_count']}次"
                    print(f"[{self.format_corrected_time()}] {stats_msg}")
                    self._last_funding_display = time.time()
                    
        except Exception as e:
            print(f"[{self.format_corrected_time()}] WebSocket 消息處理錯誤: {e}")
            print(f"錯誤詳情: {traceback.format_exc()}")
            print(f"原始數據前100字元: {str(message)[:100]}...")

    def on_error(self, ws, error):
        """處理 WebSocket 錯誤"""
        print(f"[{self.format_corrected_time()}] WebSocket 錯誤: {error}")
        print(f"錯誤詳情: {traceback.format_exc()}")
        self.ws = None
        print("嘗試重新連接 WebSocket...")
        # 延遲重連，避免立即重連造成問題
        time.sleep(2)
        self.reconnect()

    def on_close(self, ws, close_status_code, close_msg):
        """處理 WebSocket 關閉"""
        print(f"[{self.format_corrected_time()}] WebSocket 連接已關閉，狀態碼: {close_status_code}, 訊息: {close_msg}")
        self.ws = None
        print("嘗試重新連接 WebSocket...")
        # 延遲重連，避免立即重連造成問題
        time.sleep(2)
        self.reconnect()

    def on_open(self, ws):
        """WebSocket 連接開啟時的回調"""
        print(f"[{self.format_corrected_time()}] WebSocket 連接已開啟")
        # 等待連接完全建立
        time.sleep(1)
        # 訂閱所有交易對的資金費率
        self.subscribe()
        print("已發送訂閱請求")

    def start_websocket(self):
        """啟動 WebSocket 連接 - 同時獲取資金費率和買賣價數據"""
        try:
            print(f"[{self.format_corrected_time()}] 啟動 WebSocket 連接...")
            # 幣安期貨暫時只支援標記價格的集合流，bookTicker需要單獨連接
            # 先使用標記價格流，bookTicker功能後續添加
            stream_url = "wss://fstream.binance.com/ws/!markPrice@arr"
            print(f"[{self.format_corrected_time()}] 注意：期貨WebSocket暫時只獲取標記價格，點差數據使用API緩存（30秒更新最佳交易對）")
            self.ws = websocket.WebSocketApp(
                stream_url,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
                on_open=self.on_open
            )
            
            # 在新線程中啟動 WebSocket
            self.ws_thread = threading.Thread(target=lambda: self.ws.run_forever(
                ping_interval=30,
                ping_timeout=10,
                reconnect=5
            ))
            self.ws_thread.daemon = True
            self.ws_thread.start()
            
            print(f"[{self.format_corrected_time()}] WebSocket 線程已啟動 (資金費率)")
            
            # 等待 WebSocket 連接建立
            time.sleep(2)
            
        except Exception as e:
            print(f"[{self.format_corrected_time()}] 啟動 WebSocket 失敗: {e}")
            time.sleep(5)
            self.start_websocket()

    def get_spread(self, symbol: str) -> float:
        """獲取交易對的點差 (買賣價差百分比) - 按需精準緩存策略"""
        try:
            # 優先從WebSocket獲取買賣價數據 (1-3ms)
            if hasattr(self, 'book_tickers') and symbol in self.book_tickers:
                book_data = self.book_tickers[symbol]
                best_bid = book_data['bid_price']
                best_ask = book_data['ask_price']
                
                # 獲取標記價格作為參考
                ref_price = None
                if hasattr(self, 'funding_rates') and symbol in self.funding_rates:
                    if 'mark_price' in self.funding_rates[symbol]:
                        ref_price = self.funding_rates[symbol]['mark_price']
                
                # 如果沒有標記價格，使用中間價
                if ref_price is None:
                    ref_price = (best_bid + best_ask) / 2
                
                # 計算點差百分比
                spread_pct = ((best_ask - best_bid) / ref_price) * 100
                
                # 統計WebSocket使用情況
                if not hasattr(self, '_websocket_spread_count'):
                    self._websocket_spread_count = 0
                    self._api_spread_count = 0
                self._websocket_spread_count += 1
                
                return spread_pct
            
            # WebSocket數據不可用，使用按需緩存策略
            if not hasattr(self, '_spread_cache'):
                self._spread_cache = {}
                self._spread_cache_time = {}
                self._spread_update_in_progress = False
            
            # 返回緩存的點差，如果沒有則返回默認值
            if symbol in self._spread_cache:
                return self._spread_cache[symbol]
            else:
                # 如果緩存中沒有該交易對，返回默認點差估算值
                # 注意：現在改用按需更新，在get_best_opportunity()中會主動更新最佳交易對的點差
                return 0.05  # 默認點差0.05%，允許進場但不會太激進
            
        except Exception as e:
            print(f"[{self.format_corrected_time()}] 獲取點差失敗 {symbol}: {e}")
            return 999.0  # 錯誤時返回極大值，避免進場
    
    def _start_spread_cache_update(self):
        """啟動點差緩存後台更新"""
        if hasattr(self, '_spread_update_in_progress') and self._spread_update_in_progress:
            return
        
        def update_spread_cache():
            try:
                self._spread_update_in_progress = True
                print(f"[{self.format_corrected_time()}] 開始智能點差緩存更新...")
                
                # 獲取資金費率高於閾值的交易對（智能篩選）
                high_funding_symbols = []
                if hasattr(self, 'funding_rates'):
                    for symbol, data in self.funding_rates.items():
                        if self.is_valid_symbol(symbol):
                            funding_rate = data['funding_rate']
                            abs_funding_rate = abs(funding_rate)
                            # 只更新資金費率有潛力的交易對（閾值的80%）
                            if abs_funding_rate >= self.funding_rate_threshold * 0.8:
                                high_funding_symbols.append(symbol)
                
                # 智能批量更新數量
                # 基於API限制計算：1200請求/分鐘 = 20請求/秒
                # 30秒窗口內安全使用500次 (留緩衝)，每次0.1秒間隔可處理約50個
                max_symbols = min(50, len(high_funding_symbols))  # 減少到50個，但更精準
                symbols_to_update = high_funding_symbols[:max_symbols]
                
                updated_count = 0
                start_time = time.time()
                
                for symbol in symbols_to_update:
                    try:
                        # 獲取標記價格
                        mark_price = None
                        if symbol in self.funding_rates and 'mark_price' in self.funding_rates[symbol]:
                            mark_price = self.funding_rates[symbol]['mark_price']
                        
                        # 獲取訂單簿數據
                        depth = self.client.futures_order_book(symbol=symbol, limit=5)
                        
                        if depth['bids'] and depth['asks']:
                            best_bid = float(depth['bids'][0][0])
                            best_ask = float(depth['asks'][0][0])
                            ref_price = mark_price if mark_price else (best_bid + best_ask) / 2
                            spread_pct = ((best_ask - best_bid) / ref_price) * 100
                            
                            # 更新緩存
                            self._spread_cache[symbol] = spread_pct
                            updated_count += 1
                        
                        # 避免API限制，適當延遲
                        time.sleep(0.1)
                        
                    except Exception as e:
                        print(f"[{self.format_corrected_time()}] 更新點差失敗 {symbol}: {e}")
                        continue
                
                elapsed_time = time.time() - start_time
                self._spread_cache_time = time.time()
                
                # 統計API使用情況
                if not hasattr(self, '_api_spread_count'):
                    self._api_spread_count = 0
                self._api_spread_count += updated_count
                
                print(f"[{self.format_corrected_time()}] 智能點差更新完成: {updated_count}/{len(symbols_to_update)} 個高潛力交易對，耗時 {elapsed_time:.1f}秒")
                
                # 顯示緩存覆蓋情況
                total_high_funding = len(high_funding_symbols)
                high_funding_coverage = (len(symbols_to_update) / total_high_funding * 100) if total_high_funding > 0 else 0
                print(f"[{self.format_corrected_time()}] 高潛力覆蓋率: {high_funding_coverage:.1f}% ({len(symbols_to_update)}/{total_high_funding}個) | 總緩存: {len(self._spread_cache)}個交易對")
                
            except Exception as e:
                print(f"[{self.format_corrected_time()}] 點差緩存更新錯誤: {e}")
            finally:
                self._spread_update_in_progress = False
        
        # 在後台線程中執行更新
        import threading
        update_thread = threading.Thread(target=update_spread_cache)
        update_thread.daemon = True
        update_thread.start()
    
    def _should_update_spread(self, symbol: str) -> bool:
        """檢查是否需要更新該交易對的點差"""
        try:
            # 確保緩存結構正確初始化
            if not hasattr(self, '_spread_cache_time') or not isinstance(self._spread_cache_time, dict):
                self._spread_cache_time = {}
            
            current_time = time.time()
            last_update_time = self._spread_cache_time.get(symbol, 0)
            
            # 30秒緩存時間，避免頻繁更新
            return (current_time - last_update_time >= 30)
            
        except Exception as e:
            print(f"[{self.format_corrected_time()}] 檢查點差更新狀態失敗 {symbol}: {e}")
            return False
    
    def update_single_spread(self, symbol: str):
        """按需更新單一交易對的點差 - 精準高效"""
        try:
            # 確保緩存結構正確初始化
            if not hasattr(self, '_spread_cache') or not isinstance(self._spread_cache, dict):
                self._spread_cache = {}
            if not hasattr(self, '_spread_cache_time') or not isinstance(self._spread_cache_time, dict):
                self._spread_cache_time = {}
            
            current_time = time.time()
            
            # 獲取標記價格
            mark_price = None
            if hasattr(self, 'funding_rates') and symbol in self.funding_rates:
                if 'mark_price' in self.funding_rates[symbol]:
                    mark_price = self.funding_rates[symbol]['mark_price']
            
            # 獲取訂單簿數據
            depth = self.client.futures_order_book(symbol=symbol, limit=5)
            
            if depth and 'bids' in depth and 'asks' in depth and depth['bids'] and depth['asks']:
                best_bid = float(depth['bids'][0][0])
                best_ask = float(depth['asks'][0][0])
                ref_price = mark_price if mark_price else (best_bid + best_ask) / 2
                spread_pct = ((best_ask - best_bid) / ref_price) * 100
                
                # 更新單一交易對的緩存
                self._spread_cache[symbol] = spread_pct
                self._spread_cache_time[symbol] = current_time
                
                print(f"[{self.format_corrected_time()}] 精準更新點差: {symbol} = {spread_pct:.3f}%")
                
                # 統計API使用情況
                if not hasattr(self, '_api_spread_count'):
                    self._api_spread_count = 0
                self._api_spread_count += 1
            else:
                print(f"[{self.format_corrected_time()}] 無法獲取點差數據: {symbol}")
            
        except Exception as e:
            print(f"[{self.format_corrected_time()}] 更新單一點差失敗 {symbol}: {e}")
            # 錯誤時不更新緩存，使用舊數據或默認值

    def get_spread_stats(self):
        """獲取點差數據來源統計"""
        if hasattr(self, '_websocket_spread_count') and hasattr(self, '_api_spread_count'):
            total = self._websocket_spread_count + self._api_spread_count
            if total > 0:
                ws_pct = (self._websocket_spread_count / total) * 100
                api_pct = (self._api_spread_count / total) * 100
                return {
                    'websocket_count': self._websocket_spread_count,
                    'api_count': self._api_spread_count,
                    'websocket_percentage': ws_pct,
                    'api_percentage': api_pct,
                    'total_requests': total
                }
        return None

    def calculate_net_profit(self, symbol: str, funding_rate: float) -> tuple:
        """計算淨收益 = 資金費率 - 點差"""
        spread = self.get_spread(symbol)
        abs_funding_rate = abs(funding_rate)
        net_profit = abs_funding_rate - spread if spread < 999 else -999
        return net_profit, spread

    def get_best_opportunity(self, min_funding_rate: float = None) -> Optional[Dict]:
        """找出最佳交易機會 - 基於淨收益 (資金費率 - 點差) > MIN_FUNDING_RATE"""
        if not self.funding_rates:
            return None

        # 使用配置的最小資金費率
        if min_funding_rate is None:
            min_funding_rate = self.funding_rate_threshold

        # 首先基於資金費率篩選出最有潛力的交易對
        potential_opportunities = []
        for symbol, data in self.funding_rates.items():
            # 檢查交易對篩選
            if TRADING_SYMBOLS:
                if symbol not in TRADING_SYMBOLS:
                    continue
            else:
                if symbol in EXCLUDED_SYMBOLS:
                    continue
            
            funding_rate = data['funding_rate']
            abs_funding_rate = abs(funding_rate)
            
            # 只考慮資金費率有潛力的交易對（閾值的80%以上）
            if abs_funding_rate >= min_funding_rate * 0.8:
                potential_opportunities.append({
                    'symbol': symbol,
                    'funding_rate': funding_rate,
                    'abs_funding_rate': abs_funding_rate,
                    'next_funding_time': data['next_funding_time'],
                    'direction': 'long' if funding_rate < 0 else 'short'
                })
        
        if not potential_opportunities:
            return None
        
        # 按結算時間優先，然後按資金費率排序
        potential_opportunities.sort(key=lambda x: (x['next_funding_time'], -x['abs_funding_rate']))
        
        # 依次檢查所有候選，直到找到一個符合條件的
        for candidate in potential_opportunities:
            symbol = candidate['symbol']
            
            # 針對候選更新點差（按需精準更新，避免頻繁調用）
            if self._should_update_spread(symbol):
                self.update_single_spread(symbol)
            
            # 重新計算淨收益（使用最新點差）
            funding_rate = candidate['funding_rate'] 
            net_profit, spread = self.calculate_net_profit(symbol, funding_rate)
            
            # 檢查最終的淨收益和點差條件
            if net_profit >= min_funding_rate and spread <= self.max_spread:
                return {
                    'symbol': symbol,
                    'funding_rate': funding_rate,
                    'net_profit': net_profit,
                    'spread': spread,
                    'next_funding_time': candidate['next_funding_time'],
                    'direction': candidate['direction']
                }
        
        # 如果所有候選都不符合條件，返回None
        return None

    def display_current_rates(self):
        """顯示當前資金費率 - 按結算時間優先排序，顯示淨收益信息"""
        if not self.funding_rates:
            return
            
        # 收集符合條件的交易對
        opportunities = []
        for symbol, data in self.funding_rates.items():
            # 檢查交易對篩選
            if TRADING_SYMBOLS:
                if symbol not in TRADING_SYMBOLS:
                    continue
            else:
                if symbol in EXCLUDED_SYMBOLS:
                    continue
            
            funding_rate = data['funding_rate']
            net_profit, spread = self.calculate_net_profit(symbol, funding_rate)
            
            # 檢查淨收益和點差條件
            if net_profit >= self.funding_rate_threshold and spread <= self.max_spread:
                opportunities.append({
                    'symbol': symbol,
                    'funding_rate': funding_rate,
                    'net_profit': net_profit,
                    'spread': spread,
                    'next_funding_time': data['next_funding_time']
                })
        
        if not opportunities:
            return
            
        # 按結算時間優先排序
        opportunities.sort(key=lambda x: (x['next_funding_time'], -x['net_profit']))
        best = opportunities[0]
        
        next_time = datetime.fromtimestamp(best['next_funding_time'] / 1000).strftime('%H:%M:%S')
        current_time = self.get_corrected_time()
        time_to_settlement = best['next_funding_time'] - current_time
        time_to_settlement_seconds = int(time_to_settlement / 1000)
        
        # 格式化結算倒數為 XX:XX:XX 格式
        settlement_hours = time_to_settlement_seconds // 3600
        settlement_minutes = (time_to_settlement_seconds % 3600) // 60
        settlement_secs = time_to_settlement_seconds % 60
        settlement_countdown = f"{settlement_hours:02d}:{settlement_minutes:02d}:{settlement_secs:02d}"
        
        print(f"\r最佳: {best['symbol']} 資金費率:{best['funding_rate']:.4f}% | 點差:{best['spread']:.3f}% | 淨收益:{best['net_profit']:.3f}% 結算:{next_time} 倒數:{settlement_countdown}", end='', flush=True)

    def get_funding_rates(self) -> pd.DataFrame:
        """獲取所有交易對的資金費率"""
        try:
            response = requests.get("https://fapi.binance.com/fapi/v1/premiumIndex")
            all_rates = response.json()
            
            rates = []
            for data in all_rates:
                rates.append({
                    'symbol': data['symbol'],
                    'funding_rate': float(data['lastFundingRate']) * 100,
                    'next_funding_time': data['nextFundingTime']
                })
            
            df = pd.DataFrame(rates)
            df['abs_funding_rate'] = df['funding_rate'].abs()
            return df
        except Exception as e:
            print(f"\n錯誤: {str(e)}")
            return pd.DataFrame()

    def open_position(self, symbol: str, direction: str, funding_rate: float, next_funding_time: int):
        """開倉"""
        try:
            # 記錄進倉開始
            self.record_entry_step('entry_start', symbol=symbol, direction=direction, funding_rate=funding_rate)
            self.log_trade_step('entry', symbol, 'start', safe_json_serialize({
                'direction': direction, 
                'funding_rate': funding_rate,
                'next_funding_time': next_funding_time
            }))
            
            # 設置槓桿
            print(f"[{self.format_corrected_time()}] 設置槓桿: {symbol} {self.leverage}倍")
            self.log_trade_step('entry', symbol, 'set_leverage', {'leverage': self.leverage})
            self.client.futures_change_leverage(symbol=symbol, leverage=self.leverage)
            self.log_trade_step('entry', symbol, 'leverage_set', {'leverage': self.leverage})
            # 記錄槓桿設置完成（已在上面log_trade_step記錄，避免重複）
            
            # 獲取當前價格 - 使用快速方法
            print(f"[{self.format_corrected_time()}] 獲取當前價格: {symbol}")
            self.log_trade_step('entry', symbol, 'fetch_price_start', {})
            
            # 修復：正確使用字典格式獲取WebSocket標記價格（1-3ms）
            current_price = None
            if hasattr(self, 'funding_rates') and symbol in self.funding_rates:
                # 正確的字典格式訪問
                symbol_data = self.funding_rates[symbol]
                if 'mark_price' in symbol_data:
                    current_price = symbol_data['mark_price']
                    print(f"[{self.format_corrected_time()}] 使用標記價格: {symbol} = {current_price} (來源: WebSocket)")
                    self.log_trade_step('entry', symbol, 'price_from_websocket', {'price': current_price})
                else:
                    print(f"[{self.format_corrected_time()}] WebSocket數據中無標記價格: {symbol}")
            else:
                print(f"[{self.format_corrected_time()}] WebSocket中無該幣種數據: {symbol}")
            
            # 如果無法從WebSocket獲取，則使用快速API
            if current_price is None:
                try:
                    print(f"[{self.format_corrected_time()}] 嘗試24hr ticker API...")
                    # 使用24hr ticker stats (通常比single ticker快)
                    ticker_24hr = self.client.futures_24hr_ticker(symbol=symbol)
                    print(f"[{self.format_corrected_time()}] 24hr ticker回應: {ticker_24hr}")
                    current_price = float(ticker_24hr['lastPrice'])
                    print(f"[{self.format_corrected_time()}] 使用24hr ticker: {symbol} = {current_price}")
                    self.log_trade_step('entry', symbol, 'price_from_24hr_ticker', {'price': current_price})
                except Exception as e24:
                    print(f"[{self.format_corrected_time()}] 24hr ticker失敗: {e24}")
                    self.log_trade_step('entry', symbol, '24hr_ticker_failed', {'error': str(e24)})
                    try:
                        print(f"[{self.format_corrected_time()}] 嘗試symbol ticker API...")
                        # 最後備案：使用原始方法
                        ticker = self.client.futures_symbol_ticker(symbol=symbol)
                        print(f"[{self.format_corrected_time()}] symbol ticker回應: {ticker}")
                        current_price = float(ticker['price'])
                        print(f"[{self.format_corrected_time()}] 使用symbol ticker: {symbol} = {current_price}")
                        self.log_trade_step('entry', symbol, 'price_from_symbol_ticker', {'price': current_price})
                    except Exception as esym:
                        print(f"[{self.format_corrected_time()}] symbol ticker失敗: {esym}")
                        self.log_trade_step('entry', symbol, 'symbol_ticker_failed', {'error': str(esym)})
                        raise Exception(f"所有價格獲取方法都失敗: WebSocket無數據, 24hr ticker錯誤({e24}), symbol ticker錯誤({esym})")
            
            print(f"[{self.format_corrected_time()}] 當前價格: {symbol} = {current_price}")
            self.log_trade_step('entry', symbol, 'fetch_price_success', {'price': current_price})
            
            # 記錄價格獲取時間
            self.record_entry_step('price_fetched', symbol=symbol, price=current_price)
            
            # 計算數量
            print(f"[{self.format_corrected_time()}] 開始計算數量: {symbol}")
            self.log_trade_step('entry', symbol, 'calculate_quantity_start', {'price': current_price})
            quantity = self.calculate_position_size(symbol, current_price)
            print(f"[{self.format_corrected_time()}] 計算完成: {symbol} 數量 = {quantity}")
            self.log_trade_step('entry', symbol, 'calculate_quantity_success', {'quantity': quantity})
            
            # 記錄數量計算時間
            self.record_entry_step('quantity_calculated', symbol=symbol, quantity=quantity)
            
            # 確定訂單方向
            side = 'BUY' if direction == 'long' else 'SELL'
            print(f"[{self.format_corrected_time()}] 準備發送訂單: {symbol} {side} {quantity}")
            self.log_trade_step('entry', symbol, 'prepare_order', {
                'side': side, 
                'quantity': quantity, 
                'type': 'MARKET'
            })
            
            # 發送訂單
            print(f"[{self.format_corrected_time()}] 發送開倉訂單: {symbol} {side} {quantity}")
            self.log_trade_step('entry', symbol, 'send_order_start', {
                'side': side, 
                'quantity': quantity, 
                'type': 'MARKET'
            })
            order_start_time = time.time()
            # 使用超時處理的API調用
            order = self.execute_api_call_with_timeout(
                self.client.futures_create_order,
                symbol=symbol,
                side=side,
                type='MARKET',
                quantity=quantity,
                timeout=10,  # 10秒超時
                max_retries=2  # 最多重試2次
            )
            order_end_time = time.time()
            execution_time_ms = int((order_end_time - order_start_time) * 1000)
            print(f"[{self.format_corrected_time()}] 訂單發送完成: {symbol} 訂單ID:{order['orderId']} 執行時間:{execution_time_ms}ms")
            self.log_trade_step('entry', symbol, 'send_order_success', {
                'order_id': order['orderId'],
                'execution_time_ms': execution_time_ms,
                'executed_qty': order['executedQty'],
                'avg_price': order['avgPrice']
            })
            
            # 記錄訂單發送時間
            self.record_entry_step('order_sent', symbol=symbol, 
                                 order_id=order['orderId'],
                                 order_time_ms=execution_time_ms)
            
            # 記錄進倉成功
            self.record_entry_step('entry_success', symbol=symbol, 
                                 order_id=order['orderId'],
                                 executed_qty=order['executedQty'],
                                 avg_price=order['avgPrice'])
            
            # 注意：交易事件將在 log_trade_step 中記錄，避免重複
            
            print(f"[{self.format_corrected_time()}] 開倉成功] {symbol} {direction} 數量:{quantity} 價格:{current_price}")
            self.log_trade_step('entry', symbol, 'entry_complete', {
                'direction': direction,
                'quantity': quantity,
                'price': current_price,
                'order_id': order['orderId']
            })
            
            # 顯示詳細時間記錄
            self.print_detailed_timestamps(symbol)
            
            # 更新狀態
            self.current_position = {
                'symbol': symbol,
                'direction': direction,
                'quantity': quantity,
                'entry_price': current_price,
                'funding_rate': funding_rate,
                'next_funding_time': next_funding_time,
                'order_id': order['orderId']
            }
            self.position_open_time = time.time()
            
            # 添加開倉鎖定，防止重複開倉
            self.entry_locked_until = time.time() + 2.0  # 鎖定2秒，防止重複開倉
            
            # 添加倉位檢查延遲，避免開倉後立即檢查
            self.position_check_delay_until = time.time() + 0.3  # 延遲0.3秒再檢查倉位
            
            # 記錄進場完成
            self.record_entry_step('entry_complete', symbol=symbol, 
                                 funding_rate=funding_rate, 
                                 direction=direction, 
                                 next_funding_time=next_funding_time,
                                 expected_profit=self.calculate_net_profit(symbol, funding_rate)[0])
            
            # 重置進場重試計數器
            self.entry_retry_count = 0
            self.entry_retry_start_time = 0
            self.entry_retry_settlement_time = 0
            
            # ✅ 開倉成功，等待結算後時間平倉（不立即平倉）
            print(f"[{self.format_corrected_time()}] 🎯 開倉成功，等待結算後 {self.close_after_seconds} 秒時平倉")
            self.log_trade_step('entry', symbol, 'entry_success_wait_settlement', {
                'close_after_seconds': self.close_after_seconds,
                'close_method': self._close_method_display
            })
            
        except Exception as e:
            # 記錄進倉失敗
            self.record_entry_step('entry_failed', symbol=symbol, error=str(e))
            self.log_trade_event('entry_failed', symbol, {'error': str(e)})
            self.log_trade_step('entry', symbol, 'entry_failed', {'error': str(e)})
            print(f"[{self.format_corrected_time()}] 開倉失敗] {symbol} {direction} 原因: {e}")
            
            # 初始化重試機制
            if self.entry_retry_count == 0:
                self.entry_retry_start_time = time.time()
                self.entry_retry_settlement_time = next_funding_time
                print(f"[{self.format_corrected_time()}] 開始進場重試機制，結算時間: {datetime.fromtimestamp(next_funding_time / 1000).strftime('%H:%M:%S')}")
                self.log_trade_step('entry', symbol, 'retry_start', {
                    'settlement_time': datetime.fromtimestamp(next_funding_time / 1000).strftime('%H:%M:%S')
                })
            
            self.entry_retry_count += 1
            print(f"[{self.format_corrected_time()}] 進場重試 {self.entry_retry_count}/{self.max_entry_retry}")
            self.log_trade_step('entry', symbol, 'retry_attempt', {
                'retry_count': self.entry_retry_count,
                'max_retry': self.max_entry_retry
            })
            
            # 如果重試次數未達上限，且還在結算時間前，則繼續重試
            if self.entry_retry_count < self.max_entry_retry:
                current_time_ms = self.get_corrected_time()
                time_to_settlement = self.entry_retry_settlement_time - current_time_ms
                
                if time_to_settlement > 0:
                    print(f"[{self.format_corrected_time()}] 等待 {self.entry_retry_interval} 秒後重試進場...")
                    self.log_trade_step('entry', symbol, 'retry_wait', {
                        'wait_seconds': self.entry_retry_interval,
                        'time_to_settlement': time_to_settlement
                    })
                    time.sleep(self.entry_retry_interval)
                    # 重新嘗試進場
                    self.open_position(symbol, direction, funding_rate, next_funding_time)
                else:
                    print(f"[{self.format_corrected_time()}] 已過結算時間，停止進場重試")
                    self.log_trade_step('entry', symbol, 'retry_timeout', {})
                    self.entry_retry_count = 0
            else:
                print(f"[{self.format_corrected_time()}] 進場重試次數已達上限，停止重試")
                self.log_trade_step('entry', symbol, 'retry_max_reached', {})
                self.entry_retry_count = 0

    def close_position_ultra_fast(self):
        """超級極速平倉 - 最小化操作，保留關鍵記錄，增強分析數據"""
        if not self.current_position:
            return
            
        symbol = self.current_position['symbol']
        direction = self.current_position['direction']
        quantity = self.current_position['quantity']
        entry_price = self.current_position.get('entry_price', 0.0)
        funding_rate = self.current_position.get('funding_rate', 0.0)
        
        try:
            # 記錄開始時間和系統狀態
            close_start_time = time.time()
            corrected_time_ms = self.get_corrected_time()
            
            # 獲取市場狀況快照（不影響速度）
            try:
                book_ticker = self.book_tickers.get(symbol, {})
                bid_price = float(book_ticker.get('bidPrice', 0))
                ask_price = float(book_ticker.get('askPrice', 0))
                spread_amount = ask_price - bid_price if bid_price and ask_price else 0
                spread_percentage = (spread_amount / ask_price * 100) if ask_price > 0 else 0
                mid_price = (bid_price + ask_price) / 2 if bid_price and ask_price else 0
                market_liquidity = "優良" if spread_percentage < 0.05 else "正常" if spread_percentage < 0.1 else "較差" if spread_percentage < 0.2 else "很差"
            except:
                bid_price = ask_price = spread_amount = spread_percentage = mid_price = 0
                market_liquidity = "未知"
            
            # 詳細記錄開始（包含市場和系統分析）
            print(f"[{self.format_corrected_time()}] ⚡極速平倉啟動: {symbol} {direction} {quantity} | 點差:{spread_percentage:.4f}% | 流動性:{market_liquidity}")
            
            self.write_trade_analysis('ultra_fast_close_detailed_start', symbol,
                                    close_method='超級極速平倉',
                                    optimization_level='最高',
                                    trade_basic_info={
                                        'direction': direction,
                                        'quantity': quantity,
                                        'entry_price': entry_price,
                                        'funding_rate': funding_rate
                                    },
                                    market_snapshot={
                                        'bid_price': bid_price,
                                        'ask_price': ask_price,
                                        'mid_price': mid_price,
                                        'spread_amount': spread_amount,
                                        'spread_percentage': f"{spread_percentage:.4f}%",
                                        'liquidity_rating': market_liquidity
                                    },
                                    system_status={
                                        'corrected_time_ms': corrected_time_ms,
                                        'local_time_ms': int(close_start_time * 1000),
                                        'time_offset_ms': self.time_offset,
                                        'retry_count': self.close_retry_count,
                                        'is_first_attempt': self.close_retry_count == 0
                                    },
                                    skip_features=['價格重新獲取', '倉位檢查', '重試機制', '複雜日誌'])
            
            # 直接執行：確定方向 + 發送訂單
            side = 'SELL' if direction == 'long' else 'BUY'
            
            # API調用前的最後檢查
            api_prepare_start = time.time()
            order_params = {
                'symbol': symbol,
                'side': side,
                'type': 'MARKET',
                'quantity': quantity,
                'reduceOnly': True
            }
            api_prepare_time_ms = int((time.time() - api_prepare_start) * 1000)
            
            # 核心操作：直接發送平倉訂單 (使用超時處理)
            order_start_time = time.time()
            order = self.execute_api_call_with_timeout(
                self.client.futures_create_order,
                timeout=8,  # 8秒超時（平倉更急迫）
                max_retries=1,  # 極速平倉只重試1次
                **order_params
            )
            order_end_time = time.time()
            
            # 時間分析
            execution_time_ms = int((order_end_time - order_start_time) * 1000)
            total_time_ms = int((order_end_time - close_start_time) * 1000)
            
            # 提取訂單詳細信息
            order_id = order.get('orderId', 'UNKNOWN')
            executed_qty = order.get('executedQty', quantity)
            avg_price = float(order.get('avgPrice', 0)) if order.get('avgPrice') else 0
            order_status = order.get('status', 'UNKNOWN')
            
            # 效能評估
            efficiency_score = "極優" if execution_time_ms < 100 else "優秀" if execution_time_ms < 200 else "良好" if execution_time_ms < 500 else "普通" if execution_time_ms < 1000 else "需改善"
            speed_vs_market = "超快" if total_time_ms < 150 else "很快" if total_time_ms < 300 else "快速" if total_time_ms < 600 else "正常"
            
            # 價格執行分析
            price_analysis = {}
            if avg_price > 0:
                if direction == 'long':
                    # 多頭平倉，比較與賣價
                    slippage = ((bid_price - avg_price) / bid_price * 100) if bid_price > 0 else 0
                    vs_mid = ((avg_price - mid_price) / mid_price * 100) if mid_price > 0 else 0
                else:
                    # 空頭平倉，比較與買價
                    slippage = ((avg_price - ask_price) / ask_price * 100) if ask_price > 0 else 0
                    vs_mid = ((mid_price - avg_price) / mid_price * 100) if mid_price > 0 else 0
                
                price_analysis = {
                    'slippage_percentage': f"{slippage:.4f}%",
                    'vs_mid_price': f"{vs_mid:.4f}%",
                    'execution_quality': "優秀" if abs(slippage) < 0.01 else "良好" if abs(slippage) < 0.05 else "普通"
                }
            
            # 關鍵記錄：成功信息
            print(f"[{self.format_corrected_time()}] ✅極速平倉成功: {symbol} ID:{order_id} | API:{execution_time_ms}ms | 總計:{total_time_ms}ms | 效率:{efficiency_score} | 成交:{avg_price}")
            
            # 記錄到分析文件（詳細的效能和市場分析）
            self.write_trade_analysis('ultra_fast_close_detailed_success', symbol, 
                                    order_id=order_id,
                                    close_method='超級極速平倉',
                                    execution_result={
                                        'order_status': order_status,
                                        'executed_qty': executed_qty,
                                        'avg_price': avg_price,
                                        'side_executed': order.get('side', side)
                                    },
                                    performance_metrics={
                                        'api_response_time_ms': execution_time_ms,
                                        'total_process_time_ms': total_time_ms,
                                        'api_prepare_time_ms': api_prepare_time_ms,
                                        'efficiency_score': efficiency_score,
                                        'speed_rating': speed_vs_market
                                    },
                                    price_execution_analysis=price_analysis,
                                    market_condition_impact={
                                        'market_liquidity': market_liquidity,
                                        'spread_at_execution': f"{spread_percentage:.4f}%",
                                        'optimal_execution_window': "是" if spread_percentage < 0.1 else "否"
                                    },
                                    trading_context={
                                        'direction': direction,
                                        'quantity': quantity,
                                        'entry_price': entry_price,
                                        'funding_rate': funding_rate,
                                        'retry_attempt': self.close_retry_count
                                    })
            
            # 📝 記錄超詳細平倉分析
            self.record_detailed_close_analysis(symbol, order)
            
            # 立即清理狀態
            self.current_position = None
            self.position_open_time = None
            self.close_retry_count = 0
            self.is_closing = False
            
            # 延後處理：盈虧計算、收益追蹤、通知等（不影響速度）
            self.schedule_post_close_processing(symbol, direction, quantity, order)
            
            return True
            
        except Exception as e:
            error_time = time.time()
            total_error_time_ms = int((error_time - close_start_time) * 1000)
            
            print(f"[{self.format_corrected_time()}] ❌極速平倉失敗: {symbol} - {e} | 耗時:{total_error_time_ms}ms")
            
            # 詳細記錄失敗信息（包含錯誤分析）
            self.write_trade_analysis('ultra_fast_close_detailed_failed', symbol, 
                                    error=str(e),
                                    error_type=type(e).__name__,
                                    close_method='超級極速平倉',
                                    failure_analysis={
                                        'total_time_before_error_ms': total_error_time_ms,
                                        'failure_stage': 'API調用' if 'order' in str(e).lower() else 'market_data' if 'ticker' in str(e).lower() else '未知',
                                        'error_severity': 'critical' if 'connection' in str(e).lower() else 'moderate',
                                        'retry_recommended': True
                                    },
                                    context_at_failure={
                                        'direction': direction,
                                        'quantity': quantity,
                                        'entry_price': entry_price,
                                        'funding_rate': funding_rate,
                                        'retry_count': self.close_retry_count,
                                        'market_liquidity': market_liquidity if 'market_liquidity' in locals() else 'unknown'
                                    },
                                    fallback_action='切換到完整平倉重試機制',
                                    next_method='close_position_with_retry')
            
            # 失敗時回退到重試機制
            return self.close_position_with_retry()

    def close_position_fast(self):
        """極速平倉 - 只保留核心操作"""
        if not self.current_position:
            return
            
        symbol = self.current_position['symbol']
        direction = self.current_position['direction']
        quantity = self.current_position['quantity']
        
        try:
            # 記錄極速平倉開始
            self.write_trade_analysis('fast_close_start', symbol, 
                                    close_method='極速平倉',
                                    direction=direction, 
                                    quantity=quantity,
                                    trigger_reason='時間觸發或手動')
            
            # 步驟1: 確定平倉方向
            side = 'SELL' if direction == 'long' else 'BUY'
            self.write_trade_analysis('fast_close_step_side_determined', symbol,
                                    step_number='1',
                                    action='確定平倉方向',
                                    side=side,
                                    logic=f'開倉方向 {direction} -> 平倉方向 {side}')
            
            # 步驟2: 準備API調用參數
            api_params = {
                'symbol': symbol,
                'side': side,
                'type': 'MARKET',
                'quantity': quantity,
                'reduceOnly': True
            }
            self.write_trade_analysis('fast_close_step_prepare_api', symbol,
                                    step_number='2',
                                    action='準備API參數',
                                    api_method='futures_create_order',
                                    parameters=api_params)
            
            # 步驟3: 發送API請求
            self.write_trade_analysis('fast_close_step_api_call_start', symbol,
                                    step_number='3',
                                    action='開始API調用',
                                    api_endpoint='futures_create_order')
            
            order_start_time = time.time()
            # 直接發送平倉訂單 - 不獲取價格，市價單會自動匹配最佳價格 (使用超時處理)
            order = self.execute_api_call_with_timeout(
                self.client.futures_create_order,
                timeout=10,  # 10秒超時
                max_retries=2,  # 極速平倉重試2次
                **api_params
            )
            order_end_time = time.time()
            execution_time_ms = int((order_end_time - order_start_time) * 1000)
            
            # 步驟4: API回傳成功
            self.write_trade_analysis('fast_close_step_api_response', symbol,
                                    step_number='4',
                                    action='API回傳成功',
                                    execution_time_ms=execution_time_ms,
                                    order_response=safe_json_serialize(order))
            
            # 簡單記錄成功
            print(f"[{self.format_corrected_time()}] 極速平倉成功: {symbol} 訂單ID:{order['orderId']}")
            
            # 步驟5: 提取關鍵信息
            order_id = order['orderId']
            executed_qty = order.get('executedQty', 'N/A')
            avg_price = order.get('avgPrice', 'N/A')
            
            self.write_trade_analysis('fast_close_step_extract_info', symbol,
                                    step_number='5',
                                    action='提取關鍵信息',
                                    order_id=order_id,
                                    executed_qty=executed_qty,
                                    avg_price=avg_price)
            
            # 步驟6: 清空持倉記錄
            self.write_trade_analysis('fast_close_step_clear_position', symbol,
                                    step_number='6',
                                    action='清空持倉記錄',
                                    cleared_fields=['current_position', 'position_open_time', 'close_retry_count', 'is_closing'])
            
            # 清空持倉記錄
            self.current_position = None
            self.position_open_time = None
            self.close_retry_count = 0
            self.is_closing = False
            
            # 步驟7: 安排延後處理
            self.write_trade_analysis('fast_close_step_schedule_post_process', symbol,
                                    step_number='7',
                                    action='安排延後處理',
                                    delay_seconds=1.0,
                                    post_process_tasks=['盈虧計算', '收益追蹤', '通知發送'])
            
            # 延後處理：盈虧計算、收益追蹤、通知等
            self.schedule_post_close_processing(symbol, direction, quantity, order)
            
            # 記錄極速平倉成功
            self.write_trade_analysis('fast_close_success', symbol, 
                                    order_id=order_id, 
                                    execution_time_ms=execution_time_ms,
                                    executed_qty=executed_qty,
                                    avg_price=avg_price,
                                    close_method='極速平倉',
                                    total_steps=7)
            
            return True
            
        except Exception as e:
            print(f"[{self.format_corrected_time()}] 極速平倉失敗: {symbol} - {e}")
            # 記錄極速平倉失敗 - 包含詳細錯誤信息
            self.write_trade_analysis('fast_close_failed', symbol, 
                                    error=str(e),
                                    error_type=type(e).__name__,
                                    close_method='極速平倉',
                                    fallback_action='切換到完整平倉重試機制')
            # 失敗時才使用完整的重試邏輯
            return self.close_position_with_retry()
    
    def schedule_post_close_processing(self, symbol, direction, quantity, order):
        """延後處理平倉後的統計、通知等非關鍵操作"""
        # 保存當前持倉信息，因為稍後會被清空
        current_position_backup = self.current_position.copy() if self.current_position else {}
        position_open_time_backup = self.position_open_time
        
        # 從order中獲取實際的平倉價格和時間
        order_exit_price = float(order.get('avgPrice', 0)) if order.get('avgPrice') else None
        order_id = order.get('orderId', 'UNKNOWN')
        order_time = time.time()
        
        def post_process():
            try:
                print(f"[{self.format_corrected_time()}] 延後處理開始: {symbol} 訂單ID:{order_id}")
                
                # 獲取平倉價格 - 優先使用訂單中的成交價，否則重新獲取
                if order_exit_price and order_exit_price > 0:
                    exit_price = order_exit_price
                    print(f"[{self.format_corrected_time()}] 使用訂單成交價: {exit_price}")
                else:
                    ticker = self.client.futures_symbol_ticker(symbol=symbol)
                    exit_price = float(ticker['price'])
                    print(f"[{self.format_corrected_time()}] 重新獲取市價: {exit_price}")
                
                # 使用備份的進場價格，如果沒有就使用平倉價格
                entry_price = current_position_backup.get('entry_price', exit_price)
                funding_rate = current_position_backup.get('funding_rate', 0.0)
                
                # 修正空備份問題
                if not current_position_backup:
                    print(f"[{self.format_corrected_time()}] 警告：持倉備份為空，使用預設值")
                    entry_price = exit_price
                    funding_rate = 0.0
                
                # 計算盈虧
                pnl = (exit_price - entry_price) * quantity if direction == 'long' else (entry_price - exit_price) * quantity
                
                # 計算持倉時間
                if position_open_time_backup:
                    position_duration = int(order_time - position_open_time_backup)
                else:
                    position_duration = 0
                    print(f"[{self.format_corrected_time()}] 警告：開倉時間備份為空，持倉時間設為0")
                
                print(f"[{self.format_corrected_time()}] 交易資料計算完成: 進場價:{entry_price:.4f} 平倉價:{exit_price:.4f} 盈虧:{pnl:.4f} 持倉:{position_duration}秒")
                
                # 記錄詳細日誌
                self.log_trade_event('close_success', symbol, {
                    'direction': direction,
                    'quantity': quantity,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'order_id': order['orderId'],
                    'funding_rate': funding_rate,
                    'position_duration_seconds': position_duration
                })
                
                # 記錄詳細的平倉完成信息到記事本（延後處理版本）
                self.write_trade_analysis('close_position_detail', symbol,
                                        order_id=order['orderId'],
                                        executed_qty=order.get('executedQty', quantity),
                                        avg_price=order.get('avgPrice', exit_price),
                                        # 完整的交易詳細信息
                                        direction=direction,
                                        quantity=quantity,
                                        entry_price=entry_price,
                                        exit_price=exit_price,
                                        pnl=pnl,
                                        funding_rate=funding_rate,
                                        position_duration_seconds=position_duration,
                                        processing_type='延後處理')
                
                # 收益追蹤和Telegram通知
                if hasattr(self, 'profit_tracker') and self.profit_tracker:
                    # 從訂單響應中提取更準確的時間戳
                    order_time_from_api = order.get('updateTime') or order.get('time')
                    
                    # 使用API時間戳（如果有的話），否則使用程式記錄的時間
                    if order_time_from_api:
                        exit_timestamp_ms = int(order_time_from_api)
                        print(f"[{self.format_corrected_time()}] 使用API時間戳: {exit_timestamp_ms}")
                    else:
                        exit_timestamp_ms = int(order_time * 1000)
                        print(f"[{self.format_corrected_time()}] 使用程式時間戳: {exit_timestamp_ms}")
                    
                    trade_data = {
                        'symbol': symbol,
                        'direction': direction,
                        'quantity': quantity,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl': pnl,
                        'funding_rate': funding_rate,
                        'order_id': order_id,
                        'entry_timestamp': int(position_open_time_backup * 1000) if position_open_time_backup else int((order_time - 10) * 1000),
                        'exit_timestamp': exit_timestamp_ms,
                        'position_duration_seconds': position_duration,
                        # 添加額外的時間精度信息
                        'api_order_time': order_time_from_api,
                        'program_order_time': int(order_time * 1000),
                        'time_source': 'api' if order_time_from_api else 'program'
                    }
                    
                    print(f"[{self.format_corrected_time()}] 交易資料準備: {trade_data}")
                    
                    # 添加交易記錄
                    self.profit_tracker.add_trade(trade_data)
                
                    # 發送基本交易通知
                    try:
                        self.profit_tracker.send_trade_notification(trade_data)
                        print(f"[{self.format_corrected_time()}] Telegram交易通知已發送: {symbol}")
                    except Exception as notify_e:
                        print(f"[{self.format_corrected_time()}] Telegram交易通知發送失敗: {notify_e}")
                        import traceback
                        traceback.print_exc()
                
                # 延後60秒發送詳細帳戶分析報告
                def send_detailed_analysis():
                    try:
                        from account_analyzer import AccountAnalyzer
                        from config import LEVERAGE
                        from datetime import datetime
                        
                        analyzer = AccountAnalyzer()
                        
                        # 使用實際的交易時間範圍
                        entry_time_ms = int(position_open_time_backup * 1000) if position_open_time_backup else int((order_time - 10) * 1000)
                        exit_time_ms = int(order_time * 1000)
                        
                        # 擴大時間範圍以確保能找到交易記錄
                        period = [{
                            'symbol': symbol,
                            'entry_time': entry_time_ms - 5000,  # 提前5秒
                            'exit_time': exit_time_ms + 5000,    # 延後5秒
                            'direction': direction,
                            'quantity': quantity
                        }]
                        
                        print(f"[{self.format_corrected_time()}] 查詢交易記錄: {symbol} 時間範圍:{datetime.fromtimestamp(entry_time_ms/1000).strftime('%H:%M:%S.%f')[:-3]} - {datetime.fromtimestamp(exit_time_ms/1000).strftime('%H:%M:%S.%f')[:-3]}")
                        
                        result = analyzer.analyze_trades_by_time_range(period)
                        if result and result['trades_by_period']:
                            detail = result['trades_by_period'][0]
                            print(f"[{self.format_corrected_time()}] 找到交易記錄: 實際盈虧:{detail['realized_pnl']:.4f} 資金費:{detail['funding_fee']:.4f} 手續費:{detail['commission']:.4f}")
                        else:
                            print(f"[{self.format_corrected_time()}] 未找到交易記錄，使用程式計算值")
                            # 創建虛擬的detail，使用程式計算的值
                            # 估算手續費：倉位價值 * 0.04% (maker fee)
                            estimated_commission = (quantity * entry_price + quantity * exit_price) * 0.0004
                            # 估算資金費（如果確實獲得了資金費）
                            estimated_funding = quantity * entry_price * (funding_rate / 100) if funding_rate != 0 else 0.0
                            
                            detail = {
                                'symbol': symbol,
                                'direction': direction,
                                'entry_time': entry_time_ms,
                                'exit_time': exit_time_ms,
                                'realized_pnl': pnl,
                                'funding_fee': estimated_funding,
                                'commission': estimated_commission,
                                'net_profit': pnl + estimated_funding - estimated_commission,
                                'income_records': []
                            }
                            
                            print(f"[{self.format_corrected_time()}] 虛擬detail創建:")
                            print(f"  程式盈虧: {pnl:.4f}")
                            print(f"  估算資金費: {estimated_funding:.4f}")
                            print(f"  估算手續費: {estimated_commission:.4f}")
                            print(f"  估算淨利: {detail['net_profit']:.4f}")
                            
                            # 計算倉位和保證金資訊
                            position_value = quantity * entry_price
                            margin_used = position_value / LEVERAGE
                            
                            # 計算報酬率（淨利 / 保證金）
                            return_rate = (detail['net_profit'] / margin_used * 100) if margin_used > 0 else 0
                            
                            # 分析資金費詳細數據
                            funding_details = ""
                            funding_records = [inc for inc in detail.get('income_records', []) if inc['incomeType'] == 'FUNDING_FEE']
                            if funding_records:
                                funding_count = len(funding_records)
                                positive_funding = sum(float(inc['income']) for inc in funding_records if float(inc['income']) > 0)
                                negative_funding = sum(float(inc['income']) for inc in funding_records if float(inc['income']) < 0)
                                
                                # 計算資金費率（資金費 ÷ 持倉價值）
                                total_funding_fee = detail['funding_fee']
                                funding_rate_percentage = (total_funding_fee / position_value * 100) if position_value > 0 else 0
                                
                                funding_details = f"\n💰 <b>資金費詳細</b>\n"
                                funding_details += f"資金費次數: {funding_count}\n"
                                if positive_funding > 0:
                                    funding_details += f"  ↗️ 收入: +{positive_funding:.4f} USDT\n"
                                if negative_funding < 0:
                                    funding_details += f"  ↘️ 支出: {negative_funding:.4f} USDT\n"
                                funding_details += f"資金費總計: {detail['funding_fee']:.4f} USDT\n"
                                funding_details += f"資金費率: {funding_rate_percentage:.4f}% (資金費/持倉價值)"
                            else:
                                funding_details = f"\n💰 <b>資金費詳細</b>\n資金費: {detail['funding_fee']:.4f} USDT (無記錄)\n資金費率: 0.0000%"
                            
                            # 計算完整的收益分解
                            program_pnl = pnl
                            actual_pnl = detail['realized_pnl'] 
                            commission = detail['commission']
                            funding_fee = detail['funding_fee']
                            net_profit = detail['net_profit']
                            
                            # 計算理論淨利 = 程式盈虧 + 資金費 - 手續費
                            theoretical_net = program_pnl + funding_fee - commission
                            
                            msg = (
                                f"📊 <b>單筆真實收益分析</b> (⚡極速平倉)\n\n"
                                f"<b>交易對:</b> {detail['symbol']}\n"
                                f"<b>方向:</b> {detail['direction'].upper()}\n"
                                f"<b>數量:</b> {quantity:,}\n"
                                f"<b>倉位價值:</b> {position_value:.2f} USDT\n"
                                f"<b>保證金:</b> {margin_used:.2f} USDT\n"
                                f"<b>槓桿:</b> {LEVERAGE}x\n\n"
                                f"⏰ <b>時間資訊</b>\n"
                                f"<b>開倉時間:</b> {datetime.fromtimestamp(detail['entry_time']/1000).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n"
                                f"<b>平倉時間:</b> {datetime.fromtimestamp(detail['exit_time']/1000).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n"
                                f"<b>持倉時間:</b> {position_duration}秒\n"
                                f"{funding_details}\n\n"
                                f"📈 <b>收益分析</b>\n"
                                f"<b>程式盈虧:</b> {program_pnl:.4f} USDT (理論價差收益)\n"
                                f"<b>帳戶實際盈虧:</b> {actual_pnl:.4f} USDT\n"
                                f"<b>資金費收入:</b> +{funding_fee:.4f} USDT\n"
                                f"<b>手續費成本:</b> -{commission:.4f} USDT\n"
                                f"<b>理論淨利:</b> {theoretical_net:.4f} USDT (程式盈虧+資金費-手續費)\n"
                                f"<b>帳戶淨利:</b> {net_profit:.4f} USDT\n"
                                f"<b>報酬率:</b> {return_rate:.2f}% (淨利/保證金)\n\n"
                                f"<b>差異分析:</b> {net_profit - theoretical_net:.4f} USDT (帳戶-理論)\n"
                                f"<b>程式vs帳戶:</b> {net_profit - program_pnl:.4f} USDT"
                            )
                            from profit_tracker import ProfitTracker
                            ProfitTracker().send_telegram_message(msg)
                            print(f"[{self.format_corrected_time()}] 極速平倉詳細分析報告已發送: {symbol}")
                    except Exception as analysis_e:
                        print(f"[{self.format_corrected_time()}] 極速平倉詳細分析報告發送失敗: {analysis_e}")
                
                # 60秒後發送詳細分析報告
                import threading
                threading.Timer(60, send_detailed_analysis).start()
                
                print(f"[{self.format_corrected_time()}] 延後處理完成: {symbol} 盈虧:{pnl:.4f} USDT 持倉:{position_duration}秒")
            except Exception as e:
                print(f"[{self.format_corrected_time()}] 延後處理失敗: {e}")
        
        # 在1秒後執行延後處理，避免影響後續交易
        print(f"[{self.format_corrected_time()}] 延後處理已安排，將在1秒後執行: {symbol}")
        threading.Timer(1.0, post_process).start()
    
    def close_position_with_retry(self):
        """帶重試機制的完整平倉"""
        # 這裡使用原來的完整平倉邏輯
        return self.close_position_original()
    
    def close_position_minimal(self):
        """極簡平倉 - 不重試，一次搞定，適合高頻檢查策略"""
        if not self.current_position:
            return False
            
        symbol = self.current_position['symbol']
        direction = self.current_position['direction']
        quantity = self.current_position['quantity']
        entry_price = self.current_position.get('entry_price', 0.0)
        funding_rate = self.current_position.get('funding_rate', 0.0)
        
        # 📝 記錄極簡平倉開始
        self.write_trade_analysis('minimal_close_start', symbol,
                                close_method='極簡平倉',
                                direction=direction,
                                quantity=quantity,
                                entry_price=entry_price,
                                funding_rate=funding_rate,
                                strategy='不重試，一次成功或失敗',
                                optimization_level='最高速度')
        
        self.record_close_step('close_start', symbol=symbol, direction=direction, quantity=quantity)
        
        try:
            print(f"[{self.format_corrected_time()}] 🎯極簡平倉: {symbol} {direction} {quantity}")
            
            # 直接發送平倉訂單，不做任何檢查
            side = 'SELL' if direction == 'long' else 'BUY'
            
            # 📝 記錄訂單準備
            self.write_trade_analysis('minimal_close_prepare', symbol,
                                    action='準備發送訂單',
                                    side=side,
                                    order_type='MARKET',
                                    reduce_only=True,
                                    no_checks='跳過所有驗證以提高速度')
            
            start_time = time.time()
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type='MARKET',
                quantity=quantity,
                reduceOnly=True
            )
            execution_time = int((time.time() - start_time) * 1000)
            
            # 📝 記錄訂單成功
            order_id = order.get('orderId', 'N/A')
            executed_qty = order.get('executedQty', '0')
            avg_price = order.get('avgPrice', '0.0')
            
            self.write_trade_analysis('minimal_close_order_success', symbol,
                                    order_id=order_id,
                                    execution_time_ms=execution_time,
                                    executed_qty=executed_qty,
                                    avg_price=avg_price,
                                    api_response_time=f'{execution_time}ms',
                                    order_status='已發送')
            
            print(f"[{self.format_corrected_time()}] ✅極簡平倉成功: {symbol} ID:{order_id} | {execution_time}ms")
            
            # 📝 計算並記錄交易總結
            exit_price = float(avg_price) if avg_price and avg_price != '0.0' else entry_price
            pnl = 0.0
            if entry_price > 0 and exit_price > 0:
                if direction == 'long':
                    pnl = (exit_price - entry_price) * float(quantity)
                else:
                    pnl = (entry_price - exit_price) * float(quantity)
            
            position_duration = int(time.time() - self.position_open_time) if self.position_open_time else 0
            
            # 📝 記錄極簡平倉完成
            self.write_trade_analysis('minimal_close_complete', symbol,
                                    direction=direction,
                                    quantity=quantity,
                                    entry_price=entry_price,
                                    exit_price=exit_price,
                                    pnl=pnl,
                                    funding_rate=funding_rate,
                                    position_duration_seconds=position_duration,
                                    execution_time_ms=execution_time,
                                    order_id=order_id,
                                    close_method='極簡平倉',
                                    retry_count=0,
                                    total_checks=0,
                                    processing_type='即時清理')
            
            # 📝 記錄超詳細平倉分析
            self.record_detailed_close_analysis(symbol, order)
            
            self.record_close_step('close_success', symbol=symbol, 
                                 order_id=order_id, 
                                 executed_qty=executed_qty, 
                                 avg_price=avg_price,
                                 execution_time_ms=execution_time)
            
            # 📝 記錄到交易事件日誌
            self.log_trade_event('close_success', symbol, {
                'direction': direction,
                'quantity': quantity,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'pnl': pnl,
                'order_id': order_id,
                'execution_time_ms': execution_time,
                'close_method': 'minimal'
            })
            
            # 立即清理，不做延後處理
            self.current_position = None
            self.position_open_time = None
            self.is_closing = False
            
            return True
            
        except Exception as e:
            # 📝 記錄極簡平倉失敗
            self.write_trade_analysis('minimal_close_failed', symbol,
                                    error=str(e),
                                    direction=direction,
                                    quantity=quantity,
                                    close_method='極簡平倉',
                                    retry_attempt=False,
                                    cleanup_action='直接清理倉位記錄')
            
            self.record_close_step('close_failed', symbol=symbol, error=str(e))
            
            # 📝 記錄到交易事件日誌
            self.log_trade_event('close_failed', symbol, {
                'error': str(e),
                'direction': direction,
                'quantity': quantity,
                'close_method': 'minimal'
            })
            
            print(f"[{self.format_corrected_time()}] ❌極簡平倉失敗: {symbol} - {e}")
            
            # 失敗就失敗，不重試，直接清理
            self.current_position = None
            self.position_open_time = None
            self.is_closing = False
            
            return False
    
    def close_position(self):
        """平倉 - 根據配置選擇最佳平倉方式"""
        symbol = self.current_position['symbol'] if self.current_position else 'UNKNOWN'
        
        # 如果重試次數設為0，使用極簡平倉
        if hasattr(self, 'max_close_retry') and self.max_close_retry == 0:
            return self.close_position_minimal()
        # 如果CLOSE_AFTER_SECONDS <= 0.05，使用極簡平倉
        elif hasattr(self, 'close_after_seconds') and self.close_after_seconds <= 0.05:
            return self.close_position_minimal()
        # 如果CLOSE_AFTER_SECONDS <= 0.1，使用超級極速版本（結算後快速平倉）
        elif hasattr(self, 'close_after_seconds') and self.close_after_seconds <= 0.1:
            return self.close_position_ultra_fast()
        else:
            # 使用完整平倉模式
            return self.close_position_original()
    
    def close_position_original(self):
        """完整平倉 - 包含所有檢查和日誌"""
        if not self.current_position:
            return
            
        symbol = self.current_position['symbol']
        direction = self.current_position['direction']
        quantity = self.current_position['quantity']
        
        # 記錄完整平倉開始
        self.write_trade_analysis('complete_close_start', symbol,
                                close_method='完整平倉',
                                direction=direction,
                                quantity=quantity,
                                retry_count=self.close_retry_count,
                                trigger_reason='時間觸發或手動',
                                includes_features=['倉位檢查', '價格獲取', '重試機制', '詳細日誌'])
        
        try:
            # 步驟1: 決定是否檢查實際倉位
            step_num = 1
            if self.close_retry_count > 0:
                # 重試情況 - 需要檢查實際倉位
                self.write_trade_analysis('complete_close_step_retry_check', symbol,
                                        step_number=step_num,
                                        action='重試模式 - 檢查實際倉位',
                                        retry_count=self.close_retry_count,
                                        reason='重試平倉需要確認實際倉位狀況')
                
                print(f"[{self.format_corrected_time()}] 重試平倉，檢查實際倉位狀況...")
                self.log_trade_step('close', symbol, 'retry_position_check', {'retry_count': self.close_retry_count})
                
                step_num += 1
                # 步驟2: API 調用檢查倉位
                self.write_trade_analysis('complete_close_step_api_position_check', symbol,
                                        step_number=step_num,
                                        action='API調用 - 檢查倉位',
                                        api_method='check_actual_position')
                
                actual_position = self.check_actual_position(symbol)
                
                step_num += 1
                if not actual_position:
                    # 步驟3a: 無倉位情況
                    self.write_trade_analysis('complete_close_step_no_position', symbol,
                                            step_number=step_num,
                                            action='倉位檢查結果 - 無倉位',
                                            result='已無持倉，結束平倉流程',
                                            cleanup_actions=['清空current_position', '重置retry_count', '重置is_closing'])
                    
                    print(f"[{self.format_corrected_time()}] 倉位檢查: {symbol} 已無持倉，無需平倉")
                    self.log_trade_step('close', symbol, 'position_not_found', {})
                    # 清空持倉記錄
                    self.current_position = None
                    self.position_open_time = None
                    self.close_retry_count = 0
                    self.is_closing = False
                    return
                
                # 步驟3b: 檢查倉位一致性
                self.write_trade_analysis('complete_close_step_position_validation', symbol,
                                        step_number=step_num,
                                        action='倉位一致性檢查',
                                        expected_direction=direction,
                                        actual_direction=actual_position['direction'],
                                        expected_quantity=quantity,
                                        actual_quantity=actual_position['quantity'])
                
                # 檢查倉位方向是否一致
                if actual_position['direction'] != direction:
                    step_num += 1
                    self.write_trade_analysis('complete_close_step_direction_fix', symbol,
                                            step_number=step_num,
                                            action='修正倉位方向',
                                            expected=direction,
                                            actual=actual_position['direction'],
                                            action_taken='更新本地記錄')
                    
                    print(f"[{self.format_corrected_time()}] 倉位檢查: {symbol} 方向不一致，預期:{direction}，實際:{actual_position['direction']}")
                    self.log_trade_step('close', symbol, 'direction_mismatch', safe_json_serialize({
                        'expected': direction,
                        'actual': actual_position['direction']
                    }))
                    # 更新持倉記錄
                    self.current_position['direction'] = actual_position['direction']
                    direction = actual_position['direction']
                
                # 檢查倉位數量是否一致
                if abs(actual_position['quantity'] - quantity) > 0.001:  # 允許小數點誤差
                    step_num += 1
                    self.write_trade_analysis('complete_close_step_quantity_fix', symbol,
                                            step_number=step_num,
                                            action='修正倉位數量',
                                            expected=quantity,
                                            actual=actual_position['quantity'],
                                            difference=abs(actual_position['quantity'] - quantity),
                                            action_taken='更新本地記錄')
                    
                    print(f"[{self.format_corrected_time()}] 倉位檢查: {symbol} 數量不一致，預期:{quantity}，實際:{actual_position['quantity']}")
                    self.log_trade_step('close', symbol, 'quantity_mismatch', safe_json_serialize({
                        'expected': quantity,
                        'actual': actual_position['quantity']
                    }))
                    # 更新持倉記錄
                    self.current_position['quantity'] = actual_position['quantity']
                    quantity = actual_position['quantity']
            else:
                # 首次平倉情況
                self.write_trade_analysis('complete_close_step_first_attempt', symbol,
                                        step_number=step_num,
                                        action='首次平倉 - 使用開倉記錄',
                                        direction=direction,
                                        quantity=quantity,
                                        reason='首次平倉信任開倉記錄，跳過倉位檢查')
                
                # 第一次平倉，直接使用開倉記錄
                print(f"[{self.format_corrected_time()}] 第一次平倉，使用開倉記錄: {symbol} {direction} {quantity}")
                self.log_trade_step('close', symbol, 'first_close', safe_json_serialize({
                    'direction': direction,
                    'quantity': quantity
                }))
            
            # 記錄平倉開始
            step_num += 1
            self.write_trade_analysis('complete_close_step_start_process', symbol,
                                    step_number=step_num,
                                    action='開始平倉流程',
                                    validated_direction=direction,
                                    validated_quantity=quantity)
            
            self.record_close_step('close_start', symbol=symbol, direction=direction, quantity=quantity)
            
            # 步驟N: 獲取當前價格
            step_num += 1
            self.write_trade_analysis('complete_close_step_fetch_price_start', symbol,
                                    step_number=step_num,
                                    action='開始獲取當前價格',
                                    api_method='futures_symbol_ticker',
                                    reason='完整平倉需要準確價格用於記錄和計算')
            
            print(f"[{self.format_corrected_time()}] 獲取平倉價格: {symbol}")
            self.log_trade_step('close', symbol, 'fetch_close_price_start', {})
            
            price_start_time = time.time()
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            price_end_time = time.time()
            price_fetch_time_ms = int((price_end_time - price_start_time) * 1000)
            current_price = float(ticker['price'])
            
            step_num += 1
            self.write_trade_analysis('complete_close_step_fetch_price_success', symbol,
                                    step_number=step_num,
                                    action='價格獲取成功',
                                    current_price=current_price,
                                    fetch_time_ms=price_fetch_time_ms,
                                    ticker_response=safe_json_serialize(ticker))
            
            print(f"[{self.format_corrected_time()}] 平倉價格: {symbol} = {current_price}")
            self.log_trade_step('close', symbol, 'fetch_close_price_success', safe_json_serialize({'price': current_price}))
            
            # 記錄價格獲取時間
            self.record_close_step('close_price_fetched', symbol=symbol, price=current_price)
            
            # 步驟N+1: 確定平倉方向
            step_num += 1
            side = 'SELL' if direction == 'long' else 'BUY'
            self.write_trade_analysis('complete_close_step_determine_side', symbol,
                                    step_number=step_num,
                                    action='確定平倉方向',
                                    position_direction=direction,
                                    close_side=side,
                                    logic=f'持倉方向 {direction} -> 平倉方向 {side}')
            
            # 步驟N+2: 準備訂單參數
            step_num += 1
            order_params = {
                'symbol': symbol,
                'side': side,
                'type': 'MARKET',
                'quantity': quantity,
                'reduceOnly': True
            }
            self.write_trade_analysis('complete_close_step_prepare_order', symbol,
                                    step_number=step_num,
                                    action='準備平倉訂單參數',
                                    order_params=order_params,
                                    current_price=current_price)
            
            print(f"[{self.format_corrected_time()}] 準備發送平倉訂單: {symbol} {side} {quantity}")
            self.log_trade_step('close', symbol, 'prepare_close_order', safe_json_serialize({
                'side': side, 
                'quantity': quantity, 
                'type': 'MARKET'
            }))
            
            # 步驟N+3: 發送平倉訂單
            step_num += 1
            self.write_trade_analysis('complete_close_step_send_order_start', symbol,
                                    step_number=step_num,
                                    action='開始發送平倉訂單',
                                    api_method='futures_create_order',
                                    order_params=order_params)
            
            print(f"[{self.format_corrected_time()}] 發送平倉訂單: {symbol} {side} {quantity}")
            self.log_trade_step('close', symbol, 'send_close_order_start', safe_json_serialize({
                'side': side, 
                'quantity': quantity, 
                'type': 'MARKET'
            }))
            
            order_start_time = time.time()
            # 使用超時處理的API調用
            order = self.execute_api_call_with_timeout(
                self.client.futures_create_order,
                timeout=12,  # 完整平倉允許更長超時
                max_retries=3,  # 完整平倉重試3次
                **order_params
            )
            order_end_time = time.time()
            execution_time_ms = int((order_end_time - order_start_time) * 1000)
            
            step_num += 1
            self.write_trade_analysis('complete_close_step_order_response', symbol,
                                    step_number=step_num,
                                    action='平倉訂單回傳成功',
                                    execution_time_ms=execution_time_ms,
                                    order_response=safe_json_serialize(order),
                                    order_id=order['orderId'],
                                    executed_qty=order.get('executedQty', 'N/A'),
                                    avg_price=order.get('avgPrice', 'N/A'))
            
            print(f"[{self.format_corrected_time()}] 平倉訂單發送完成: {symbol} 訂單ID:{order['orderId']} 執行時間:{execution_time_ms}ms")
            self.log_trade_step('close', symbol, 'send_close_order_success', safe_json_serialize({
                'order_id': order['orderId'],
                'execution_time_ms': execution_time_ms,
                'executed_qty': order['executedQty'],
                'avg_price': order['avgPrice']
            }))
            
            # 記錄訂單發送時間
            self.record_close_step('close_order_sent', symbol=symbol, 
                                 order_id=order['orderId'],
                                 order_time_ms=execution_time_ms)
            
            # 記錄平倉成功
            self.record_close_step('close_success', symbol=symbol, 
                                 order_id=order['orderId'],
                                 executed_qty=order['executedQty'],
                                 avg_price=order['avgPrice'])
            
            # 計算盈虧
            entry_price = self.current_position['entry_price']
            pnl = (current_price - entry_price) * quantity if direction == 'long' else (entry_price - current_price) * quantity
            print(f"[{self.format_corrected_time()}] 計算盈虧: 開倉價:{entry_price} 平倉價:{current_price} 盈虧:{pnl:.2f} USDT")
            self.log_trade_step('close', symbol, 'pnl_calculation', safe_json_serialize({
                'entry_price': entry_price,
                'exit_price': current_price,
                'pnl': pnl,
                'direction': direction,
                'quantity': quantity
            }))
            
            # 注意：交易事件將在延後處理中記錄，避免重複
            
            # 添加收益追蹤
            trade_data = {
                'symbol': symbol,
                'direction': direction,
                'quantity': quantity,
                'entry_price': entry_price,
                'exit_price': current_price,
                'pnl': pnl,
                'funding_rate': self.current_position.get('funding_rate', 0.0),
                'execution_time_ms': execution_time_ms,
                'position_duration_seconds': int(time.time() - self.position_open_time),
                'retry_count': self.close_retry_count,
                'order_id': order['orderId'],
                # 添加精確的時間戳
                'entry_timestamp': int(self.position_open_time * 1000),  # 進倉時間戳
                'exit_timestamp': int(time.time() * 1000)  # 平倉時間戳
            }
            self.profit_tracker.add_trade(trade_data)
            
            # 📝 記錄超詳細平倉分析
            self.record_detailed_close_analysis(symbol, order)

            # 平倉後自動推送單筆帳戶分析到TG（延遲1分鐘）
            def send_trade_account_analysis(trade_data):
                from account_analyzer import AccountAnalyzer
                from config import LEVERAGE
                analyzer = AccountAnalyzer()
                period = [{
                    'symbol': trade_data['symbol'],
                    'entry_time': trade_data['entry_timestamp'],
                    'exit_time': trade_data['exit_timestamp'],
                    'direction': trade_data['direction'],
                    'quantity': trade_data['quantity']
                }]
                result = analyzer.analyze_trades_by_time_range(period)
                if result and result['trades_by_period']:
                    detail = result['trades_by_period'][0]
                    
                    # 計算倉位和保證金資訊
                    position_value = trade_data['quantity'] * trade_data['entry_price']
                    margin_used = position_value / LEVERAGE
                    
                    # 計算報酬率（淨利 / 保證金）
                    return_rate = (detail['net_profit'] / margin_used * 100) if margin_used > 0 else 0
                    
                    # 分析資金費詳細數據
                    funding_details = ""
                    funding_records = [inc for inc in detail.get('income_records', []) if inc['incomeType'] == 'FUNDING_FEE']
                    if funding_records:
                        funding_count = len(funding_records)
                        positive_funding = sum(float(inc['income']) for inc in funding_records if float(inc['income']) > 0)
                        negative_funding = sum(float(inc['income']) for inc in funding_records if float(inc['income']) < 0)
                        
                        # 計算資金費率（資金費 ÷ 持倉價值）
                        total_funding_fee = detail['funding_fee']
                        funding_rate_percentage = (total_funding_fee / position_value * 100) if position_value > 0 else 0
                        
                        funding_details = f"\n💰 <b>資金費詳細</b>\n"
                        funding_details += f"資金費次數: {funding_count}\n"
                        if positive_funding > 0:
                            funding_details += f"  ↗️ 收入: +{positive_funding:.4f} USDT\n"
                        if negative_funding < 0:
                            funding_details += f"  ↘️ 支出: {negative_funding:.4f} USDT\n"
                        funding_details += f"資金費總計: {detail['funding_fee']:.4f} USDT\n"
                        funding_details += f"資金費率: {funding_rate_percentage:.4f}% (資金費/持倉價值)"
                    else:
                        funding_details = f"\n💰 <b>資金費詳細</b>\n資金費: {detail['funding_fee']:.4f} USDT (無記錄)\n資金費率: 0.0000%"
                    
                    # 計算完整的收益分解
                    program_pnl = trade_data['pnl']
                    actual_pnl = detail['realized_pnl'] 
                    commission = detail['commission']
                    funding_fee = detail['funding_fee']
                    net_profit = detail['net_profit']
                    
                    # 計算理論淨利 = 程式盈虧 + 資金費 - 手續費
                    theoretical_net = program_pnl + funding_fee - commission
                    
                    msg = (
                        f"📊 <b>單筆真實收益分析</b>\n\n"
                        f"<b>交易對:</b> {detail['symbol']}\n"
                        f"<b>方向:</b> {detail['direction'].upper()}\n"
                        f"<b>數量:</b> {trade_data['quantity']:,}\n"
                        f"<b>倉位價值:</b> {position_value:.2f} USDT\n"
                        f"<b>保證金:</b> {margin_used:.2f} USDT\n"
                        f"<b>槓桿:</b> {LEVERAGE}x\n\n"
                        f"⏰ <b>時間資訊</b>\n"
                        f"<b>開倉時間:</b> {datetime.fromtimestamp(detail['entry_time']/1000).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n"
                        f"<b>平倉時間:</b> {datetime.fromtimestamp(detail['exit_time']/1000).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n"
                        f"<b>持倉時間:</b> {trade_data['position_duration_seconds']}秒\n"
                        f"{funding_details}\n\n"
                        f"📈 <b>收益分析</b>\n"
                        f"<b>程式盈虧:</b> {program_pnl:.4f} USDT (理論價差收益)\n"
                        f"<b>帳戶實際盈虧:</b> {actual_pnl:.4f} USDT\n"
                        f"<b>資金費收入:</b> +{funding_fee:.4f} USDT\n"
                        f"<b>手續費成本:</b> -{commission:.4f} USDT\n"
                        f"<b>理論淨利:</b> {theoretical_net:.4f} USDT (程式盈虧+資金費-手續費)\n"
                        f"<b>帳戶淨利:</b> {net_profit:.4f} USDT\n"
                        f"<b>報酬率:</b> {return_rate:.2f}% (淨利/保證金)\n\n"
                        f"<b>差異分析:</b> {net_profit - theoretical_net:.4f} USDT (帳戶-理論)\n"
                        f"<b>程式vs帳戶:</b> {net_profit - program_pnl:.4f} USDT"
                    )
                    from profit_tracker import ProfitTracker
                    ProfitTracker().send_telegram_message(msg)
            threading.Timer(60, send_trade_account_analysis, args=(trade_data,)).start()
            
            print(f"[{self.format_corrected_time()}] 平倉成功] {symbol} {direction} 數量:{quantity} 價格:{current_price} 盈虧:{pnl:.2f} USDT (重試次數:{self.close_retry_count})")
            self.log_trade_step('close', symbol, 'close_complete', safe_json_serialize({
                'direction': direction,
                'quantity': quantity,
                'price': current_price,
                'pnl': pnl,
                'order_id': order['orderId'],
                'retry_count': self.close_retry_count
            }))
            
            # 顯示詳細時間記錄
            self.print_detailed_timestamps(symbol)
            
            # 清空持倉記錄
            self.current_position = None
            self.position_open_time = None
            
            # 重置鎖定時間，但保持結算時間記錄
            self.entry_locked_until = time.time() + 1.0  # 鎖定1秒，防止立即重複進場
            # 注意：詳細的平倉記錄將在延後處理中完成，避免重複記錄
            
            # 重置平倉重試計數器
            self.close_retry_count = 0
            self.close_retry_start_time = 0
            self.is_closing = False
            
        except Exception as e:
            # 記錄平倉失敗
            self.record_close_step('close_failed', symbol=symbol, error=str(e))
            self.log_trade_event('close_failed', symbol, {'error': str(e)})
            self.log_trade_step('close', symbol, 'close_failed', {'error': str(e)})
            print(f"[{self.format_corrected_time()}] 平倉失敗] {symbol} {direction} 原因: {e}")
            
            # 初始化重試機制
            if self.close_retry_count == 0:
                self.close_retry_start_time = time.time()
                print(f"[{self.format_corrected_time()}] 開始平倉重試機制")
                self.log_trade_step('close', symbol, 'retry_start', {})
            
            self.close_retry_count += 1
            print(f"[{self.format_corrected_time()}] 平倉重試 {self.close_retry_count}/{self.max_close_retry}")
            self.log_trade_step('close', symbol, 'retry_attempt', safe_json_serialize({
                'retry_count': self.close_retry_count,
                'max_retry': self.max_close_retry
            }))
            
            # 如果重試次數未達上限，則繼續重試
            if self.close_retry_count < self.max_close_retry:
                print(f"[{self.format_corrected_time()}] 等待 {self.close_retry_interval} 秒後重試平倉...")
                self.log_trade_step('close', symbol, 'retry_wait', safe_json_serialize({
                    'wait_seconds': self.close_retry_interval
                }))
                time.sleep(self.close_retry_interval)
                # 重新嘗試平倉
                self.close_position()
            else:
                print(f"[{self.format_corrected_time()}] 平倉重試次數已達上限，嘗試強制平倉")
                self.log_trade_step('close', symbol, 'retry_max_reached', {})
                self.force_close_position()

    def check_actual_position(self, symbol: str) -> dict:
        """檢查實際倉位狀況"""
        try:
            # 獲取當前持倉信息
            positions = self.client.futures_position_information()
            
            for pos in positions:
                if pos['symbol'] == symbol:
                    position_amt = float(pos['positionAmt'])
                    
                    # 如果沒有持倉
                    if abs(position_amt) < 0.001:  # 允許小數點誤差
                        return None
                    
                    # 安全地獲取倉位信息，處理可能的鍵缺失
                    try:
                        entry_price = float(pos.get('entryPrice', 0))
                        unrealized_pnl = float(pos.get('unRealizedProfit', 0))
                        margin_type = pos.get('marginType', 'unknown')
                        isolated_margin = float(pos.get('isolatedMargin', 0)) if margin_type == 'isolated' else 0
                    except (KeyError, ValueError, TypeError) as e:
                        print(f"[{self.format_corrected_time()}] 解析倉位數據時出現問題: {e}")
                        print(f"[{self.format_corrected_time()}] 原始數據: {pos}")
                        # 即使解析失敗，只要有持倉數量就返回基本信息
                        return {
                            'symbol': symbol,
                            'direction': 'long' if position_amt > 0 else 'short',
                            'quantity': abs(position_amt),
                            'entry_price': 0,
                            'unrealized_pnl': 0,
                            'margin_type': 'unknown',
                            'isolated_margin': 0
                        }
                    
                    # 返回實際倉位信息
                    return {
                        'symbol': symbol,
                        'direction': 'long' if position_amt > 0 else 'short',
                        'quantity': abs(position_amt),
                        'entry_price': entry_price,
                        'unrealized_pnl': unrealized_pnl,
                        'margin_type': margin_type,
                        'isolated_margin': isolated_margin
                    }
            
            # 如果找不到該交易對的持倉
            return None
            
        except Exception as e:
            print(f"[{self.format_corrected_time()}] 檢查實際倉位失敗: {e}")
            print(f"[{self.format_corrected_time()}] 錯誤詳情: {traceback.format_exc()}")
            # 不要因為API錯誤就認為沒有持倉，返回None讓調用方決定
            return None

    def force_close_position(self):
        """強制平倉 - 使用市價單強制平倉，包含詳細分析記錄"""
        if not self.current_position:
            return
            
        symbol = self.current_position['symbol']
        direction = self.current_position['direction']
        quantity = self.current_position['quantity']
        entry_price = self.current_position.get('entry_price', 0.0)
        funding_rate = self.current_position.get('funding_rate', 0.0)
        
        try:
            # 記錄強制平倉開始時間和狀況
            force_close_start_time = time.time()
            corrected_time_ms = self.get_corrected_time()
            
            print(f"[{self.format_corrected_time()}] 🚨開始強制平倉，檢查實際倉位狀況...")
            
            # 獲取市場狀況
            try:
                book_ticker = self.book_tickers.get(symbol, {})
                bid_price = float(book_ticker.get('bidPrice', 0))
                ask_price = float(book_ticker.get('askPrice', 0))
                spread_amount = ask_price - bid_price if bid_price and ask_price else 0
                spread_percentage = (spread_amount / ask_price * 100) if ask_price > 0 else 0
                market_liquidity = "優良" if spread_percentage < 0.05 else "正常" if spread_percentage < 0.1 else "較差" if spread_percentage < 0.2 else "很差"
            except:
                bid_price = ask_price = spread_amount = spread_percentage = 0
                market_liquidity = "未知"
            
            # 記錄強制平倉開始（含詳細分析）
            self.write_trade_analysis('force_close_detailed_start', symbol, 
                                    close_method='強制平倉',
                                    trigger_reason='重試次數達上限',
                                    initial_position={
                                        'direction': direction,
                                        'quantity': quantity,
                                        'entry_price': entry_price,
                                        'funding_rate': funding_rate
                                    },
                                    system_status={
                                        'retry_count': self.close_retry_count,
                                        'max_retry': self.max_close_retry,
                                        'retry_duration_seconds': int(time.time() - self.close_retry_start_time) if self.close_retry_start_time else 0,
                                        'corrected_time_ms': corrected_time_ms
                                    },
                                    market_conditions={
                                        'bid_price': bid_price,
                                        'ask_price': ask_price,
                                        'spread_percentage': f"{spread_percentage:.4f}%",
                                        'liquidity_status': market_liquidity
                                    })
            
            # 檢查實際倉位狀況
            position_check_start = time.time()
            actual_position = self.check_actual_position(symbol)
            position_check_time_ms = int((time.time() - position_check_start) * 1000)
            
            if not actual_position:
                print(f"[{self.format_corrected_time()}] 強制平倉檢查: {symbol} 已無持倉，無需強制平倉")
                self.write_trade_analysis('force_close_no_position_detailed', symbol,
                                        check_result='無持倉',
                                        position_check_time_ms=position_check_time_ms,
                                        cleanup_actions=['清空持倉記錄', '重置重試計數器', '解除平倉鎖定'])
                # 清空持倉記錄
                self.current_position = None
                self.position_open_time = None
                self.close_retry_count = 0
                self.is_closing = False
                return
            
            # 比較預期vs實際倉位
            position_diff_analysis = {
                'expected_direction': direction,
                'actual_direction': actual_position['direction'],
                'expected_quantity': quantity,
                'actual_quantity': actual_position['quantity'],
                'direction_match': direction == actual_position['direction'],
                'quantity_match': abs(quantity - actual_position['quantity']) < 0.001,
                'has_discrepancy': direction != actual_position['direction'] or abs(quantity - actual_position['quantity']) >= 0.001
            }
            
            # 使用實際倉位信息
            direction = actual_position['direction']
            quantity = actual_position['quantity']
            
            print(f"[{self.format_corrected_time()}] 🎯強制平倉確認: {symbol} {direction} {quantity} | 倉位檢查:{position_check_time_ms}ms | 流動性:{market_liquidity}")
            
            # 記錄倉位檢查結果
            self.write_trade_analysis('force_close_position_validated', symbol,
                                    position_check_time_ms=position_check_time_ms,
                                    actual_position=actual_position,
                                    position_comparison=position_diff_analysis,
                                    will_use_actual_position=True)
            
            # 確定平倉方向（與開倉相反）
            side = 'SELL' if direction == 'long' else 'BUY'
            
            # 準備強制平倉訂單
            order_params = {
                'symbol': symbol,
                'side': side,
                'type': 'MARKET',
                'quantity': quantity,
                'reduceOnly': True
            }
            
            # 執行強制平倉
            order_start_time = time.time()
            order = self.client.futures_create_order(**order_params)
            order_end_time = time.time()
            execution_time_ms = int((order_end_time - order_start_time) * 1000)
            total_force_close_time_ms = int((order_end_time - force_close_start_time) * 1000)
            
            # 提取訂單詳細信息
            order_id = order.get('orderId', 'UNKNOWN')
            executed_qty = order.get('executedQty', quantity)
            avg_price = float(order.get('avgPrice', 0)) if order.get('avgPrice') else 0
            order_status = order.get('status', 'UNKNOWN')
            
            # 計算強制平倉效果
            if avg_price > 0:
                if direction == 'long':
                    slippage = ((bid_price - avg_price) / bid_price * 100) if bid_price > 0 else 0
                else:
                    slippage = ((avg_price - ask_price) / ask_price * 100) if ask_price > 0 else 0
                
                execution_quality = "優秀" if abs(slippage) < 0.02 else "良好" if abs(slippage) < 0.1 else "普通" if abs(slippage) < 0.2 else "較差"
            else:
                slippage = 0
                execution_quality = "未知"
            
            print(f"[{self.format_corrected_time()}] ✅強制平倉成功: {symbol} ID:{order_id} | API:{execution_time_ms}ms | 總計:{total_force_close_time_ms}ms | 成交:{avg_price} | 滑點:{slippage:.4f}%")
            
            # 記錄強制平倉成功（含詳細分析）
            self.write_trade_analysis('force_close_detailed_success', symbol, 
                                    order_id=order_id,
                                    close_method='強制平倉',
                                    execution_result={
                                        'order_status': order_status,
                                        'executed_qty': executed_qty,
                                        'avg_price': avg_price,
                                        'side_executed': order.get('side', side)
                                    },
                                    performance_metrics={
                                        'api_response_time_ms': execution_time_ms,
                                        'total_process_time_ms': total_force_close_time_ms,
                                        'position_check_time_ms': position_check_time_ms,
                                        'execution_quality': execution_quality
                                    },
                                    market_execution_analysis={
                                        'slippage_percentage': f"{slippage:.4f}%",
                                        'expected_vs_actual': f"預期 vs 實際成交價格差異分析",
                                        'market_impact': "市價單對市場流動性的影響",
                                        'liquidity_consumption': market_liquidity
                                    },
                                    retry_context={
                                        'retry_count': self.close_retry_count,
                                        'max_retry': self.max_close_retry,
                                        'retry_duration_seconds': int(time.time() - self.close_retry_start_time) if self.close_retry_start_time else 0,
                                        'previous_attempts': '前次嘗試均失敗，觸發強制平倉'
                                    },
                                    position_reconciliation={
                                        'original_entry_price': entry_price,
                                        'actual_entry_price': actual_position['entry_price'],
                                        'unrealized_pnl': actual_position['unrealized_pnl'],
                                        'margin_type': actual_position.get('margin_type', 'unknown'),
                                        'position_accuracy': '已驗證' if not position_diff_analysis['has_discrepancy'] else '發現差異'
                                    })
            
            # 記錄強制平倉事件
            self.log_trade_event('force_close_success', symbol, {
                'direction': direction,
                'quantity': quantity,
                'order_id': order_id,
                'retry_count': self.close_retry_count,
                'actual_entry_price': actual_position['entry_price'],
                'unrealized_pnl': actual_position['unrealized_pnl'],
                'execution_time_ms': execution_time_ms,
                'total_time_ms': total_force_close_time_ms
            })
            
            # 📝 記錄超詳細平倉分析
            self.record_detailed_close_analysis(symbol, order)
            
            # 清空持倉記錄
            self.current_position = None
            self.position_open_time = None
            self.close_retry_count = 0
            self.is_closing = False
            
        except Exception as e:
            error_time = time.time()
            total_error_time_ms = int((error_time - force_close_start_time) * 1000)
            
            print(f"[{self.format_corrected_time()}] ❌強制平倉失敗: {symbol} - {e} | 耗時:{total_error_time_ms}ms")
            
            # 詳細記錄強制平倉失敗（包含完整的錯誤分析）
            self.write_trade_analysis('force_close_detailed_failed', symbol, 
                                    error=str(e),
                                    error_type=type(e).__name__,
                                    close_method='強制平倉',
                                    failure_analysis={
                                        'total_time_before_error_ms': total_error_time_ms,
                                        'failure_stage': 'API調用' if 'order' in str(e).lower() else 'position_check' if 'position' in str(e).lower() else 'market_data' if 'ticker' in str(e).lower() else '未知',
                                        'error_severity': 'critical' if 'connection' in str(e).lower() else 'high' if 'force' in str(e).lower() else 'moderate',
                                        'is_final_attempt': True,
                                        'retry_exhausted': True
                                    },
                                    retry_history={
                                        'retry_count': self.close_retry_count,
                                        'max_retry': self.max_close_retry,
                                        'retry_duration_seconds': int(time.time() - self.close_retry_start_time) if self.close_retry_start_time else 0,
                                        'all_attempts_failed': True
                                    },
                                    context_at_failure={
                                        'direction': direction,
                                        'quantity': quantity,
                                        'entry_price': entry_price,
                                        'funding_rate': funding_rate,
                                        'market_liquidity': market_liquidity if 'market_liquidity' in locals() else 'unknown',
                                        'has_actual_position': 'actual_position' in locals() and actual_position is not None
                                    },
                                    impact_assessment={
                                        'position_status': '可能仍有持倉',
                                        'risk_level': 'high',
                                        'manual_intervention_required': True,
                                        'suggested_actions': ['手動檢查Binance帳戶', '手動平倉', '檢查網路連線', '聯繫技術支援']
                                    })
            
            # 記錄強制平倉失敗事件
            self.log_trade_event('force_close_failed', symbol, {
                'direction': direction,
                'quantity': quantity,
                'error': str(e),
                'error_type': type(e).__name__,
                'retry_count': self.close_retry_count,
                'total_time_ms': total_error_time_ms
            })
            
            # 重置重試計數器，避免無限重試
            self.close_retry_count = 0
            self.is_closing = False
            
            print(f"[{self.format_corrected_time()}] ⚠️警告: 強制平倉失敗，持倉可能仍然存在，請手動檢查Binance帳戶")

    def check_position(self):
        """檢查持倉狀態 - 定期同步實際倉位狀況"""
        try:
            if not self.current_position:
                return
            
            # 檢查是否在倉位檢查延遲期間
            if hasattr(self, 'position_check_delay_until') and time.time() < self.position_check_delay_until:
                remaining_delay = self.position_check_delay_until - time.time()
                if remaining_delay > 0.1:  # 只顯示剩餘延遲大於0.1秒的情況
                    print(f"[{self.format_corrected_time()}] 倉位檢查延遲中，剩餘 {remaining_delay:.1f} 秒")
                return
            
            # 添加持倉檢查頻率控制
            current_time = time.time()
            if not hasattr(self, '_last_position_check_time'):
                self._last_position_check_time = 0
            
            # 檢查是否到了持倉檢查時間
            if current_time - self._last_position_check_time < self.position_check_interval:
                return
            
            self._last_position_check_time = current_time
            
            symbol = self.current_position['symbol']
            
            # 檢查實際倉位狀況
            actual_position = self.check_actual_position(symbol)
            
            if not actual_position:
                # 檢查失敗，可能是API問題，不要立即清理持倉記錄
                # 增加重試計數器，連續失敗多次才清理
                if not hasattr(self, '_position_check_fail_count'):
                    self._position_check_fail_count = 0
                
                self._position_check_fail_count += 1
                
                if self._position_check_fail_count >= 5:  # 連續失敗5次才清理（從3次改回5次）
                    print(f"[{self.format_corrected_time()}] 倉位檢查連續失敗{self._position_check_fail_count}次，清理程式記錄")
                    self.current_position = None
                    self.position_open_time = None
                    self.is_closing = False
                    self._position_check_fail_count = 0
                else:
                    print(f"[{self.format_corrected_time()}] 倉位檢查失敗 ({self._position_check_fail_count}/5)，可能是API問題，保留持倉記錄")
                return
            
            # 檢查成功，重置失敗計數器
            if hasattr(self, '_position_check_fail_count'):
                self._position_check_fail_count = 0
            
            # 檢查倉位信息是否一致
            expected_direction = self.current_position['direction']
            expected_quantity = self.current_position['quantity']
            actual_direction = actual_position['direction']
            actual_quantity = actual_position['quantity']
            
            # 檢查方向是否一致
            if expected_direction != actual_direction:
                print(f"[{self.format_corrected_time()}] 倉位同步: {symbol} 方向不一致，預期:{expected_direction}，實際:{actual_direction}")
                self.current_position['direction'] = actual_direction
            
            # 檢查數量是否一致（允許小數點誤差）
            if abs(expected_quantity - actual_quantity) > 0.001:
                print(f"[{self.format_corrected_time()}] 倉位同步: {symbol} 數量不一致，預期:{expected_quantity}，實際:{actual_quantity}")
                self.current_position['quantity'] = actual_quantity
            
            # 檢查未實現盈虧
            unrealized_pnl = actual_position['unrealized_pnl']
            if abs(unrealized_pnl) > 0.01:  # 只顯示有明顯盈虧的情況
                print(f"[{self.format_corrected_time()}] 倉位狀態: {symbol} {actual_direction} 數量:{actual_quantity} 未實現盈虧:{unrealized_pnl:.2f} USDT")
            
        except Exception as e:
            print(f"[{self.format_corrected_time()}] 檢查持倉狀態時發生錯誤: {str(e)}")
            print(f"[{self.format_corrected_time()}] 錯誤詳情: {traceback.format_exc()}")

    def check_all_positions_and_cleanup(self):
        """定期檢查所有倉位並清理超時倉位"""
        if not self.enable_position_cleanup:
            return
            
        try:
            current_time = time.time()
            current_time_ms = self.get_corrected_time()
            
            # 統一檢查機制 - 簡化版本
            check_interval = self.account_check_interval  # 使用統一的檢查間隔
            if not hasattr(self, '_last_normal_check_msg') or current_time - getattr(self, '_last_normal_check_msg', 0) >= 300:
                print(f"[{self.format_corrected_time()}] 定期檢查（每{check_interval}秒）...")
                self._last_normal_check_msg = current_time
            
            # 檢查是否到了檢查時間
            if not hasattr(self, 'last_account_check_time'):
                self.last_account_check_time = 0
                
            if current_time - self.last_account_check_time < check_interval:
                return
                
            self.last_account_check_time = current_time
            
            # 獲取所有持倉信息
            positions = self.client.futures_position_information()
            
            positions_to_cleanup = []
            
            for pos in positions:
                try:
                    symbol = pos['symbol']
                    position_amt = float(pos['positionAmt'])
                    
                    # 只檢查有持倉的幣種
                    if abs(position_amt) < 0.001:
                        continue
                        
                    # 檢查是否為我們正在交易的幣種
                    if not self.is_valid_symbol(symbol):
                        continue
                    
                    # 獲取倉位方向
                    direction = 'long' if position_amt > 0 else 'short'
                    quantity = abs(position_amt)
                    
                    # 檢查倉位時間（這裡需要從其他地方獲取開倉時間）
                    # 由於Binance API不直接提供開倉時間，我們使用程式內部的記錄
                    position_age = 0
                    
                    # 如果是我們程式開的倉，檢查持倉時間
                    if (self.current_position and 
                        self.current_position['symbol'] == symbol and 
                        self.position_open_time):
                        position_age = current_time - self.position_open_time
                    else:
                        # 如果不是我們程式開的倉，假設是超時倉位
                        position_age = self.position_timeout_seconds + 1
                    
                    # 檢查是否需要清理倉位 - 簡化版本
                    should_cleanup = False
                    cleanup_reason = ""
                    
                    if position_age > self.position_timeout_seconds:
                        # 超時清理機制
                        should_cleanup = True
                        cleanup_reason = "超時清理"
                        print(f"[{self.format_corrected_time()}] 發現超時倉位: {symbol} {direction} 數量:{quantity} 持倉時間:{position_age:.1f}秒")
                    
                    if should_cleanup:
                        positions_to_cleanup.append({
                            'symbol': symbol,
                            'direction': direction,
                            'quantity': quantity,
                            'age_seconds': position_age,
                            'reason': cleanup_reason
                        })
                    
                except Exception as e:
                    print(f"[{self.format_corrected_time()}] 檢查倉位 {pos.get('symbol', 'unknown')} 時出錯: {e}")
                    continue
            
            # 清理超時倉位
            if positions_to_cleanup:
                print(f"[{self.format_corrected_time()}] 開始清理 {len(positions_to_cleanup)} 個超時倉位...")
                
                for pos_info in positions_to_cleanup:
                    try:
                        symbol = pos_info['symbol']
                        direction = pos_info['direction']
                        quantity = pos_info['quantity']
                        
                        # 確定平倉方向（與持倉相反）
                        side = 'SELL' if direction == 'long' else 'BUY'
                        
                        print(f"[{self.format_corrected_time()}] 清理倉位: {symbol} {direction} 數量:{quantity}")
                        
                        # 記錄倉位清理開始
                        self.write_trade_analysis('cleanup_start', symbol, 
                                                direction=direction, 
                                                quantity=quantity,
                                                age_seconds=pos_info['age_seconds'],
                                                reason=pos_info['reason'])
                        
                        order_start_time = time.time()
                        # 發送平倉訂單
                        order = self.client.futures_create_order(
                            symbol=symbol,
                            side=side,
                            type='MARKET',
                            quantity=quantity,
                            reduceOnly=True  # 確保只平倉，不開新倉
                        )
                        order_end_time = time.time()
                        execution_time_ms = int((order_end_time - order_start_time) * 1000)
                        
                        print(f"[{self.format_corrected_time()}] 超時倉位清理成功: {symbol} 訂單ID:{order['orderId']}")
                        
                        # 記錄倉位清理成功  
                        self.write_trade_analysis('cleanup_success', symbol, 
                                                order_id=order['orderId'],
                                                execution_time_ms=execution_time_ms,
                                                age_seconds=pos_info['age_seconds'],
                                                reason=pos_info['reason'])
                        
                        # 記錄清理事件
                        self.log_trade_event('timeout_cleanup', symbol, {
                            'direction': direction,
                            'quantity': quantity,
                            'age_seconds': pos_info['age_seconds'],
                            'order_id': order['orderId'],
                            'reason': pos_info['reason']
                        })
                        
                        # 如果清理的是我們程式記錄的倉位，清空記錄
                        if (self.current_position and 
                            self.current_position['symbol'] == symbol):
                            print(f"[{self.format_corrected_time()}] 清空程式倉位記錄: {symbol}")
                            self.current_position = None
                            self.position_open_time = None
                            self.is_closing = False
                        
                    except Exception as e:
                        print(f"[{self.format_corrected_time()}] 清理倉位 {symbol} 失敗: {e}")
                        
                        # 記錄倉位清理失敗
                        self.write_trade_analysis('cleanup_failed', symbol, 
                                                error=str(e),
                                                direction=direction,
                                                quantity=quantity)
                        
                        self.log_trade_event('timeout_cleanup_failed', symbol, {
                            'error': str(e),
                            'direction': direction,
                            'quantity': quantity
                        })
                        continue
                
                print(f"[{self.format_corrected_time()}] 超時倉位清理完成")
            else:
                print(f"[{self.format_corrected_time()}] 沒有發現需要清理的超時倉位")
                
        except Exception as e:
            print(f"[{self.format_corrected_time()}] 定期檢查帳戶時發生錯誤: {str(e)}")
            print(f"[{self.format_corrected_time()}] 錯誤詳情: {traceback.format_exc()}")

    def run(self):
        """運行交易機器人 - WebSocket模式：使用真實結算時間進行交易"""
        print("=== 資金費率套利機器人啟動 ===")
        print(f"啟動時間: {self.format_corrected_time('%Y-%m-%d %H:%M:%S')}")
        print(f"最大保證金: {MAX_POSITION_SIZE} USDT")
        print(f"槓桿倍數: {LEVERAGE}")
        print(f"目標倉位大小: {MAX_POSITION_SIZE * LEVERAGE} USDT")
        print(f"最小資金費率: {MIN_FUNDING_RATE}%")
        print(f"最大點差閾值: {MAX_SPREAD}%")
        print(f"進場提前時間: {ENTRY_BEFORE_SECONDS} 秒")
        print(f"平倉提前時間: {CLOSE_BEFORE_SECONDS} 秒")
        print(f"主循環檢查間隔: {CHECK_INTERVAL} 秒")
        print(f"持倉檢查間隔: {POSITION_CHECK_INTERVAL} 秒")
        print(f"交易時間: {TRADING_HOURS}")
        print(f"交易幣種: {TRADING_SYMBOLS if TRADING_SYMBOLS else '全部'}")
        print(f"排除幣種: {EXCLUDED_SYMBOLS}")
        print("--- 重試機制配置 ---")
        print(f"進場重試次數: {MAX_ENTRY_RETRY}")
        print(f"進場重試間隔: {ENTRY_RETRY_INTERVAL} 秒")
        print(f"結算前持續重試進場: {ENTRY_RETRY_UNTIL_SETTLEMENT}")
        print(f"平倉重試次數: {MAX_CLOSE_RETRY}")
        print(f"平倉重試間隔: {CLOSE_RETRY_INTERVAL} 秒")
        print(f"結算時強制平倉: {FORCE_CLOSE_AT_SETTLEMENT}")
        print(f"強制平倉時間: 結算後 {FORCE_CLOSE_AFTER_SECONDS} 秒")
        print("--- 平倉模式配置 ---")
        print(f"🎯 當前平倉模式: {self._close_method_display}")
        print(f"平倉等待時間: 結算後 {CLOSE_AFTER_SECONDS} 秒")
        print("--- 定期檢查配置 ---")
        print(f"帳戶檢查間隔: {ACCOUNT_CHECK_INTERVAL} 秒")
        print(f"倉位超時時間: {POSITION_TIMEOUT_SECONDS} 秒")
        print(f"啟用倉位清理: {ENABLE_POSITION_CLEANUP}")
        print("=" * 50)
        
        # 記錄程序啟動
        self.log_system_event('program_start', {
            'max_position_size': self.max_position_size,
            'leverage': self.leverage,
            'funding_rate_threshold': self.funding_rate_threshold,
            'entry_before_seconds': self.entry_before_seconds,
            'close_before_seconds': self.close_before_seconds
        })
        
        # 初始化交易環境
        if not self.initialize_trading():
            print("[ERROR] 交易環境初始化失敗，請檢查賬戶狀態")
            self.log_system_event('initialization_failed', {'error': '交易環境初始化失敗'})
            return
        
        # 啟動時同步時間
        print("[LOG] 啟動時同步 Binance 服務器時間...")
        self.sync_server_time()
        
        # 啟動 WebSocket 連接
        self.start_websocket()
        
        # 主循環 - WebSocket模式
        try:
            print("[LOG] 進入WebSocket模式主循環，等待交易機會...")
            while True:
                try:
                    # 檢查是否需要同步時間
                    if self.should_sync_time():
                        print(f"[{self.format_corrected_time()}] 定期時間同步...")
                        self.sync_server_time()
                    
                    # 定期記錄系統狀態（每分鐘一次）
                    if not hasattr(self, '_last_status_log_time') or time.time() - self._last_status_log_time >= 60:
                        self.log_system_event('system_status', {
                            'current_position': self.current_position is not None,
                            'funding_rates_count': len(self.funding_rates),
                            'time_offset': self.time_offset,
                            'websocket_connected': self.ws and self.ws.sock and self.ws.sock.connected
                        })
                        self._last_status_log_time = time.time()
                    
                    # 定期更新資金費率數據（每30秒一次）
                    if not hasattr(self, '_last_funding_update_time') or time.time() - self._last_funding_update_time >= 30:
                        updated_count = self.update_funding_rates()
                        if updated_count > 0:
                            print(f"[{self.format_corrected_time()}] 更新資金費率: {updated_count} 個交易對")
                        self._last_funding_update_time = time.time()
                    
                    # 🔒 併發安全檢查：如果API調用正在進行，跳過非關鍵操作
                    if self.is_api_calling:
                        api_duration = time.time() - self.api_call_start_time
                        if api_duration < self.max_api_call_duration:
                            # API調用正在進行且未超時，跳過非關鍵操作
                            time.sleep(0.1)  # 短暫等待
                            continue
                        else:
                            # API調用可能卡住，記錄警告但繼續執行
                            print(f"[{self.format_corrected_time()}] ⚠️ 檢測到長時間API調用，已運行{api_duration:.1f}秒")
                    
                    # 檢查持倉狀態
                    self.check_position()
                    
                    # 定期檢查所有倉位並清理超時倉位 - 統一檢查機制
                    self.check_all_positions_and_cleanup()
                    
                    # 添加調試信息（每10秒顯示一次）
                    if not hasattr(self, '_last_debug_time') or time.time() - self._last_debug_time >= 10:
                        api_status = "進行中" if self.is_api_calling else "空閒"
                        print(f"[DEBUG] 主循環狀態: 持倉={self.current_position is not None}, 平倉中={self.is_closing}, API狀態={api_status}, 資金費率數量={len(self.funding_rates)}")
                        self._last_debug_time = time.time()
                    
                    # 🎯 **優先檢查當前持倉的平倉時機** - 獨立於最佳機會
                    if self.current_position and not self.is_closing:
                        # 獲取當前持倉的結算時間
                        current_position_settlement_time = self.current_position.get('next_funding_time', 0)
                        if current_position_settlement_time > 0:
                            # 計算當前時間
                            current_time_ms = self.get_corrected_time()
                            
                            # 計算平倉時間（結算後 CLOSE_AFTER_SECONDS 秒）
                            close_time_ms = current_position_settlement_time + self.close_after_seconds * 1000
                            time_to_close = close_time_ms - current_time_ms
                            
                            # 檢查是否到達平倉時間
                            if time_to_close <= 0:
                                symbol = self.current_position['symbol']
                                print(f"\n[{self.format_corrected_time()}] 🎯 持倉平倉時間到（結算後{self.close_after_seconds}秒），開始平倉 - 使用: {self._close_method_display}")
                                self.log_trade_step('close', symbol, 'independent_time_triggered', safe_json_serialize({
                                    'time_to_close': time_to_close,
                                    'close_after_seconds': self.close_after_seconds,
                                    'settlement_time': datetime.fromtimestamp(current_position_settlement_time / 1000).strftime('%H:%M:%S.%f'),
                                    'trigger_source': 'independent_position_check'
                                }))
                                
                                # 🔒 平倉前併發檢查
                                if self.is_api_calling:
                                    print(f"[{self.format_corrected_time()}] 檢測到API調用進行中，但平倉是優先操作，等待完成")
                                    self.log_trade_step('close', symbol, 'wait_for_api_completion', {
                                        'api_call_duration': time.time() - self.api_call_start_time
                                    })
                                    # 平倉是緊急操作，短暫等待後繼續
                                    time.sleep(0.1)
                                
                                self.is_closing = True
                                self.close_position()
                                time.sleep(self.check_interval)
                                continue
                            
                            # 檢查是否需要備用強制平倉（第2層：結算後1秒檢查）
                            time_to_settlement = current_position_settlement_time - current_time_ms
                            if time_to_settlement <= 0:
                                # 計算結算後經過的時間
                                time_since_settlement = abs(time_to_settlement) / 1000  # 轉換為秒
                                
                                # 🎯 第2層檢查：結算後1秒，有持倉就執行強制平倉
                                if time_since_settlement >= self.force_close_after_seconds:
                                    symbol = self.current_position['symbol']
                                    print(f"\n[{self.format_corrected_time()}] 🚨 第2層強制平倉觸發：結算後{time_since_settlement:.3f}秒，檢查到持倉執行強制平倉")
                                    self.log_trade_step('close', symbol, 'layer2_independent_force_close', safe_json_serialize({
                                        'time_to_settlement': time_to_settlement,
                                        'time_since_settlement': time_since_settlement,
                                        'close_after_seconds': self.close_after_seconds,
                                        'force_close_after_seconds': self.force_close_after_seconds,
                                        'settlement_time': datetime.fromtimestamp(current_position_settlement_time / 1000).strftime('%H:%M:%S.%f'),
                                        'reason': '第2層平倉機制：結算後1秒檢查到持倉',
                                        'trigger_source': 'independent_position_check'
                                    }))
                                    
                                    # 🔒 強制平倉前併發檢查
                                    if self.is_api_calling:
                                        print(f"[{self.format_corrected_time()}] 檢測到API調用進行中，但強制平倉是最優先操作，等待完成")
                                        self.log_trade_step('close', symbol, 'force_wait_for_api_completion', {
                                            'api_call_duration': time.time() - self.api_call_start_time
                                        })
                                        # 強制平倉是最緊急操作，短暫等待後繼續
                                        time.sleep(0.1)
                                    
                                    self.is_closing = True
                                    self.force_close_position()
                                    time.sleep(self.check_interval)
                                    continue
                    
                    # 獲取校正後的時間
                    now = datetime.now()
                    current_time_ms = self.get_corrected_time()
                    
                    # 使用WebSocket篩選出的最佳機會
                    best_opportunity = self.get_best_opportunity()
                    
                    if best_opportunity:
                        # 使用真實的結算時間計算倒數
                        real_settlement_time = best_opportunity['next_funding_time']
                        
                        # 計算距離結算的時間
                        time_to_settlement = real_settlement_time - current_time_ms
                        
                        if time_to_settlement > 0:
                            # 計算進場時間（結算前 ENTRY_BEFORE_SECONDS 秒）
                            entry_time_ms = real_settlement_time - self.entry_before_seconds * 1000
                            time_to_entry = entry_time_ms - current_time_ms
                            
                            # 計算平倉時間（結算後 CLOSE_AFTER_SECONDS 秒）
                            close_time_ms = real_settlement_time + self.close_after_seconds * 1000
                            time_to_close = close_time_ms - current_time_ms
                            
                            # 顯示倒數計時 - 每秒顯示一次
                            if time_to_entry > 0:
                                # 格式化進場倒數計時
                                entry_seconds_total = int(time_to_entry / 1000)
                                entry_hours = entry_seconds_total // 3600
                                entry_minutes = (entry_seconds_total % 3600) // 60
                                entry_secs = entry_seconds_total % 60
                                entry_milliseconds = int(time_to_entry % 1000)
                                entry_countdown = f"{entry_hours:02d}:{entry_minutes:02d}:{entry_secs:02d}.{entry_milliseconds:03d}"
                                
                                # 格式化平倉倒數計時（結算後平倉）
                                if time_to_close > 0:
                                    # 結算後平倉：顯示到平倉時間的倒數
                                    close_seconds_total = int(time_to_close / 1000)
                                    close_hours = close_seconds_total // 3600
                                    close_minutes = (close_seconds_total % 3600) // 60
                                    close_secs = close_seconds_total % 60
                                    close_milliseconds = int(time_to_close % 1000)
                                    close_countdown = f"{close_hours:02d}:{close_minutes:02d}:{close_secs:02d}.{close_milliseconds:03d}"
                                else:
                                    # 已過平倉時間
                                    close_countdown = "00:00:00.000"
                                
                                # 顯示倒數計時 - 每秒顯示一次
                                settlement_time_str = datetime.fromtimestamp(real_settlement_time / 1000).strftime('%H:%M:%S')
                                
                                # 計算該幣種距離結算時間的倒數
                                time_to_settlement_seconds = int(time_to_settlement / 1000)
                                settlement_hours = time_to_settlement_seconds // 3600
                                settlement_minutes = (time_to_settlement_seconds % 3600) // 60
                                settlement_secs = time_to_settlement_seconds % 60
                                settlement_milliseconds = int(time_to_settlement % 1000)
                                settlement_countdown = f"{settlement_hours:02d}:{settlement_minutes:02d}:{settlement_secs:02d}.{settlement_milliseconds:03d}"
                                
                                # 每秒顯示一次
                                if entry_secs != getattr(self, '_last_display_sec', -1):
                                    # 計算淨收益和點差
                                    net_profit = best_opportunity.get('net_profit', 0)
                                    spread = best_opportunity.get('spread', 0)
                                    spread_display = f"點差:{spread:.3f}%" if spread < 999 else "點差:N/A"
                                    
                                    # 檢查是否滿足淨收益條件
                                    profit_ok = net_profit >= self.funding_rate_threshold
                                    spread_ok = spread <= self.max_spread
                                    status = "✓" if (profit_ok and spread_ok) else "✗"
                                    
                                    # 格式化顯示，顯示資金費率、點差、淨收益
                                    funding_rate = best_opportunity['funding_rate']
                                    status_line = f"[{self.format_corrected_time()}] 倒計時: 進場{entry_countdown:>12} | 平倉{close_countdown:>12} | 結算:{settlement_time_str:>8} | 結算倒數{settlement_countdown:>12} | 最佳: {best_opportunity['symbol']:<10} 資金費率:{funding_rate:.4f}% | 點差:{spread:.3f}% | 淨收益:{net_profit:.3f}%{status} {best_opportunity['direction']:<4} | 時間差:{self.time_offset:+5d}ms {self._close_method_display}"
                                    print(status_line)
                                    self._last_display_sec = entry_secs
                            
                            # 檢查是否到達平倉時間（結算後立即平倉）
                            if time_to_close <= 0:  # 結算後立即平倉（獲得資金費後）
                                if self.current_position and not self.is_closing:
                                    print(f"\n[{self.format_corrected_time()}] 平倉時間到（結算後{self.close_after_seconds}秒），開始平倉 - 使用: {self._close_method_display}")
                                    self.log_trade_step('close', best_opportunity['symbol'], 'time_triggered', safe_json_serialize({
                                        'time_to_close': time_to_close,
                                        'close_after_seconds': self.close_after_seconds,
                                        'settlement_time': datetime.fromtimestamp(real_settlement_time / 1000).strftime('%H:%M:%S.%f')
                                    }))
                                    self.is_closing = True
                                    self.close_position()
                                    time.sleep(self.check_interval)
                                    continue
                            
                            # 檢查是否需要備用強制平倉（第2層：結算後1秒檢查）
                            if time_to_settlement <= 0 and self.current_position and not self.is_closing:
                                # 計算結算後經過的時間
                                time_since_settlement = abs(time_to_settlement) / 1000  # 轉換為秒
                                
                                # 🎯 第2層檢查：結算後1秒，有持倉就執行強制平倉
                                if time_since_settlement >= self.force_close_after_seconds:
                                    print(f"\n[{self.format_corrected_time()}] 🚨 第2層強制平倉觸發：結算後{time_since_settlement:.3f}秒，檢查到持倉執行強制平倉")
                                    self.log_trade_step('close', best_opportunity['symbol'], 'layer2_force_close_triggered', safe_json_serialize({
                                            'time_to_settlement': time_to_settlement,
                                            'time_since_settlement': time_since_settlement,
                                            'force_close_after_seconds': self.force_close_after_seconds,
                                        'settlement_time': datetime.fromtimestamp(real_settlement_time / 1000).strftime('%H:%M:%S.%f'),
                                        'reason': '第2層平倉機制：結算後1秒檢查到持倉'
                                }))
                                self.is_closing = True
                                self.force_close_position()
                                time.sleep(self.check_interval)
                                continue
                            
                            # 檢查是否接近進場時間
                            if time_to_entry <= self.entry_time_tolerance:  # 使用配置的進場時間容差
                                print(f"\n[{self.format_corrected_time()}] 進場時間到！")
                                self.log_trade_step('entry', best_opportunity['symbol'], 'time_triggered', safe_json_serialize({
                                    'time_to_entry': time_to_entry,
                                    'entry_time_tolerance': self.entry_time_tolerance,
                                    'settlement_time': datetime.fromtimestamp(real_settlement_time / 1000).strftime('%H:%M:%S.%f')
                                }))
                                
                                # 檢查是否已有持倉
                                if self.current_position:
                                    print(f"[{self.format_corrected_time()}] 已有持倉，跳過進場")
                                    self.log_trade_step('entry', best_opportunity['symbol'], 'skip_existing_position', safe_json_serialize({
                                        'current_position': self.current_position
                                    }))
                                    time.sleep(self.check_interval)
                                    continue
                                
                                # 檢查是否在平倉狀態
                                if self.is_closing:
                                    print(f"[{self.format_corrected_time()}] 正在平倉，跳過進場")
                                    self.log_trade_step('entry', best_opportunity['symbol'], 'skip_closing', {})
                                    time.sleep(self.check_interval)
                                    continue
                                
                                # 檢查是否在開倉鎖定期間
                                if hasattr(self, 'entry_locked_until') and time.time() < self.entry_locked_until:
                                    remaining_lock = self.entry_locked_until - time.time()
                                    print(f"[{self.format_corrected_time()}] 開倉鎖定中，剩餘 {remaining_lock:.1f} 秒，跳過進場")
                                    self.log_trade_step('entry', best_opportunity['symbol'], 'skip_locked', safe_json_serialize({
                                        'remaining_lock': remaining_lock
                                    }))
                                    time.sleep(self.check_interval)
                                    continue
                                
                                print(f"[{self.format_corrected_time()}] 進場時間到（結算前{self.entry_before_seconds}秒）！")
                                
                                # 進場前最終檢查：淨收益和點差
                                final_net_profit = best_opportunity.get('net_profit', 0)
                                final_spread = best_opportunity.get('spread', 0)
                                funding_rate = best_opportunity['funding_rate']
                                
                                print(f"[{self.format_corrected_time()}] 進場前檢查: {best_opportunity['symbol']} | 資金費率: {funding_rate:.4f}% | 點差: {final_spread:.3f}% | 淨收益: {final_net_profit:.3f}% (閾值:{self.funding_rate_threshold}%) | 方向: {best_opportunity['direction']}")
                                
                                if final_net_profit < self.funding_rate_threshold:
                                    print(f"[{self.format_corrected_time()}] 進場取消：淨收益{final_net_profit:.3f}%低於閾值{self.funding_rate_threshold}%")
                                    self.log_trade_step('entry', best_opportunity['symbol'], 'skip_low_net_profit', safe_json_serialize({
                                        'funding_rate': funding_rate,
                                        'spread': final_spread,
                                        'net_profit': final_net_profit,
                                        'threshold': self.funding_rate_threshold
                                    }))
                                    time.sleep(self.check_interval)
                                    continue
                                
                                if final_spread > self.max_spread:  # 點差超過配置閾值則跳過
                                    print(f"[{self.format_corrected_time()}] 進場取消：點差過大{final_spread:.3f}% (>{self.max_spread}%)")
                                    self.log_trade_step('entry', best_opportunity['symbol'], 'skip_high_spread', safe_json_serialize({
                                        'spread': final_spread,
                                        'max_spread': self.max_spread,
                                        'net_profit': final_net_profit
                                    }))
                                    time.sleep(self.check_interval)
                                    continue
                                
                                print(f"[{self.format_corrected_time()}] 檢查通過，開始進場: {best_opportunity['symbol']} | 資金費率: {funding_rate:.4f}% | 點差: {final_spread:.3f}% | 淨收益: {final_net_profit:.3f}% | 方向: {best_opportunity['direction']}")
                                self.log_trade_step('entry', best_opportunity['symbol'], 'start_entry', safe_json_serialize({
                                    'funding_rate': funding_rate,
                                    'direction': best_opportunity['direction'],
                                    'spread': final_spread,
                                    'net_profit': final_net_profit,
                                    'entry_before_seconds': self.entry_before_seconds,
                                    'settlement_time': datetime.fromtimestamp(real_settlement_time / 1000).strftime('%H:%M:%S.%f')
                                }))
                                
                                # 🔒 進場前併發檢查
                                if self.is_api_calling:
                                    print(f"[{self.format_corrected_time()}] 檢測到API調用進行中，延遲進場以避免衝突")
                                    self.log_trade_step('entry', best_opportunity['symbol'], 'delayed_for_api', {
                                        'api_call_duration': time.time() - self.api_call_start_time
                                    })
                                    time.sleep(0.2)  # 等待API調用完成
                                    
                                    # 再次檢查
                                    if self.is_api_calling:
                                        print(f"[{self.format_corrected_time()}] API調用仍在進行，取消此次進場")
                                        self.log_trade_step('entry', best_opportunity['symbol'], 'cancelled_for_api', {})
                                        time.sleep(self.check_interval)
                                        continue
                                
                                # 開倉
                                self.open_position(best_opportunity['symbol'], best_opportunity['direction'], best_opportunity['funding_rate'], best_opportunity['next_funding_time'])
                    else:
                        # 沒有篩選出符合條件的交易對，顯示詳細等待信息
                        if not hasattr(self, '_last_no_opportunity_time') or time.time() - self._last_no_opportunity_time >= 10.0:
                            # 計算有多少交易對因為資金費率太低被排除
                            total_pairs = len(self.funding_rates) if self.funding_rates else 0
                            if total_pairs > 0:
                                low_rate_count = 0
                                for symbol, data in self.funding_rates.items():
                                    if abs(data['funding_rate']) < self.funding_rate_threshold:
                                        low_rate_count += 1
                                
                                print(f"[{self.format_corrected_time()}] 等待符合條件的交易機會... | 總交易對:{total_pairs} | 低於{self.funding_rate_threshold}%閾值:{low_rate_count} | 時間差:{self.time_offset:+5d}ms")
                            else:
                                print(f"[{self.format_corrected_time()}] 等待WebSocket數據... | 時間差:{self.time_offset:+5d}ms")
                            self._last_no_opportunity_time = time.time()
                    
                    time.sleep(self.check_interval)
                except KeyboardInterrupt:
                    print("\n收到停止信號，正在關閉...")
                    break
                except Exception as e:
                    print(f"[ERROR] 主循環錯誤: {e}")
                    print(f"[ERROR] 錯誤詳情: {traceback.format_exc()}")
                    print(f"[ERROR] 當前狀態: 持倉={self.current_position is not None}, 平倉中={self.is_closing}")
                    time.sleep(5)
        except Exception as e:
            print(f"[ERROR] 主循環發生嚴重錯誤: {e}")
        finally:
            print("WebSocket模式交易機器人已停止")

    def __del__(self):
        """析構函數 - 程式關閉時清理"""
        try:
            # 刷新所有緩存的記錄
            if hasattr(self, '_analysis_buffer'):
                self._flush_analysis_buffer()
                
            if hasattr(self, 'current_position') and self.current_position:
                print(f"[{self.format_corrected_time()}] 程式關閉，發現持倉，嘗試清理...")
                self.force_close_position()
        except Exception as e:
            print(f"[{self.format_corrected_time()}] 程式關閉時清理失敗: {e}")
        
        try:
            if hasattr(self, 'ws') and self.ws:
                self.ws.close()
        except Exception as e:
            print(f"[{self.format_corrected_time()}] 關閉WebSocket失敗: {e}")

    def reconnect(self):
        """重新連接 WebSocket"""
        try:
            print(f"[{self.format_corrected_time()}] 開始重新連接 WebSocket...")
            if self.ws:
                try:
                    self.ws.close()
                except Exception as e:
                    print(f"[{self.format_corrected_time()}] 關閉舊 ws 失敗: {e}")
            self.ws = None
            
            # 等待一段時間再重連
            time.sleep(3)
            
            # 重新啟動 WebSocket
            self.start_websocket()
            print(f"[{self.format_corrected_time()}] WebSocket 重新連接成功")
        except Exception as e:
            print(f"[{self.format_corrected_time()}] WebSocket 重連失敗: {e}")
            # 如果重連失敗，等待更長時間再嘗試
            time.sleep(10)
            self.reconnect()

    def start(self):
        """啟動交易機器人"""
        global trader_instance
        trader_instance = self
        
        # 設置信號處理
        signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # 終止信號
        
        print(f"[{self.format_corrected_time()}] 信號處理已設置，按Ctrl+C可優雅關閉程式")
        
        # 發送啟動通知
        print(f"[{self.format_corrected_time()}] 準備發送啟動通知...")
        try:
            print(f"[{self.format_corrected_time()}] 調用 send_start_notification...")
            self.profit_tracker.send_start_notification()
            print(f"[{self.format_corrected_time()}] 啟動通知發送完成")
        except Exception as e:
            print(f"[{self.format_corrected_time()}] 發送啟動通知失敗: {e}")
            print(f"[{self.format_corrected_time()}] 錯誤詳情: {traceback.format_exc()}")
        
        try:
            self.run()
        except KeyboardInterrupt:
            print(f"\n[{self.format_corrected_time()}] 收到鍵盤中斷信號")
            # 發送關閉通知
            try:
                if not hasattr(self, '_stop_notification_sent') or not self._stop_notification_sent:
                    self.profit_tracker.send_stop_notification()
                    self._stop_notification_sent = True  # 標記已發送
                    print(f"[{self.format_corrected_time()}] KeyboardInterrupt 處理器已發送停止通知")
                else:
                    print(f"[{self.format_corrected_time()}] KeyboardInterrupt 處理器跳過停止通知（已發送）")
            except Exception as e:
                print(f"[{self.format_corrected_time()}] 發送關閉通知失敗: {e}")
        except Exception as e:
            print(f"[{self.format_corrected_time()}] 程式運行異常: {e}")
            print(f"[{self.format_corrected_time()}] 錯誤詳情: {traceback.format_exc()}")
            # 發送重大錯誤通知
            try:
                error_msg = f"程式運行異常: {e}\n詳情: {traceback.format_exc()}"
                self.profit_tracker.send_error_notification(error_msg)
            except Exception as notify_e:
                print(f"[{self.format_corrected_time()}] 發送錯誤通知失敗: {notify_e}")
            # 發送停止通知
            try:
                if not hasattr(self, '_stop_notification_sent') or not self._stop_notification_sent:
                    self.profit_tracker.send_stop_notification()
                    self._stop_notification_sent = True  # 標記已發送
                    print(f"[{self.format_corrected_time()}] Exception 處理器已發送停止通知")
                else:
                    print(f"[{self.format_corrected_time()}] Exception 處理器跳過停止通知（已發送）")
            except Exception as notify_e:
                print(f"[{self.format_corrected_time()}] Exception 處理器發送停止通知失敗: {notify_e}")
        finally:
            # 確保程式關閉時清理
            if self.current_position:
                print(f"[{self.format_corrected_time()}] 程式異常退出，嘗試清理持倉...")
                try:
                    self.force_close_position()
                except Exception as e:
                    print(f"[{self.format_corrected_time()}] 清理持倉失敗: {e}")
            # 只在未發送過停止通知時才發送
            if not hasattr(self, '_stop_notification_sent') or not self._stop_notification_sent:
                try:
                    self.profit_tracker.send_stop_notification()
                except Exception as e:
                    print(f"[{self.format_corrected_time()}] 發送關閉通知失敗: {e}")
            print(f"[{self.format_corrected_time()}] 程式已關閉")

    def get_quantity_precision(self, symbol: str) -> int:
        """獲取交易對的數量精度 - 已簡化，保留兼容性"""
        return 0

    def format_quantity(self, symbol: str, quantity: float) -> float:
        """格式化數量到正確的精度 - 極簡化版本，避免過度精確"""
        # 對於所有交易對，直接取整數，避免精度問題
        return int(quantity)

    def initialize_trading(self):
        """初始化交易環境"""
        try:
            # 檢查賬戶狀態
            account = self.client.futures_account()
            total_balance = float(account['totalWalletBalance'])
            available_balance = float(account['availableBalance'])
            
            print(f"[{self.format_corrected_time()}] 賬戶總餘額: {total_balance:.2f} USDT")
            print(f"[{self.format_corrected_time()}] 可用餘額: {available_balance:.2f} USDT")
            
            if available_balance < self.max_position_size:
                print(f"[{self.format_corrected_time()}] 警告: 可用餘額不足，無法開倉")
                return False
            
            # 啟動時檢查是否有遺留持倉
            print(f"[{self.format_corrected_time()}] 檢查是否有遺留持倉...")
            positions = self.client.futures_position_information()
            legacy_positions = []
            
            for pos in positions:
                position_amt = float(pos['positionAmt'])
                if abs(position_amt) > 0.001:  # 有持倉
                    symbol = pos['symbol']
                    direction = 'long' if position_amt > 0 else 'short'
                    quantity = abs(position_amt)
                    legacy_positions.append({
                        'symbol': symbol,
                        'direction': direction,
                        'quantity': quantity
                    })
                    print(f"[{self.format_corrected_time()}] 發現遺留持倉: {symbol} {direction} 數量:{quantity}")
            
            if legacy_positions:
                print(f"[{self.format_corrected_time()}] 發現 {len(legacy_positions)} 個遺留持倉")
                print(f"[{self.format_corrected_time()}] 建議手動檢查或等待定期清理機制處理")
                print(f"[{self.format_corrected_time()}] 程式將繼續運行，定期檢查機制會自動清理超時倉位")
            else:
                print(f"[{self.format_corrected_time()}] 沒有發現遺留持倉")
            
            # 設置槓桿
            print(f"[{self.format_corrected_time()}] 設置槓桿倍數: {self.leverage}")
            
            # 啟動首次點差緩存更新
            print(f"[{self.format_corrected_time()}] 啟動首次點差緩存更新...")
            self._start_spread_cache_update()
            
            return True
            
        except Exception as e:
            print(f"[{self.format_corrected_time()}] 初始化交易環境失敗: {e}")
            return False

    def check_margin_sufficient(self, symbol: str, quantity: float) -> bool:
        """檢查保證金是否足夠"""
        try:
            # 獲取當前價格
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            current_price = float(ticker['price'])
            
            # 計算所需保證金：數量 * 價格 / 槓桿
            required_margin = (quantity * current_price) / self.leverage
            
            # 檢查可用餘額
            account = self.client.futures_account()
            available_balance = float(account['availableBalance'])
            
            print(f"[{self.format_corrected_time()}] 檢查保證金: 需要 {required_margin:.2f} USDT, 可用 {available_balance:.2f} USDT")
            
            return available_balance >= required_margin
            
        except Exception as e:
            print(f"[{self.format_corrected_time()}] 檢查保證金失敗: {e}")
            return False

    def sync_server_time(self):
        """同步 Binance 服務器時間 - 考慮網路延遲的精確同步"""
        try:
            # 記錄請求前的本地時間
            local_time_before = int(time.time() * 1000)
            
            # 獲取服務器時間
            server_time = self.client.get_server_time()
            
            # 記錄請求後的本地時間
            local_time_after = int(time.time() * 1000)
            
            # 計算網路延遲
            network_delay = local_time_after - local_time_before
            
            # 估算請求中點的本地時間（補償網路延遲的一半）
            adjusted_local_time = local_time_before + (network_delay / 2)
            
            old_offset = self.time_offset
            self.time_offset = int(server_time['serverTime'] - adjusted_local_time)
            self.last_sync_time = local_time_after
            
            print(f"[{self.format_corrected_time()}] 時間同步: 本地時間差 {self.time_offset}ms (變化: {self.time_offset - old_offset}ms) 網路延遲: {network_delay}ms")
            
            # 記錄時間同步事件
            self.log_system_event('time_sync', {
                'server_time': server_time['serverTime'],
                'local_time_before': local_time_before,
                'local_time_after': local_time_after,
                'network_delay': network_delay,
                'adjusted_local_time': adjusted_local_time,
                'time_offset': self.time_offset,
                'offset_change': self.time_offset - old_offset
            })
            
            # 如果網路延遲過大，給出警告
            if network_delay > 100:  # 超過100ms
                print(f"[{self.format_corrected_time()}] ⚠️ 網路延遲較大 ({network_delay}ms)，可能影響交易精度")
            
            return True
        except Exception as e:
            print(f"[{self.format_corrected_time()}] 時間同步失敗: {e}")
            self.log_system_event('time_sync_failed', {'error': str(e)})
            return False

    def get_corrected_time(self):
        """獲取校正後的時間（毫秒）"""
        return int(time.time() * 1000) + self.time_offset

    def get_corrected_datetime(self):
        """獲取校正後的datetime對象"""
        corrected_ms = self.get_corrected_time()
        return datetime.fromtimestamp(corrected_ms / 1000)

    def format_corrected_time(self, format_str='%H:%M:%S.%f'):
        """格式化校正後的時間戳"""
        corrected_dt = self.get_corrected_datetime()
        return corrected_dt.strftime(format_str)[:-3]  # 去掉微秒的最後3位

    def should_sync_time(self):
        """檢查是否需要同步時間"""
        current_time = int(time.time() * 1000)
        return current_time - self.last_sync_time > self.sync_interval * 1000

    def log_trade_event(self, event_type: str, symbol: str, details: dict):
        """記錄交易事件"""
        timestamp = self.format_corrected_time('%Y-%m-%d %H:%M:%S.%f')
        log_entry = {
            'timestamp': timestamp,
            'event_type': event_type,
            'symbol': symbol,
            'details': safe_json_serialize(details)
        }
        self.logger.info(f"TRADE: {json.dumps(log_entry, ensure_ascii=False)}")

    def log_system_event(self, event_type: str, details: dict):
        """記錄系統事件"""
        timestamp = self.format_corrected_time('%Y-%m-%d %H:%M:%S.%f')
        log_entry = {
            'timestamp': timestamp,
            'event_type': event_type,
            'details': safe_json_serialize(details)
        }
        self.logger.info(f"SYSTEM: {json.dumps(log_entry, ensure_ascii=False)}")

    def log_trade_step(self, step: str, symbol: str, action: str, details: dict = None):
        """記錄交易步驟 - 包含所有print內容"""
        timestamp = self.format_corrected_time('%Y-%m-%d %H:%M:%S.%f')
        log_entry = {
            'timestamp': timestamp,
            'step': step,
            'symbol': symbol,
            'action': action,
            'details': safe_json_serialize(details or {})
        }
        self.logger.info(f"STEP: {json.dumps(log_entry, ensure_ascii=False)}")

    def record_entry_step(self, step: str, symbol: str, **kwargs):
        """記錄進場步驟"""
        step_data = {
            'timestamp': self.format_corrected_time('%H:%M:%S.%f'),
            'step': step,
            'symbol': symbol,
            **kwargs
        }
        print(f"[{self.format_corrected_time()}] 進場步驟: {step} | {symbol} | {kwargs}")
        # 同時記錄到日誌文件
        self.log_trade_step('entry', symbol, step, safe_json_serialize(kwargs))
        
        # 記錄到交易分析記事本 - 避免重複的step參數
        clean_kwargs = {k: v for k, v in kwargs.items() if k != 'step'}
        self.write_trade_analysis(step, symbol, **clean_kwargs)

    def record_close_step(self, step: str, symbol: str, **kwargs):
        """記錄平倉步驟"""
        step_data = {
            'timestamp': self.format_corrected_time('%H:%M:%S.%f'),
            'step': step,
            'symbol': symbol,
            **kwargs
        }
        print(f"[{self.format_corrected_time()}] 平倉步驟: {step} | {symbol} | {kwargs}")
        # 同時記錄到日誌文件
        self.log_trade_step('close', symbol, step, safe_json_serialize(kwargs))
        
        # 記錄到交易分析記事本 - 避免重複的step參數
        clean_kwargs = {k: v for k, v in kwargs.items() if k != 'step'}
        self.write_trade_analysis(step, symbol, **clean_kwargs)

    def write_trade_analysis(self, step: str, symbol: str, **kwargs):
        """寫入交易分析記事本 - 易讀格式，包含進場、平倉、指令發送接收等"""
        try:
            # 確保logs目錄存在
            import os
            os.makedirs('logs', exist_ok=True)
            
            timestamp = self.format_corrected_time('%Y-%m-%d %H:%M:%S.%f')
            # 顯示時間時包含毫秒 (取前23個字符：2025-06-29 22:00:00.123)
            display_time = timestamp[:23]
            
            # 效率優化: 批量記錄緩存
            if not hasattr(self, '_analysis_buffer'):
                self._analysis_buffer = []
                self._buffer_start_time = time.time()
            
            # 檢查是否為關鍵步驟（需要立即寫入）
            critical_steps = [
                'entry_success', 'entry_failed', 'entry_complete',
                'close_position', 'close_position_detail',
                'fast_close_success', 'fast_close_failed',
                'ultra_fast_close_success', 'ultra_fast_close_failed',
                'force_close_success', 'force_close_failed',
                'minimal_close_complete', 'minimal_close_failed',
                # 新增的詳細記錄步驟
                'close_with_full_context', 'close_market_analysis',
                'close_network_analysis', 'close_balance_analysis'
            ]
            
            is_critical = step in critical_steps
            is_buffer_timeout = (time.time() - self._buffer_start_time) > 2.0  # 2秒超時
            is_buffer_full = len(self._analysis_buffer) >= 20  # 緩存滿20條
            
            # 根據不同步驟記錄不同內容
            # ========== 進場相關步驟 ==========
            if step == 'entry_start':
                content = f"\n{'='*60}\n"
                content += f"🚀 開始進場: {symbol}\n"
                content += f"時間: {timestamp}\n"
                content += f"方向: {kwargs.get('direction', 'N/A')}\n"
                content += f"資金費率: {kwargs.get('funding_rate', 'N/A')}%\n"
                content += f"結算時間: {kwargs.get('settlement_time', 'N/A')}\n"
                content += f"{'='*60}\n"
                
            elif step == 'leverage_set':
                content = f"[{display_time}] ⚙️ 槓桿設置完成: {kwargs.get('leverage', 'N/A')}倍\n"
                
            elif step == 'entry_price_fetched':
                content = f"[{display_time}] 📊 價格獲取完成: {kwargs.get('price', 'N/A')}\n"
                
            elif step == 'entry_quantity_calculated':
                content = f"[{display_time}] 📏 數量計算完成: {kwargs.get('quantity', 'N/A')}\n"
                
            elif step == 'entry_order_sent':
                content = f"[{display_time}] 📤 進場訂單發送: ID:{kwargs.get('order_id', 'N/A')} 耗時:{kwargs.get('order_time_ms', 'N/A')}ms\n"
                
            elif step == 'entry_success':
                content = f"[{display_time}] ✅ 進場成功: 成交量:{kwargs.get('executed_qty', 'N/A')} 均價:{kwargs.get('avg_price', 'N/A')}\n"
                content += f"[{display_time}] 🎯 預期盈利: {kwargs.get('expected_profit', 'N/A')} USDT\n"
                
            elif step == 'entry_failed':
                content = f"[{display_time}] ❌ 進場失敗: {kwargs.get('error', 'N/A')}\n"
                
            elif step == 'entry_complete':
                content = f"[{display_time}] 🏁 進場完成\n"
                content += f"{'='*60}\n\n"
                
            # ========== 平倉相關步驟 ==========
            elif step == 'close_start':
                content = f"\n{'='*60}\n"
                content += f"開始平倉: {symbol}\n"
                content += f"時間: {timestamp}\n"
                content += f"方向: {kwargs.get('direction', 'N/A')}\n"
                content += f"數量: {kwargs.get('quantity', 'N/A')}\n"
                content += f"{'='*60}\n"
                
            elif step == 'close_price_fetched':
                content = f"[{display_time}] 價格獲取完成: {kwargs.get('price', 'N/A')}\n"
                
            elif step == 'close_order_sent':
                content = f"[{display_time}] 訂單發送完成: ID:{kwargs.get('order_id', 'N/A')} 耗時:{kwargs.get('order_time_ms', 'N/A')}ms\n"
                
            elif step == 'close_success':
                content = f"[{display_time}] ✅ 平倉訂單成功: 成交量:{kwargs.get('executed_qty', 'N/A')} 均價:{kwargs.get('avg_price', 'N/A')}\n"
                
            elif step == 'close_failed':
                content = f"[{display_time}] ❌ 平倉失敗: {kwargs.get('error', 'N/A')}\n"
                
            elif step == 'close_position':
                content = f"[{display_time}] ✅ 平倉完成\n"
                content += f"[{display_time}] 📊 交易總結:\n"
                content += f"[{display_time}]    ├─ 方向: {kwargs.get('direction', 'N/A').upper()}\n"
                content += f"[{display_time}]    ├─ 數量: {kwargs.get('quantity', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 進場價: {kwargs.get('entry_price', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 平倉價: {kwargs.get('exit_price', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 盈虧: {kwargs.get('pnl', 'N/A')} USDT\n"
                content += f"[{display_time}]    ├─ 資金費率: {kwargs.get('funding_rate', 'N/A')}%\n"
                content += f"[{display_time}]    ├─ 持倉時間: {kwargs.get('position_duration_seconds', 'N/A')} 秒\n"
                content += f"[{display_time}]    ├─ 執行時間: {kwargs.get('execution_time_ms', 'N/A')} ms\n"
                content += f"[{display_time}]    ├─ 重試次數: {kwargs.get('retry_count', 'N/A')}\n"
                content += f"[{display_time}]    └─ 訂單ID: {kwargs.get('order_id', 'N/A')}\n"
                content += f"{'='*60}\n\n"
                
            # 極速平倉相關步驟
            elif step == 'fast_close_start':
                content = f"\n{'='*60}\n"
                content += f"🚀 開始極速平倉: {symbol}\n"
                content += f"時間: {timestamp}\n"
                content += f"方向: {kwargs.get('direction', 'N/A')}\n"
                content += f"數量: {kwargs.get('quantity', 'N/A')}\n"
                content += f"{'='*60}\n"
                
            elif step == 'fast_close_success':
                content = f"[{display_time}] ✅ 極速平倉成功: ID:{kwargs.get('order_id', 'N/A')} 耗時:{kwargs.get('execution_time_ms', 'N/A')}ms\n"
                content += f"[{display_time}] 成交量:{kwargs.get('executed_qty', 'N/A')} 均價:{kwargs.get('avg_price', 'N/A')}\n"
                # 如果有詳細信息，則顯示
                if kwargs.get('direction'):
                    content += f"[{display_time}] 📊 交易總結:\n"
                    content += f"[{display_time}]    ├─ 方向: {kwargs.get('direction', 'N/A').upper()}\n"
                    content += f"[{display_time}]    ├─ 數量: {kwargs.get('quantity', 'N/A')}\n"
                    content += f"[{display_time}]    ├─ 進場價: {kwargs.get('entry_price', 'N/A')}\n"
                    content += f"[{display_time}]    ├─ 平倉價: {kwargs.get('exit_price', 'N/A')}\n"
                    content += f"[{display_time}]    ├─ 盈虧: {kwargs.get('pnl', 'N/A')} USDT\n"
                    content += f"[{display_time}]    ├─ 資金費率: {kwargs.get('funding_rate', 'N/A')}%\n"
                    content += f"[{display_time}]    └─ 持倉時間: {kwargs.get('position_duration_seconds', 'N/A')} 秒\n"
                content += f"{'='*60}\n\n"
                
            elif step == 'fast_close_failed':
                content = f"[{display_time}] ❌ 極速平倉失敗: {kwargs.get('error', 'N/A')}\n"
                content += f"{'='*60}\n\n"
                
            # 超級極速平倉相關步驟
            elif step == 'ultra_fast_close_success':
                content = f"[{display_time}] ⚡ 超級極速平倉成功: ID:{kwargs.get('order_id', 'N/A')} 耗時:{kwargs.get('execution_time_ms', 'N/A')}ms\n"
                content += f"[{display_time}] 📊 方向:{kwargs.get('direction', 'N/A').upper()} 數量:{kwargs.get('quantity', 'N/A')}\n"
                content += f"[{display_time}] 🚀 方法:{kwargs.get('close_method', 'N/A')}\n"
                content += f"{'='*60}\n\n"
                
            elif step == 'ultra_fast_close_failed':
                content = f"[{display_time}] ❌ 超級極速平倉失敗: {kwargs.get('error', 'N/A')}\n"
                content += f"[{display_time}] 🔄 回退方案: {kwargs.get('fallback', 'N/A')}\n"
                content += f"{'='*60}\n\n"
                
            # 平倉完成詳細記錄（延後處理）
            elif step == 'close_position_detail':
                content = f"[{display_time}] 📋 平倉詳細總結 ({kwargs.get('processing_type', '延後處理')})\n"
                content += f"[{display_time}] 📊 完整交易數據:\n"
                content += f"[{display_time}]    ├─ 交易對: {symbol}\n"
                content += f"[{display_time}]    ├─ 方向: {kwargs.get('direction', 'N/A').upper()}\n"
                content += f"[{display_time}]    ├─ 數量: {kwargs.get('quantity', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 進場價: {kwargs.get('entry_price', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 平倉價: {kwargs.get('exit_price', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 盈虧: {kwargs.get('pnl', 'N/A')} USDT\n"
                content += f"[{display_time}]    ├─ 資金費率: {kwargs.get('funding_rate', 'N/A')}%\n"
                content += f"[{display_time}]    ├─ 持倉時間: {kwargs.get('position_duration_seconds', 'N/A')} 秒\n"
                content += f"[{display_time}]    ├─ 訂單ID: {kwargs.get('order_id', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 成交量: {kwargs.get('executed_qty', 'N/A')}\n"
                content += f"[{display_time}]    └─ 成交均價: {kwargs.get('avg_price', 'N/A')}\n"
                content += f"[{display_time}] ✅ 所有記錄和統計已完成\n"
                content += f"{'='*60}\n\n"
                
            # ========== 新增超詳細記錄類型 ==========
            elif step == 'close_with_full_context':
                content = f"\n{'='*90}\n"
                content += f"🎯 超詳細平倉記錄: {symbol}\n"
                content += f"時間: {timestamp}\n"
                content += f"{'='*90}\n"
                
                # 1. 訂單執行詳情
                order_details = kwargs.get('order_details', {})
                content += f"📋 訂單執行詳情:\n"
                content += f"   ├─ 訂單ID: {order_details.get('order_id', 'N/A')}\n"
                content += f"   ├─ 訂單狀態: {order_details.get('status', 'N/A')}\n"
                content += f"   ├─ 訂單類型: {order_details.get('type', 'N/A')}\n"
                content += f"   ├─ 訂單方向: {order_details.get('side', 'N/A')}\n"
                content += f"   ├─ 委託數量: {order_details.get('orig_qty', 'N/A')}\n"
                content += f"   ├─ 成交數量: {order_details.get('executed_qty', 'N/A')}\n"
                content += f"   ├─ 成交均價: {order_details.get('avg_price', 'N/A')}\n"
                content += f"   ├─ 成交金額: {order_details.get('cumulative_quote_qty', 'N/A')}\n"
                content += f"   ├─ 手續費: {order_details.get('commission', 'N/A')}\n"
                content += f"   ├─ 手續費資產: {order_details.get('commission_asset', 'N/A')}\n"
                content += f"   ├─ 創建時間: {order_details.get('time', 'N/A')}\n"
                content += f"   └─ 更新時間: {order_details.get('update_time', 'N/A')}\n"
                
                # 2. 網絡與API質量
                network_quality = kwargs.get('network_quality', {})
                content += f"🌐 網絡與API質量:\n"
                content += f"   ├─ API響應時間: {network_quality.get('api_response_ms', 'N/A')}ms\n"
                content += f"   ├─ 連接狀態: {network_quality.get('connection_status', 'N/A')}\n"
                content += f"   └─ 請求質量評分: {network_quality.get('request_quality_score', 'N/A')}\n"
                
                # 3. 賬戶餘額變化
                balance_changes = kwargs.get('balance_changes', {})
                content += f"💰 賬戶餘額變化:\n"
                content += f"   ├─ 平倉前餘額: {balance_changes.get('balance_before', 'N/A')} USDT\n"
                content += f"   ├─ 平倉後餘額: {balance_changes.get('balance_after', 'N/A')} USDT\n"
                content += f"   ├─ 餘額變化: {balance_changes.get('balance_change', 'N/A')} USDT\n"
                content += f"   ├─ 可用餘額: {balance_changes.get('available_balance', 'N/A')} USDT\n"
                content += f"   ├─ 佔用保證金: {balance_changes.get('used_margin', 'N/A')} USDT\n"
                content += f"   ├─ 未實現盈虧: {balance_changes.get('unrealized_pnl', 'N/A')} USDT\n"
                content += f"   └─ 錢包餘額: {balance_changes.get('wallet_balance', 'N/A')} USDT\n"
                
                # 4. 市場深度與流動性
                market_depth = kwargs.get('market_depth', {})
                content += f"📊 市場深度與流動性:\n"
                content += f"   ├─ 最佳買價: {market_depth.get('best_bid', 'N/A')}\n"
                content += f"   ├─ 最佳賣價: {market_depth.get('best_ask', 'N/A')}\n"
                content += f"   ├─ 買價量: {market_depth.get('bid_qty', 'N/A')}\n"
                content += f"   ├─ 賣價量: {market_depth.get('ask_qty', 'N/A')}\n"
                content += f"   ├─ 點差: {market_depth.get('spread', 'N/A')}\n"
                content += f"   ├─ 點差百分比: {market_depth.get('spread_percentage', 'N/A')}%\n"
                content += f"   └─ 流動性評分: {market_depth.get('liquidity_score', 'N/A')}\n"
                
                # 5. 系統性能指標
                system_metrics = kwargs.get('system_metrics', {})
                content += f"⚡ 系統性能指標:\n"
                content += f"   ├─ CPU使用率: {system_metrics.get('cpu_usage', 'N/A')}%\n"
                content += f"   ├─ 記憶體使用: {system_metrics.get('memory_usage', 'N/A')}%\n"
                content += f"   ├─ 線程數: {system_metrics.get('thread_count', 'N/A')}\n"
                content += f"   ├─ 處理時間: {system_metrics.get('processing_time_ms', 'N/A')}ms\n"
                content += f"   └─ 系統負載: {system_metrics.get('system_load', 'N/A')}\n"
                
                content += f"{'='*90}\n\n"
                
            # ========== 市場數據分析記錄 ==========
            elif step == 'close_market_analysis':
                content = f"\n{'='*80}\n"
                content += f"📊 平倉市場分析: {symbol}\n"
                content += f"時間: {timestamp}\n"
                content += f"{'='*80}\n"
                
                # 24小時統計
                daily_stats = kwargs.get('daily_stats', {})
                content += f"📈 24小時統計:\n"
                content += f"   ├─ 開盤價: {daily_stats.get('open_price', 'N/A')}\n"
                content += f"   ├─ 最高價: {daily_stats.get('high_price', 'N/A')}\n"
                content += f"   ├─ 最低價: {daily_stats.get('low_price', 'N/A')}\n"
                content += f"   ├─ 收盤價: {daily_stats.get('close_price', 'N/A')}\n"
                content += f"   ├─ 成交量: {daily_stats.get('volume', 'N/A')}\n"
                content += f"   ├─ 成交額: {daily_stats.get('quote_volume', 'N/A')}\n"
                content += f"   ├─ 漲跌幅: {daily_stats.get('price_change_percent', 'N/A')}%\n"
                content += f"   └─ 波動率: {daily_stats.get('volatility', 'N/A')}%\n"
                
                content += f"{'='*80}\n\n"
                
            # ========== 極簡平倉相關步驟 ==========
            elif step == 'minimal_close_start':
                content = f"\n{'='*60}\n"
                content += f"⚡ 開始極簡平倉: {symbol}\n"
                content += f"時間: {timestamp}\n"
                content += f"策略: {kwargs.get('strategy', 'N/A')}\n"
                content += f"優化等級: {kwargs.get('optimization_level', 'N/A')}\n"
                content += f"方向: {kwargs.get('direction', 'N/A')}\n"
                content += f"數量: {kwargs.get('quantity', 'N/A')}\n"
                content += f"進場價: {kwargs.get('entry_price', 'N/A')}\n"
                content += f"資金費率: {kwargs.get('funding_rate', 'N/A')}%\n"
                content += f"{'='*60}\n"
                
            elif step == 'minimal_close_prepare':
                content = f"[{display_time}] 📤 {kwargs.get('action', '準備訂單')}\n"
                content += f"[{display_time}]    ├─ 訂單方向: {kwargs.get('side', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 訂單類型: {kwargs.get('order_type', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 僅減倉: {kwargs.get('reduce_only', 'N/A')}\n"
                content += f"[{display_time}]    └─ 優化: {kwargs.get('no_checks', 'N/A')}\n"
                
            elif step == 'minimal_close_order_success':
                content = f"[{display_time}] ✅ 極簡訂單成功: ID:{kwargs.get('order_id', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 執行時間: {kwargs.get('execution_time_ms', 'N/A')}ms\n"
                content += f"[{display_time}]    ├─ 成交量: {kwargs.get('executed_qty', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 成交價: {kwargs.get('avg_price', 'N/A')}\n"
                content += f"[{display_time}]    └─ 狀態: {kwargs.get('order_status', 'N/A')}\n"
                
            elif step == 'minimal_close_complete':
                content = f"[{display_time}] 🎯 極簡平倉完成\n"
                content += f"[{display_time}] 📊 最終交易總結:\n"
                content += f"[{display_time}]    ├─ 交易對: {symbol}\n"
                content += f"[{display_time}]    ├─ 方向: {kwargs.get('direction', 'N/A').upper()}\n"
                content += f"[{display_time}]    ├─ 數量: {kwargs.get('quantity', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 進場價: {kwargs.get('entry_price', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 平倉價: {kwargs.get('exit_price', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 盈虧: {kwargs.get('pnl', 'N/A')} USDT\n"
                content += f"[{display_time}]    ├─ 資金費率: {kwargs.get('funding_rate', 'N/A')}%\n"
                content += f"[{display_time}]    ├─ 持倉時間: {kwargs.get('position_duration_seconds', 'N/A')} 秒\n"
                content += f"[{display_time}]    ├─ 執行時間: {kwargs.get('execution_time_ms', 'N/A')} ms\n"
                content += f"[{display_time}]    ├─ 重試次數: {kwargs.get('retry_count', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 檢查次數: {kwargs.get('total_checks', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 處理類型: {kwargs.get('processing_type', 'N/A')}\n"
                content += f"[{display_time}]    └─ 訂單ID: {kwargs.get('order_id', 'N/A')}\n"
                content += f"[{display_time}] ⚡ 極簡平倉策略執行完成\n"
                content += f"{'='*60}\n\n"
                
            elif step == 'minimal_close_failed':
                content = f"[{display_time}] ❌ 極簡平倉失敗: {kwargs.get('error', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 方向: {kwargs.get('direction', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 數量: {kwargs.get('quantity', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 重試: {kwargs.get('retry_attempt', 'N/A')}\n"
                content += f"[{display_time}]    └─ 清理: {kwargs.get('cleanup_action', 'N/A')}\n"
                content += f"{'='*60}\n\n"
                
            # ========== 平倉方式選擇 ==========
            elif step == 'close_decision_start':
                content = f"\n{'='*60}\n"
                content += f"🤔 平倉方式選擇開始: {symbol}\n"
                content += f"時間: {timestamp}\n"
                content += f"CLOSE_BEFORE_SECONDS: {kwargs.get('close_before_seconds', 'N/A')}\n"
                content += f"{'='*60}\n"
                
            elif step == 'close_decision_made':
                content = f"[{display_time}] ✅ 選擇平倉方式: {kwargs.get('chosen_method', 'N/A')}\n"
                content += f"[{display_time}] 📋 選擇原因: {kwargs.get('reason', 'N/A')}\n"
                content += f"[{display_time}] 🔧 處理邏輯: {kwargs.get('logic', 'N/A')}\n"
                
            # ========== 極速平倉詳細步驟 ==========
            elif step.startswith('fast_close_step_'):
                step_name = step.replace('fast_close_step_', '')
                content = f"[{display_time}] 步驟{kwargs.get('step_number', '?')}: {kwargs.get('action', step_name)}\n"
                
                if step_name == 'side_determined':
                    content += f"[{display_time}]    └─ {kwargs.get('logic', 'N/A')}\n"
                elif step_name == 'prepare_api':
                    content += f"[{display_time}]    ├─ API方法: {kwargs.get('api_method', 'N/A')}\n"
                    content += f"[{display_time}]    └─ 參數: {kwargs.get('parameters', 'N/A')}\n"
                elif step_name == 'api_call_start':
                    content += f"[{display_time}]    └─ 端點: {kwargs.get('api_endpoint', 'N/A')}\n"
                elif step_name == 'api_response':
                    content += f"[{display_time}]    ├─ 執行時間: {kwargs.get('execution_time_ms', 'N/A')}ms\n"
                    content += f"[{display_time}]    └─ 回傳成功\n"
                elif step_name == 'extract_info':
                    content += f"[{display_time}]    ├─ 訂單ID: {kwargs.get('order_id', 'N/A')}\n"
                    content += f"[{display_time}]    ├─ 成交量: {kwargs.get('executed_qty', 'N/A')}\n"
                    content += f"[{display_time}]    └─ 均價: {kwargs.get('avg_price', 'N/A')}\n"
                elif step_name == 'clear_position':
                    content += f"[{display_time}]    └─ 清空: {kwargs.get('cleared_fields', 'N/A')}\n"
                elif step_name == 'schedule_post_process':
                    content += f"[{display_time}]    ├─ 延遲: {kwargs.get('delay_seconds', 'N/A')}秒\n"
                    content += f"[{display_time}]    └─ 任務: {kwargs.get('post_process_tasks', 'N/A')}\n"
                    
            # ========== 完整平倉詳細步驟 ==========
            elif step.startswith('complete_close_step_'):
                step_name = step.replace('complete_close_step_', '')
                content = f"[{display_time}] 步驟{kwargs.get('step_number', '?')}: {kwargs.get('action', step_name)}\n"
                
                if step_name == 'retry_check':
                    content += f"[{display_time}]    ├─ 重試次數: {kwargs.get('retry_count', 'N/A')}\n"
                    content += f"[{display_time}]    └─ 原因: {kwargs.get('reason', 'N/A')}\n"
                elif step_name == 'api_position_check':
                    content += f"[{display_time}]    └─ API方法: {kwargs.get('api_method', 'N/A')}\n"
                elif step_name == 'no_position':
                    content += f"[{display_time}]    ├─ 結果: {kwargs.get('result', 'N/A')}\n"
                    content += f"[{display_time}]    └─ 清理: {kwargs.get('cleanup_actions', 'N/A')}\n"
                elif step_name == 'position_validation':
                    content += f"[{display_time}]    ├─ 預期方向/實際: {kwargs.get('expected_direction', 'N/A')}/{kwargs.get('actual_direction', 'N/A')}\n"
                    content += f"[{display_time}]    └─ 預期數量/實際: {kwargs.get('expected_quantity', 'N/A')}/{kwargs.get('actual_quantity', 'N/A')}\n"
                elif step_name in ['direction_fix', 'quantity_fix']:
                    content += f"[{display_time}]    ├─ 預期: {kwargs.get('expected', 'N/A')}\n"
                    content += f"[{display_time}]    ├─ 實際: {kwargs.get('actual', 'N/A')}\n"
                    content += f"[{display_time}]    └─ 處理: {kwargs.get('action_taken', 'N/A')}\n"
                elif step_name == 'first_attempt':
                    content += f"[{display_time}]    ├─ 方向: {kwargs.get('direction', 'N/A')}\n"
                    content += f"[{display_time}]    ├─ 數量: {kwargs.get('quantity', 'N/A')}\n"
                    content += f"[{display_time}]    └─ 原因: {kwargs.get('reason', 'N/A')}\n"
                elif step_name == 'start_process':
                    content += f"[{display_time}]    ├─ 確認方向: {kwargs.get('validated_direction', 'N/A')}\n"
                    content += f"[{display_time}]    └─ 確認數量: {kwargs.get('validated_quantity', 'N/A')}\n"
                elif step_name == 'fetch_price_start':
                    content += f"[{display_time}]    ├─ API方法: {kwargs.get('api_method', 'N/A')}\n"
                    content += f"[{display_time}]    └─ 原因: {kwargs.get('reason', 'N/A')}\n"
                elif step_name == 'fetch_price_success':
                    content += f"[{display_time}]    ├─ 價格: {kwargs.get('current_price', 'N/A')}\n"
                    content += f"[{display_time}]    └─ 耗時: {kwargs.get('fetch_time_ms', 'N/A')}ms\n"
                elif step_name == 'determine_side':
                    content += f"[{display_time}]    └─ {kwargs.get('logic', 'N/A')}\n"
                elif step_name == 'prepare_order':
                    content += f"[{display_time}]    ├─ 參數: {kwargs.get('order_params', 'N/A')}\n"
                    content += f"[{display_time}]    └─ 參考價格: {kwargs.get('current_price', 'N/A')}\n"
                elif step_name == 'send_order_start':
                    content += f"[{display_time}]    ├─ API方法: {kwargs.get('api_method', 'N/A')}\n"
                    content += f"[{display_time}]    └─ 參數: {kwargs.get('order_params', 'N/A')}\n"
                elif step_name == 'order_response':
                    content += f"[{display_time}]    ├─ 執行時間: {kwargs.get('execution_time_ms', 'N/A')}ms\n"
                    content += f"[{display_time}]    ├─ 訂單ID: {kwargs.get('order_id', 'N/A')}\n"
                    content += f"[{display_time}]    ├─ 成交量: {kwargs.get('executed_qty', 'N/A')}\n"
                    content += f"[{display_time}]    └─ 均價: {kwargs.get('avg_price', 'N/A')}\n"
                    
            # ========== 完整平倉開始 ==========
            elif step == 'complete_close_start':
                content = f"\n{'='*60}\n"
                content += f"🔧 開始完整平倉: {symbol}\n"
                content += f"時間: {timestamp}\n"
                content += f"方向: {kwargs.get('direction', 'N/A')}\n"
                content += f"數量: {kwargs.get('quantity', 'N/A')}\n"
                content += f"重試次數: {kwargs.get('retry_count', 'N/A')}\n"
                content += f"包含功能: {kwargs.get('includes_features', 'N/A')}\n"
                content += f"{'='*60}\n"
                
            # 強制平倉相關步驟
            elif step == 'force_close_start':
                content = f"\n{'='*60}\n"
                content += f"⚡ 開始強制平倉: {symbol}\n"
                content += f"時間: {timestamp}\n"
                content += f"方向: {kwargs.get('direction', 'N/A')}\n"
                content += f"數量: {kwargs.get('quantity', 'N/A')}\n"
                content += f"{'='*60}\n"
                
            elif step == 'force_close_success':
                content = f"[{display_time}] ✅ 強制平倉成功: ID:{kwargs.get('order_id', 'N/A')} 耗時:{kwargs.get('execution_time_ms', 'N/A')}ms\n"
                content += f"[{display_time}] 重試次數:{kwargs.get('retry_count', 'N/A')} 實際進場價:{kwargs.get('actual_entry_price', 'N/A')} 未實現盈虧:{kwargs.get('unrealized_pnl', 'N/A')}\n"
                content += f"{'='*60}\n\n"
                
            elif step == 'force_close_failed':
                content = f"[{display_time}] ❌ 強制平倉失敗: {kwargs.get('error', 'N/A')} (重試次數:{kwargs.get('retry_count', 'N/A')})\n"
                content += f"{'='*60}\n\n"
                
            elif step == 'force_close_no_position':
                content = f"[{display_time}] ℹ️ 強制平倉檢查: 已無持倉，無需平倉\n"
                content += f"{'='*60}\n\n"
                
            # 倉位清理相關步驟  
            elif step == 'cleanup_start':
                content = f"\n{'='*60}\n"
                content += f"🧹 開始清理超時倉位: {symbol}\n"
                content += f"時間: {timestamp}\n"
                content += f"方向: {kwargs.get('direction', 'N/A')}\n"
                content += f"數量: {kwargs.get('quantity', 'N/A')}\n"
                content += f"持倉時間: {kwargs.get('age_seconds', 'N/A')} 秒\n"
                content += f"清理原因: {kwargs.get('reason', 'N/A')}\n"
                content += f"{'='*60}\n"
                
            elif step == 'cleanup_success':
                content = f"[{display_time}] ✅ 倉位清理成功: ID:{kwargs.get('order_id', 'N/A')} 耗時:{kwargs.get('execution_time_ms', 'N/A')}ms\n"
                content += f"[{display_time}] 持倉時間:{kwargs.get('age_seconds', 'N/A')}秒 原因:{kwargs.get('reason', 'N/A')}\n"
                content += f"{'='*60}\n\n"
                
            elif step == 'cleanup_failed':
                content = f"[{display_time}] ❌ 倉位清理失敗: {kwargs.get('error', 'N/A')}\n"
                content += f"[{display_time}] 方向:{kwargs.get('direction', 'N/A')} 數量:{kwargs.get('quantity', 'N/A')}\n"
                content += f"{'='*60}\n\n"
                
            # ========== 新增詳細記錄類型 ==========
            # 超級極速平倉詳細記錄
            elif step == 'ultra_fast_close_detailed_start':
                content = f"\n{'='*80}\n"
                content += f"⚡ 超級極速平倉啟動: {symbol}\n"
                content += f"時間: {timestamp}\n"
                content += f"最佳化等級: {kwargs.get('optimization_level', 'N/A')}\n"
                
                # 交易基本信息
                trade_info = kwargs.get('trade_basic_info', {})
                content += f"📊 交易信息:\n"
                content += f"   ├─ 方向: {trade_info.get('direction', 'N/A')}\n"
                content += f"   ├─ 數量: {trade_info.get('quantity', 'N/A')}\n"
                content += f"   ├─ 進場價: {trade_info.get('entry_price', 'N/A')}\n"
                content += f"   └─ 資金費率: {trade_info.get('funding_rate', 'N/A')}%\n"
                
                # 市場快照
                market_info = kwargs.get('market_snapshot', {})
                content += f"📈 市場狀況:\n"
                content += f"   ├─ 買價: {market_info.get('bid_price', 'N/A')}\n"
                content += f"   ├─ 賣價: {market_info.get('ask_price', 'N/A')}\n"
                content += f"   ├─ 中間價: {market_info.get('mid_price', 'N/A')}\n"
                content += f"   ├─ 點差: {market_info.get('spread_percentage', 'N/A')}\n"
                content += f"   └─ 流動性: {market_info.get('liquidity_rating', 'N/A')}\n"
                
                # 系統狀態
                system_info = kwargs.get('system_status', {})
                content += f"🔧 系統狀態:\n"
                content += f"   ├─ 校正時間: {system_info.get('corrected_time_ms', 'N/A')}ms\n"
                content += f"   ├─ 時間偏移: {system_info.get('time_offset_ms', 'N/A')}ms\n"
                content += f"   ├─ 重試次數: {system_info.get('retry_count', 'N/A')}\n"
                content += f"   └─ 首次嘗試: {system_info.get('is_first_attempt', 'N/A')}\n"
                
                content += f"{'='*80}\n"
                
            elif step == 'ultra_fast_close_detailed_success':
                content = f"[{display_time}] ✅ 超級極速平倉成功: ID:{kwargs.get('order_id', 'N/A')}\n"
                
                # 執行結果
                exec_result = kwargs.get('execution_result', {})
                content += f"[{display_time}] 📊 執行結果:\n"
                content += f"[{display_time}]    ├─ 訂單狀態: {exec_result.get('order_status', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 成交量: {exec_result.get('executed_qty', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 成交價: {exec_result.get('avg_price', 'N/A')}\n"
                content += f"[{display_time}]    └─ 執行方向: {exec_result.get('side_executed', 'N/A')}\n"
                
                # 效能指標
                performance = kwargs.get('performance_metrics', {})
                content += f"[{display_time}] ⚡ 效能指標:\n"
                content += f"[{display_time}]    ├─ API響應: {performance.get('api_response_time_ms', 'N/A')}ms\n"
                content += f"[{display_time}]    ├─ 總處理時間: {performance.get('total_process_time_ms', 'N/A')}ms\n"
                content += f"[{display_time}]    ├─ 準備時間: {performance.get('api_prepare_time_ms', 'N/A')}ms\n"
                content += f"[{display_time}]    ├─ 效率評分: {performance.get('efficiency_score', 'N/A')}\n"
                content += f"[{display_time}]    └─ 速度評級: {performance.get('speed_rating', 'N/A')}\n"
                
                # 價格執行分析
                price_analysis = kwargs.get('price_execution_analysis', {})
                if price_analysis:
                    content += f"[{display_time}] 💰 價格分析:\n"
                    content += f"[{display_time}]    ├─ 滑點: {price_analysis.get('slippage_percentage', 'N/A')}\n"
                    content += f"[{display_time}]    ├─ 相對中間價: {price_analysis.get('vs_mid_price', 'N/A')}\n"
                    content += f"[{display_time}]    └─ 執行品質: {price_analysis.get('execution_quality', 'N/A')}\n"
                
                # 市場條件影響
                market_impact = kwargs.get('market_condition_impact', {})
                content += f"[{display_time}] 📊 市場影響:\n"
                content += f"[{display_time}]    ├─ 流動性: {market_impact.get('market_liquidity', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 執行時點差: {market_impact.get('spread_at_execution', 'N/A')}\n"
                content += f"[{display_time}]    └─ 最佳執行窗口: {market_impact.get('optimal_execution_window', 'N/A')}\n"
                
                content += f"{'='*80}\n\n"
                
            elif step == 'ultra_fast_close_detailed_failed':
                content = f"[{display_time}] ❌ 超級極速平倉失敗: {kwargs.get('error', 'N/A')}\n"
                content += f"[{display_time}] 錯誤類型: {kwargs.get('error_type', 'N/A')}\n"
                
                # 失敗分析
                failure_analysis = kwargs.get('failure_analysis', {})
                content += f"[{display_time}] 🔍 失敗分析:\n"
                content += f"[{display_time}]    ├─ 失敗前耗時: {failure_analysis.get('total_time_before_error_ms', 'N/A')}ms\n"
                content += f"[{display_time}]    ├─ 失敗階段: {failure_analysis.get('failure_stage', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 嚴重程度: {failure_analysis.get('error_severity', 'N/A')}\n"
                content += f"[{display_time}]    └─ 建議重試: {failure_analysis.get('retry_recommended', 'N/A')}\n"
                
                # 失敗時上下文
                context = kwargs.get('context_at_failure', {})
                content += f"[{display_time}] 📋 失敗上下文:\n"
                content += f"[{display_time}]    ├─ 方向: {context.get('direction', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 數量: {context.get('quantity', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 重試次數: {context.get('retry_count', 'N/A')}\n"
                content += f"[{display_time}]    └─ 市場流動性: {context.get('market_liquidity', 'N/A')}\n"
                
                content += f"[{display_time}] 🔄 回退方案: {kwargs.get('fallback_action', 'N/A')}\n"
                content += f"[{display_time}] ➡️ 下個方法: {kwargs.get('next_method', 'N/A')}\n"
                content += f"{'='*80}\n\n"
                
            # 強制平倉詳細記錄
            elif step == 'force_close_detailed_start':
                content = f"\n{'='*80}\n"
                content += f"🚨 強制平倉開始: {symbol}\n"
                content += f"時間: {timestamp}\n"
                content += f"觸發原因: {kwargs.get('trigger_reason', 'N/A')}\n"
                
                # 初始倉位信息
                initial_pos = kwargs.get('initial_position', {})
                content += f"📊 初始倉位:\n"
                content += f"   ├─ 方向: {initial_pos.get('direction', 'N/A')}\n"
                content += f"   ├─ 數量: {initial_pos.get('quantity', 'N/A')}\n"
                content += f"   ├─ 進場價: {initial_pos.get('entry_price', 'N/A')}\n"
                content += f"   └─ 資金費率: {initial_pos.get('funding_rate', 'N/A')}%\n"
                
                # 系統狀態
                system_status = kwargs.get('system_status', {})
                content += f"🔧 系統狀態:\n"
                content += f"   ├─ 重試次數: {system_status.get('retry_count', 'N/A')}/{system_status.get('max_retry', 'N/A')}\n"
                content += f"   ├─ 重試歷時: {system_status.get('retry_duration_seconds', 'N/A')}秒\n"
                content += f"   └─ 校正時間: {system_status.get('corrected_time_ms', 'N/A')}ms\n"
                
                # 市場條件
                market_cond = kwargs.get('market_conditions', {})
                content += f"📈 市場條件:\n"
                content += f"   ├─ 買價: {market_cond.get('bid_price', 'N/A')}\n"
                content += f"   ├─ 賣價: {market_cond.get('ask_price', 'N/A')}\n"
                content += f"   ├─ 點差: {market_cond.get('spread_percentage', 'N/A')}\n"
                content += f"   └─ 流動性: {market_cond.get('liquidity_status', 'N/A')}\n"
                
                content += f"{'='*80}\n"
                
            elif step == 'force_close_detailed_success':
                content = f"[{display_time}] ✅ 強制平倉成功: ID:{kwargs.get('order_id', 'N/A')}\n"
                
                # 執行結果
                exec_result = kwargs.get('execution_result', {})
                content += f"[{display_time}] 📊 執行結果:\n"
                content += f"[{display_time}]    ├─ 訂單狀態: {exec_result.get('order_status', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 成交量: {exec_result.get('executed_qty', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 成交價: {exec_result.get('avg_price', 'N/A')}\n"
                content += f"[{display_time}]    └─ 執行方向: {exec_result.get('side_executed', 'N/A')}\n"
                
                # 效能指標
                performance = kwargs.get('performance_metrics', {})
                content += f"[{display_time}] ⚡ 效能指標:\n"
                content += f"[{display_time}]    ├─ API響應: {performance.get('api_response_time_ms', 'N/A')}ms\n"
                content += f"[{display_time}]    ├─ 總處理時間: {performance.get('total_process_time_ms', 'N/A')}ms\n"
                content += f"[{display_time}]    ├─ 倉位檢查: {performance.get('position_check_time_ms', 'N/A')}ms\n"
                content += f"[{display_time}]    └─ 執行品質: {performance.get('execution_quality', 'N/A')}\n"
                
                # 市場執行分析
                market_exec = kwargs.get('market_execution_analysis', {})
                content += f"[{display_time}] 💰 市場執行:\n"
                content += f"[{display_time}]    ├─ 滑點: {market_exec.get('slippage_percentage', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 流動性消耗: {market_exec.get('liquidity_consumption', 'N/A')}\n"
                content += f"[{display_time}]    └─ 市場影響: {market_exec.get('market_impact', 'N/A')}\n"
                
                # 重試上下文
                retry_context = kwargs.get('retry_context', {})
                content += f"[{display_time}] 🔄 重試歷程:\n"
                content += f"[{display_time}]    ├─ 重試次數: {retry_context.get('retry_count', 'N/A')}/{retry_context.get('max_retry', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 重試歷時: {retry_context.get('retry_duration_seconds', 'N/A')}秒\n"
                content += f"[{display_time}]    └─ 前次狀況: {retry_context.get('previous_attempts', 'N/A')}\n"
                
                # 倉位校正
                position_recon = kwargs.get('position_reconciliation', {})
                content += f"[{display_time}] 📋 倉位校正:\n"
                content += f"[{display_time}]    ├─ 原始進場價: {position_recon.get('original_entry_price', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 實際進場價: {position_recon.get('actual_entry_price', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 未實現盈虧: {position_recon.get('unrealized_pnl', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 保證金類型: {position_recon.get('margin_type', 'N/A')}\n"
                content += f"[{display_time}]    └─ 倉位準確性: {position_recon.get('position_accuracy', 'N/A')}\n"
                
                content += f"{'='*80}\n\n"
                
            elif step == 'force_close_detailed_failed':
                content = f"[{display_time}] ❌ 強制平倉失敗: {kwargs.get('error', 'N/A')}\n"
                content += f"[{display_time}] 錯誤類型: {kwargs.get('error_type', 'N/A')}\n"
                
                # 失敗分析
                failure_analysis = kwargs.get('failure_analysis', {})
                content += f"[{display_time}] 🔍 失敗分析:\n"
                content += f"[{display_time}]    ├─ 失敗前耗時: {failure_analysis.get('total_time_before_error_ms', 'N/A')}ms\n"
                content += f"[{display_time}]    ├─ 失敗階段: {failure_analysis.get('failure_stage', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 嚴重程度: {failure_analysis.get('error_severity', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 最終嘗試: {failure_analysis.get('is_final_attempt', 'N/A')}\n"
                content += f"[{display_time}]    └─ 重試已耗盡: {failure_analysis.get('retry_exhausted', 'N/A')}\n"
                
                # 重試歷史
                retry_history = kwargs.get('retry_history', {})
                content += f"[{display_time}] 📊 重試歷史:\n"
                content += f"[{display_time}]    ├─ 重試次數: {retry_history.get('retry_count', 'N/A')}/{retry_history.get('max_retry', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 重試歷時: {retry_history.get('retry_duration_seconds', 'N/A')}秒\n"
                content += f"[{display_time}]    └─ 全部失敗: {retry_history.get('all_attempts_failed', 'N/A')}\n"
                
                # 失敗時上下文
                context = kwargs.get('context_at_failure', {})
                content += f"[{display_time}] 📋 失敗上下文:\n"
                content += f"[{display_time}]    ├─ 方向: {context.get('direction', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 數量: {context.get('quantity', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 市場流動性: {context.get('market_liquidity', 'N/A')}\n"
                content += f"[{display_time}]    └─ 有實際倉位: {context.get('has_actual_position', 'N/A')}\n"
                
                # 影響評估
                impact = kwargs.get('impact_assessment', {})
                content += f"[{display_time}] ⚠️ 影響評估:\n"
                content += f"[{display_time}]    ├─ 倉位狀態: {impact.get('position_status', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 風險等級: {impact.get('risk_level', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 需人工介入: {impact.get('manual_intervention_required', 'N/A')}\n"
                content += f"[{display_time}]    └─ 建議動作: {impact.get('suggested_actions', 'N/A')}\n"
                
                content += f"{'='*80}\n\n"
                
            # 其他新增的詳細記錄類型
            elif step == 'force_close_no_position_detailed':
                content = f"[{display_time}] ℹ️ 強制平倉檢查: {kwargs.get('check_result', 'N/A')}\n"
                content += f"[{display_time}] 檢查耗時: {kwargs.get('position_check_time_ms', 'N/A')}ms\n"
                content += f"[{display_time}] 清理動作: {kwargs.get('cleanup_actions', 'N/A')}\n"
                content += f"{'='*60}\n\n"
                
            elif step == 'force_close_position_validated':
                content = f"[{display_time}] ✅ 倉位驗證完成: 耗時{kwargs.get('position_check_time_ms', 'N/A')}ms\n"
                
                # 實際倉位信息
                actual_pos = kwargs.get('actual_position', {})
                content += f"[{display_time}] 📊 實際倉位:\n"
                content += f"[{display_time}]    ├─ 方向: {actual_pos.get('direction', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 數量: {actual_pos.get('quantity', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 進場價: {actual_pos.get('entry_price', 'N/A')}\n"
                content += f"[{display_time}]    └─ 未實現盈虧: {actual_pos.get('unrealized_pnl', 'N/A')}\n"
                
                # 倉位比較
                pos_comp = kwargs.get('position_comparison', {})
                content += f"[{display_time}] 🔍 倉位比較:\n"
                content += f"[{display_time}]    ├─ 方向匹配: {pos_comp.get('direction_match', 'N/A')}\n"
                content += f"[{display_time}]    ├─ 數量匹配: {pos_comp.get('quantity_match', 'N/A')}\n"
                content += f"[{display_time}]    └─ 有差異: {pos_comp.get('has_discrepancy', 'N/A')}\n"
                
                content += f"[{display_time}] 將使用實際倉位: {kwargs.get('will_use_actual_position', 'N/A')}\n"
                
            elif step == 'ultra_fast_api_prepare':
                content = f"[{display_time}] 🔧 API準備: {kwargs.get('api_method', 'N/A')}\n"
                content += f"[{display_time}] 預期方向: {kwargs.get('expected_side', 'N/A')}\n"
                content += f"[{display_time}] 準備耗時: {kwargs.get('prepare_time_ms', 'N/A')}ms\n"
                content += f"[{display_time}] 訂單參數: {kwargs.get('order_params', 'N/A')}\n"
                
            else:
                # 其他步驟的一般記錄
                content = f"[{display_time}] {step}: {kwargs}\n"
            
            # 效率優化: 使用緩存機制減少I/O操作
            self._analysis_buffer.append(content)
            
            # 只在以下情況才立即寫入:
            # 1. 關鍵步驟 (交易完成、失敗等)
            # 2. 緩存滿了 (20條記錄)  
            # 3. 緩存超時 (2秒)
            if is_critical or is_buffer_full or is_buffer_timeout:
                self._flush_analysis_buffer()
                
        except Exception as e:
            print(f"[{self.format_corrected_time()}] 記錄平倉分析失敗: {e}")
    
    def _flush_analysis_buffer(self):
        """批量寫入緩存的分析記錄"""
        try:
            if hasattr(self, '_analysis_buffer') and self._analysis_buffer:
                with open('logs/trade_analysis.txt', 'a', encoding='utf-8') as f:
                    f.write(''.join(self._analysis_buffer))
                    f.flush()
                
                # 重置緩存
                self._analysis_buffer = []
                self._buffer_start_time = time.time()
                
        except Exception as e:
            print(f"[{self.format_corrected_time()}] 批量寫入分析記錄失敗: {e}")

    def print_detailed_timestamps(self, symbol: str):
        """顯示詳細的時間記錄"""
        if symbol in self.entry_timestamps:
            print(f"\n=== {symbol} 進倉時間記錄 ===")
            for step, data in self.entry_timestamps[symbol].items():
                print(f"  {step}: {data['timestamp']} - {data['details']}")
        
        if symbol in self.close_timestamps:
            print(f"\n=== {symbol} 平倉時間記錄 ===")
            for step, data in self.close_timestamps[symbol].items():
                print(f"  {step}: {data['timestamp']} - {data['details']}")
                
    def calculate_position_size(self, symbol: str, current_price: float) -> float:
        """計算持倉數量"""
        # 計算目標倉位大小：保證金 × 槓桿
        target_position_value = self.max_position_size * self.leverage
        
        # 計算數量：目標倉位大小 / 價格
        quantity = target_position_value / current_price
        
        # 極簡數量格式化：直接取整，確保數量不會太小
        quantity = int(quantity)
        
        # 確保數量至少為1
        if quantity < 1:
            quantity = 1
            
        print(f"[{self.format_corrected_time()}] 計算數量: 價格={current_price}, 目標倉位={target_position_value} USDT, 原始數量={target_position_value / current_price:.6f}, 最終數量={quantity}, 實際倉位={quantity * current_price:.2f} USDT, 所需保證金={(quantity * current_price) / self.leverage:.2f} USDT")
        
        return quantity

    def update_funding_rates(self):
        """定期更新資金費率數據"""
        try:
            # 獲取最新的資金費率數據
            df = self.get_funding_rates()
            
            # 更新資金費率字典
            self.funding_rates = {}
            for _, row in df.iterrows():
                self.funding_rates[row['symbol']] = {
                    'funding_rate': row['funding_rate'],
                    'next_funding_time': row['next_funding_time']
                }
            
            return len(df)
        except Exception as e:
            print(f"[{self.format_corrected_time()}] 更新資金費率時發生錯誤: {e}")
            return 0

    def run_with_smart_restart(self, max_restarts=10, restart_delay=10):
        """智能重啟邏輯 - 根據錯誤類型決定是否重啟"""
        restart_count = 0
        
        while restart_count < max_restarts:
            try:
                print(f"[{self.format_corrected_time()}] 啟動交易機器人 (第{restart_count + 1}次)")
                self.run()
                
            except KeyboardInterrupt:
                print(f"\n[{self.format_corrected_time()}] 收到鍵盤中斷信號，程式退出")
                break
                
            except Exception as e:
                restart_count += 1
                error_msg = str(e)
                print(f"[{self.format_corrected_time()}] 程式異常: {error_msg}")
                print(f"[{self.format_corrected_time()}] 錯誤詳情: {traceback.format_exc()}")
                
                # 判斷是否應該重啟
                should_restart = self.should_restart_on_error(error_msg)
                
                if should_restart and restart_count < max_restarts:
                    print(f"[{self.format_corrected_time()}] 錯誤可恢復，等待 {restart_delay} 秒後重啟... (重啟次數: {restart_count}/{max_restarts})")
                    time.sleep(restart_delay)
                else:
                    if not should_restart:
                        print(f"[{self.format_corrected_time()}] 錯誤不可恢復，停止重啟")
                    else:
                        print(f"[{self.format_corrected_time()}] 重啟次數已達上限，程式退出")
                    break
        
        # 最終清理
        if self.current_position:
            print(f"[{self.format_corrected_time()}] 程式最終退出，嘗試清理持倉...")
            try:
                self.force_close_position()
            except Exception as e:
                print(f"[{self.format_corrected_time()}] 清理持倉失敗: {e}")

    def should_restart_on_error(self, error_msg):
        """判斷錯誤是否應該重啟"""
        # 可恢復的錯誤（網路、API限流等）
        recoverable_errors = [
            'Connection',
            'Timeout',
            'Network',
            'rate limit',
            'too many requests',
            'API',
            'WebSocket'
        ]
        
        # 不可恢復的錯誤（配置錯誤、認證失敗等）
        non_recoverable_errors = [
            'Invalid API key',
            'Invalid signature',
            'Configuration',
            'Authentication',
            'Permission'
        ]
        
        error_lower = error_msg.lower()
        
        # 檢查不可恢復的錯誤
        for error in non_recoverable_errors:
            if error.lower() in error_lower:
                return False
        
        # 檢查可恢復的錯誤
        for error in recoverable_errors:
            if error.lower() in error_lower:
                return True
        
        # 預設為可恢復（保守策略）
        return True

    def run_with_restart(self, max_restarts=5, restart_delay=10):
        """帶重啟邏輯的運行方法"""
        restart_count = 0
        
        while restart_count < max_restarts:
            try:
                print(f"[{self.format_corrected_time()}] 啟動交易機器人 (第{restart_count + 1}次)")
                self.run()
                
            except KeyboardInterrupt:
                print(f"\n[{self.format_corrected_time()}] 收到鍵盤中斷信號，程式退出")
                break
                
            except Exception as e:
                restart_count += 1
                print(f"[{self.format_corrected_time()}] 程式異常: {e}")
                print(f"[{self.format_corrected_time()}] 錯誤詳情: {traceback.format_exc()}")
                
                if restart_count < max_restarts:
                    print(f"[{self.format_corrected_time()}] 等待 {restart_delay} 秒後重啟... (重啟次數: {restart_count}/{max_restarts})")
                    time.sleep(restart_delay)
                else:
                    print(f"[{self.format_corrected_time()}] 重啟次數已達上限，程式退出")
                    break
        
        # 最終清理
        if self.current_position:
            print(f"[{self.format_corrected_time()}] 程式最終退出，嘗試清理持倉...")
            try:
                self.force_close_position()
            except Exception as e:
                print(f"[{self.format_corrected_time()}] 清理持倉失敗: {e}")

    def get_detailed_balance_info(self):
        """獲取詳細的賬戶餘額信息"""
        try:
            account_info = self.client.futures_account()
            
            balance_info = {
                'total_wallet_balance': float(account_info.get('totalWalletBalance', 0)),
                'total_unrealized_pnl': float(account_info.get('totalUnrealizedProfit', 0)),
                'total_margin_balance': float(account_info.get('totalMarginBalance', 0)),
                'total_position_initial_margin': float(account_info.get('totalPositionInitialMargin', 0)),
                'total_open_order_initial_margin': float(account_info.get('totalOpenOrderInitialMargin', 0)),
                'available_balance': float(account_info.get('availableBalance', 0)),
                'max_withdraw_amount': float(account_info.get('maxWithdrawAmount', 0)),
                'can_trade': account_info.get('canTrade', False),
                'can_withdraw': account_info.get('canWithdraw', False),
                'can_deposit': account_info.get('canDeposit', False),
                'update_time': account_info.get('updateTime', 0)
            }
            
            return balance_info
        except Exception as e:
            print(f"[{self.format_corrected_time()}] 獲取賬戶餘額信息失敗: {e}")
            return {}

    def get_detailed_market_info(self, symbol: str):
        """獲取詳細的市場信息"""
        try:
            # 獲取24小時統計
            ticker_24h = self.client.futures_ticker(symbol=symbol)
            
            # 獲取訂單簿
            order_book = self.client.futures_order_book(symbol=symbol, limit=10)
            
            # 獲取最新價格
            current_price = float(self.client.futures_symbol_ticker(symbol=symbol)['price'])
            
            market_info = {
                'current_price': current_price,
                'price_change_24h': float(ticker_24h.get('priceChange', 0)),
                'price_change_percent_24h': float(ticker_24h.get('priceChangePercent', 0)),
                'high_price_24h': float(ticker_24h.get('highPrice', 0)),
                'low_price_24h': float(ticker_24h.get('lowPrice', 0)),
                'volume_24h': float(ticker_24h.get('volume', 0)),
                'quote_volume_24h': float(ticker_24h.get('quoteVolume', 0)),
                'open_price_24h': float(ticker_24h.get('openPrice', 0)),
                'close_price_24h': float(ticker_24h.get('lastPrice', 0)),
                'best_bid_price': float(order_book['bids'][0][0]) if order_book['bids'] else 0,
                'best_bid_qty': float(order_book['bids'][0][1]) if order_book['bids'] else 0,
                'best_ask_price': float(order_book['asks'][0][0]) if order_book['asks'] else 0,
                'best_ask_qty': float(order_book['asks'][0][1]) if order_book['asks'] else 0,
                'bid_ask_spread': float(order_book['asks'][0][0]) - float(order_book['bids'][0][0]) if order_book['bids'] and order_book['asks'] else 0,
                'spread_percentage': ((float(order_book['asks'][0][0]) - float(order_book['bids'][0][0])) / float(order_book['bids'][0][0]) * 100) if order_book['bids'] and order_book['asks'] else 0
            }
            
            return market_info
        except Exception as e:
            print(f"[{self.format_corrected_time()}] 獲取市場信息失敗: {e}")
            return {}

    def get_network_quality_info(self):
        """獲取網絡質量信息"""
        try:
            import psutil
            import time
            
            # 測試API響應時間
            start_time = time.time()
            self.client.futures_ping()
            api_response_time = int((time.time() - start_time) * 1000)
            
            # 獲取系統信息
            system_info = {
                'api_response_time_ms': api_response_time,
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'network_io_sent': psutil.net_io_counters().bytes_sent,
                'network_io_recv': psutil.net_io_counters().bytes_recv,
                'thread_count': psutil.Process().num_threads(),
                'timestamp': int(time.time() * 1000)
            }
            
            return system_info
        except Exception as e:
            print(f"[{self.format_corrected_time()}] 獲取網絡質量信息失敗: {e}")
                        return {}
    
    def execute_api_call_with_timeout(self, api_func, *args, max_retries=3, timeout=10, **kwargs):
        """執行API調用，包含超時處理和重試機制（併發保護版）"""
        
        # 🔒 併發保護：檢查是否可以進行API調用
        with self.api_call_lock:
            # 檢查是否超過最大併發數
            if self.concurrent_api_calls >= self.max_concurrent_api_calls:
                wait_time = 0.1
                print(f"[{self.format_corrected_time()}] 🔒 API調用排隊中，等待{wait_time}秒...")
                time.sleep(wait_time)
                
                # 再次檢查
                if self.concurrent_api_calls >= self.max_concurrent_api_calls:
                    raise Exception(f"API調用忙碌，已達到最大併發數限制: {self.max_concurrent_api_calls}")
            
            # 檢查是否有長時間運行的API調用
            if self.is_api_calling:
                stuck_duration = time.time() - self.api_call_start_time
                if stuck_duration > self.max_api_call_duration:
                    print(f"[{self.format_corrected_time()}] 🚨 檢測到卡住的API調用，已運行{stuck_duration:.1f}秒，重置狀態")
                    self.is_api_calling = False
                    self.concurrent_api_calls = 0
                else:
                    raise Exception(f"API調用進行中，已運行{stuck_duration:.1f}秒，請稍後重試")
            
            # 設置API調用狀態
            self.is_api_calling = True
            self.api_call_start_time = time.time()
            self.concurrent_api_calls += 1
        
        try:
            # 執行重試邏輯
            for attempt in range(max_retries + 1):
                try:
                    start_time = time.time()
                    
                    # 執行API調用
                    result = api_func(*args, **kwargs)
                    execution_time = int((time.time() - start_time) * 1000)
                    
                    # 記錄成功調用
                    if execution_time > 2000:  # 超過2秒的極慢調用
                        print(f"[{self.format_corrected_time()}] 🚨 API調用極慢: {api_func.__name__} - {execution_time}ms")
                    elif execution_time > 1000:  # 超過1秒的慢調用
                        print(f"[{self.format_corrected_time()}] ⚠️ API調用較慢: {api_func.__name__} - {execution_time}ms")
                    
                    return result
                        
                except (requests.exceptions.Timeout, requests.exceptions.RequestException, BinanceAPIException) as e:
                    execution_time = int((time.time() - start_time) * 1000)
                    
                    if attempt < max_retries:
                        backoff_time = (0.5 * (2 ** attempt))  # 指數退避：0.5s, 1s, 2s
                        print(f"[{self.format_corrected_time()}] ⚠️ API調用超時重試 {attempt+1}/{max_retries}: {api_func.__name__} - {execution_time}ms, 等待{backoff_time:.1f}秒後重試")
                        
                        # 🔒 重試期間暫時釋放鎖定，但保持計數
                        with self.api_call_lock:
                            self.is_api_calling = False
                        
                        time.sleep(backoff_time)
                        
                        # 重新獲取鎖定
                        with self.api_call_lock:
                            self.is_api_calling = True
                            self.api_call_start_time = time.time()
                    else:
                        print(f"[{self.format_corrected_time()}] ❌ API調用最終失敗: {api_func.__name__} - {execution_time}ms, 錯誤: {e}")
                        raise e
                        
                except Exception as e:
                    execution_time = int((time.time() - start_time) * 1000)
                    print(f"[{self.format_corrected_time()}] ❌ API調用異常: {api_func.__name__} - {execution_time}ms, 錯誤: {e}")
                    raise e
            
            raise Exception(f"API調用失敗，已重試{max_retries}次")
            
        finally:
            # 🔒 無論成功失敗都要重置狀態
            with self.api_call_lock:
                self.is_api_calling = False
                self.concurrent_api_calls = max(0, self.concurrent_api_calls - 1)
                
                # 如果有其他等待的API調用，記錄狀態
                if self.concurrent_api_calls > 0:
                    print(f"[{self.format_corrected_time()}] 📋 API調用完成，仍有{self.concurrent_api_calls}個調用進行中")
    
    def safe_api_call(self, api_func, *args, **kwargs):
        """安全的API調用包裝器"""
        try:
            return self.execute_api_call_with_timeout(api_func, *args, **kwargs)
        except Exception as e:
            print(f"[{self.format_corrected_time()}] API調用失敗: {api_func.__name__} - {e}")
            return None
    
    def record_detailed_close_analysis(self, symbol: str, order_data: dict, pre_balance: dict = None):
        """記錄詳細的平倉分析"""
        try:
            # 獲取平倉後的詳細信息
            post_balance = self.get_detailed_balance_info()
            market_info = self.get_detailed_market_info(symbol)
            network_info = self.get_network_quality_info()
            
            # 計算餘額變化
            balance_change = 0
            if pre_balance and post_balance:
                balance_change = post_balance.get('total_wallet_balance', 0) - pre_balance.get('total_wallet_balance', 0)
            
            # 記錄超詳細信息
            self.write_trade_analysis('close_with_full_context', symbol,
                                    order_details={
                                        'order_id': order_data.get('orderId', 'N/A'),
                                        'status': order_data.get('status', 'N/A'),
                                        'type': order_data.get('type', 'N/A'),
                                        'side': order_data.get('side', 'N/A'),
                                        'orig_qty': order_data.get('origQty', 'N/A'),
                                        'executed_qty': order_data.get('executedQty', 'N/A'),
                                        'avg_price': order_data.get('avgPrice', 'N/A'),
                                        'cumulative_quote_qty': order_data.get('cumQuote', 'N/A'),
                                        'commission': order_data.get('commission', 'N/A'),
                                        'commission_asset': order_data.get('commissionAsset', 'N/A'),
                                        'time': order_data.get('time', 'N/A'),
                                        'update_time': order_data.get('updateTime', 'N/A')
                                    },
                                    network_quality={
                                        'api_response_ms': network_info.get('api_response_time_ms', 'N/A'),
                                        'connection_status': '良好' if network_info.get('api_response_time_ms', 999) < 100 else '一般',
                                        'request_quality_score': '優' if network_info.get('api_response_time_ms', 999) < 50 else '良' if network_info.get('api_response_time_ms', 999) < 100 else '普通'
                                    },
                                    balance_changes={
                                        'balance_before': pre_balance.get('total_wallet_balance', 'N/A') if pre_balance else 'N/A',
                                        'balance_after': post_balance.get('total_wallet_balance', 'N/A'),
                                        'balance_change': balance_change if balance_change else 'N/A',
                                        'available_balance': post_balance.get('available_balance', 'N/A'),
                                        'used_margin': post_balance.get('total_position_initial_margin', 'N/A'),
                                        'unrealized_pnl': post_balance.get('total_unrealized_pnl', 'N/A'),
                                        'wallet_balance': post_balance.get('total_wallet_balance', 'N/A')
                                    },
                                    market_depth={
                                        'best_bid': market_info.get('best_bid_price', 'N/A'),
                                        'best_ask': market_info.get('best_ask_price', 'N/A'),
                                        'bid_qty': market_info.get('best_bid_qty', 'N/A'),
                                        'ask_qty': market_info.get('best_ask_qty', 'N/A'),
                                        'spread': market_info.get('bid_ask_spread', 'N/A'),
                                        'spread_percentage': f"{market_info.get('spread_percentage', 0):.4f}",
                                        'liquidity_score': '優' if market_info.get('spread_percentage', 999) < 0.1 else '良' if market_info.get('spread_percentage', 999) < 0.2 else '普通'
                                    },
                                    system_metrics={
                                        'cpu_usage': network_info.get('cpu_percent', 'N/A'),
                                        'memory_usage': network_info.get('memory_percent', 'N/A'),
                                        'thread_count': network_info.get('thread_count', 'N/A'),
                                        'processing_time_ms': network_info.get('api_response_time_ms', 'N/A'),
                                        'system_load': '正常' if network_info.get('cpu_percent', 100) < 80 else '偏高'
                                    })
            
            # 記錄市場分析
            self.write_trade_analysis('close_market_analysis', symbol,
                                    daily_stats={
                                        'open_price': market_info.get('open_price_24h', 'N/A'),
                                        'high_price': market_info.get('high_price_24h', 'N/A'),
                                        'low_price': market_info.get('low_price_24h', 'N/A'),
                                        'close_price': market_info.get('close_price_24h', 'N/A'),
                                        'volume': market_info.get('volume_24h', 'N/A'),
                                        'quote_volume': market_info.get('quote_volume_24h', 'N/A'),
                                        'price_change_percent': f"{market_info.get('price_change_percent_24h', 0):.4f}",
                                        'volatility': abs(market_info.get('price_change_percent_24h', 0))
                                    })
            
            print(f"[{self.format_corrected_time()}] ✅ 詳細平倉分析記錄完成: {symbol}")
            
        except Exception as e:
            print(f"[{self.format_corrected_time()}] 記錄詳細平倉分析失敗: {e}")

if __name__ == "__main__":
    try:
        # 清理舊日誌文件
        cleanup_old_logs()
        
        # 顯示日誌統計
        print(get_log_stats())
        
        # 創建交易機器人實例
        trader = FundingRateTrader()
        
        # 啟動時同步時間
        print("[LOG] 啟動時同步 Binance 服務器時間...")
        trader.sync_server_time()
        
        print("=== 資金費率套利機器人啟動 ===")
        print(f"啟動時間: {trader.format_corrected_time('%Y-%m-%d %H:%M:%S')}")
        print(f"最大保證金: {MAX_POSITION_SIZE} USDT")
        print(f"槓桿倍數: {LEVERAGE}")
        print(f"目標倉位大小: {MAX_POSITION_SIZE * LEVERAGE} USDT")
        print(f"最小資金費率: {MIN_FUNDING_RATE}%")
        print(f"進場提前時間: {ENTRY_BEFORE_SECONDS} 秒")
        print(f"平倉提前時間: {CLOSE_BEFORE_SECONDS} 秒")
        print(f"主循環檢查間隔: {CHECK_INTERVAL} 秒")
        print(f"持倉檢查間隔: {POSITION_CHECK_INTERVAL} 秒")
        print(f"交易時間: {TRADING_HOURS}")
        print(f"交易幣種: {TRADING_SYMBOLS if TRADING_SYMBOLS else '全部'}")
        print(f"排除幣種: {EXCLUDED_SYMBOLS}")
        print("--- 重試機制配置 ---")
        print(f"進場重試次數: {MAX_ENTRY_RETRY}")
        print(f"進場重試間隔: {ENTRY_RETRY_INTERVAL} 秒")
        print(f"結算前持續重試進場: {ENTRY_RETRY_UNTIL_SETTLEMENT}")
        print(f"平倉重試次數: {MAX_CLOSE_RETRY}")
        print(f"平倉重試間隔: {CLOSE_RETRY_INTERVAL} 秒")
        print(f"結算時強制平倉: {FORCE_CLOSE_AT_SETTLEMENT}")
        print(f"強制平倉時間: 結算後 {FORCE_CLOSE_AFTER_SECONDS} 秒")
        print("--- 定期檢查配置 ---")
        print(f"帳戶檢查間隔: {ACCOUNT_CHECK_INTERVAL} 秒")
        print(f"倉位超時時間: {POSITION_TIMEOUT_SECONDS} 秒")
        print(f"啟用倉位清理: {ENABLE_POSITION_CLEANUP}")
        print("=" * 50)
        
        # 使用 start() 方法，這樣會執行啟動通知
        trader.start()
        
    except KeyboardInterrupt:
        print("\n程序被用戶中斷")
        # 只在 trader.start() 方法未發送過停止通知時才發送
        try:
            if (hasattr(trader, 'profit_tracker') and trader.profit_tracker and 
                (not hasattr(trader, '_stop_notification_sent') or not trader._stop_notification_sent)):
                trader.profit_tracker.send_stop_notification()
                trader._stop_notification_sent = True
        except Exception as e:
            print(f"發送停止通知失敗: {e}")
    except Exception as e:
        print(f"程序異常退出: {e}")
        # 只在 trader.start() 方法未發送過停止通知時才發送
        try:
            if (hasattr(trader, 'profit_tracker') and trader.profit_tracker and 
                (not hasattr(trader, '_stop_notification_sent') or not trader._stop_notification_sent)):
                trader.profit_tracker.send_stop_notification()
                trader._stop_notification_sent = True
        except Exception as notify_e:
            print(f"發送停止通知失敗: {notify_e}")
        traceback.print_exc()
