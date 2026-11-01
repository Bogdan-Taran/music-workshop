import sys, tempfile, threading, subprocess, shutil, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import imageio_ffmpeg
from youtube_import import normalize_url, download_audio, DownloadCancelled, convert_to_mp3, find_js_runtime
from tag_engine import read_track, export_track, existing_cover, load_cover, Image

class ImportTests(unittest.TestCase):
    def test_urls(self):
        canonical = 'https://www.youtube.com/watch?v=BaW_jenozKc'
        for url in ['https://youtu.be/BaW_jenozKc?t=4', canonical+'&list=foo',
                    'https://www.youtube.com/shorts/BaW_jenozKc', 'music.youtube.com/watch?v=BaW_jenozKc']:
            self.assertEqual(normalize_url(url), canonical)
        for url in ['https://youtube.com.evil.com/watch?v=BaW_jenozKc', 'file:///etc/passwd',
                    'https://youtube.com/playlist?list=foo', 'https://youtube.com/watch?v=bad',
                    'https://u:p@youtube.com/watch?v=BaW_jenozKc']:
            with self.assertRaises(ValueError): normalize_url(url)

    def test_download_convert_edit_and_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            source=root/'video.mp4'
            ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
            subprocess.run([ffmpeg,'-v','error','-f','lavfi','-i','color=c=blue:s=64x64:d=0.3',
                            '-f','lavfi','-i','sine=frequency=440:duration=0.3','-c:v','mpeg4','-c:a','aac',str(source)],check=True)
            class FakeDL:
                def __init__(self, opts): self.opts=opts
                def __enter__(self): return self
                def __exit__(self, *a): pass
                def extract_info(self, url, download):
                    assert self.opts['noplaylist'] is True
                    assert self.opts['match_filter']({'is_live':True})
                    target=Path(self.opts['outtmpl'].replace('%(ext)s','mp4'))
                    shutil.copyfile(source,target)
                    self.opts['progress_hooks'][0]({'status':'finished'})
                    return {'title':'Тестовая песня', 'id':'BaW_jenozKc','ext':'mp4'}
                def prepare_filename(self, info): return self.opts['outtmpl'].replace('%(ext)s','mp4')
            runtime={'node':{'path':'unused'}}
            messages=[]
            with patch('yt_dlp.YoutubeDL', FakeDL), patch('youtube_import.find_js_runtime',return_value=runtime):
                result=download_audio('https://youtu.be/BaW_jenozKc',root/'out',lambda *args:messages.append(args))
                duplicate=download_audio('https://youtu.be/BaW_jenozKc',root/'out',lambda *args:None)
                self.assertEqual(sorted(p.suffix for p in (root/'out').iterdir()),['.mp3','.mp3'])
                self.assertIn('(2)',duplicate.name)
                track=read_track(result)
                self.assertEqual(track.tags['title'],'Тестовая песня')
                self.assertEqual(track.tags['comment'],'https://www.youtube.com/watch?v=BaW_jenozKc')
                track.changes={'title':'Моё название','artist':'Мой исполнитель'}
                Image.new('RGB',(30,30),'red').save(root/'cover.png')
                track.cover=load_cover(root/'cover.png')
                saved=export_track(track,root/'edited','Название')
                self.assertEqual(read_track(saved).tags['title'],'Моё название')
                self.assertTrue(existing_cover(saved))
                cancel=threading.Event(); cancel.set()
                with self.assertRaises(DownloadCancelled):
                    download_audio('https://youtu.be/BaW_jenozKc',root/'cancelled',lambda *args:None,cancel)
                self.assertFalse(list((root/'cancelled').iterdir()))
            # Broken input fails without leaving an MP3 in the download folder.
            class BadDL(FakeDL):
                def extract_info(self,*args,**kwargs):
                    super().extract_info(*args,**kwargs)
                    raise RuntimeError('network failure')
            with patch('yt_dlp.YoutubeDL', BadDL), patch('youtube_import.find_js_runtime',return_value=runtime):
                with self.assertRaisesRegex(RuntimeError,'network failure'):
                    download_audio('https://youtu.be/BaW_jenozKc',root/'failure',lambda *args:None)
                self.assertFalse(list((root/'failure').iterdir()))
            print('Full local flow: video -> audio-only MP3 -> tags + cover -> exported copy; cleanup/cancel OK')

if __name__=='__main__': unittest.main()
