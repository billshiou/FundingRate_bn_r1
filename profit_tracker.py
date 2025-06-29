#!/usr/bin/env python3
"""
收益追蹤和統計模組
包含 Telegram 通知功能
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests
from config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ENABLE_TELEGRAM_NOTIFY,
    NOTIFY_ON_TRADE, NOTIFY_ON_ERROR, NOTIFY_ON_START, NOTIFY_ON_STOP,
    MAX_POSITION_SIZE, LEVERAGE, MIN_FUNDING_RATE, 
    ENTRY_BEFORE_SECONDS, CLOSE_BEFORE_SECONDS,
    TRADING_HOURS, TRADING_SYMBOLS, EXCLUDED_SYMBOLS
)
import traceback

class ProfitTracker:
    def __init__(self):
        self.trades = []
        self.total_pnl = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.max_profit = 0.0
        self.max_loss = 0.0
        self.start_time = time.time()
        self.session_start_time = datetime.now()
        
        # 載入歷史數據
        self.load_trade_history()
        
        # 初始化帳戶分析器（延遲導入避免循環依賴）
        self.account_analyzer = None
        
        # 重置本次套利的統計數據
        self.reset_session_stats()
    
    def get_account_analyzer(self):
        """延遲初始化帳戶分析器"""
        if self.account_analyzer is None:
            try:
                from account_analyzer import AccountAnalyzer
                self.account_analyzer = AccountAnalyzer()
            except ImportError:
                print("警告: 無法導入帳戶分析器，將使用程式內部統計")
                return None
        return self.account_analyzer
    
    def compare_with_account_data(self, days: int = 7) -> Dict:
        """比較程式統計與實際帳戶數據"""
        analyzer = self.get_account_analyzer()
        if not analyzer:
            return {
                'error': '無法獲取帳戶分析器',
                'program_stats': self.get_session_stats()
            }
        
        try:
            # 獲取帳戶實際數據
            account_report = analyzer.generate_comprehensive_report(days=days)
            
            # 程式內部統計
            program_stats = self.get_session_stats()
            
            # 計算差異
            account_total = account_report['summary']['net_profit']
            program_total = program_stats['total_pnl']
            difference = account_total - program_total
            
            comparison = {
                'account_data': account_report,
                'program_stats': program_stats,
                'comparison': {
                    'account_total': account_total,
                    'program_total': program_total,
                    'difference': difference,
                    'difference_percentage': (difference / account_total * 100) if account_total != 0 else 0,
                    'accuracy': (1 - abs(difference) / abs(account_total)) * 100 if account_total != 0 else 0
                }
            }
            
            return comparison
            
        except Exception as e:
            return {
                'error': f'比較失敗: {str(e)}',
                'program_stats': self.get_session_stats()
            }
    
    def send_account_comparison_notification(self, days: int = 7):
        """發送帳戶數據對比通知"""
        comparison = self.compare_with_account_data(days)
        
        if 'error' in comparison:
            message = f"⚠️ <b>帳戶數據對比失敗</b>\n\n"
            message += f"錯誤: {comparison['error']}\n"
            message += f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            self.send_telegram_message(message)
            return
        
        comp = comparison['comparison']
        account_data = comparison['account_data']
        program_stats = comparison['program_stats']
        
        message = f"📊 <b>程式 vs 帳戶數據對比</b>\n\n"
        message += f"📅 <b>時間範圍</b>\n"
        message += f"最近 {days} 天\n\n"
        
        message += f"💰 <b>收益對比</b>\n"
        message += f"帳戶實際: {comp['account_total']:.4f} USDT\n"
        message += f"程式統計: {comp['program_total']:.4f} USDT\n"
        message += f"差異: {comp['difference']:.4f} USDT\n"
        message += f"準確度: {comp['accuracy']:.1f}%\n\n"
        
        message += f"📈 <b>帳戶詳情</b>\n"
        message += f"總收入: {account_data['summary']['total_income']:.4f} USDT\n"
        message += f"已實現盈虧: {account_data['summary']['realized_pnl']:.4f} USDT\n"
        message += f"手續費: {account_data['summary']['total_commission']:.4f} USDT\n"
        message += f"資金費率: {account_data['summary']['total_funding']:.4f} USDT\n\n"
        
        message += f"🔄 <b>程式統計</b>\n"
        message += f"總交易: {program_stats['total_trades']}\n"
        message += f"勝率: {program_stats['win_rate']:.1f}%\n"
        message += f"平均盈虧: {program_stats['avg_profit']:.4f} USDT\n"
        
        # 添加差異分析
        if abs(comp['difference']) > 0.01:  # 差異大於 0.01 USDT
            message += f"\n⚠️ <b>差異分析</b>\n"
            if comp['difference'] > 0:
                message += f"帳戶收益高於程式統計 {comp['difference']:.4f} USDT\n"
                message += f"可能原因: 手續費、滑點、其他收入"
            else:
                message += f"程式統計高於帳戶收益 {abs(comp['difference']):.4f} USDT\n"
                message += f"可能原因: 遺漏交易、計算誤差"
        
        self.send_telegram_message(message)
    
    def reset_session_stats(self):
        """重置本次套利的統計數據，只計算本次啟動到停止的盈虧"""
        self.session_trades = []  # 本次套利的交易記錄
        self.session_total_trades = 0
        self.session_winning_trades = 0
        self.session_total_pnl = 0.0
        self.session_max_profit = 0.0
        self.session_max_loss = 0.0
        self.session_start_time = time.time()
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 已重置本次套利統計數據")
    
    def add_trade(self, trade_data: Dict):
        """添加交易記錄"""
        # 添加時間戳
        trade_data['timestamp'] = datetime.now().isoformat()
        
        # 計算盈虧
        pnl = trade_data.get('pnl', 0.0)
        
        # 添加到總記錄
        self.trades.append(trade_data)
        self.total_trades += 1
        self.total_pnl += pnl
        
        # 添加到本次套利記錄
        self.session_trades.append(trade_data)
        self.session_total_trades += 1
        self.session_total_pnl += pnl
        
        # 更新統計
        if pnl > 0:
            self.winning_trades += 1
            self.session_winning_trades += 1
            
        # 更新最大盈利/虧損
        if pnl > self.max_profit:
            self.max_profit = pnl
        if pnl > self.session_max_profit:
            self.session_max_profit = pnl
            
        if pnl < self.max_loss:
            self.max_loss = pnl
        if pnl < self.session_max_loss:
            self.session_max_loss = pnl
        
        # 保存交易歷史
        self.save_trade_history()
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 交易記錄已添加: {trade_data.get('symbol', 'Unknown')} - {pnl:.4f} USDT")
    
    def get_session_stats(self) -> Dict:
        """獲取本次套利統計（只計算本次啟動到停止的盈虧）"""
        if self.session_total_trades == 0:
            return {
                'total_trades': 0,
                'total_pnl': 0.0,
                'win_rate': 0.0,
                'avg_profit': 0.0,
                'max_profit': 0.0,
                'max_loss': 0.0,
                'session_duration': 0,
                # 詳細費用分解
                'realized_pnl': 0.0,
                'total_commission': 0.0,
                'total_funding': 0.0,
                'positive_funding': 0.0,
                'negative_funding': 0.0,
                'funding_count': 0,
                'net_profit': 0.0
            }
        
        win_rate = (self.session_winning_trades / self.session_total_trades) * 100
        avg_profit = self.session_total_pnl / self.session_total_trades
        session_duration = time.time() - self.session_start_time
        
        # 獲取套利期間的詳細費用分解
        detailed_stats = self.get_session_detailed_stats()
        
        return {
            'total_trades': self.session_total_trades,
            'total_pnl': self.session_total_pnl,
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'max_profit': self.session_max_profit,
            'max_loss': self.session_max_loss,
            'session_duration': session_duration,
            # 詳細費用分解
            'realized_pnl': detailed_stats.get('realized_pnl', self.session_total_pnl),
            'total_commission': detailed_stats.get('total_commission', 0.0),
            'total_funding': detailed_stats.get('total_funding', 0.0),
            'positive_funding': detailed_stats.get('positive_funding', 0.0),
            'negative_funding': detailed_stats.get('negative_funding', 0.0),
            'funding_count': detailed_stats.get('funding_count', 0),
            'net_profit': detailed_stats.get('net_profit', self.session_total_pnl)
        }
    
    def get_session_detailed_stats(self) -> Dict:
        """獲取套利期間的詳細費用分解"""
        try:
            # 嘗試使用帳戶分析器獲取套利期間的實際數據
            analyzer = self.get_account_analyzer()
            if analyzer:
                # 計算套利期間的時間範圍（從啟動到現在）
                session_start_ms = int(self.session_start_time * 1000)
                session_end_ms = int(time.time() * 1000)
                
                # 獲取套利期間的收入記錄
                income_history = analyzer.get_account_income_history(
                    start_time=session_start_ms, 
                    end_time=session_end_ms
                )
                
                # 獲取套利期間的交易記錄
                trade_history = analyzer.get_trade_history(
                    start_time=session_start_ms, 
                    end_time=session_end_ms
                )
                
                # 分析數據
                income_by_type = analyzer.analyze_income_by_type(income_history)
                realized_pnl = analyzer.calculate_realized_pnl(trade_history)
                funding_income = analyzer.get_funding_rate_income(income_history)
                
                return {
                    'realized_pnl': realized_pnl['total_pnl'],
                    'total_commission': realized_pnl['total_commission'],
                    'total_funding': funding_income['total_funding'],
                    'positive_funding': funding_income.get('positive_funding', 0),
                    'negative_funding': funding_income.get('negative_funding', 0),
                    'funding_count': funding_income.get('funding_count', 0),
                    'net_profit': realized_pnl['total_pnl'] + funding_income['total_funding'] - realized_pnl['total_commission']
                }
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 獲取套利詳細統計失敗: {e}")
        
        # 備用方案：返回空的詳細統計
        return {
            'realized_pnl': 0.0,
            'total_commission': 0.0,
            'total_funding': 0.0,
            'positive_funding': 0.0,
            'negative_funding': 0.0,
            'funding_count': 0,
            'net_profit': 0.0
        }
    
    def get_daily_stats(self) -> Dict:
        """獲取今日統計 - 使用帳戶分析器獲取實際數據，包含詳細費用分解"""
        try:
            # 嘗試使用帳戶分析器獲取今日實際數據
            analyzer = self.get_account_analyzer()
            if analyzer:
                # 獲取今日帳戶報告
                account_report = analyzer.generate_comprehensive_report(days=1)
                
                # 獲取詳細的費用分解
                summary = account_report['summary']
                funding_income = account_report['funding_income']
                
                return {
                    'daily_trades': len(account_report.get('trades', [])),
                    'daily_pnl': account_report['summary']['net_profit'],
                    'daily_win_rate': (len([t for t in account_report.get('trades', []) if t.get('realizedPnl', 0) > 0]) / max(len(account_report.get('trades', [])), 1)) * 100,
                    # 詳細費用分解
                    'realized_pnl': summary['realized_pnl'],           # 交易盈虧（未扣費用）
                    'total_commission': summary['total_commission'],    # 手續費
                    'total_funding': summary['total_funding'],          # 資金費率總計
                    'positive_funding': funding_income.get('positive_funding', 0),  # 正資金費率（收入）
                    'negative_funding': funding_income.get('negative_funding', 0),  # 負資金費率（支出）
                    'funding_count': funding_income.get('funding_count', 0),        # 資金費率次數
                    'net_profit': summary['net_profit']                # 最終淨利潤
                }
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 獲取帳戶今日統計失敗: {e}")
        
        # 備用方案：使用程式記錄的今日統計
        today = datetime.now().date()
        today_trades = [t for t in self.trades if datetime.fromisoformat(t['timestamp']).date() == today]
        
        if not today_trades:
            return {
                'daily_trades': 0,
                'daily_pnl': 0.0,
                'daily_win_rate': 0.0,
                'realized_pnl': 0.0,
                'total_commission': 0.0,
                'total_funding': 0.0,
                'positive_funding': 0.0,
                'negative_funding': 0.0,
                'funding_count': 0,
                'net_profit': 0.0
            }
        
        daily_pnl = sum(t.get('pnl', 0.0) for t in today_trades)
        daily_wins = sum(1 for t in today_trades if t.get('pnl', 0.0) > 0)
        daily_win_rate = (daily_wins / len(today_trades)) * 100
        
        return {
            'daily_trades': len(today_trades),
            'daily_pnl': daily_pnl,
            'daily_win_rate': daily_win_rate,
            'realized_pnl': daily_pnl,  # 程式記錄沒有費用分解，使用總盈虧
            'total_commission': 0.0,    # 程式記錄中沒有
            'total_funding': 0.0,       # 程式記錄中沒有
            'positive_funding': 0.0,
            'negative_funding': 0.0,
            'funding_count': 0,
            'net_profit': daily_pnl
        }
    
    def format_trade_message(self, trade_data: Dict) -> str:
        """格式化交易訊息"""
        symbol = trade_data.get('symbol', 'Unknown')
        direction = trade_data.get('direction', 'Unknown')
        pnl = trade_data.get('pnl', 0.0)
        quantity = trade_data.get('quantity', 0)
        entry_price = trade_data.get('entry_price', 0.0)
        exit_price = trade_data.get('exit_price', 0.0)
        funding_rate = trade_data.get('funding_rate', 0.0)
        execution_time = trade_data.get('execution_time_ms', 0)
        position_duration = trade_data.get('position_duration_seconds', 0)
        entry_timestamp = trade_data.get('entry_timestamp', 0)
        exit_timestamp = trade_data.get('exit_timestamp', 0)
        
        # 計算保證金和槓桿資訊
        position_value = quantity * entry_price
        margin_used = position_value / LEVERAGE  # 使用實際槓桿設定
        leverage = LEVERAGE  # 從配置讀取
        
        # 表情符號
        emoji = "🟢" if pnl > 0 else "🔴"
        direction_emoji = "📈" if direction == 'long' else "📉"
        
        message = f"{emoji} <b>交易完成</b>\n\n"
        message += f"<b>交易對:</b> {symbol}\n"
        message += f"<b>方向:</b> {direction_emoji} {direction.upper()}\n"
        message += f"<b>數量:</b> {quantity:,}\n"
        message += f"<b>開倉價:</b> {entry_price:.6f}\n"
        message += f"<b>平倉價:</b> {exit_price:.6f}\n"
        message += f"<b>資金費率:</b> {funding_rate:.4f}%\n\n"
        
        # 時間資訊
        if entry_timestamp and exit_timestamp:
            entry_time = datetime.fromtimestamp(entry_timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
            exit_time = datetime.fromtimestamp(exit_timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
            message += f"<b>開倉時間:</b> {entry_time}\n"
            message += f"<b>平倉時間:</b> {exit_time}\n"
            message += f"<b>持倉時間:</b> {position_duration}秒\n"
        
        # 倉位和保證金資訊
        message += f"<b>倉位價值:</b> {position_value:.2f} USDT\n"
        message += f"<b>保證金:</b> {margin_used:.2f} USDT\n"
        message += f"<b>槓桿:</b> {leverage}x\n"
        message += f"<b>執行時間:</b> {execution_time}ms\n"
        message += f"<b>盈虧:</b> {pnl:.4f} USDT\n"
        
        # 添加統計信息
        stats = self.get_session_stats()
        message += f"\n📊 <b>套利統計</b>\n"
        message += f"總交易: {stats['total_trades']}\n"
        message += f"總盈虧: {stats['total_pnl']:.4f} USDT\n"
        message += f"勝率: {stats['win_rate']:.1f}%\n"
        message += f"平均盈虧: {stats['avg_profit']:.4f} USDT"
        
        return message
    
    def format_summary_message(self) -> str:
        """格式化總結訊息 - 包含詳細費用分解"""
        session_stats = self.get_session_stats()
        daily_stats = self.get_daily_stats()
        
        message = "📈 <b>資金費率套利機器人 - 總結報告</b>\n\n"
        
        # 套利統計 - 詳細費用分解
        message += "🕐 <b>本次套利</b>\n"
        message += f"總交易: {session_stats['total_trades']}\n"
        
        # 總是顯示套利詳細分解（保持與今日統計的一致性）
        if 'realized_pnl' in session_stats:
            message += f"\n💰 <b>套利收益分解</b>\n"
            message += f"交易盈虧: {session_stats['realized_pnl']:.4f} USDT\n"
            message += f"手續費: -{session_stats['total_commission']:.4f} USDT\n"
            
            # 套利資金費率詳情
            message += f"\n💸 <b>套利資金費率</b>\n"
            message += f"資金費率總計: {session_stats['total_funding']:.4f} USDT\n"
            if session_stats['positive_funding'] != 0:
                message += f"  ↗️ 收入: +{session_stats['positive_funding']:.4f} USDT\n"
            if session_stats['negative_funding'] != 0:
                message += f"  ↘️ 支出: {session_stats['negative_funding']:.4f} USDT\n"
            message += f"資金費率次數: {session_stats['funding_count']}\n"
            
            message += f"\n📊 <b>套利總結</b>\n"
            message += f"最終淨利潤: {session_stats['net_profit']:.4f} USDT\n"
            message += f"勝率: {session_stats['win_rate']:.1f}%\n"
            message += f"平均盈虧: {session_stats['avg_profit']:.4f} USDT\n"
            message += f"最大盈利: {session_stats['max_profit']:.4f} USDT\n"
            message += f"最大虧損: {session_stats['max_loss']:.4f} USDT\n"
            message += f"運行時間: {session_stats['session_duration']/3600:.1f} 小時\n"
        else:
            # 備用方案（當沒有詳細數據結構時）
            message += f"總盈虧: {session_stats['total_pnl']:.4f} USDT\n"
            message += f"勝率: {session_stats['win_rate']:.1f}%\n"
            message += f"平均盈虧: {session_stats['avg_profit']:.4f} USDT\n"
            message += f"最大盈利: {session_stats['max_profit']:.4f} USDT\n"
            message += f"最大虧損: {session_stats['max_loss']:.4f} USDT\n"
            message += f"運行時間: {session_stats['session_duration']/3600:.1f} 小時\n"
        
        message += "\n"
        
        # 近24小時統計 - 詳細費用分解（顯示具體時間範圍）
        from datetime import datetime, timedelta
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        
        message += "📅 <b>近24小時統計</b>\n"
        message += f"時間範圍: {yesterday.strftime('%m-%d %H:%M')} ~ {now.strftime('%m-%d %H:%M')}\n"
        message += f"交易次數: {daily_stats['daily_trades']}\n"
        
        # 如果有詳細的費用分解數據（不依賴交易次數）
        if 'realized_pnl' in daily_stats and ('total_commission' in daily_stats or 'total_funding' in daily_stats):
            message += f"\n💰 <b>近24小時收益分解</b>\n"
            message += f"交易盈虧: {daily_stats['realized_pnl']:.4f} USDT\n"
            message += f"手續費: -{daily_stats['total_commission']:.4f} USDT\n"
            
            # 資金費率詳情
            message += f"\n💸 <b>資金費率</b>\n"
            message += f"資金費率總計: {daily_stats['total_funding']:.4f} USDT\n"
            if daily_stats['positive_funding'] != 0:
                message += f"  ↗️ 收入: +{daily_stats['positive_funding']:.4f} USDT\n"
            if daily_stats['negative_funding'] != 0:
                message += f"  ↘️ 支出: {daily_stats['negative_funding']:.4f} USDT\n"
            message += f"資金費率次數: {daily_stats['funding_count']}\n"
            
            message += f"\n📊 <b>近24小時總結</b>\n"
            message += f"最終淨利潤: {daily_stats['net_profit']:.4f} USDT\n"
            message += f"勝率: {daily_stats['daily_win_rate']:.1f}%\n"
            
            # 計算公式說明
            message += f"\n🧮 <b>計算公式</b>\n"
            message += f"淨利潤 = 交易盈虧 + 資金費率 - 手續費\n"
            message += f"= {daily_stats['realized_pnl']:.4f} + {daily_stats['total_funding']:.4f} - {daily_stats['total_commission']:.4f}\n"
            message += f"= {daily_stats['net_profit']:.4f} USDT"
        else:
            # 簡化顯示（當沒有詳細數據時）
            message += f"盈虧: {daily_stats['daily_pnl']:.4f} USDT\n"
            message += f"勝率: {daily_stats['daily_win_rate']:.1f}%"
        
        return message
    
    def send_telegram_message(self, message: str, parse_mode: str = 'HTML') -> bool:
        """發送 Telegram 訊息"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] send_telegram_message 被調用")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ENABLE_TELEGRAM_NOTIFY = {ENABLE_TELEGRAM_NOTIFY}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] TELEGRAM_BOT_TOKEN = {TELEGRAM_BOT_TOKEN[:10] if TELEGRAM_BOT_TOKEN else 'None'}...")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] TELEGRAM_CHAT_ID = {TELEGRAM_CHAT_ID}")
        
        if not ENABLE_TELEGRAM_NOTIFY or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Telegram 通知條件不滿足，退出")
            return False
        
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 準備發送 Telegram 消息...")
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {
                'chat_id': TELEGRAM_CHAT_ID,
                'text': message,
                'parse_mode': parse_mode
            }
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 發送請求到: {url}")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 消息內容: {message[:100]}...")
            
            response = requests.post(url, data=data, timeout=10)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 發送結果: 狀態碼 {response.status_code}")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 響應內容: {response.text}")
            
            success = response.status_code == 200
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 發送{'成功' if success else '失敗'}")
            return success
            
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Telegram 發送失敗: {e}")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 錯誤詳情: {traceback.format_exc()}")
            return False
    
    def send_trade_notification(self, trade_data: Dict):
        """發送交易通知"""
        message = self.format_trade_message(trade_data)
        self.send_telegram_message(message)
    
    def send_start_notification(self):
        """發送啟動通知"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] send_start_notification 被調用")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] NOTIFY_ON_START = {NOTIFY_ON_START}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ENABLE_TELEGRAM_NOTIFY = {ENABLE_TELEGRAM_NOTIFY}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] TELEGRAM_BOT_TOKEN = {TELEGRAM_BOT_TOKEN[:10]}...")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] TELEGRAM_CHAT_ID = {TELEGRAM_CHAT_ID}")
        
        if not NOTIFY_ON_START:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 啟動通知已禁用，退出")
            return
            
        import os
        
        message = "🚀 <b>資金費率套利機器人已啟動</b>\n\n"
        message += f"啟動時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        message += f"主機: {os.uname().nodename if hasattr(os, 'uname') else os.getenv('COMPUTERNAME', 'Unknown')}\n"
        message += f"PID: {os.getpid()}\n\n"
        
        message += "⚙️ <b>配置參數</b>\n"
        message += f"最大倉位: {MAX_POSITION_SIZE} USDT\n"
        message += f"槓桿倍數: {LEVERAGE}x\n"
        message += f"最小資金費率: {MIN_FUNDING_RATE}%\n"
        message += f"進場提前: {ENTRY_BEFORE_SECONDS}秒\n"
        message += f"平倉提前: {CLOSE_BEFORE_SECONDS}秒\n"
        message += f"交易時間: {TRADING_HOURS}\n"
        message += f"交易幣種: {TRADING_SYMBOLS if TRADING_SYMBOLS else '全部'}\n"
        message += f"排除幣種: {EXCLUDED_SYMBOLS}\n\n"
        
        message += "正在監控資金費率機會..."
        
        self.send_telegram_message(message)
    
    def send_stop_notification(self):
        """發送停止通知"""
        if not NOTIFY_ON_STOP:
            return
            
        import os
        
        message = self.format_summary_message()
        message += f"\n\n⏹️ <b>機器人已停止</b>\n"
        message += f"停止時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        message += f"主機: {os.uname().nodename if hasattr(os, 'uname') else os.getenv('COMPUTERNAME', 'Unknown')}\n"
        message += f"PID: {os.getpid()}"
        
        self.send_telegram_message(message)
    
    def send_error_notification(self, error_msg: str):
        """發送錯誤通知"""
        if not NOTIFY_ON_ERROR:
            return
            
        import os
        
        message = "⚠️ <b>機器人發生錯誤</b>\n\n"
        message += f"錯誤時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        message += f"主機: {os.uname().nodename if hasattr(os, 'uname') else os.getenv('COMPUTERNAME', 'Unknown')}\n"
        message += f"PID: {os.getpid()}\n\n"
        message += f"錯誤訊息:\n{error_msg}"
        
        self.send_telegram_message(message)
    
    def save_trade_history(self):
        """保存交易歷史到文件"""
        try:
            with open('trade_history.json', 'w', encoding='utf-8') as f:
                json.dump(self.trades, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存交易歷史失敗: {e}")
    
    def load_trade_history(self):
        """載入交易歷史"""
        try:
            with open('trade_history.json', 'r', encoding='utf-8') as f:
                self.trades = json.load(f)
                
            # 重新計算統計
            self.total_pnl = sum(t.get('pnl', 0.0) for t in self.trades)
            self.total_trades = len(self.trades)
            self.winning_trades = sum(1 for t in self.trades if t.get('pnl', 0.0) > 0)
            self.losing_trades = self.total_trades - self.winning_trades
            
            if self.trades:
                profits = [t.get('pnl', 0.0) for t in self.trades if t.get('pnl', 0.0) > 0]
                losses = [t.get('pnl', 0.0) for t in self.trades if t.get('pnl', 0.0) < 0]
                
                self.max_profit = max(profits) if profits else 0.0
                self.max_loss = min(losses) if losses else 0.0
                
        except FileNotFoundError:
            # 文件不存在，使用空列表
            self.trades = []
        except Exception as e:
            print(f"載入交易歷史失敗: {e}")
            self.trades = []
    
    def export_trades_to_csv(self, filename: str = None):
        """導出交易記錄到 CSV"""
        if not filename:
            filename = f"trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        try:
            import pandas as pd
            
            df = pd.DataFrame(self.trades)
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"交易記錄已導出到: {filename}")
            
            return filename
        except Exception as e:
            print(f"導出 CSV 失敗: {e}")
            return None 