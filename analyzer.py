from __future__ import annotations

import re
import traceback
from dataclasses import dataclass
from typing import Literal, TypedDict

import httpx
from langgraph.graph import END, START, StateGraph


CODE_KEYWORDS = {
    "def",
    "class",
    "import",
    "from",
    "return",
    "try",
    "except",
    "while",
    "for",
    "if",
    "else",
    "elif",
    "function",
    "const",
    "let",
    "var",
    "public",
    "private",
    "static",
    "async",
    "await",
    "package",
    "using",
    "namespace",
}

CODE_SYMBOLS = ("{", "}", "()", "[]", "=>", "::", "#include", "</", "/>", "==", "!=", "&&", "||", ";")

CODE_SYSTEM_PROMPT = """Ты объясняешь код для человека, который хочет действительно понять его.
Отвечай на русском языке.
Дай структурированное, подробное объяснение:
1. Что делает код целиком.
2. Как устроены ключевые части.
3. Как идет поток выполнения.
4. Что важно заметить: зависимости, ограничения, возможные ошибки, неочевидные детали.
Если код неполный, прямо скажи об этом и объясни только то, что можно уверенно вывести."""

TEXT_SYSTEM_PROMPT = """Ты делаешь короткую и полезную выжимку обычного текста.
Отвечай на русском языке.
Формат:
Главная суть: одна короткая фраза.
Краткая выжимка: 2-4 коротких пункта без воды.
Сохраняй только смысл, не пересказывай текст целиком."""


class AnalyzerState(TypedDict, total=False):
    content: str
    content_type: Literal["code", "text"]
    result: str


def build_error_message(error: Exception) -> str:
    error_name = type(error).__name__
    details = str(error).strip() or "без дополнительного описания"
    trace_tail = traceback.format_exc(limit=2).strip()
    if trace_tail == "NoneType: None":
        trace_tail = "traceback недоступен"
    return f"[Clipboard AI Error] {error_name}: {details}\n{trace_tail}"


def looks_like_code(content: str) -> bool:
    stripped = content.strip()
    if not stripped:
        return False

    lines = [line.rstrip() for line in stripped.splitlines() if line.strip()]
    lowered = stripped.lower()
    keyword_hits = sum(1 for keyword in CODE_KEYWORDS if re.search(rf"\b{re.escape(keyword)}\b", lowered))
    symbol_hits = sum(stripped.count(symbol) for symbol in CODE_SYMBOLS)
    indented_lines = sum(1 for line in lines if line.startswith((" ", "\t")))
    ending_hits = sum(1 for line in lines if line.endswith(("{", "}", ";", ":", ")")))
    assignment_hits = len(re.findall(r"\b\w+\s*=\s*[^=]", stripped))

    score = keyword_hits * 2 + symbol_hits + indented_lines + ending_hits + assignment_hits

    if "```" in stripped:
        return True
    if len(lines) >= 2 and score >= 4:
        return True
    return score >= 6


@dataclass
class Analyzer:
    api_key: str
    model: str
    base_url: str
    provider: str = "proxyapi_gemini"
    timeout_sec: int = 60
    max_input_chars: int = 12000
    max_output_chars: int = 5000

    def __post_init__(self) -> None:
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(AnalyzerState)
        graph.add_node("classify_content", self._classify_content_node)
        graph.add_node("explain_code", self._explain_code_node)
        graph.add_node("summarize_text", self._summarize_text_node)
        graph.add_edge(START, "classify_content")
        graph.add_conditional_edges(
            "classify_content",
            self._route_after_classification,
            {"code": "explain_code", "text": "summarize_text"},
        )
        graph.add_edge("explain_code", END)
        graph.add_edge("summarize_text", END)
        return graph.compile()

    def _classify_content_node(self, state: AnalyzerState) -> AnalyzerState:
        return {"content_type": "code" if looks_like_code(state["content"]) else "text"}

    def _route_after_classification(self, state: AnalyzerState) -> str:
        return state["content_type"]

    def _explain_code_node(self, state: AnalyzerState) -> AnalyzerState:
        return {
            "result": self._generate_via_proxyapi_gemini(
                content=state["content"],
                system_prompt=CODE_SYSTEM_PROMPT,
                user_prefix="Ниже код для объяснения:\n\n",
            )
        }

    def _summarize_text_node(self, state: AnalyzerState) -> AnalyzerState:
        return {
            "result": self._generate_via_proxyapi_gemini(
                content=state["content"],
                system_prompt=TEXT_SYSTEM_PROMPT,
                user_prefix="Ниже текст для краткой выжимки:\n\n",
            )
        }

    def _sanitize_input(self, text: str) -> str:
        safe = (text or "").replace("\x00", "").strip()
        if len(safe) > self.max_input_chars:
            safe = safe[: self.max_input_chars]
        return safe

    def _sanitize_output(self, text: str) -> str:
        safe = (text or "").replace("\x00", "").strip()
        if not safe:
            raise RuntimeError("Gemini вернул пустой ответ.")
        if len(safe) > self.max_output_chars:
            safe = safe[: self.max_output_chars]
        return safe

    def _generate_via_proxyapi_gemini(self, content: str, system_prompt: str, user_prefix: str) -> str:
        if self.provider != "proxyapi_gemini":
            raise ValueError(f"Неподдерживаемый LLM_PROVIDER: {self.provider}")
        if not self.api_key.strip():
            raise ValueError("LLM_API_KEY is empty. Please set it in .env or environment.")

        safe_content = self._sanitize_input(content)
        safe_system_prompt = self._sanitize_input(system_prompt)
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{user_prefix}{safe_content}"}],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1024,
            },
        }
        if safe_system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": safe_system_prompt}]}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url.rstrip('/')}/models/{self.model}:generateContent"

        response = httpx.post(url, headers=headers, json=payload, timeout=self.timeout_sec)
        response.raise_for_status()
        data = response.json()

        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError("LLM response does not contain candidates")

        parts = candidates[0].get("content", {}).get("parts", [])
        chunks = [part["text"] for part in parts if isinstance(part, dict) and isinstance(part.get("text"), str)]
        return self._sanitize_output("\n".join(chunks))

    def analyze(self, content: str) -> str:
        final_state = self.graph.invoke({"content": content})
        result = final_state.get("result", "").strip()
        if not result:
            raise RuntimeError("LangGraph завершился без результата.")
        return result
