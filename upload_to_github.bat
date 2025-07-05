@echo off
chcp 65001 > nul
echo ===========================================
echo 資金費率套利機器人 - GitHub上傳腳本
echo ===========================================
echo.

echo [1/4] 檢查Git狀態...
git status

echo.
echo [2/4] 添加所有檔案到Git...
git add .

echo.
echo [3/4] 檢查要上傳的檔案...
echo 以下檔案將被上傳：
git diff --cached --name-only
echo.
echo 以下檔案將被忽略（不會上傳）：
echo - config.py （包含API密鑰）
echo - logs/ （日誌檔案）
echo - trade_history.json （交易記錄）
echo - __pycache__/ （Python快取）

echo.
echo [4/4] 提交並推送...
set /p commit_msg="請輸入提交訊息 (直接按Enter使用預設訊息): "
if "%commit_msg%"=="" set commit_msg=更新資金費率套利機器人

git commit -m "%commit_msg%"

echo.
echo 推送到GitHub...
git push origin main

echo.
echo ===========================================
echo 上傳完成！
echo GitHub地址: https://github.com/billshiou/funding_rates_bn_r1
echo ===========================================
echo.
pause 