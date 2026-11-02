import os, secrets, tempfile, threading, uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Header, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from tag_engine import read_track, export_track, load_cover, EXTENSIONS
from youtube_import import download_audio

ROOT = Path(os.environ.get('MUSIC_DATA_DIR', './data')).resolve()
ROOT.mkdir(parents=True, exist_ok=True)
API_KEY = os.environ.get('MUSIC_API_KEY', '')
app = FastAPI(title='Music API', version='0.1.0')
pool = ThreadPoolExecutor(max_workers=2)
jobs = {}

def authorize(x_api_key: str = Header(default='')):
    if not API_KEY or not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail='Invalid API key')

def job_path(job_id):
    if not job_id.isalnum() or len(job_id) != 32:
        raise HTTPException(404, 'Not found')
    return ROOT / job_id

def submit(task):
    job_id = uuid.uuid4().hex
    directory = job_path(job_id)
    directory.mkdir()
    jobs[job_id] = {'status': 'queued'}
    def run():
        jobs[job_id] = {'status': 'running'}
        try:
            path = task(directory)
            jobs[job_id] = {'status': 'done', 'filename': path.name}
        except Exception:
            jobs[job_id] = {'status': 'error', 'message': 'Не удалось обработать файл или ссылку.'}
    pool.submit(run)
    return {'id': job_id, 'status': 'queued'}

class Link(BaseModel):
    url: str

@app.get('/health')
def health():
    return {'status': 'ok'}

@app.post('/jobs/youtube', dependencies=[Depends(authorize)], status_code=202)
def youtube(body: Link):
    from youtube_import import normalize_url
    try:
        url = normalize_url(body.url)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return submit(lambda directory: download_audio(url, directory, lambda *_: None))

@app.post('/jobs/tags', dependencies=[Depends(authorize)], status_code=202)
def tags(audio: UploadFile = File(...), title: str = Form(default=''), artist: str = Form(default=''), album: str = Form(default=''), cover: UploadFile | None = File(default=None)):
    suffix = Path(audio.filename or '').suffix.lower()
    if suffix not in EXTENSIONS:
        raise HTTPException(400, 'Unsupported audio format')
    def read_limited(upload, limit):
        data = upload.file.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(413, 'File too large')
        return data
    audio_data = read_limited(audio, 100 * 1024 * 1024)
    cover_data = read_limited(cover, 10 * 1024 * 1024) if cover else None
    def process(directory):
        original = directory / ('source' + suffix)
        original.write_bytes(audio_data)
        track = read_track(original)
        track.changes = {k: v for k, v in {'title': title, 'artist': artist, 'album': album}.items() if v}
        if cover_data:
            image = directory / 'cover'
            image.write_bytes(cover_data)
            track.cover = load_cover(image)
        output = directory / 'result'
        path = export_track(track, output, 'Название')
        original.unlink()
        if cover_data: image.unlink()
        return path
    return submit(process)

@app.get('/jobs/{job_id}', dependencies=[Depends(authorize)])
def status(job_id: str):
    job_path(job_id)
    if job_id not in jobs: raise HTTPException(404, 'Not found')
    return jobs[job_id]

@app.get('/jobs/{job_id}/file', dependencies=[Depends(authorize)])
def file(job_id: str):
    directory = job_path(job_id)
    job = jobs.get(job_id)
    if not job or job['status'] != 'done': raise HTTPException(404, 'File not ready')
    name = job['filename']
    candidates = [directory / name, directory / 'result' / name]
    path = next((p for p in candidates if p.is_file()), None)
    if not path: raise HTTPException(404, 'File not found')
    return FileResponse(path, filename=name, media_type='application/octet-stream')
