@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto dependencies
where py >nul 2>nul
if errorlevel 1 goto usepython
py -3 -m venv .venv
if errorlevel 1 goto error
goto dependencies
:usepython
python -m venv .venv
if errorlevel 1 goto error
:dependencies
.venv\Scripts\python.exe -c "import sys; assert sys.version_info >= (3,11)"
if errorlevel 1 goto error
.venv\Scripts\python.exe -c "import mutagen, PIL.ImageTk, yt_dlp, yt_dlp_ejs, imageio_ffmpeg, yandex_music" >nul 2>nul
if not errorlevel 1 goto launch
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto error
:launch
.venv\Scripts\python.exe music_tagger.py
if errorlevel 1 goto error
exit /b 0
:error
echo Установите Python 3.11 или новее с python.org. При первой установке библиотек нужен интернет.
echo Подробности ошибки выше.
pause
exit /b 1
