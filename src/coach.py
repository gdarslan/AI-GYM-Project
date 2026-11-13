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
PROMPT_VERSION = os.environ.get("GYM_COACH_PROMPT", "v3")
# v1: progress numbers only. v2: the code also lists the key findings, so the model does not have to work them
# out itself (v1 called an improving lift "stalled" and ignored legs that were not trained for 17 days).
# v3: v2 + next-session targets and consistency, a rule for users with little data, and no internal field names
# in answers (v2 sometimes said "according to the key_findings").
WEEKLY_SUMMARY_QUESTION = ("Write my weekly summary: one sentence on what went well, one on what I skipped or should "
                           "watch, and one clear focus for next week. Use the numbers. At most 80 words.")
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
        "enough_data": summary.get("enough_data", False),
    }


def build_context(goal: str, experience: str, summary: dict, version: str = PROMPT_VERSION,
                  next_session: list | None = None, consistency: dict | None = None) -> dict:
    """Everything the model gets to see about the user."""
    context = {"goal": goal, "experience": experience}
    if version != "v1" and summary.get("workouts"):
        context["key_findings"] = key_findings(summary)
    if version not in ("v1", "v2"):
        # the target as text ("3 × 9 @ 77.5 kg", "35 min @ level 6"); no "weight_kg" field, a name kept for
        # body weight, which is never sent
        context["next_session"] = [{"exercise": t["exercise"], "target": t["target"], "reason": t["reason"]}
                                   for t in (next_session or [])[:8]]
        context["consistency"] = consistency or {}
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


# ---------------- fallback without a language model ----------------
FALLBACK_MODEL = "template (AI coach offline)"


def fallback_answer(context: dict) -> str:
    """A plain summary of the calculated numbers, used when the language model cannot be reached.

    It does not try to answer the question itself: it says the coach is offline and lists the facts.
    """
    kf = context.get("key_findings") or {}
    lines = ["The AI coach is not available right now, so here is what the app calculated for you:"]
    if not context.get("progress", {}).get("workouts"):
        lines.append("- No workouts in the last weeks yet. Log a workout to see your progress.")
    elif not kf.get("enough_data", True):
        lines.append("- You have logged only a few workouts, so these numbers are not reliable yet.")
    neglected = kf.get("neglected_muscles") or {}
    if neglected:
        lines.append("- Not trained for 10 days or more: " + ", ".join(
            f"{m} ({d} days)" if d is not None else f"{m} (not in this period)" for m, d in neglected.items()) + ".")
    for key, label in [("stalled_lifts", "Stalled"), ("improving_lifts", "Improving"),
                       ("muscles_recovering", "Still recovering (trained less than 48 hours ago)")]:
        if kf.get(key):
            lines.append(f"- {label}: {', '.join(kf[key])}.")
    targets = context.get("next_session") or []
    if targets:
        lines.append("- Next session: " + "; ".join(f"{t['exercise']} {t['target']}" for t in targets[:5]) + ".")
    c = context.get("consistency") or {}
    if c:
        lines.append(f"- This week: {c.get('this_week', 0)} of {c.get('weekly_target', 3)} training days; "
                     f"week streak: {c.get('week_streak', 0)}.")
    lines.append("Ask again later for an answer to your question.")
    return "\n".join(lines)
