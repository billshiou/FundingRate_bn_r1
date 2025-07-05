@echo off
chcp 65001 > nul
echo ===========================================
echo 資金費率套利機器人 - 強制覆蓋上傳腳本
echo ⚠️ 警告：這將強制覆蓋GitHub上的所有內容！
echo ===========================================
echo.

echo [1/4] 檢查Git狀態...
git status

echo.
echo [2/4] 添加所有檔案到Git...
git add .

echo.
echo [3/4] 提交變更...
set /p commit_msg="請輸入提交訊息 (直接按Enter使用預設訊息): "
if "%commit_msg%"=="" set commit_msg=強制更新資金費率套利機器人

git commit -m "%commit_msg%"

echo.
echo [4/4] 強制推送到GitHub...
echo ⚠️ 最後確認：這將覆蓋GitHub上的所有內容！
pause
git push origin main --force

echo.
echo ===========================================
echo 強制上傳完成！
echo GitHub地址: https://github.com/billshiou/funding_rates_bn_r1
echo ===========================================
echo.
pause 