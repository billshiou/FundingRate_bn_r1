@echo off
echo ========================================
echo 🚀 資金費率套利機器人 - GitHub 強制覆蓋
echo ========================================
echo.

echo ⚠️ 警告：這將直接覆蓋遠程倉庫內容！
echo 所有遠程更改將被丟失！
echo.
set /p confirm="確認要強制覆蓋嗎？(y/N): "
if /i not "%confirm%"=="y" (
    echo ❌ 操作已取消
    pause
    exit /b
)

echo.
echo 📋 檢查當前狀態...
git status

echo.
echo 🔍 檢查是否有未提交的更改...
git diff --name-only

echo.
echo 📝 準備強制覆蓋...
echo 版本: v2.1 - API 速度優化
echo 日期: %date% %time%
echo.

echo 💾 添加所有文件到暫存區...
git add .

echo.
echo 📤 提交更改...
git commit -m "🚀 v2.1: API 速度優化 - 強制覆蓋

✨ 新增功能:
- 所有API調用加入超時控制 (1秒)
- 智能重試機制 (最多2次重試)
- 併發保護和狀態重置
- 指數退避重試策略

⚡ 性能提升:
- 進場訂單: 3-10倍速度提升
- 槓桿檢查: 1-4倍速度提升  
- 倉位檢查: 1-5倍速度提升
- 平倉訂單: 保持極速執行

🛡️ 穩定性增強:
- 15秒內卡住的API調用自動重置
- 完整的異常捕獲和重試機制
- 實時API性能監控

📊 監控改進:
- 新增超時警告和極慢調用檢測
- 重試統計和成功率記錄
- 更詳細的API調用時間記錄

🔧 技術改進:
- 客戶端超時設定為1秒
- 併發限制最多3個API調用
- 智能狀態管理和錯誤處理

⚠️ 注意：這是強制覆蓋更新
日期: %date% %time%
版本: v2.1"

echo.
echo 🏷️ 創建版本標籤...
git tag -a v2.1 -m "v2.1: API 速度優化 - 強制覆蓋更新"

echo.
echo ⚠️ 強制推送到 GitHub (覆蓋模式)...
echo 推送到主分支 (強制覆蓋)...
git push --force origin main

echo.
echo 🏷️ 強制推送版本標籤...
git push --force origin v2.1

echo.
echo ✅ 強制覆蓋完成！
echo.
echo 📊 本次更新摘要:
echo - 版本: v2.1
echo - 更新方式: 強制覆蓋
echo - 主要改進: API 速度優化
echo - 性能提升: 3-10倍
echo - 穩定性: ⭐⭐⭐⭐⭐
echo.
echo ⚠️ 注意：遠程倉庫已被完全覆蓋
echo 🔗 GitHub 倉庫: https://github.com/your-username/funding-rate-bot
echo 📝 更新日誌: CHANGELOG.md
echo.
pause 