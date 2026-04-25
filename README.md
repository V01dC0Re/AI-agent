# AI Clipboard Agent

Python-агент на `langgraph`, который через нативный Windows hotkey API слушает глобальную горячую клавишу, читает текст из буфера обмена и отправляет его в `Gemini Flash`.

Сценарии:
- Если в буфере код, агент делает подробное объяснение.
- Если в буфере обычный текст, агент делает короткую выжимку с выделением сути.
- Результат всегда возвращается обратно в буфер обмена.
- Если происходит ошибка, текст ошибки копируется в буфер обмена и записывается в `error_log.txt`.

## Как используется LangGraph

В [analyzer.py](/c:/Users/John/AI-agent/analyzer.py:1) построен `StateGraph` с тремя узлами:
- `classify_content`
- `explain_code`
- `summarize_text`

После классификации граф маршрутизирует содержимое либо в ветку объяснения кода, либо в ветку краткой выжимки текста.

## Как это сделано

- ключ берется из `.env` или переменных окружения
- используются поля `LLM_API_KEY`, `LLM_PROVIDER`, `LLM_MODEL`, `LLM_BASE_URL`
- запрос к Gemini идет через `proxyapi` на `.../models/{model}:generateContent`

## Горячая клавиша

По умолчанию используется `Ctrl+Shift+Space`.


## Настройка ключа

Создайте `.env` по примеру [`.env.example`] и заполните:

```env
LLM_API_KEY=ваш_ключ
LLM_PROVIDER=proxyapi_gemini
LLM_MODEL=gemini-2.0-flash
LLM_BASE_URL=https://api.proxyapi.ru/google/v1beta
```

## Установка

```powershell
pip install -r requirements.txt
```

## Запуск

```powershell
python main.py
```

После запуска:
1. Скопируйте код или обычный текст.
2. Нажмите `Ctrl+Shift+Space`.
3. Готовый результат появится в буфере обмена.

## Лог ошибок

- Файл: `error_log.txt`
- Туда пишутся только ошибки
- Файл автоматически очищается раз в `3600` секунд

## Настройка

В [config.py](/c:/Users/John/AI-agent/config.py:1) и `.env` можно изменить:
- `LLM_MODEL`
- `LLM_BASE_URL`
- `HOTKEY`
- `LOG_CLEAR_INTERVAL_SECONDS`
