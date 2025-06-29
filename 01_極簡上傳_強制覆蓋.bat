@echo off
git add .
git commit -m "update"
git branch -M main
git push --force origin main
pause 