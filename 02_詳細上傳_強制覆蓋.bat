@echo off
echo =======================================
echo   GitHub Force Upload (Overwrite Mode)
echo =======================================
echo.

echo Adding all files...
git add .

echo Committing changes...
git commit -m "update %date% %time%"

echo Force pushing to GitHub...
git push --force origin main

if errorlevel 1 (
    echo.
    echo ERROR: Force push failed!
    echo Check your network connection and GitHub credentials.
) else (
    echo.
    echo SUCCESS: Force upload completed!
    echo Your project is now on GitHub.
)

echo.
pause 