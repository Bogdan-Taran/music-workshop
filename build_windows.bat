@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Сначала запустите start_windows.bat.
 pause
 exit /b 1
)
.venv\Scripts\python.exe -m pip install -r requirements.txt "pyinstaller>=6.16,<7"
if errorlevel 1 goto error
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --collect-all imageio_ffmpeg --collect-all yt_dlp_ejs --collect-all yt_dlp --collect-all yandex_music --name MusicTagger music_tagger.py
if errorlevel 1 goto error
echo Готово: dist\MusicTagger.exe. Для запуска Python не нужен. Для YouTube нужен Node.js 22+ или Deno 2.3+.
pause
exit /b 0
:error
echo Сборка не выполнена. Подробности ошибки выше.
pause
exit /b 1
