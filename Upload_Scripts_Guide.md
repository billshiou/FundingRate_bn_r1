# GitHub Upload Scripts Guide

## 📁 Available Upload Scripts

### `00_舊版上傳_有編碼問題.bat`
- **Status**: ❌ **NOT RECOMMENDED**
- **Issue**: Chinese encoding problems in Command Prompt
- **Function**: Complex checking and setup process
- **Recommendation**: Keep for reference only, do not use

### `01_極簡上傳_強制覆蓋.bat` ⭐ **RECOMMENDED for daily use**
- **Status**: ✅ **WORKING**
- **Features**: Simplest - only 5 lines of code
- **Function**: Direct force push to GitHub
- **Advantages**: Fastest, simplest operation
- **Best for**: Personal projects, when you want to overwrite

### `02_詳細上傳_強制覆蓋.bat`
- **Status**: ✅ **WORKING**
- **Features**: Detailed status messages
- **Function**: Force push + detailed feedback
- **Advantages**: Shows upload progress and results
- **Best for**: When you need detailed information

### `03_安全上傳_錯誤處理.bat`
- **Status**: ✅ **WORKING**
- **Features**: Try safe push first, offers options on failure
- **Function**: Safe push + error handling
- **Advantages**: Safest, won't accidentally overwrite
- **Best for**: Collaborative projects or important repositories

## 🚀 Usage Recommendations

### For Daily Quick Upload:
```
Double-click: 01_極簡上傳_強制覆蓋.bat
```

### For Detailed Information:
```
Double-click: 02_詳細上傳_強制覆蓋.bat
```

### For Safe Upload:
```
Double-click: 03_安全上傳_錯誤處理.bat
```

## ⚠️ Important Notes

1. **Protected Files**: All scripts automatically exclude `config.py` (sensitive information protected)
2. **Force Push**: Will replace ALL content on GitHub
3. **Network**: Ensure stable internet connection before upload
4. **Custom Messages**: Edit the "update" part in scripts to customize commit messages

## 🔗 Your GitHub Repository

**Project URL**: https://github.com/billshiou/funding_rates_bn_r1

After successful upload, you can view all files at the above link.

## 🛠️ Script Contents

### Minimal Script (01_極簡上傳_強制覆蓋.bat):
```batch
@echo off
git add .
git commit -m "update"
git branch -M main
git push --force origin main
pause
```

### Detailed Script (02_詳細上傳_強制覆蓋.bat):
```batch
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
```

## ✅ Setup Completed

Your upload scripts are now ready to use! Choose the one that best fits your needs. 