"""Metadata editing: original files are never written to."""
import base64
import io
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
import mutagen
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4Cover
from mutagen.flac import FLAC, Picture
from mutagen.oggvorbis import OggVorbis
from mutagen.oggopus import OggOpus
from mutagen.id3 import TIT2, TPE1, TALB, TPE2, TDRC, TCON, TRCK, COMM, APIC
from PIL import Image, ImageOps

EXTENSIONS = {'.mp3', '.flac', '.m4a', '.ogg', '.opus'}
FIELDS = {'title': 'Название', 'artist': 'Исполнитель', 'album': 'Альбом',
          'albumartist': 'Исполнитель альбома', 'date': 'Год / дата',
          'genre': 'Жанр', 'tracknumber': 'Номер трека', 'comment': 'Комментарий'}
ID3_KEYS = dict(zip(FIELDS, ['TIT2', 'TPE1', 'TALB', 'TPE2', 'TDRC', 'TCON', 'TRCK', 'COMM']))
ID3_CLASSES = dict(zip(FIELDS, [TIT2, TPE1, TALB, TPE2, TDRC, TCON, TRCK, COMM]))
MP4_KEYS = dict(zip(FIELDS, ['\xa9nam', '\xa9ART', '\xa9alb', 'aART', '\xa9day', '\xa9gen', 'trkn', '\xa9cmt']))
PATTERNS = {'Название': '{title}', 'Исполнитель — Название': '{artist} — {title}',
            'Номер — Название': '{tracknumber} — {title}', 'Исходное имя': '{original}'}

@dataclass
class Track:
    path: Path
    tags: dict
    changes: dict = field(default_factory=dict)
    cover: object = None  # None: preserve; False: remove; bytes: replace
    status: str = 'Без изменений'

    def values(self):
        return dict(self.tags, **self.changes)


def open_audio(path):
    audio = mutagen.File(path)
    if not isinstance(audio, (MP3, MP4, FLAC, OggVorbis, OggOpus)):
        raise ValueError('Неподдерживаемый формат аудио')
    return audio


def read_track(path):
    path = Path(path).resolve()
    audio = open_audio(path)
    tags = {}
    for key in FIELDS:
        if isinstance(audio, MP3):
            frames = audio.tags.getall(ID3_KEYS[key]) if audio.tags else []
            tags[key] = str(frames[0].text[0]) if frames and frames[0].text else ''
        elif isinstance(audio, MP4):
            value = (audio.tags or {}).get(MP4_KEYS[key], [])
            if key == 'tracknumber' and value:
                number, total = value[0]
                tags[key] = str(number) + (f'/{total}' if total else '')
            else:
                tags[key] = str(value[0]) if value else ''
        else:
            tags[key] = (audio.tags or {}).get(key, [''])[0]
    return Track(path, tags)


def load_cover(path):
    with Image.open(path) as source:
        source.load()
        im = ImageOps.exif_transpose(source).convert('RGB')
        im.thumbnail((1600, 1600))
        out = io.BytesIO()
        im.save(out, 'JPEG', quality=92)
        return out.getvalue()


def existing_cover(path):
    audio = open_audio(path)
    if isinstance(audio, MP3):
        pics = audio.tags.getall('APIC') if audio.tags else []
        return pics[0].data if pics else None
    if isinstance(audio, MP4):
        pics = (audio.tags or {}).get('covr', [])
        return bytes(pics[0]) if pics else None
    if isinstance(audio, FLAC):
        return audio.pictures[0].data if audio.pictures else None
    pics = (audio.tags or {}).get('metadata_block_picture', [])
    return Picture(base64.b64decode(pics[0])).data if pics else None


def validate(changes):
    number = changes.get('tracknumber', '')
    if number:
        if not re.fullmatch(r'\d{1,5}(/\d{1,5})?', number):
            raise ValueError('Номер трека: число или число/всего, например 3/12')
        nums = [int(n) for n in number.split('/')]
        if any(n < 1 or n > 65535 for n in nums) or (len(nums) == 2 and nums[0] > nums[1]):
            raise ValueError('Неверный номер трека или общее число треков')
    date = changes.get('date', '')
    if date:
        if not re.fullmatch(r'\d{4}(-\d{2}(-\d{2})?)?', date):
            raise ValueError('Дата: ГГГГ, ГГГГ-ММ или ГГГГ-ММ-ДД')
        import datetime
        parts = [int(p) for p in date.split('-')]
        datetime.date(*((parts + [1, 1])[:3]))


def remove_tag(tags, key):
    if key in tags:
        del tags[key]


def write_tags(path, changes, cover):
    validate(changes)
    audio = open_audio(path)
    if audio.tags is None:
        audio.add_tags()
    for key, value in changes.items():
        if isinstance(audio, MP3):
            audio.tags.delall(ID3_KEYS[key])
            if value:
                args = dict(encoding=3, text=[value])
                if key == 'comment':
                    args.update(lang='eng', desc='')
                audio.tags.add(ID3_CLASSES[key](**args))
        elif isinstance(audio, MP4):
            atom = MP4_KEYS[key]
            remove_tag(audio.tags, atom)
            if value:
                if key == 'tracknumber':
                    parts = [int(p) for p in value.split('/')]
                    audio.tags[atom] = [(parts[0], parts[1] if len(parts) > 1 else 0)]
                else:
                    audio.tags[atom] = [value]
        else:
            remove_tag(audio.tags, key)
            if value:
                audio.tags[key] = [value]
    if cover is not None:
        if isinstance(audio, MP3):
            audio.tags.delall('APIC')
            if cover:
                audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=cover))
        elif isinstance(audio, MP4):
            remove_tag(audio.tags, 'covr')
            if cover:
                audio.tags['covr'] = [MP4Cover(cover, imageformat=MP4Cover.FORMAT_JPEG)]
        else:
            if isinstance(audio, FLAC):
                audio.clear_pictures()
            else:
                for key in ('metadata_block_picture', 'coverart', 'coverartmime'):
                    remove_tag(audio.tags, key)
            if cover:
                pic = Picture()
                pic.type, pic.mime, pic.desc, pic.data = 3, 'image/jpeg', 'Cover', cover
                with Image.open(io.BytesIO(cover)) as im:
                    pic.width, pic.height = im.size
                pic.depth = 24
                if isinstance(audio, FLAC):
                    audio.add_picture(pic)
                else:
                    audio.tags['metadata_block_picture'] = [base64.b64encode(pic.write()).decode('ascii')]
    audio.save()


def safe_name(value):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', value).strip(' .')
    # Bound both characters and encoded byte length for macOS/Linux file systems.
    value = value[:150]
    while len(value.encode('utf-8')) > 180:
        value = value[:-1]
    value = value.rstrip(' .') or 'Без названия'
    if re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])($|\.)', value, re.I):
        value = '_' + value
    return value


def output_name(track, pattern):
    values = track.values()
    values['title'] = values.get('title') or track.path.stem
    values['artist'] = values.get('artist') or 'Неизвестный исполнитель'
    values['tracknumber'] = (values.get('tracknumber') or '0').split('/')[0].zfill(2)
    values['original'] = track.path.stem
    return safe_name(PATTERNS[pattern].format(**values)) + track.path.suffix.lower()


def publish_file(temporary, folder, name):
    """Atomically publish a file from the same filesystem without overwriting."""
    folder = Path(folder)
    index = 1
    while True:
        candidate = folder / (name if index == 1 else f'{Path(name).stem} ({index}){Path(name).suffix}')
        try:
            fd = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666)
            os.close(fd)
            break
        except FileExistsError:
            index += 1
    try:
        os.replace(temporary, candidate)
    except BaseException:
        candidate.unlink(missing_ok=True)
        raise
    return candidate


def export_track(track, folder, pattern):
    validate(track.changes)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.music-tagger-', suffix=track.path.suffix, dir=folder)
    os.close(fd)
    try:
        shutil.copyfile(track.path, temporary)
        write_tags(temporary, track.changes, track.cover)
        return publish_file(temporary, folder, output_name(track, pattern))
    finally:
        Path(temporary).unlink(missing_ok=True)
