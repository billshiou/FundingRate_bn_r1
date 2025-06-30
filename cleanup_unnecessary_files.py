#!/usr/bin/env python3
"""
清理多餘檔案腳本
安全地移除測試檔案、工具檔案和說明文件
"""

import os
import shutil
from typing import List

def cleanup_project():
    """清理專案中的多餘檔案"""
    
    # 測試檔案（可安全刪除）
    test_files = [
        'test_close_record_improvement.py',  # 已修復完成
        'test_trading_functions.py',
        'test_funding_rates.py',
        'test_notifications.py',
        'test_telegram.py',
        'test_telegram_connection.py',
        'test_trade_notification.py',
        'test_account_comparison.py',
        'test_calculation.py',
        'debug_filtering.py',
    ]
    
    # 工具檔案（用完可刪除）
    tool_files = [
        'cleanup_project.py',  # 原有的清理工具
        'fix_dependencies.py',
        'check_commission.py',
        'setup.py',
        'pytest.ini',
    ]
    
    # 上傳腳本（部署完可刪除）
    upload_files = [
        '01_極簡上傳_強制覆蓋.bat',
        '02_詳細上傳_強制覆蓋.bat',
        '03_安全上傳_錯誤處理.bat',
        'Upload_Scripts_Guide.md',
        '上傳腳本說明.txt',
    ]
    
    # 說明文件（可選刪除）
    doc_files = [
        'STRATEGY_OVERVIEW.md',
        'TELEGRAM_SETUP.md', 
        'DEPLOYMENT.md',
        'PROFIT_TRACKING_README.md',
        '交易分析記事本說明.md',
        'config_example.py',  # 已有config.py
        '1.0.16',  # 版本檔案
    ]
    
    # 數據檔案（謹慎處理）
    data_files = [
        'trade_history.json',  # 可能包含有用數據，建議備份
    ]
    
    print("🧹 開始清理多餘檔案...")
    print("=" * 50)
    
    total_deleted = 0
    total_size_saved = 0
    
    # 刪除測試檔案
    print("\n🧪 清理測試檔案...")
    deleted, size_saved = delete_files(test_files, "測試檔案")
    total_deleted += deleted
    total_size_saved += size_saved
    
    # 刪除工具檔案
    print("\n🔧 清理工具檔案...")
    deleted, size_saved = delete_files(tool_files, "工具檔案")
    total_deleted += deleted
    total_size_saved += size_saved
    
    # 刪除上傳腳本
    print("\n📤 清理上傳腳本...")
    deleted, size_saved = delete_files(upload_files, "上傳腳本")
    total_deleted += deleted
    total_size_saved += size_saved
    
    # 詢問是否刪除說明文件
    print("\n📖 發現說明文件:")
    for file in doc_files:
        if os.path.exists(file):
            size = os.path.getsize(file) / 1024
            print(f"   📄 {file} ({size:.1f} KB)")
    
    if doc_files and input("\n是否刪除說明文件？(y/N): ").lower().startswith('y'):
        deleted, size_saved = delete_files(doc_files, "說明文件")
        total_deleted += deleted
        total_size_saved += size_saved
    
    # 清理編譯檔案和快取
    print("\n🗑️ 清理快取檔案...")
    cleanup_cache()
    
    print("\n" + "=" * 50)
    print(f"✅ 清理完成！")
    print(f"📊 刪除檔案: {total_deleted} 個")
    print(f"💾 節省空間: {total_size_saved / 1024:.1f} MB")
    
    print(f"\n🎯 核心檔案保留:")
    core_files = [
        'test_trading_minute.py',
        'config.py', 
        'start_bot.py',
        'profit_tracker.py',
        'account_analyzer.py',
        'api_monitor.py',
        'requirements.txt'
    ]
    
    for file in core_files:
        if os.path.exists(file):
            size = os.path.getsize(file) / 1024
            print(f"   ✅ {file} ({size:.1f} KB)")

def delete_files(file_list: List[str], category: str) -> tuple:
    """刪除指定的檔案列表"""
    deleted_count = 0
    total_size = 0
    
    for file_path in file_list:
        if os.path.exists(file_path):
            try:
                # 獲取檔案大小
                file_size = os.path.getsize(file_path)
                total_size += file_size
                
                # 刪除檔案
                os.remove(file_path)
                deleted_count += 1
                
                print(f"   🗑️ 已刪除: {file_path} ({file_size/1024:.1f} KB)")
                
            except Exception as e:
                print(f"   ❌ 刪除失敗: {file_path} - {e}")
        else:
            print(f"   ⏭️ 檔案不存在: {file_path}")
    
    if deleted_count > 0:
        print(f"   📊 {category}: 刪除 {deleted_count} 個檔案，節省 {total_size/1024:.1f} KB")
    
    return deleted_count, total_size

def cleanup_cache():
    """清理快取檔案和目錄"""
    cache_items = [
        '__pycache__',
        '*.pyc',
        '*.pyo',
        '.pytest_cache'
    ]
    
    # 刪除 __pycache__ 目錄
    if os.path.exists('__pycache__'):
        try:
            shutil.rmtree('__pycache__')
            print("   🗑️ 已清理: __pycache__/ 目錄")
        except Exception as e:
            print(f"   ❌ 清理失敗: __pycache__/ - {e}")
    
    # 清理 .pyc 檔案
    import glob
    pyc_files = glob.glob('**/*.pyc', recursive=True)
    for pyc_file in pyc_files:
        try:
            os.remove(pyc_file)
            print(f"   🗑️ 已清理: {pyc_file}")
        except Exception as e:
            print(f"   ❌ 清理失敗: {pyc_file} - {e}")

if __name__ == "__main__":
    print("🧹 專案檔案清理工具")
    print("=" * 50)
    print("⚠️  此工具將刪除測試檔案、工具檔案和上傳腳本")
    print("📋 核心交易檔案將被保留")
    print("💾 建議先備份重要數據")
    
    if input("\n確定要繼續清理嗎？(y/N): ").lower().startswith('y'):
        cleanup_project()
        # 清理完成後，刪除自己
        print(f"\n🗑️ 清理工具自我刪除...")
        try:
            os.remove(__file__)
            print("   ✅ cleanup_unnecessary_files.py 已刪除")
        except Exception as e:
            print(f"   ❌ 自我刪除失敗: {e}")
    else:
        print("❌ 清理已取消") 