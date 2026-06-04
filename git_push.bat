@echo off
set /p msg="Введи комментарий к коммиту: "
git add .
git commit -m "%msg%"
git push
echo ✅ Git push выполнен
