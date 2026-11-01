import sys
import os
import json
import time
import tempfile
import threading
import unittest
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from download_services import AccountStore, parse_link, login_yandex, download_yandex
from youtube_import import DownloadCancelled
from tag_engine import read_track
import imageio_ffmpeg

class ServiceTests(unittest.TestCase):
    def test_links(self):
        for value in ['https://music.yandex.ru/album/5600810/track/38816585?ref=1',
                      r'[песня](https://music.yandex.ru/album/5600810/track/38816585\?ref\=1\&x\=2)']:
            self.assertEqual(parse_link(value)[2], '38816585:5600810')
        self.assertEqual(parse_link('music.yandex.kz/track/123')[2], '123')
        self.assertEqual(parse_link('[ролик](https://youtu.be/BaW_jenozKc?si=x)')[0], 'YouTube')
        for url in ['https://music.yandex.ru.evil.test/track/12', 'https://music.yandex.ru/album/123', 'https://x:password@music.yandex.ru/track/12']:
            with self.assertRaises(ValueError): parse_link(url)

    def test_store_persistence_expiry_import_and_logout(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'settings/account.json'
            store = AccountStore(path)
            store.save(NS(access_token='test-only-token', expires_in=3600), 'Test')
            self.assertEqual(AccountStore(path).load()['access_token'], 'test-only-token')
            if os.name != 'nt': self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            second = AccountStore(Path(temp)/'migrated/account.json')
            second.import_file(path)
            self.assertEqual(second.load()['display_name'], 'Test')
            second.clear()
            self.assertIsNone(second.load())
            path.write_text('{bad json')
            self.assertIsNone(store.load())
            store.save(NS(access_token='expired',expires_in=-1),'Expired')
            self.assertIsNone(store.load())

    def test_auth_saved_token_force_login_cancellation_and_redaction(self):
        with tempfile.TemporaryDirectory() as temp:
            store=AccountStore(Path(temp)/'account.json')
            calls=[]
            class FakeClient:
                def __init__(self,token=None,**kwargs): self.token=token; self.me=NS(account=NS(login='Test')); calls.append(token)
                def init(self): return self
                def device_auth(self,**kwargs):
                    kwargs['on_code'](NS(user_code='1234',verification_url='https://oauth.yandex.ru/device',expires_in=300))
                    return NS(access_token='test-token',expires_in=3600)
            codes=[]
            with patch('yandex_music.Client',FakeClient):
                login_yandex(store,codes.append,threading.Event())
                login_yandex(store,codes.append,threading.Event())
                login_yandex(store,codes.append,threading.Event(),force_login=True)
            self.assertEqual(calls,[None,'test-token',None])
            self.assertEqual(len(codes),2)
            cancel=threading.Event(); cancel.set()
            with self.assertRaises(DownloadCancelled): login_yandex(store,codes.append,cancel)
            with patch('yandex_music.Client',side_effect=Exception('secret-token-must-not-be-displayed')):
                with self.assertRaises(RuntimeError) as error: login_yandex(store,codes.append,threading.Event())
                self.assertNotIn('secret-token',str(error.exception))

    def test_yandex_download_real_audio_and_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            src=root/'source.mp3'
            subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-f','lavfi','-i','sine=duration=0.1','-c:a','libmp3lame',str(src)],check=True)
            data=src.read_bytes()
            best=NS(codec='mp3',bitrate_in_kbps=320,get_direct_link=lambda **_: 'https://test.invalid/audio')
            low=NS(codec='mp3',bitrate_in_kbps=128,get_direct_link=lambda **_: self.fail('Wrong bitrate'))
            track=NS(id='123',title='Название',artists=[NS(name='Исполнитель')],albums=[NS(title='Альбом',year=2026)],get_download_info=lambda:[low,best])
            client=NS(tracks=lambda _: [track])
            cancel=threading.Event()
            class Response:
                headers={'Content-Length':str(len(data))}
                def __enter__(self): return self
                def __exit__(self,*args): pass
                def raise_for_status(self): pass
                def iter_content(self,*args): yield data
            with patch('download_services.login_yandex',return_value=client), patch('download_services.requests.get',return_value=Response()):
                p=download_yandex('123','https://music.yandex.ru/track/123',root/'out',lambda *a:None,cancel,AccountStore(root/'account.json'),lambda code:None)
                duplicate=download_yandex('123','https://music.yandex.ru/track/123',root/'out',lambda *a:None,cancel,AccountStore(root/'account.json'),lambda code:None)
                self.assertEqual(read_track(p).tags['artist'],'Исполнитель')
                self.assertEqual(read_track(p).tags['album'],'Альбом')
                self.assertIn('(2)',duplicate.name)
                self.assertEqual(len(list((root/'out').iterdir())),2)
            class Interrupted(Response):
                def iter_content(self,*args): cancel.set(); yield data
            with patch('download_services.login_yandex',return_value=client), patch('download_services.requests.get',return_value=Interrupted()):
                with self.assertRaises(DownloadCancelled):
                    download_yandex('123','https://music.yandex.ru/track/123',root/'cancelled',lambda *a:None,cancel,AccountStore(root/'account.json'),lambda code:None)
                self.assertFalse(list((root/'cancelled').iterdir()))

if __name__=='__main__': unittest.main()
