@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Сначала запустите start_windows.bat.
 pause
 exit /b 1
)
.venv\Scripts\python.exe -m pip install --upgrade -r requirements.txt
if errorlevel 1 (
 echo Не удалось обновить библиотеки. Подробности ошибки выше.
 pause
 exit /b 1
)
echo Обновлено. Перезапустите приложение. Если используете EXE, соберите его заново через build_windows.bat.
pause
