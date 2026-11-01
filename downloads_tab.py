"""Download queue and account UI. Workers communicate only through events."""
import queue
import threading
import webbrowser
from pathlib import Path
from urllib.parse import urlparse
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from download_services import AccountStore, parse_link, login_yandex, download_yandex
from youtube_import import download_audio, DownloadCancelled


class Downloads:
    def __init__(self, app, notebook, frame, account_frame, on_tracks):
        self.app, self.notebook, self.frame = app, notebook, frame
        self.account_frame, self.on_tracks = account_frame, on_tracks
        self.store = AccountStore()
        self.jobs = {}
        self.running = False
        self.cancel = threading.Event()
        self.events = queue.Queue()
        self.folder = tk.StringVar(value=str(Path.home() / 'Music' / 'MusicTagger' / 'Загрузки'))
        self.auto_add = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value='Добавьте ссылки — сервис определится автоматически.')
        self.account_status = tk.StringVar(value=self.store.summary())
        self.code, self.auth_url = tk.StringVar(), None
        self.build_downloads()
        self.build_account()
        self.app.after(100, self.poll)

    def build_downloads(self):
        top = ttk.LabelFrame(self.frame, text='1. Добавьте ссылки', padding=12)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(2, weight=1)
        top.grid(row=0, column=0, sticky='ew')
        ttk.Label(top, text='YouTube или Яндекс Музыка • одна ссылка на строку • ссылки из чата тоже подходят').pack(anchor='w')
        self.urls = tk.Text(top, height=3, wrap='word', font=('Arial', 12))
        self.urls.pack(fill='x', pady=8)
        controls = ttk.Frame(top)
        controls.pack(fill='x')
        ttk.Button(controls, text='Добавить в очередь', command=self.add_links).pack(side='left')
        ttk.Button(controls, text='Вставить из буфера', command=self.paste_links).pack(side='left', padx=8)
        ttk.Label(controls, text='YouTube → MP3; Яндекс → лучший доступный MP3').pack(side='right')
        destination = ttk.Frame(self.frame)
        destination.grid(row=1, column=0, sticky='ew', pady=10)
        ttk.Label(destination, text='Папка загрузки:').pack(side='left')
        ttk.Entry(destination, textvariable=self.folder).pack(side='left', fill='x', expand=True, padx=8)
        ttk.Button(destination, text='Выбрать…', command=self.choose_folder).pack(side='left')
        group = ttk.LabelFrame(self.frame, text='2. Скачайте музыку', padding=10)
        group.grid(row=2, column=0, sticky='nsew')
        self.table = ttk.Treeview(group, columns=('service', 'name', 'status'), show='headings', selectmode='extended')
        for key, title, width in [('service', 'Сервис', 140), ('name', 'Ссылка / готовый файл', 570), ('status', 'Состояние', 180)]:
            self.table.heading(key, text=title)
            self.table.column(key, width=width, minwidth=80)
        self.table.grid(row=0, column=0, sticky='nsew')
        scroll = ttk.Scrollbar(group, orient='vertical', command=self.table.yview)
        scroll.grid(row=0, column=1, sticky='ns')
        self.table.configure(yscrollcommand=scroll.set)
        group.rowconfigure(0, weight=1)
        group.columnconfigure(0, weight=1)
        self.table.bind('<<TreeviewSelect>>', self.show_details)
        self.table.bind('<Double-1>', self.full_details)
        self.details = tk.StringVar(value='Выберите строку, чтобы увидеть путь к файлу или причину ошибки.')
        ttk.Label(group, textvariable=self.details, wraplength=1030).grid(row=1, column=0, columnspan=2, sticky='w', pady=6)
        actions = ttk.Frame(group)
        actions.grid(row=2, column=0, columnspan=2, sticky='ew')
        self.start_button = ttk.Button(actions, text='Скачать очередь', command=self.start)
        self.start_button.pack(side='left')
        self.cancel_button = ttk.Button(actions, text='Отменить', command=self.stop, state='disabled')
        self.cancel_button.pack(side='left', padx=6)
        ttk.Button(actions, text='Повторить выбранные', command=self.retry).pack(side='left', padx=6)
        ttk.Button(actions, text='Убрать выбранные', command=self.remove).pack(side='left')
        footer = ttk.Frame(self.frame)
        footer.grid(row=3, column=0, sticky='ew')
        self.progress = ttk.Progressbar(footer)
        self.progress.pack(fill='x', pady=(10, 4))
        ttk.Label(footer, textvariable=self.status, wraplength=1060).pack(anchor='w')
        transfer = ttk.LabelFrame(footer, text='3. Перейдите к тегам и обложкам', padding=10)
        transfer.pack(fill='x', pady=(10, 0))
        ttk.Checkbutton(transfer, text='Автоматически добавлять готовые файлы в редактор тегов', variable=self.auto_add).pack(side='left')
        ttk.Button(transfer, text='Открыть выбранные в редакторе →', command=self.transfer).pack(side='right')

    def build_account(self):
        box = ttk.Frame(self.account_frame, padding=20)
        box.pack(fill='both', expand=True)
        ttk.Label(box, text='Аккаунт Яндекс Музыки', font=('Arial', 18, 'bold')).pack(anchor='w')
        ttk.Label(box, text='Войдите по коду один раз. Аккаунт сохранится для следующих запусков.\nПароль вводится только на странице Яндекса в браузере.', wraplength=800).pack(anchor='w', pady=12)
        ttk.Label(box, textvariable=self.account_status).pack(anchor='w', pady=8)
        buttons = ttk.Frame(box)
        buttons.pack(anchor='w')
        self.login_button = ttk.Button(buttons, text='Войти / сменить аккаунт', command=self.login)
        self.login_button.pack(side='left')
        self.logout_button = ttk.Button(buttons, text='Забыть аккаунт', command=self.logout)
        self.logout_button.pack(side='left', padx=8)
        ttk.Button(buttons, text='Перенести вход из старого скрипта…', command=self.import_account).pack(side='left')
        self.auth_panel = ttk.LabelFrame(box, text='Подтверждение входа', padding=16)
        ttk.Label(self.auth_panel, text='1. Откройте страницу Яндекса.\n2. Введите этот код и подтвердите вход.\n3. Вернитесь в приложение — оно продолжит автоматически.').pack(anchor='w')
        ttk.Entry(self.auth_panel, textvariable=self.code, state='readonly', width=25, font=('Arial', 20)).pack(anchor='w', pady=12)
        actions = ttk.Frame(self.auth_panel)
        actions.pack(anchor='w')
        ttk.Button(actions, text='Открыть Яндекс', command=self.open_auth).pack(side='left')
        ttk.Button(actions, text='Скопировать код', command=self.copy_code).pack(side='left', padx=8)
        ttk.Button(actions, text='Отменить вход', command=self.stop).pack(side='left')
        self.auth_note = tk.StringVar()
        ttk.Label(self.auth_panel, textvariable=self.auth_note, wraplength=800).pack(anchor='w', pady=8)
        ttk.Label(box, text='Если сохранённый вход истёк, при следующем скачивании будет предложен новый код.\nДоступность треков и качества зависит от аккаунта и сервиса. Для YouTube вход в Яндекс не нужен.', wraplength=900).pack(anchor='w', pady=20)

    def paste_links(self):
        if self.running:
            return
        try:
            text = self.app.clipboard_get()
            if self.urls.get('1.0', 'end').strip():
                self.urls.insert('end', '\n')
            self.urls.insert('end', text)
        except tk.TclError:
            self.status.set('В буфере обмена нет текста.')

    def add_links(self):
        if self.running:
            return
        lines = [line.strip() for line in self.urls.get('1.0', 'end').splitlines() if line.strip()]
        if not lines:
            self.status.set('Вставьте хотя бы одну ссылку.')
            return
        parsed, errors = [], []
        for index, line in enumerate(lines, 1):
            try:
                parsed.append(parse_link(line))
            except ValueError as exc:
                errors.append(f'Строка {index}: {exc}')
        if errors:
            messagebox.showerror('Проверьте ссылки', '\n'.join(errors)[:3000], parent=self.app)
            return
        known = {job['url'] for job in self.jobs.values()}
        added = 0
        for service, url, identifier in parsed:
            if url in known:
                continue
            iid = self.table.insert('', 'end', values=(service, url, 'В очереди'))
            self.jobs[iid] = dict(service=service, url=url, identifier=identifier, state='pending', path=None, error='')
            known.add(url)
            added += 1
        self.urls.delete('1.0', 'end')
        self.status.set(f'Добавлено: {added}. Одинаковые ссылки в очереди не дублируются.')

    def choose_folder(self):
        if not self.running:
            selected = filedialog.askdirectory(title='Папка для скачанной музыки', parent=self.app)
            if selected:
                self.folder.set(selected)

    def show_details(self, _=None):
        selected = self.table.selection()
        if selected:
            job = self.jobs[selected[0]]
            text = str(job['path'] or job['error'] or job['url'])
            self.details.set(text[:350] + ('… Двойной щелчок — подробнее.' if len(text) > 350 else ''))

    def full_details(self, _=None):
        selected = self.table.selection()
        if selected:
            job = self.jobs[selected[0]]
            messagebox.showinfo('Сведения о загрузке', str(job['path'] or job['error'] or job['url']), parent=self.app)

    def update_job(self, iid, state, status, path=None, error=''):
        job = self.jobs[iid]
        job.update(state=state, error=error)
        if path is not None:
            job['path'] = Path(path)
        self.table.item(iid, values=(job['service'], job['path'].name if job['path'] else job['url'], status))
        self.show_details()

    def retry(self):
        if self.running:
            return
        for iid in self.table.selection():
            if self.jobs[iid]['state'] in ('error', 'cancelled'):
                self.update_job(iid, 'pending', 'В очереди')
        self.start()

    def remove(self):
        if self.running:
            return
        for iid in self.table.selection():
            self.table.delete(iid)
            del self.jobs[iid]
        self.details.set('Файлы на диске не удаляются.')

    def transfer(self):
        paths = [self.jobs[iid]['path'] for iid in self.table.selection() if self.jobs[iid]['state'] == 'done']
        if paths:
            self.on_tracks(paths, True)
        else:
            self.status.set('Выделите одну или несколько готовых загрузок.')

    def set_running(self, value):
        self.running = value
        self.start_button.configure(state='disabled' if value else 'normal')
        self.cancel_button.configure(state='normal' if value else 'disabled')
        self.login_button.configure(state='disabled' if value else 'normal')
        self.logout_button.configure(state='disabled' if value else 'normal')
        self.urls.configure(state='disabled' if value else 'normal')
        if not value:
            self.progress.stop()
            self.progress.configure(mode='determinate')
            self.auth_panel.pack_forget()
            self.auth_url = None
            self.code.set('')
            self.account_status.set(self.store.summary())

    def on_code(self, code):
        # Only public device code and verification URL cross into the UI.
        self.events.put(('auth_code', code.user_code, code.verification_url, code.expires_in))

    def login(self):
        if self.running:
            return
        self.cancel.clear()
        self.set_running(True)
        self.status.set('Получаю код для входа в Яндекс…')
        self.account_status.set('Получаю код для входа…')
        def worker():
            try:
                login_yandex(self.store, self.on_code, self.cancel, force_login=True)
                self.events.put(('login_done', 'Аккаунт сохранён. Можно скачивать музыку.'))
            except DownloadCancelled:
                self.events.put(('login_done', 'Вход отменён.'))
            except Exception as exc:
                self.events.put(('login_error', str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def logout(self):
        if self.running:
            return
        try:
            self.store.clear()
            self.account_status.set(self.store.summary())
            self.status.set('Сохранённый вход удалён с этого компьютера.')
        except OSError:
            messagebox.showerror('Не удалось выйти', 'Проверьте доступ к папке настроек приложения.', parent=self.app)

    def import_account(self):
        if self.running:
            return
        path = filedialog.askopenfilename(title='Выберите .yandex_music_token.json из старого скрипта',
                                         filetypes=[('JSON', '*.json'), ('Все файлы', '*.*')], parent=self.app)
        if path:
            try:
                self.store.import_file(path)
                self.account_status.set(self.store.summary())
                self.status.set('Вход перенесён. Он будет проверен при скачивании.')
            except (OSError, ValueError):
                messagebox.showerror('Не удалось перенести вход', 'Файл повреждён, недоступен или срок входа истёк. Войдите по коду.', parent=self.app)

    def open_auth(self):
        if self.auth_url:
            webbrowser.open(self.auth_url)

    def copy_code(self):
        self.app.clipboard_clear()
        self.app.clipboard_append(self.code.get())

    def start(self):
        if self.running:
            return
        pending = [(iid, dict(job)) for iid, job in self.jobs.items() if job['state'] == 'pending']
        if not pending:
            self.status.set('В очереди нет новых ссылок. Добавьте ссылки или повторите ошибочные загрузки.')
            return
        if not self.folder.get().strip():
            self.status.set('Выберите папку загрузки.')
            return
        folder = Path(self.folder.get()).expanduser().resolve()
        self.cancel.clear()
        self.set_running(True)
        def worker():
            successful = failed = 0
            for number, (iid, job) in enumerate(pending, 1):
                if self.cancel.is_set():
                    break
                self.events.put(('started', iid, number, len(pending)))
                progress = lambda text, pct: self.events.put(('progress', iid, text, pct))
                try:
                    if job['service'] == 'YouTube':
                        path = download_audio(job['url'], folder, progress, self.cancel)
                    else:
                        path = download_yandex(job['identifier'], job['url'], folder, progress,
                                               self.cancel, self.store, self.on_code,
                                               on_authenticated=lambda: self.events.put(('auth_ready',)))
                    successful += 1
                    self.events.put(('file_done', iid, path))
                except DownloadCancelled:
                    self.events.put(('file_cancelled', iid))
                    break
                except Exception as exc:
                    failed += 1
                    self.events.put(('file_error', iid, str(exc)[:3000]))
            self.events.put(('batch_done', successful, failed, self.cancel.is_set()))
        threading.Thread(target=worker, daemon=True).start()

    def stop(self):
        if self.running:
            self.cancel.set()
            self.cancel_button.configure(state='disabled')
            self.status.set('Отменяю… Ожидание сетевого ответа может занять некоторое время.')
            self.account_status.set('Отменяю текущую операцию…')

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == 'auth_code':
                    if self.cancel.is_set():
                        continue
                    _, code, url, seconds = event
                    parsed = urlparse(url)
                    if parsed.scheme != 'https' or parsed.hostname not in ('oauth.yandex.ru', 'oauth.yandex.com', 'passport.yandex.ru', 'passport.yandex.com', 'yandex.ru', 'yandex.com'):
                        self.stop()
                        self.status.set('Яндекс вернул неподдерживаемый адрес входа. Обновите библиотеку.')
                        continue
                    self.code.set(code)
                    self.auth_url = url
                    self.auth_note.set(f'{url}\nКод действует до {seconds} секунд; приложение ожидает подтверждение не более 5 минут.')
                    self.account_status.set('Подтвердите вход по коду в браузере.')
                    self.auth_panel.pack(fill='x', pady=16)
                    self.notebook.select(self.account_frame)
                elif kind == 'auth_ready':
                    self.auth_panel.pack_forget()
                    self.code.set('')
                    self.auth_url = None
                    self.account_status.set(self.store.summary())
                    if self.notebook.select() == str(self.account_frame):
                        self.notebook.select(self.frame)
                elif kind in ('login_done', 'login_error'):
                    self.set_running(False)
                    self.status.set(event[1])
                    if kind == 'login_error':
                        messagebox.showerror('Вход в Яндекс', event[1], parent=self.app)
                elif kind == 'started':
                    self.update_job(event[1], 'running', f'Скачивание {event[2]}/{event[3]}')
                elif kind == 'progress':
                    if not self.cancel.is_set():
                        _, iid, text, pct = event
                        self.status.set(text)
                        self.progress.stop()
                        if pct is None:
                            self.progress.configure(mode='indeterminate')
                            self.progress.start(20)
                        else:
                            self.progress.configure(mode='determinate', maximum=100, value=pct)
                elif kind == 'file_done':
                    self.update_job(event[1], 'done', 'Готово', path=event[2])
                    if self.auto_add.get():
                        self.on_tracks([event[2]], False)
                elif kind == 'file_error':
                    self.update_job(event[1], 'error', 'Ошибка — выберите строку', error=event[2])
                    self.auth_panel.pack_forget()
                    self.code.set('')
                    self.auth_url = None
                elif kind == 'file_cancelled':
                    self.update_job(event[1], 'cancelled', 'Отменено')
                elif kind == 'batch_done':
                    self.set_running(False)
                    self.progress.configure(maximum=100, value=0 if event[3] else 100)
                    self.status.set(f'{"Очередь остановлена" if event[3] else "Очередь обработана"}. Готово: {event[1]}; ошибок: {event[2]}. Готовые файлы можно открыть в редакторе.')
        except queue.Empty:
            pass
        self.app.after(100, self.poll)
