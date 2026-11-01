#!/bin/bash
source "$(dirname -- "$0")/macos_setup.sh"
"$MAC_PYTHON" -m pip install --upgrade -r requirements.txt
printf '\nБиблиотеки обновлены. Перезапустите MusicTagger. Если используете .app, заново запустите build_macos.command.\n'
if [ -t 0 ]; then read -r -p 'Нажмите Enter…' unused_reply; fi
