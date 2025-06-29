#!/usr/bin/env python3
"""
帳戶分析器 - 爬取幣安帳戶資金流水和交易記錄
提供更準確的收益分析
"""

import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException
from config import API_KEY, API_SECRET
import json

class AccountAnalyzer:
    def __init__(self):
        self.client = Client(API_KEY, API_SECRET)
        
    def get_account_income_history(self, symbol: str = None, start_time: int = None, end_time: int = None) -> List[Dict]:
        """獲取帳戶收入歷史（包含資金費率、手續費等）"""
        try:
            # 如果沒有指定時間範圍，預設查詢最近7天
            if not start_time:
                start_time = int((datetime.now() - timedelta(days=7)).timestamp() * 1000)
            if not end_time:
                end_time = int(datetime.now().timestamp() * 1000)
            
            params = {
                'startTime': start_time,
                'endTime': end_time,
                'limit': 1000  # 最大查詢數量
            }
            
            if symbol:
                params['symbol'] = symbol
            
            income_history = self.client.futures_income_history(**params)
            
            print(f"獲取到 {len(income_history)} 條收入記錄")
            return income_history
            
        except BinanceAPIException as e:
            print(f"獲取收入歷史失敗: {e}")
            return []
    
    def get_trade_history(self, symbol: str = None, start_time: int = None, end_time: int = None) -> List[Dict]:
        """獲取交易歷史"""
        try:
            # 如果沒有指定時間範圍，預設查詢最近7天
            if not start_time:
                start_time = int((datetime.now() - timedelta(days=7)).timestamp() * 1000)
            if not end_time:
                end_time = int(datetime.now().timestamp() * 1000)
            
            params = {
                'startTime': start_time,
                'endTime': end_time,
                'limit': 1000
            }
            
            if symbol:
                params['symbol'] = symbol
            
            trade_history = self.client.futures_account_trades(**params)
            
            print(f"獲取到 {len(trade_history)} 條交易記錄")
            return trade_history
            
        except BinanceAPIException as e:
            print(f"獲取交易歷史失敗: {e}")
            return []
    
    def get_account_balance_history(self, start_time: int = None, end_time: int = None) -> List[Dict]:
        """獲取帳戶餘額變化歷史"""
        try:
            # 獲取帳戶快照
            if not start_time:
                start_time = int((datetime.now() - timedelta(days=7)).timestamp() * 1000)
            if not end_time:
                end_time = int(datetime.now().timestamp() * 1000)
            
            account_snapshots = self.client.futures_account_snapshot(
                startTime=start_time,
                endTime=end_time,
                limit=30  # 最多30個快照
            )
            
            print(f"獲取到 {len(account_snapshots)} 個帳戶快照")
            return account_snapshots
            
        except BinanceAPIException as e:
            print(f"獲取帳戶快照失敗: {e}")
            return []
    
    def analyze_income_by_type(self, income_history: List[Dict]) -> Dict:
        """按類型分析收入"""
        income_by_type = {}
        
        for income in income_history:
            income_type = income['incomeType']
            amount = float(income['income'])
            
            if income_type not in income_by_type:
                income_by_type[income_type] = {
                    'total_amount': 0.0,
                    'count': 0,
                    'details': []
                }
            
            income_by_type[income_type]['total_amount'] += amount
            income_by_type[income_type]['count'] += 1
            income_by_type[income_type]['details'].append(income)
        
        return income_by_type
    
    def calculate_realized_pnl(self, trade_history: List[Dict]) -> Dict:
        """計算已實現盈虧"""
        realized_pnl = {
            'total_pnl': 0.0,
            'total_commission': 0.0,
            'trades': [],
            'by_symbol': {}
        }
        
        for trade in trade_history:
            symbol = trade['symbol']
            realized_pnl_amount = float(trade['realizedPnl'])
            commission = float(trade['commission'])
            
            realized_pnl['total_pnl'] += realized_pnl_amount
            realized_pnl['total_commission'] += commission
            
            # 按交易對統計
            if symbol not in realized_pnl['by_symbol']:
                realized_pnl['by_symbol'][symbol] = {
                    'pnl': 0.0,
                    'commission': 0.0,
                    'trades': 0
                }
            
            realized_pnl['by_symbol'][symbol]['pnl'] += realized_pnl_amount
            realized_pnl['by_symbol'][symbol]['commission'] += commission
            realized_pnl['by_symbol'][symbol]['trades'] += 1
            
            # 記錄詳細交易
            trade_detail = {
                'symbol': symbol,
                'side': trade['side'],
                'quantity': float(trade['qty']),
                'price': float(trade['price']),
                'realized_pnl': realized_pnl_amount,
                'commission': commission,
                'time': datetime.fromtimestamp(trade['time'] / 1000),
                'order_id': trade['orderId']
            }
            realized_pnl['trades'].append(trade_detail)
        
        return realized_pnl
    
    def get_funding_rate_income(self, income_history: List[Dict]) -> Dict:
        """獲取資金費率收入"""
        funding_income = {
            'total_funding': 0.0,
            'positive_funding': 0.0,
            'negative_funding': 0.0,
            'funding_count': 0,
            'by_symbol': {}
        }
        
        for income in income_history:
            if income['incomeType'] == 'FUNDING_FEE':
                symbol = income['symbol']
                amount = float(income['income'])
                
                funding_income['total_funding'] += amount
                funding_income['funding_count'] += 1
                
                if amount > 0:
                    funding_income['positive_funding'] += amount
                else:
                    funding_income['negative_funding'] += amount
                
                # 按交易對統計
                if symbol not in funding_income['by_symbol']:
                    funding_income['by_symbol'][symbol] = {
                        'total': 0.0,
                        'positive': 0.0,
                        'negative': 0.0,
                        'count': 0
                    }
                
                funding_income['by_symbol'][symbol]['total'] += amount
                funding_income['by_symbol'][symbol]['count'] += 1
                
                if amount > 0:
                    funding_income['by_symbol'][symbol]['positive'] += amount
                else:
                    funding_income['by_symbol'][symbol]['negative'] += amount
        
        return funding_income
    
    def analyze_trades_by_time_range(self, trade_periods: List[Dict]) -> Dict:
        """
        根據程式交易時間範圍分析帳戶資金流水
        
        Args:
            trade_periods: 程式交易時間範圍列表
            [
                {
                    'symbol': 'BTCUSDT',
                    'entry_time': 1640995200000,  # 進倉時間戳
                    'exit_time': 1640995260000,   # 平倉時間戳
                    'direction': 'long',
                    'quantity': 1000
                }
            ]
        """
        try:
            all_income = []
            all_trades = []
            
            # 為每個交易時間範圍獲取帳戶數據
            for i, period in enumerate(trade_periods):
                symbol = period['symbol']
                entry_time = period['entry_time']
                exit_time = period['exit_time']
                
                print(f"分析交易 {i+1}: {symbol} ({datetime.fromtimestamp(entry_time/1000)} - {datetime.fromtimestamp(exit_time/1000)})")
                
                # 獲取該時間範圍的收入記錄
                income_records = self.get_account_income_history(
                    symbol=symbol,
                    start_time=entry_time,
                    end_time=exit_time + 60000  # 延長1分鐘，確保包含所有相關記錄
                )
                
                # 獲取該時間範圍的交易記錄
                trade_records = self.get_trade_history(
                    symbol=symbol,
                    start_time=entry_time,
                    end_time=exit_time + 60000
                )
                
                # 標記這些記錄屬於哪個交易
                for income in income_records:
                    income['trade_period_index'] = i
                    income['trade_symbol'] = symbol
                    income['trade_direction'] = period.get('direction', 'unknown')
                    all_income.append(income)
                
                for trade in trade_records:
                    trade['trade_period_index'] = i
                    trade['trade_symbol'] = symbol
                    trade['trade_direction'] = period.get('direction', 'unknown')
                    all_trades.append(trade)
            
            # 分析所有記錄
            income_by_type = self.analyze_income_by_type(all_income)
            realized_pnl = self.calculate_realized_pnl(all_trades)
            funding_income = self.get_funding_rate_income(all_income)
            
            # 按交易期間分組
            trades_by_period = {}
            for i, period in enumerate(trade_periods):
                period_income = [inc for inc in all_income if inc.get('trade_period_index') == i]
                period_trades = [trd for trd in all_trades if trd.get('trade_period_index') == i]
                
                period_pnl = sum(float(trd['realizedPnl']) for trd in period_trades)
                period_commission = sum(float(trd['commission']) for trd in period_trades)
                period_funding = sum(float(inc['income']) for inc in period_income if inc['incomeType'] == 'FUNDING_FEE')
                
                trades_by_period[i] = {
                    'symbol': period['symbol'],
                    'direction': period['direction'],
                    'entry_time': period['entry_time'],
                    'exit_time': period['exit_time'],
                    'duration_seconds': (period['exit_time'] - period['entry_time']) / 1000,
                    'realized_pnl': period_pnl,
                    'commission': period_commission,
                    'funding_fee': period_funding,
                    'net_profit': period_pnl + period_funding - period_commission,
                    'income_records': period_income,
                    'trade_records': period_trades
                }
            
            return {
                'total_trades': len(trade_periods),
                'total_realized_pnl': realized_pnl['total_pnl'],
                'total_commission': realized_pnl['total_commission'],
                'total_funding': funding_income['total_funding'],
                'total_net_profit': realized_pnl['total_pnl'] + funding_income['total_funding'] - realized_pnl['total_commission'],
                'trades_by_period': trades_by_period,
                'income_by_type': income_by_type,
                'realized_pnl': realized_pnl,
                'funding_income': funding_income
            }
            
        except Exception as e:
            print(f"按時間範圍分析失敗: {e}")
            return None
    
    def load_program_trades_from_json(self, json_file: str = 'trade_history.json') -> List[Dict]:
        """從程式的 trade_history.json 載入交易記錄並轉換為時間範圍"""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                trades = json.load(f)
            
            trade_periods = []
            for trade in trades:
                # 使用精確的時間戳（如果有的話）
                if 'entry_timestamp' in trade and 'exit_timestamp' in trade:
                    entry_time = trade['entry_timestamp']
                    exit_time = trade['exit_timestamp']
                else:
                    # 回退到估算時間
                    timestamp = datetime.fromisoformat(trade['timestamp'])
                    trade_time = int(timestamp.timestamp() * 1000)
                    entry_time = trade_time - 60000  # 1分鐘前
                    exit_time = trade_time + 60000   # 1分鐘後
                
                trade_periods.append({
                    'symbol': trade['symbol'],
                    'entry_time': entry_time,
                    'exit_time': exit_time,
                    'direction': trade['direction'],
                    'quantity': trade['quantity'],
                    'program_pnl': trade['pnl'],
                    'timestamp': trade['timestamp']
                })
            
            print(f"載入 {len(trade_periods)} 筆程式交易記錄")
            return trade_periods
            
        except FileNotFoundError:
            print(f"找不到交易記錄文件: {json_file}")
            return []
        except Exception as e:
            print(f"載入交易記錄失敗: {e}")
            return []
    
    def compare_program_vs_account_by_period(self) -> Dict:
        """比較程式統計與帳戶實際數據（按交易期間）"""
        try:
            # 載入程式交易記錄
            trade_periods = self.load_program_trades_from_json()
            
            if not trade_periods:
                return {'error': '沒有找到程式交易記錄'}
            
            # 分析帳戶數據
            account_analysis = self.analyze_trades_by_time_range(trade_periods)
            
            if not account_analysis:
                return {'error': '帳戶分析失敗'}
            
            # 比較結果
            comparison = {
                'program_total_pnl': sum(t['program_pnl'] for t in trade_periods),
                'account_total_pnl': account_analysis['total_realized_pnl'],
                'account_total_commission': account_analysis['total_commission'],
                'account_total_funding': account_analysis['total_funding'],
                'account_net_profit': account_analysis['total_net_profit'],
                'difference': account_analysis['total_net_profit'] - sum(t['program_pnl'] for t in trade_periods),
                'trades_comparison': []
            }
            
            # 逐筆比較
            for i, period in enumerate(trade_periods):
                if i in account_analysis['trades_by_period']:
                    account_trade = account_analysis['trades_by_period'][i]
                    program_pnl = period['program_pnl']
                    account_pnl = account_trade['net_profit']
                    
                    comparison['trades_comparison'].append({
                        'symbol': period['symbol'],
                        'direction': period['direction'],
                        'program_pnl': program_pnl,
                        'account_pnl': account_pnl,
                        'difference': account_pnl - program_pnl,
                        'commission': account_trade['commission'],
                        'funding_fee': account_trade['funding_fee'],
                        'duration_seconds': account_trade['duration_seconds']
                    })
            
            return comparison
            
        except Exception as e:
            return {'error': f'比較失敗: {str(e)}'}
    
    def format_period_comparison_for_telegram(self, comparison: Dict) -> str:
        """格式化期間對比報告用於 Telegram"""
        if 'error' in comparison:
            return f"⚠️ <b>對比失敗</b>\n\n{comparison['error']}"
        
        message = f"📊 <b>程式 vs 帳戶對比報告</b>\n\n"
        
        # 總體對比
        message += f"💰 <b>總體對比</b>\n"
        message += f"程式統計: {comparison['program_total_pnl']:.4f} USDT\n"
        message += f"帳戶淨利: {comparison['account_net_profit']:.4f} USDT\n"
        message += f"差異: {comparison['difference']:.4f} USDT\n\n"
        
        # 帳戶詳情
        message += f"📈 <b>帳戶詳情</b>\n"
        message += f"已實現盈虧: {comparison['account_total_pnl']:.4f} USDT\n"
        message += f"手續費: {comparison['account_total_commission']:.4f} USDT\n"
        message += f"資金費率: {comparison['account_total_funding']:.4f} USDT\n\n"
        
        # 逐筆對比（只顯示前5筆）
        if comparison['trades_comparison']:
            message += f"📋 <b>逐筆對比</b>\n"
            for i, trade in enumerate(comparison['trades_comparison'][:5]):
                message += f"{trade['symbol']}: 程式{trade['program_pnl']:.4f} vs 帳戶{trade['account_pnl']:.4f} (差{trade['difference']:.4f})\n"
            
            if len(comparison['trades_comparison']) > 5:
                message += f"... 還有 {len(comparison['trades_comparison']) - 5} 筆\n"
        
        return message
    
    def generate_comprehensive_report(self, days: int = 7) -> Dict:
        """生成綜合報告"""
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
        
        print(f"分析時間範圍: {datetime.fromtimestamp(start_time/1000)} 到 {datetime.fromtimestamp(end_time/1000)}")
        
        # 獲取各種數據
        income_history = self.get_account_income_history(start_time=start_time, end_time=end_time)
        trade_history = self.get_trade_history(start_time=start_time, end_time=end_time)
        
        # 分析數據
        income_by_type = self.analyze_income_by_type(income_history)
        realized_pnl = self.calculate_realized_pnl(trade_history)
        funding_income = self.get_funding_rate_income(income_history)
        
        # 計算總收益
        total_income = sum(float(income['income']) for income in income_history)
        
        # 生成報告
        report = {
            'time_range': {
                'start': datetime.fromtimestamp(start_time/1000),
                'end': datetime.fromtimestamp(end_time/1000),
                'days': days
            },
            'summary': {
                'total_income': total_income,
                'realized_pnl': realized_pnl['total_pnl'],
                'total_commission': realized_pnl['total_commission'],
                'total_funding': funding_income['total_funding'],
                'net_profit': realized_pnl['total_pnl'] + funding_income['total_funding'] - realized_pnl['total_commission']
            },
            'income_by_type': income_by_type,
            'realized_pnl': realized_pnl,
            'funding_income': funding_income,
            'trade_count': len(trade_history),
            'income_count': len(income_history)
        }
        
        return report
    
    def format_report_for_telegram(self, report: Dict) -> str:
        """格式化報告用於 Telegram 發送"""
        summary = report['summary']
        time_range = report['time_range']
        
        message = f"📊 <b>帳戶收益分析報告</b>\n\n"
        message += f"📅 <b>時間範圍</b>\n"
        message += f"開始: {time_range['start'].strftime('%Y-%m-%d %H:%M')}\n"
        message += f"結束: {time_range['end'].strftime('%Y-%m-%d %H:%M')}\n"
        message += f"天數: {time_range['days']} 天\n\n"
        
        message += f"💰 <b>收益總結</b>\n"
        message += f"總收入: {summary['total_income']:.4f} USDT\n"
        message += f"已實現盈虧: {summary['realized_pnl']:.4f} USDT\n"
        message += f"手續費: {summary['total_commission']:.4f} USDT\n"
        message += f"資金費率: {summary['total_funding']:.4f} USDT\n"
        message += f"淨利潤: {summary['net_profit']:.4f} USDT\n\n"
        
        # 資金費率詳情
        funding = report['funding_income']
        message += f"📈 <b>資金費率詳情</b>\n"
        message += f"總資金費率: {funding['total_funding']:.4f} USDT\n"
        message += f"正資金費率: {funding['positive_funding']:.4f} USDT\n"
        message += f"負資金費率: {funding['negative_funding']:.4f} USDT\n"
        message += f"資金費率次數: {funding['funding_count']}\n\n"
        
        # 交易統計
        message += f"🔄 <b>交易統計</b>\n"
        message += f"總交易次數: {report['trade_count']}\n"
        message += f"收入記錄數: {report['income_count']}\n"
        
        # 按交易對統計
        if report['realized_pnl']['by_symbol']:
            message += f"\n📋 <b>按交易對統計</b>\n"
            for symbol, data in report['realized_pnl']['by_symbol'].items():
                message += f"{symbol}: {data['pnl']:.4f} USDT ({data['trades']} 筆)\n"
        
        return message
    
    def export_to_csv(self, report: Dict, filename: str = None) -> str:
        """導出報告到 CSV"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"account_report_{timestamp}.csv"
        
        # 創建 DataFrame
        data = []
        
        # 添加收入記錄
        for income_type, details in report['income_by_type'].items():
            for income in details['details']:
                data.append({
                    'type': 'income',
                    'income_type': income_type,
                    'symbol': income.get('symbol', ''),
                    'amount': float(income['income']),
                    'time': datetime.fromtimestamp(income['time'] / 1000),
                    'info': income.get('info', '')
                })
        
        # 添加交易記錄
        for trade in report['realized_pnl']['trades']:
            data.append({
                'type': 'trade',
                'income_type': 'TRADE',
                'symbol': trade['symbol'],
                'amount': trade['realized_pnl'],
                'time': trade['time'],
                'info': f"{trade['side']} {trade['quantity']} @ {trade['price']}"
            })
        
        # 創建 DataFrame 並排序
        df = pd.DataFrame(data)
        df = df.sort_values('time')
        
        # 導出到 CSV
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"報告已導出到: {filename}")
        
        return filename

def main():
    """主函數 - 測試帳戶分析器"""
    print("🔍 開始分析帳戶...")
    
    try:
        analyzer = AccountAnalyzer()
        
        # 測試連接
        print("測試 API 連接...")
        account = analyzer.client.futures_account()
        print(f"✅ API 連接成功，帳戶總餘額: {float(account['totalWalletBalance']):.2f} USDT")
        
        # 測試按時間範圍分析
        print("\n" + "="*50)
        print("測試按時間範圍分析...")
        print("="*50)
        
        comparison = analyzer.compare_program_vs_account_by_period()
        
        if 'error' in comparison:
            print(f"❌ 對比失敗: {comparison['error']}")
        else:
            print(f"✅ 對比成功!")
            print(f"程式總盈虧: {comparison['program_total_pnl']:.4f} USDT")
            print(f"帳戶淨利: {comparison['account_net_profit']:.4f} USDT")
            print(f"差異: {comparison['difference']:.4f} USDT")
            print(f"手續費: {comparison['account_total_commission']:.4f} USDT")
            print(f"資金費率: {comparison['account_total_funding']:.4f} USDT")
            
            # 顯示逐筆對比
            if comparison['trades_comparison']:
                print(f"\n逐筆對比:")
                for i, trade in enumerate(comparison['trades_comparison'][:3]):  # 只顯示前3筆
                    print(f"  {trade['symbol']}: 程式{trade['program_pnl']:.4f} vs 帳戶{trade['account_pnl']:.4f} (差{trade['difference']:.4f})")
            
            # 格式化 Telegram 消息
            telegram_message = analyzer.format_period_comparison_for_telegram(comparison)
            print(f"\n" + "="*50)
            print("Telegram 格式消息:")
            print("="*50)
            print(telegram_message)
        
        # 生成7天報告（原有功能）
        print("\n" + "="*50)
        print("生成7天報告...")
        print("="*50)
        
        report = analyzer.generate_comprehensive_report(days=7)
        
        # 顯示報告
        summary = report['summary']
        print(f"總收入: {summary['total_income']:.4f} USDT")
        print(f"已實現盈虧: {summary['realized_pnl']:.4f} USDT")
        print(f"手續費: {summary['total_commission']:.4f} USDT")
        print(f"資金費率: {summary['total_funding']:.4f} USDT")
        print(f"淨利潤: {summary['net_profit']:.4f} USDT")
        print(f"交易次數: {report['trade_count']}")
        print(f"收入記錄數: {report['income_count']}")
        
        # 顯示收入類型詳情
        print(f"\n收入類型詳情:")
        for income_type, details in report['income_by_type'].items():
            print(f"  {income_type}: {details['total_amount']:.4f} USDT ({details['count']} 筆)")
        
        # 導出 CSV
        csv_file = analyzer.export_to_csv(report)
        print(f"\nCSV 文件: {csv_file}")
        
    except Exception as e:
        print(f"❌ 分析過程中發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        
        # 嘗試獲取更多調試信息
        try:
            print(f"\n🔍 調試信息:")
            analyzer = AccountAnalyzer()
            
            # 測試基本 API 調用
            print("測試基本 API 調用...")
            account = analyzer.client.futures_account()
            print(f"帳戶信息獲取成功")
            
            # 測試收入歷史
            print("測試收入歷史...")
            income = analyzer.get_account_income_history()
            print(f"收入歷史: {len(income)} 條記錄")
            
            # 測試交易歷史
            print("測試交易歷史...")
            trades = analyzer.get_trade_history()
            print(f"交易歷史: {len(trades)} 條記錄")
            
        except Exception as debug_e:
            print(f"調試也失敗: {debug_e}")

if __name__ == "__main__":
    main() 