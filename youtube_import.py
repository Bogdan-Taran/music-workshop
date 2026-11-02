"""One YouTube video -> local MP3, with cancellation and isolated temporary files."""
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from tag_engine import safe_name, write_tags, publish_file, read_track


class DownloadCancelled(Exception):
    pass


def normalize_url(value):
    value = value.strip()
    if '://' not in value:
        value = 'https://' + value
    parsed = urlparse(value)
    if parsed.scheme not in ('https', 'http') or parsed.username or parsed.password or parsed.port:
        raise ValueError('Вставьте обычную ссылку на один ролик YouTube.')
    host = (parsed.hostname or '').lower()
    pieces = parsed.path.strip('/').split('/')
    if host in ('youtu.be', 'www.youtu.be') and len(pieces) == 1:
        video_id = pieces[0]
    elif host in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com'):
        if parsed.path.rstrip('/') == '/watch':
            video_id = parse_qs(parsed.query).get('v', [''])[0]
        elif len(pieces) == 2 and pieces[0] in ('shorts', 'embed', 'live'):
            video_id = pieces[1]
        else:
            video_id = ''
    else:
        video_id = ''
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
        raise ValueError('Нужна ссылка на отдельный ролик YouTube, а не канал или плейлист.')
    return 'https://www.youtube.com/watch?v=' + video_id


def find_js_runtime():
    """Finder does not inherit the usual shell PATH."""
    directories = [Path.home() / '.deno/bin', Path('/opt/homebrew/bin'), Path('/usr/local/bin')]
    if os.name == 'nt':
        directories += [Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'nodejs']
    for name, minimum in [('deno', (2, 3, 0)), ('node', (22, 0, 0))]:
        executable = name + ('.exe' if os.name == 'nt' else '')
        candidates = [shutil.which(name)] + [str(p / executable) for p in directories]
        for candidate in candidates:
            if not candidate or not Path(candidate).is_file():
                continue
            try:
                result = subprocess.run([candidate, '--version'], capture_output=True, text=True,
                                        timeout=5, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                match = re.search(r'(\d+)\.(\d+)\.(\d+)', result.stdout)
                if result.returncode == 0 and match and tuple(map(int, match.groups())) >= minimum:
                    return {name: {'path': candidate}}
            except (OSError, subprocess.TimeoutExpired):
                continue
    raise RuntimeError('Для загрузки YouTube установите Node.js 22 или новее с https://nodejs.org/ '
                       '(либо Deno 2.3+) и перезапустите приложение. Редактор локальных песен работает без него.')


def convert_to_mp3(source, destination, ffmpeg, cancel):
    if cancel.is_set():
        raise DownloadCancelled()
    command = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
               '-i', str(source), '-map', '0:a:0', '-vn', '-c:a', 'libmp3lame', '-q:a', '2',
               '-map_metadata', '-1', str(destination)]
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=log,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            while process.poll() is None:
                if cancel.wait(0.15):
                    raise DownloadCancelled()
            if process.returncode:
                log.seek(0)
                raise RuntimeError('Не удалось извлечь аудио: ' + log.read().decode('utf-8', 'replace')[-2000:])
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
    # Verify there is a valid MP3 before publishing anything.
    read_track(destination)


def download_audio(url, destination, progress, cancel=None):
    """progress receives (message, percent or None). Returns persistent MP3 path."""
    import yt_dlp
    import imageio_ffmpeg
    cancel = cancel or threading.Event()
    url = normalize_url(url)
    runtimes = find_js_runtime()
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    destination = Path(destination).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    last_update = 0.0

    def check_cancel():
        if cancel.is_set():
            raise DownloadCancelled()

    def hook(event):
        nonlocal last_update
        check_cancel()
        now = time.monotonic()
        if event['status'] == 'downloading' and now - last_update > 0.2:
            last_update = now
            total = event.get('total_bytes') or event.get('total_bytes_estimate')
            done = event.get('downloaded_bytes', 0)
            percent = min(85, done * 85 / total) if total else None
            progress(f'Загрузка аудио: {done / 1024 / 1024:.1f} МБ', percent)
        elif event['status'] == 'finished':
            progress('Аудио загружено. Подготавливаю MP3…', 85)

    def match_filter(info, *, incomplete=False):
        check_cancel()
        if info.get('is_live') or info.get('live_status') in ('is_live', 'is_upcoming', 'post_live'):
            return 'Прямые эфиры и запланированные трансляции не поддерживаются. Используйте опубликованную запись.'
        return None

    class Logger:
        def debug(self, message):
            pass
        def warning(self, message):
            progress('YouTube: ' + message, None)
        def error(self, message):
            pass  # yt-dlp also raises DownloadError with the same details.

    with tempfile.TemporaryDirectory(prefix='.youtube-', dir=destination) as temporary:
        workspace = Path(temporary)
        options = {
            'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True, 'no_warnings': False,
            'outtmpl': str(workspace / 'source.%(ext)s'), 'overwrites': False,
            'progress_hooks': [hook], 'match_filter': match_filter, 'logger': Logger(),
            'socket_timeout': 15, 'retries': 2, 'fragment_retries': 2,
            'js_runtimes': runtimes, 'cachedir': False,
            'windowsfilenames': True,
        }
        progress('Получаю информацию о ролике…', None)
        try:
            with yt_dlp.YoutubeDL(options) as downloader:
                info = downloader.extract_info(url, download=True)
                check_cancel()
                if not info or info.get('_type') in ('playlist', 'multi_video'):
                    raise ValueError('Не удалось получить отдельный ролик. Проверьте ссылку и доступность записи.')
                source = Path(downloader.prepare_filename(info))
        except Exception:
            check_cancel()
            raise
        if not source.is_file():
            raise RuntimeError('YouTube не предоставил файл аудио. Попробуйте обновить загрузчик.')
        check_cancel()
        progress('Преобразую в MP3. Это может занять некоторое время…', 90)
        mp3 = workspace / 'audio.mp3'
        convert_to_mp3(source, mp3, ffmpeg, cancel)
        title = str(info.get('track') or info.get('title') or info.get('id') or 'YouTube')
        artist = str(info.get('artist') or '')
        write_tags(mp3, {'title': title, 'artist': artist, 'comment': url}, None)
        check_cancel()
        name = safe_name(title) + '.mp3'
        final = publish_file(mp3, destination, name)
        progress('Аудио готово — добавляю в редактор.', 100)
        return final
