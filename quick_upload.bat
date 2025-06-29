@echo off
chcp 65001 >nul
cls
echo ========================================
echo   資金費率套利機器人 - GitHub 快速上傳
echo ========================================
echo.

REM 檢查是否為Git倉庫
git status >nul 2>&1
if errorlevel 1 (
    echo ❌ 錯誤: 當前目錄不是Git倉庫
    echo 正在初始化Git倉庫...
    git init
    echo ✅ Git倉庫初始化完成
    echo.
)

REM 檢查是否有遠程倉庫
git remote -v >nul 2>&1
if errorlevel 1 (
    echo ⚠️  尚未設置GitHub遠程倉庫
    echo.
    echo 請選擇操作:
    echo 1. 設置新的GitHub倉庫
    echo 2. 跳過此步驟
    echo.
    set /p choice="請輸入選擇 (1/2): "
    
    if "!choice!"=="1" (
        echo.
        echo 📝 請在GitHub上創建新倉庫後，提供倉庫URL
        echo 格式例如: https://github.com/yourusername/funding-rate-bot.git
        echo.
        set /p repo_url="請輸入GitHub倉庫URL: "
        
        if not "!repo_url!"=="" (
            git remote add origin !repo_url!
            echo ✅ 遠程倉庫設置完成: !repo_url!
        ) else (
            echo ❌ 未輸入倉庫URL，跳過設置
        )
    )
    echo.
)

echo 📋 檢查Git狀態...
git status

echo.
echo 📦 添加所有文件到暫存區...
git add .

echo.
echo 💬 提交更改...
set commit_msg=Auto update: %date% %time%
git commit -m "%commit_msg%"

if errorlevel 1 (
    echo ⚠️  沒有新的更改需要提交
) else (
    echo ✅ 提交完成
)

echo.
echo 🚀 推送到GitHub...

REM 檢查是否有遠程倉庫
git remote get-url origin >nul 2>&1
if errorlevel 1 (
    echo ❌ 錯誤: 沒有設置遠程倉庫
    echo 請先在GitHub創建倉庫，然後運行:
    echo git remote add origin https://github.com/yourusername/your-repo.git
    goto end
)

REM 檢查遠程分支是否存在
git ls-remote --heads origin main >nul 2>&1
if errorlevel 1 (
    echo 📝 首次推送到main分支...
    git branch -M main
    git push -u origin main
) else (
    echo 📝 推送到現有的main分支...
    git push origin main
)

if errorlevel 1 (
    echo ❌ 推送失敗，可能需要先pull最新更改
    echo 嘗試強制推送? (謹慎使用)
    set /p force_choice="是否強制推送? (y/N): "
    if /i "!force_choice!"=="y" (
        git push --force origin main
        if errorlevel 1 (
            echo ❌ 強制推送失敗
        ) else (
            echo ✅ 強制推送成功
        )
    )
) else (
    echo ✅ 推送成功!
)

:end
echo.
echo ========================================
echo   上傳完成！
echo ========================================
echo.
echo 💡 提示:
echo - 確保config.py不會被上傳（已在.gitignore中排除）
echo - 如需修改遠程倉庫: git remote set-url origin [新URL]
echo - 檢查倉庫狀態: git status
echo.
pause 