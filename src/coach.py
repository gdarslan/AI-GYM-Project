"""The AI coach: the code calculates the user's progress, a language model explains it.

Only the goal, experience level and computed progress numbers are sent to the model - never the username,
user id, age, height, weight or gender (data minimisation). The model runs locally through Ollama by default.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import httpx

from src.progress import neglected_muscles

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "prompts"
PROMPT_VERSION = os.environ.get("GYM_COACH_PROMPT", "v2")
# v1: progress numbers only. v2: the code also lists the key findings, so the model does not have to work them
# out itself (v1 called an improving lift "stalled" and ignored legs that were not trained for 17 days).
LOG_FILE = ROOT / "logs" / "coach_log.jsonl"
MAX_HISTORY_TURNS = 6          # earlier messages sent along, so follow-up questions make sense


class CoachUnavailable(Exception):
    """The language model could not be reached."""


class LLMClient(Protocol):
    model: str

    def chat(self, messages: list[dict]) -> str: ...


class OllamaClient:
    def __init__(self, model: str | None = None, url: str | None = None, timeout: float = 120):
        self.model = model or os.environ.get("GYM_LLM_MODEL", "llama3.2:3b")
        # 127.0.0.1, not "localhost": on Windows "localhost" tries IPv6 first and each request then waits ~2 s
        self.url = (url or os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")).rstrip("/")
        self.timeout = timeout
        self._http = httpx.Client(timeout=timeout)       # one connection that stays open

    def chat(self, messages: list[dict]) -> str:
        try:
            r = self._http.post(f"{self.url}/api/chat", json={
                "model": self.model, "messages": messages, "stream": False, "options": {"temperature": 0.2},
                "keep_alive": "30m"})     # keep the model loaded; loading it again takes ~50 s
        except httpx.HTTPError as e:
            raise CoachUnavailable(f"Ollama is not reachable at {self.url}. Is it running? ({e})") from e
        if r.status_code == 404:
            raise CoachUnavailable(f"Model '{self.model}' is not installed. Run: ollama pull {self.model}")
        r.raise_for_status()
        return r.json()["message"]["content"].strip()


def load_prompt(version: str = PROMPT_VERSION) -> str:
    return (PROMPTS / f"coach_{version}.txt").read_text(encoding="utf-8")


def key_findings(summary: dict) -> dict:
    """The conclusions the code can draw itself, so the model only has to explain them."""
    days = summary.get("days_since_last_trained", {})
    trends = summary.get("strength_trends", {})
    lifts = lambda trend: [ex for ex, t in trends.items() if t["trend"] == trend]
    return {
        "neglected_muscles": {m: days.get(m) for m in neglected_muscles(summary)},
        "improving_lifts": lifts("improving"),
        "stalled_lifts": lifts("stalled"),
        "lifts_not_done_recently": lifts("not done recently"),
        "muscles_recovering": [m for m, s in summary.get("recovery_guideline", {}).items() if s == "recovering"],
    }


def build_context(goal: str, experience: str, summary: dict, version: str = PROMPT_VERSION) -> dict:
    """Everything the model gets to see about the user."""
    context = {"goal": goal, "experience": experience}
    if version != "v1" and summary.get("workouts"):
        context["key_findings"] = key_findings(summary)
    return context | {"progress": summary}


def build_messages(question: str, context: dict, history: list[dict] | None = None,
                   version: str = PROMPT_VERSION) -> list[dict]:
    system = load_prompt(version) + "\n\nTraining data:\n" + json.dumps(context, indent=1)
    turns = [m for m in (history or []) if m.get("role") in ("user", "assistant")][-2 * MAX_HISTORY_TURNS:]
    return [{"role": "system", "content": system}, *turns, {"role": "user", "content": question}]


def ask(question: str, context: dict, client: LLMClient, history: list[dict] | None = None,
        version: str = PROMPT_VERSION, log_file: Path | None = LOG_FILE) -> str:
    answer = client.chat(build_messages(question, context, history, version))
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({"time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                "model": client.model, "prompt_version": version, "question": question,
                                "answer": answer, "context": context}) + "\n")
    return answer
