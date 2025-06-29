@echo off
echo =======================================
echo   GitHub Quick Upload Script
echo =======================================
echo.

echo Step 1: Check Git status...
git status

echo.
echo Step 2: Add all files...
git add .

echo.
echo Step 3: Commit changes...
git commit -m "Auto update %date% %time%"

echo.
echo Step 4: Check remote repository...
git remote -v

echo.
echo Step 5: Push to GitHub...
git branch -M main
git push -u origin main

if errorlevel 1 (
    echo.
    echo ERROR: Push failed!
    echo.
    echo Possible solutions:
    echo 1. Add GitHub repository:
    echo    git remote add origin https://github.com/yourusername/your-repo.git
    echo.
    echo 2. Or force push:
    echo    git push --force origin main
    echo.
    echo 3. Or create new repository on GitHub first
    echo.
) else (
    echo.
    echo SUCCESS: Upload completed!
)

echo.
pause 