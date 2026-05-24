"""GUI для парсера one-chip.ru.

Запуск:
    python app.py

Окно содержит:
    - выбор категорий (Загрузчики / Редакторы)
    - количество потоков
    - папку для результатов
    - кнопки «Запустить» и «Остановить»
    - этап + прогресс-бар
    - живой лог событий
    - кнопку «Открыть папку с результатами» по завершении
"""
from __future__ import annotations

import os
import queue
import sys
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

import parser as parser_mod

APP_TITLE = "Парсер one-chip.ru"


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title(APP_TITLE)
        root.geometry("980x680")
        root.minsize(820, 560)

        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.msg_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.start_time: float | None = None
        self.last_out_dir: str | None = None

        self._build_ui()
        self._poll_queue()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        # верхняя панель — настройки
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="Категории:").grid(row=0, column=0, sticky="w")
        self.var_zagr = tk.BooleanVar(value=True)
        self.var_red = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Загрузчики", variable=self.var_zagr).grid(
            row=0, column=1, sticky="w", padx=(8, 8))
        ttk.Checkbutton(top, text="Редакторы", variable=self.var_red).grid(
            row=0, column=2, sticky="w", padx=(0, 16))
        ttk.Label(top, text="Потоков:").grid(row=0, column=3, sticky="e")
        self.var_threads = tk.IntVar(value=8)
        sp = ttk.Spinbox(top, from_=1, to=32, textvariable=self.var_threads, width=5)
        sp.grid(row=0, column=4, sticky="w", padx=(4, 16))

        self.var_proxy = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            top, text="Использовать системный прокси (VPN)",
            variable=self.var_proxy,
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))

        # ссылки на разделы сайта (кликабельные)
        links = ttk.Frame(self.root, padding=(10, 0))
        links.pack(fill="x")
        ttk.Label(links, text="Источники:").pack(side="left")
        for title, url in parser_mod.ROOT_CATEGORIES.values():
            lbl = tk.Label(
                links, text=f"{title}: {url}",
                fg="#1a73e8", cursor="hand2",
                font=("Segoe UI", 9, "underline"),
            )
            lbl.pack(side="left", padx=(8, 0))
            lbl.bind("<Button-1>", lambda _e, u=url: webbrowser.open(u))

        ttk.Label(top, text="Папка результатов:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.var_outdir = tk.StringVar(value=os.path.abspath("."))
        ent = ttk.Entry(top, textvariable=self.var_outdir)
        ent.grid(row=1, column=1, columnspan=3, sticky="we", pady=(8, 0), padx=(8, 8))
        ttk.Button(top, text="Обзор...", command=self._choose_dir).grid(
            row=1, column=4, sticky="we", pady=(8, 0))

        top.columnconfigure(2, weight=0)
        top.columnconfigure(3, weight=0)
        top.columnconfigure(1, weight=1)

        # кнопки управления
        btns = ttk.Frame(self.root, padding=(10, 0))
        btns.pack(fill="x")
        self.btn_start = ttk.Button(btns, text="▶  Запустить", command=self._start)
        self.btn_start.pack(side="left")
        self.btn_stop = ttk.Button(btns, text="■  Остановить", command=self._stop, state="disabled")
        self.btn_stop.pack(side="left", padx=8)
        self.btn_open = ttk.Button(btns, text="Открыть папку результатов",
                                   command=self._open_outdir, state="disabled")
        self.btn_open.pack(side="left", padx=8)
        self.btn_retry = ttk.Button(btns, text="↻ Догрузить failed.txt",
                                    command=self._retry)
        self.btn_retry.pack(side="left", padx=8)
        self.btn_clear = ttk.Button(btns, text="Очистить лог", command=self._clear_log)
        self.btn_clear.pack(side="right")

        # прогресс
        prog = ttk.Frame(self.root, padding=10)
        prog.pack(fill="x")
        self.var_phase = tk.StringVar(value="Готов к работе")
        ttk.Label(prog, textvariable=self.var_phase, font=("Segoe UI", 10, "bold")).pack(anchor="w")

        bar_row = ttk.Frame(prog)
        bar_row.pack(fill="x", pady=(4, 0))
        self.progress = ttk.Progressbar(bar_row, mode="determinate", maximum=100, value=0)
        self.progress.pack(side="left", fill="x", expand=True)
        self.var_progress_label = tk.StringVar(value="0 / 0")
        ttk.Label(bar_row, textvariable=self.var_progress_label, width=18, anchor="e").pack(
            side="right", padx=(8, 0))

        # лог
        log_frame = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        log_frame.pack(fill="both", expand=True)
        ttk.Label(log_frame, text="Лог:").pack(anchor="w")
        text_wrap = ttk.Frame(log_frame)
        text_wrap.pack(fill="both", expand=True)
        self.log_text = tk.Text(text_wrap, height=18, wrap="none", font=("Consolas", 9))
        self.log_text.pack(side="left", fill="both", expand=True)
        self.log_text.configure(state="disabled")
        scroll_y = ttk.Scrollbar(text_wrap, orient="vertical", command=self.log_text.yview)
        scroll_y.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scroll_y.set)

        # статус-бар
        self.var_status = tk.StringVar(value="Ожидание...")
        status = ttk.Label(self.root, textvariable=self.var_status, anchor="w",
                           relief="sunken", padding=(8, 2))
        status.pack(fill="x", side="bottom")

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Команды
    # ------------------------------------------------------------------
    def _choose_dir(self) -> None:
        d = filedialog.askdirectory(initialdir=self.var_outdir.get(), title="Папка для результатов")
        if d:
            self.var_outdir.set(d)

    def _open_outdir(self) -> None:
        path = self.last_out_dir or self.var_outdir.get()
        if path and os.path.isdir(path):
            webbrowser.open(path)

    def _retry(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        # ищем failed.txt: сначала в последней папке прогона, потом в основной
        candidates: list[str] = []
        if self.last_out_dir:
            candidates.append(self.last_out_dir)
        base = self.var_outdir.get().strip() or "."
        candidates.append(base)
        out_dir = ""
        failed_path = ""
        for d in candidates:
            p = os.path.join(d, "failed.txt")
            if os.path.isfile(p):
                out_dir = d
                failed_path = p
                break
        if not failed_path:
            # дадим пользователю выбрать вручную
            chosen = filedialog.askdirectory(
                initialdir=base,
                title="Папка с failed.txt",
            )
            if not chosen:
                return
            failed_path = os.path.join(chosen, "failed.txt")
            if not os.path.isfile(failed_path):
                messagebox.showwarning(
                    APP_TITLE, f"Файл не найден:\n{failed_path}",
                )
                return
            out_dir = chosen
        self.last_out_dir = out_dir
        threads = max(1, int(self.var_threads.get() or 1))
        use_proxy = bool(self.var_proxy.get())
        self.stop_event = threading.Event()
        self.start_time = time.time()
        self._set_running(True)
        self._set_progress(0, 0)
        self.var_phase.set("Догрузка...")
        self._log_line(
            f"=== Догрузка из failed.txt | потоков: {threads}"
            f" | системный прокси: {'да' if use_proxy else 'нет'} ==="
        )
        self._log_line(f"Папка: {out_dir}")
        self.worker = threading.Thread(
            target=self._run_retry_worker,
            args=(threads, out_dir, failed_path, use_proxy),
            daemon=True,
        )
        self.worker.start()

    def _clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _start(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        targets: list[str] = []
        if self.var_zagr.get():
            targets.append("zagruzchiki")
        if self.var_red.get():
            targets.append("redaktory")
        if not targets:
            messagebox.showwarning(APP_TITLE, "Выберите хотя бы одну категорию.")
            return

        base_dir = self.var_outdir.get().strip() or "."
        # каждый запуск — в свою подпапку с датой и временем
        ts = time.strftime("%Y-%m-%d_%H-%M-%S")
        out_dir = os.path.join(base_dir, f"parse_{ts}")
        try:
            os.makedirs(out_dir, exist_ok=True)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror(APP_TITLE, f"Не удалось создать папку:\n{e}")
            return
        self.last_out_dir = out_dir

        threads = max(1, int(self.var_threads.get() or 1))
        use_proxy = bool(self.var_proxy.get())
        self.stop_event = threading.Event()
        self.start_time = time.time()
        self._set_running(True)
        self._set_progress(0, 0)
        self.var_phase.set("Запуск...")
        self._log_line(
            f"=== Запуск парсинга: {', '.join(targets)} | потоков: {threads}"
            f" | системный прокси: {'да' if use_proxy else 'нет'} ==="
        )
        self._log_line(f"Папка результатов: {out_dir}")

        self.worker = threading.Thread(
            target=self._run_worker,
            args=(threads, out_dir, targets, use_proxy),
            daemon=True,
        )
        self.worker.start()

    def _stop(self) -> None:
        if self.worker and self.worker.is_alive():
            self.stop_event.set()
            self.var_phase.set("Останавливается...")
            self._log_line("--- Получен сигнал остановки ---")
            self.btn_stop.configure(state="disabled")

    def _on_close(self) -> None:
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno(APP_TITLE, "Парсинг ещё идёт. Закрыть приложение?"):
                return
            self.stop_event.set()
        self.root.destroy()

    # ------------------------------------------------------------------
    # Поток парсинга
    # ------------------------------------------------------------------
    def _run_worker(self, threads: int, out_dir: str, targets: list[str], use_proxy: bool) -> None:
        def log(s: str) -> None:
            self.msg_queue.put(("log", s))

        def on_progress(done: int, total: int) -> None:
            self.msg_queue.put(("progress", (done, total)))

        def on_phase(phase: str) -> None:
            self.msg_queue.put(("phase", phase))

        try:
            result = parser_mod.run(
                threads=threads,
                out_dir=out_dir,
                targets=targets,
                use_proxy=use_proxy,
                log=log,
                on_progress=on_progress,
                on_phase=on_phase,
                stop_event=self.stop_event,
            )
            self.msg_queue.put(("done", result))
        except parser_mod.StoppedError:
            self.msg_queue.put(("stopped", None))
        except Exception as e:  # noqa: BLE001
            self.msg_queue.put(("error", str(e)))

    def _run_retry_worker(self, threads: int, out_dir: str, failed_path: str, use_proxy: bool) -> None:
        def log(s: str) -> None:
            self.msg_queue.put(("log", s))

        def on_progress(done: int, total: int) -> None:
            self.msg_queue.put(("progress", (done, total)))

        def on_phase(phase: str) -> None:
            self.msg_queue.put(("phase", phase))

        try:
            result = parser_mod.retry_failed(
                failed_path=failed_path,
                out_dir=out_dir,
                threads=threads,
                use_proxy=use_proxy,
                log=log,
                on_progress=on_progress,
                on_phase=on_phase,
                stop_event=self.stop_event,
            )
            self.msg_queue.put(("done", result))
        except parser_mod.StoppedError:
            self.msg_queue.put(("stopped", None))
        except Exception as e:  # noqa: BLE001
            self.msg_queue.put(("error", str(e)))

    # ------------------------------------------------------------------
    # Очередь сообщений из потока в UI
    # ------------------------------------------------------------------
    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == "log":
                    self._log_line(str(payload))
                elif kind == "phase":
                    self.var_phase.set(str(payload))
                elif kind == "progress":
                    done, total = payload  # type: ignore[misc]
                    self._set_progress(done, total)
                elif kind == "done":
                    self._set_progress_done()
                    self._set_running(False)
                    self.btn_open.configure(state="normal")
                    elapsed = self._elapsed()
                    self.var_phase.set(f"Готово ({elapsed})")
                    self.var_status.set(f"Спарсено {len(payload.products)} товаров за {elapsed}")
                    messagebox.showinfo(
                        APP_TITLE,
                        f"Готово. Спарсено {len(payload.products)} товаров.\n\n"
                        f"JSON: {payload.json_path}\nCSV : {payload.csv_path}\n"
                        f"XLSX: {payload.xlsx_path}",
                    )
                elif kind == "stopped":
                    self._set_running(False)
                    self.var_phase.set("Остановлено")
                    self.var_status.set("Парсинг остановлен пользователем")
                    self._log_line("=== Остановлено ===")
                elif kind == "error":
                    self._set_running(False)
                    self.var_phase.set("Ошибка")
                    self.var_status.set(f"Ошибка: {payload}")
                    self._log_line(f"!!! Ошибка: {payload}")
                    messagebox.showerror(APP_TITLE, f"Ошибка:\n{payload}")
        except queue.Empty:
            pass
        # обновляем статус с таймером, если идёт работа
        if self.worker and self.worker.is_alive():
            self.var_status.set(f"Работает... {self._elapsed()}")
        self.root.after(120, self._poll_queue)

    # ------------------------------------------------------------------
    # Утилиты
    # ------------------------------------------------------------------
    def _elapsed(self) -> str:
        if not self.start_time:
            return "00:00"
        s = int(time.time() - self.start_time)
        return f"{s // 60:02d}:{s % 60:02d}"

    def _set_running(self, running: bool) -> None:
        self.btn_start.configure(state="disabled" if running else "normal")
        self.btn_stop.configure(state="normal" if running else "disabled")

    def _set_progress(self, done: int, total: int) -> None:
        if total > 0:
            self.progress.configure(maximum=total, value=done)
            self.var_progress_label.set(f"{done} / {total}")
        else:
            self.progress.configure(maximum=100, value=0)
            self.var_progress_label.set("0 / 0")

    def _set_progress_done(self) -> None:
        m = self.progress.cget("maximum")
        try:
            mv = int(float(m))
        except Exception:  # noqa: BLE001
            mv = 100
        self.progress.configure(value=mv)

    def _log_line(self, s: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", s.rstrip() + "\n")
        # ограничиваем буфер 8000 строк
        line_count = int(self.log_text.index("end-1c").split(".")[0])
        if line_count > 8000:
            self.log_text.delete("1.0", f"{line_count - 6000}.0")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")


def main() -> None:
    root = tk.Tk()
    try:
        # на Windows немного приятнее со стилем 'vista'
        style = ttk.Style()
        if sys.platform == "win32" and "vista" in style.theme_names():
            style.theme_use("vista")
    except Exception:  # noqa: BLE001
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
