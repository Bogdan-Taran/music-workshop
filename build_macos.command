#!/bin/bash
source "$(dirname -- "$0")/macos_setup.sh"
"$MAC_PYTHON" -m pip install 'pyinstaller>=6.16,<7'
export PYINSTALLER_CONFIG_DIR="$PWD/.build-cache"
"$MAC_PYTHON" -m PyInstaller --noconfirm --clean --onedir --windowed \
    --collect-all imageio_ffmpeg --collect-all yt_dlp_ejs --collect-all yt_dlp --collect-all yandex_music \
    --name MusicTagger --osx-bundle-identifier local.musictagger.app \
    --distpath dist-macos --workpath build-macos music_tagger.py
printf '\nГотово: %s/dist-macos/MusicTagger.app\nПеренесите MusicTagger.app в «Программы».\n' "$PWD"
open -R "$PWD/dist-macos/MusicTagger.app"
