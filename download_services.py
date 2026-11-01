"""Shared URL handling and Yandex Music service. Never log account tokens."""
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse
import requests
from tag_engine import read_track, write_tags, safe_name, publish_file
from youtube_import import normalize_url as youtube_url, DownloadCancelled

YANDEX_HOSTS = {'music.yandex.ru', 'music.yandex.com', 'music.yandex.by', 'music.yandex.kz', 'music.yandex.uz'}


def clean_url(value):
    value = value.strip()
    match = re.fullmatch(r'\[.*\]\((https?://.*)\)', value, re.DOTALL)
    if match:
        value = match.group(1)
    value = re.sub(r'\\+([?&=/#])', r'\1', value)
    return value if '://' in value else 'https://' + value


def parse_link(value):
    url = clean_url(value)
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or parsed.username or parsed.password or parsed.port:
        raise ValueError('Укажите обычную ссылку YouTube или Яндекс Музыки.')
    if parsed.hostname in YANDEX_HOSTS:
        match = re.fullmatch(r'/(?:album/(\d+)/)?track/(\d+)/?', parsed.path)
        if not match:
            raise ValueError('Яндекс: нужна ссылка на один трек /track/456 или /album/123/track/456.')
        album, track = match.groups()
        path = f'/album/{album}/track/{track}' if album else f'/track/{track}'
        return 'Яндекс Музыка', 'https://music.yandex.ru' + path, f'{track}:{album}' if album else track
    return 'YouTube', youtube_url(url), None


def settings_path():
    if sys.platform == 'darwin':
        base = Path.home() / 'Library/Application Support'
    elif os.name == 'nt':
        base = Path(os.environ.get('APPDATA', str(Path.home() / 'AppData/Roaming')))
    else:
        base = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
    return base / 'MusicTagger' / 'yandex_account.json'


class AccountStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else settings_path()

    def load(self):
        try:
            value = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(value, dict) or not isinstance(value.get('access_token'), str):
                return None
            if float(value.get('expires_at', 0)) <= time.time() + 60:
                return None
            return value
        except (OSError, ValueError, TypeError):
            return None

    def summary(self):
        saved = self.load()
        if saved:
            return 'Сохранён вход: ' + (saved.get('display_name') or 'аккаунт Яндекса')
        return 'Вход не выполнен или срок авторизации истёк'

    def save(self, credentials, display_name):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {'access_token': credentials.access_token,
                'expires_at': time.time() + float(credentials.expires_in or 0),
                'display_name': display_name}
        fd, temporary = tempfile.mkstemp(prefix='.account-', dir=self.path.parent)
        try:
            if os.name != 'nt':
                os.fchmod(fd, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(data, stream, ensure_ascii=False)
            os.replace(temporary, self.path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def import_file(self, path):
        from types import SimpleNamespace
        data = AccountStore(path).load()
        if not data or not data['access_token']:
            raise ValueError('Неподходящий файл авторизации')
        self.save(SimpleNamespace(access_token=data['access_token'],
                                  expires_in=float(data['expires_at']) - time.time()),
                  data.get('display_name') or 'перенесённый аккаунт')

    def clear(self):
        self.path.unlink(missing_ok=True)


def check_cancel(cancel):
    if cancel.is_set():
        raise DownloadCancelled()


def yandex_client(store, on_code, cancel, force_login=False):
    from yandex_music import Client
    from yandex_music.exceptions import UnauthorizedError
    from yandex_music.utils.request import Request
    check_cancel(cancel)
    saved = None if force_login else store.load()
    if saved:
        client = Client(saved['access_token'], request=Request(timeout=15))
        try:
            client.init()
            check_cancel(cancel)
            return client
        except UnauthorizedError:
            store.clear()
    client = Client(request=Request(timeout=15))
    credentials = client.device_auth(on_code=on_code, should_cancel=cancel.is_set,
                                     timeout=300, device_name='MusicTagger')
    check_cancel(cancel)
    client.init()
    check_cancel(cancel)
    account = getattr(getattr(client, 'me', None), 'account', None)
    display = getattr(account, 'display_name', None) or getattr(account, 'login', None) or 'Яндекс'
    store.save(credentials, display)
    return client


def login_yandex(store, on_code, cancel, force_login=False):
    try:
        return yandex_client(store, on_code, cancel, force_login)
    except Exception as exc:
        check_cancel(cancel)
        # OAuth responses may contain sensitive server data; don't display raw exceptions.
        if isinstance(exc, OSError) and not isinstance(exc, requests.RequestException):
            raise RuntimeError('Не удалось сохранить вход. Проверьте доступ к папке настроек приложения.') from None
        raise RuntimeError('Не удалось войти в Яндекс. Проверьте интернет, подтвердите код вовремя и попробуйте снова.') from None


def download_yandex(identifier, url, folder, progress, cancel, store, on_code, on_authenticated=lambda: None):
    try:
        progress('Подключаюсь к Яндекс Музыке…', None)
        client = login_yandex(store, on_code, cancel)
        on_authenticated()
        check_cancel(cancel)
        tracks = client.tracks([identifier])
        if not tracks:
            raise RuntimeError('Трек не найден в Яндекс Музыке.')
        track = tracks[0]
        variants = [info for info in track.get_download_info() if info.codec == 'mp3']
        if not variants:
            raise RuntimeError('Для этого трека нет доступного MP3. Проверьте доступ аккаунта и подписку.')
        best = max(variants, key=lambda item: item.bitrate_in_kbps or 0)
        direct = best.get_direct_link(timeout=15)
        check_cancel(cancel)
        folder = Path(folder).expanduser().resolve()
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.yandex-', dir=folder) as temporary:
            path = Path(temporary) / 'audio.mp3'
            progress(f'Скачиваю MP3 • {best.bitrate_in_kbps} кбит/с', None)
            with requests.get(direct, stream=True, timeout=(10, 15)) as response:
                response.raise_for_status()
                total = int(response.headers.get('Content-Length', 0))
                downloaded, last_update = 0, 0.0
                with path.open('wb') as stream:
                    for chunk in response.iter_content(64 * 1024):
                        check_cancel(cancel)
                        if chunk:
                            stream.write(chunk)
                            downloaded += len(chunk)
                            now = time.monotonic()
                            if now - last_update > 0.2:
                                last_update = now
                                progress(f'Яндекс: {downloaded / 1024 / 1024:.1f} МБ', min(95, downloaded * 95 / total) if total else None)
                if not downloaded:
                    raise RuntimeError('Яндекс вернул пустой файл.')
            check_cancel(cancel)
            read_track(path)
            artists = ', '.join(artist.name for artist in track.artists or [])
            album = next(iter(track.albums or []), None)
            tags = {'title': track.title or str(track.id), 'artist': artists, 'comment': url}
            if album:
                tags['album'] = album.title or ''
                if getattr(album, 'year', None):
                    tags['date'] = str(album.year)
            write_tags(path, tags, None)
            check_cancel(cancel)
            name = safe_name(f'{artists} — {tags["title"]}' if artists else tags['title'])
            result = publish_file(path, folder, name + '.mp3')
            progress('Трек готов.', 100)
            return result
    except (RuntimeError, DownloadCancelled):
        raise
    except Exception:
        check_cancel(cancel)
        raise RuntimeError('Яндекс не смог скачать трек. Проверьте интернет и доступность трека для аккаунта; при необходимости войдите заново.') from None
