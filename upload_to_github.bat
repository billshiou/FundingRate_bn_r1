@echo off
title 上传到GitHub
cls

echo ========================================
echo        上传到GitHub仓库
echo ========================================
echo.

REM 检查Git状态
echo 📊 检查Git状态...
git status

echo.
echo 🔄 添加所有更改...
git add .

echo.
echo 📝 输入提交信息 (或按Enter使用默认信息):
set /p commit_msg="提交信息: "
if "%commit_msg%"=="" set commit_msg=🚀 更新代码和优化

echo.
echo 💾 提交更改...
git commit -m "%commit_msg%"

echo.
echo 📤 推送到GitHub...
git push origin main

echo.
if %errorlevel% equ 0 (
    echo ✅ 成功上传到GitHub! 
    echo 🔗 查看你的仓库: https://github.com/billshiou/fun_rates_bn_r1
) else (
    echo ❌ 上传失败，请检查网络连接或Git配置
)

echo.
echo 按任意键退出...
pause >nul 