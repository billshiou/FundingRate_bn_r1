@echo off
chcp 65001 >nul
echo ========================================
echo    資金費率交易機器人 - GitHub 上傳
echo ========================================
echo.

:: 檢查是否在正確的目錄
if not exist "test_trading_minute.py" (
    echo [錯誤] 請在專案根目錄執行此腳本
    echo 當前目錄: %CD%
    pause
    exit /b 1
)

echo [步驟 1] 檢查 Git 狀態...
git status
echo.

echo [步驟 2] 添加所有文件到暫存區...
git add .
echo.

echo [步驟 3] 提交更改...
set /p commit_msg="請輸入提交訊息 (預設: Update trading bot): "
if "%commit_msg%"=="" set commit_msg=Update trading bot
git commit -m "%commit_msg%"
echo.

echo [步驟 4] 檢查遠端倉庫...
git remote -v
echo.

echo [步驟 5] 強制推送到 GitHub (覆蓋遠端)...
echo 警告：這將覆蓋遠端倉庫的內容！
set /p confirm="確定要繼續嗎？(y/N): "
if /i "%confirm%"=="y" (
    echo 正在強制推送...
    git push --force origin main
    if %errorlevel% equ 0 (
        echo.
        echo ✅ 上傳成功！
        echo 遠端倉庫已被覆蓋更新
    ) else (
        echo.
        echo ❌ 上傳失敗！
        echo 請檢查網路連接和 GitHub 權限
    )
) else (
    echo 操作已取消
)

echo.
echo ========================================
echo 按任意鍵退出...
pause >nul 