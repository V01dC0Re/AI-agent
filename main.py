from __future__ import annotations

import ctypes
import threading
import time
from pathlib import Path

import pyperclip

from analyzer import Analyzer, build_error_message
from config import settings

HOTKEY = settings.HOTKEY
LOG_FILE = Path(settings.LOG_FILE)

HOTKEY_ID = 1
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
VK_SPACE = 0x20
WM_HOTKEY = 0x0312


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", ctypes.c_uint),
        ("pt_x", ctypes.c_long),
        ("pt_y", ctypes.c_long),
    ]


def append_error_to_log(message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as log_file:
        log_file.write(f"[{timestamp}] {message}\n")


def clear_log_periodically(stop_event: threading.Event) -> None:
    while not stop_event.wait(settings.LOG_CLEAR_INTERVAL_SECONDS):
        LOG_FILE.write_text("", encoding="utf-8")


def process_clipboard(analyzer: Analyzer) -> None:
    try:
        content = pyperclip.paste()
        if not content or not content.strip():
            raise ValueError("Буфер обмена пуст. Скопируйте код или текст и нажмите горячие клавиши еще раз.")

        result = analyzer.analyze(content)
        pyperclip.copy(result)
    except Exception as error:
        error_message = build_error_message(error)
        pyperclip.copy(error_message)
        append_error_to_log(error_message)


def register_hotkey() -> None:
    user32 = ctypes.windll.user32
    if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_SHIFT, VK_SPACE):
        raise RuntimeError(f"Не удалось зарегистрировать горячую клавишу {HOTKEY}. Возможно, она уже занята.")


def run_hotkey_loop(analyzer: Analyzer) -> None:
    user32 = ctypes.windll.user32
    message = MSG()
    register_hotkey()
    try:
        while True:
            result = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
            if result == 0:
                break
            if result == -1:
                raise RuntimeError("Windows message loop завершился с ошибкой.")
            if message.message == WM_HOTKEY and message.wParam == HOTKEY_ID:
                process_clipboard(analyzer)
    finally:
        user32.UnregisterHotKey(None, HOTKEY_ID)


def main() -> None:
    LOG_FILE.touch(exist_ok=True)
    stop_event = threading.Event()
    cleaner = threading.Thread(
        target=clear_log_periodically,
        args=(stop_event,),
        daemon=True,
    )
    cleaner.start()

    analyzer = Analyzer(
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        base_url=settings.LLM_BASE_URL,
        provider=settings.LLM_PROVIDER,
        timeout_sec=settings.LLM_TIMEOUT_SEC,
        max_input_chars=settings.LLM_MAX_INPUT_CHARS,
        max_output_chars=settings.LLM_MAX_OUTPUT_CHARS,
    )

    try:
        run_hotkey_loop(analyzer)
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()


if __name__ == "__main__":
    main()
