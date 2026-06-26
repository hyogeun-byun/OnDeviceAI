"""LLM benchmark: speed + quality comparison across Ollama-served models.

Mirrors the structure of camera-worker/scripts/benchmark_movenet_int8.py.

Measures per model:
  - Latency (total wall-clock, TTFT via streaming)
  - Throughput (tokens / second)
  - Quality: Korean-ratio, length compliance, format compliance

Usage examples
--------------
# Quick comparison with default models against the Ollama server:
  python scratch/benchmark_llm.py

# Specify models and Ollama base URL:
  python scratch/benchmark_llm.py \\
      --models smollm2:360m qwen2.5:0.5b qwen2.5:1.5b exaone3.5:2.4b \\
      --base-url http://localhost:11434 \\
      --runs 5

# Save results to JSON:
  python scratch/benchmark_llm.py --output results/llm_bench.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Model size reference table (GGUF Q4_K_M, megabytes)
# ---------------------------------------------------------------------------
MODEL_SIZE_MB: dict[str, float] = {
    # sub-1B
    "smollm2:360m":    230,
    "qwen2.5:0.5b":    397,
    # ~1B class
    "gemma:2b":       1500,
    "llama3.2:1b":    1300,
    "qwen2.5:1.5b":    986,
    # ~2-3B class  (comparable to exaone3.5:2.4b ~1.6 GB)
    "llama3.2:3b":    2020,
    "qwen2.5:3b":     1900,
    "phi3.5:mini":    2400,
    "exaone3.5:2.4b": 1623,
    # 3B+
    "phi4-mini:3.8b": 2500,
}


# ---------------------------------------------------------------------------
# Task prompts  (same prompt structures that game_narrator.py sends to the LLM)
# ---------------------------------------------------------------------------
TASKS: list[dict[str, object]] = [
    {
        "name": "mc_comment_high",
        "description": "MC 1줄 멘트 – 고득점 라운드",
        "max_tokens": 64,
        "temperature": 0.9,
        "messages": [
            {
                "role": "system",
                "content": (
                    "너는 활기찬 한국 예능 프로그램의 진행자(MC)야. "
                    "방금 끝난 '몸으로 텔레파시 맞추기' 라운드 결과를 보고 "
                    "재치 있는 한 줄 멘트를 한국어로 말한다. "
                    "반드시 한 문장, 30자 이내로 짧게. 이모지·특수기호·설명 없이 멘트만."
                ),
            },
            {
                "role": "user",
                "content": (
                    "제시어: 손흥민\n"
                    "참가자 수: 3, 동작을 취한 사람: 3\n"
                    "텔레파시 점수(0~100): 92\n"
                    "한 문장 멘트만 출력해."
                ),
            },
        ],
        "quality_checks": {
            "max_chars": 40,          # 30자 + 여유
            "single_line": True,
            "korean_ratio_min": 0.5,
        },
    },
    {
        "name": "mc_comment_low",
        "description": "MC 1줄 멘트 – 저득점 라운드",
        "max_tokens": 64,
        "temperature": 0.9,
        "messages": [
            {
                "role": "system",
                "content": (
                    "너는 활기찬 한국 예능 프로그램의 진행자(MC)야. "
                    "방금 끝난 '몸으로 텔레파시 맞추기' 라운드 결과를 보고 "
                    "재치 있는 한 줄 멘트를 한국어로 말한다. "
                    "반드시 한 문장, 30자 이내로 짧게. 이모지·특수기호·설명 없이 멘트만."
                ),
            },
            {
                "role": "user",
                "content": (
                    "제시어: 무에타이\n"
                    "참가자 수: 3, 동작을 취한 사람: 2\n"
                    "텔레파시 점수(0~100): 18\n"
                    "한 문장 멘트만 출력해."
                ),
            },
        ],
        "quality_checks": {
            "max_chars": 40,
            "single_line": True,
            "korean_ratio_min": 0.5,
        },
    },
    {
        "name": "final_report",
        "description": "최종 텔레파시 궁합 분석 (2~3문장)",
        "max_tokens": 150,
        "temperature": 0.8,
        "messages": [
            {
                "role": "system",
                "content": (
                    "너는 재치 있는 '텔레파시 궁합 분석가'야. "
                    "라운드별 점수를 보고 참가자들의 호흡을 재미있게 분석하는 "
                    "짧은 한국어 멘트를 2~3문장으로 만들어줘. "
                    "이모지·특수기호 없이 텍스트만."
                ),
            },
            {
                "role": "user",
                "content": (
                    "1라운드 '손흥민': 87점\n"
                    "2라운드 '무에타이': 23점\n"
                    "3라운드 '아이언맨': 68점\n"
                    "총점: 59점\n"
                    "2~3문장 분석 멘트만 출력해."
                ),
            },
        ],
        "quality_checks": {
            "max_chars": 200,
            "single_line": False,
            "korean_ratio_min": 0.5,
        },
    },
    {
        "name": "today_weather",
        "description": "오늘 날씨 질문 – 자유응답",
        "max_tokens": 150,
        "temperature": 0.7,
        "messages": [
            {
                "role": "system",
                "content": (
                    "너는 친절한 한국어 AI 어시스턴트야. "
                    "사용자 질문에 자연스러운 한국어로 답해줘."
                ),
            },
            {
                "role": "user",
                "content": "오늘 날씨가 어때?",
            },
        ],
        "quality_checks": {
            "max_chars": 500,
            "single_line": False,
            "korean_ratio_min": 0.3,
        },
    },
]


# ---------------------------------------------------------------------------
# Quality scoring helpers
# ---------------------------------------------------------------------------
_EMOJI_RE = re.compile(
    r"[\U0001F000-\U0001FAFF\U00002600-\U000027BF"
    r"\U0001F1E6-\U0001F1FF\U00002190-\U000021FF"
    r"\U00002B00-\U00002BFF\uFE0F]"
)
_KOREAN_RE = re.compile(r"[\uAC00-\uD7A3\u1100-\u11FF\u3130-\u318F]")


def _korean_ratio(text: str) -> float:
    if not text:
        return 0.0
    letters = re.sub(r"\s", "", text)
    if not letters:
        return 0.0
    return len(_KOREAN_RE.findall(letters)) / len(letters)


def _has_emoji(text: str) -> bool:
    return bool(_EMOJI_RE.search(text))


def score_quality(text: str, checks: dict[str, object]) -> dict[str, object]:
    """Return per-check pass/fail and a 0-100 aggregate quality score."""
    max_chars: int = int(checks.get("max_chars", 9999))
    single_line: bool = bool(checks.get("single_line", False))
    korean_ratio_min: float = float(checks.get("korean_ratio_min", 0.0))

    char_ok = len(text) <= max_chars
    line_ok = (len(text.strip().splitlines()) == 1) if single_line else True
    emoji_ok = not _has_emoji(text)
    kr_ratio = _korean_ratio(text)
    kr_ok = kr_ratio >= korean_ratio_min
    nonempty = bool(text.strip())

    checks_passed = sum([nonempty, char_ok, line_ok, emoji_ok, kr_ok])
    total_checks = 5
    score = round(checks_passed / total_checks * 100)

    return {
        "score": score,
        "nonempty": nonempty,
        "char_count": len(text),
        "char_limit_ok": char_ok,
        "single_line_ok": line_ok,
        "no_emoji_ok": emoji_ok,
        "korean_ratio": round(kr_ratio, 3),
        "korean_ratio_ok": kr_ok,
    }


# ---------------------------------------------------------------------------
# HTTP helpers (streaming + non-streaming)
# ---------------------------------------------------------------------------

def _build_request(base_url: str, payload: dict[str, object]) -> urllib.request.Request:
    data = json.dumps(payload).encode("utf-8")
    return urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        data=data,
        headers={"Content-Type": "application/json"},
    )


def call_chat_streaming(
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float,
    timeout: float,
) -> dict[str, object]:
    """
    Call the chat endpoint with stream=True.
    Returns:
      text, ttft_ms (time-to-first-token), total_ms, prompt_tokens, completion_tokens
    """
    payload: dict[str, object] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }
    req = _build_request(base_url, payload)
    started = time.perf_counter()
    ttft_ms: float | None = None
    chunks: list[str] = []
    prompt_tokens = 0
    completion_tokens = 0

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8").strip()
            if not line.startswith("data:"):
                continue
            payload_str = line[len("data:"):].strip()
            if payload_str == "[DONE]":
                break
            try:
                chunk = json.loads(payload_str)
            except json.JSONDecodeError:
                continue

            # Token usage (last chunk from Ollama may carry usage)
            usage = chunk.get("usage") or {}
            if usage.get("prompt_tokens"):
                prompt_tokens = int(usage["prompt_tokens"])
            if usage.get("completion_tokens"):
                completion_tokens = int(usage["completion_tokens"])

            delta = chunk.get("choices", [{}])[0].get("delta", {})
            content = delta.get("content") or ""
            if content:
                if ttft_ms is None:
                    ttft_ms = (time.perf_counter() - started) * 1000
                chunks.append(content)

    total_ms = (time.perf_counter() - started) * 1000
    text = "".join(chunks)

    # Fallback token count: rough word/char split if server didn't report
    if completion_tokens == 0:
        completion_tokens = max(1, len(text.split()))

    return {
        "text": text,
        "ttft_ms": round(ttft_ms or total_ms, 1),
        "total_ms": round(total_ms, 1),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "tokens_per_sec": round(completion_tokens / (total_ms / 1000), 1) if total_ms > 0 else 0.0,
    }


# ---------------------------------------------------------------------------
# Single-model, single-task benchmark
# ---------------------------------------------------------------------------

def run_task_benchmark(
    base_url: str,
    model: str,
    task: dict[str, object],
    warmup_runs: int,
    runs: int,
    timeout: float,
) -> dict[str, object]:
    messages: list[dict[str, str]] = task["messages"]  # type: ignore[assignment]
    max_tokens: int = int(task["max_tokens"])  # type: ignore[arg-type]
    temperature: float = float(task["temperature"])  # type: ignore[arg-type]
    checks: dict[str, object] = task["quality_checks"]  # type: ignore[assignment]

    # Warmup
    for i in range(warmup_runs):
        try:
            call_chat_streaming(base_url, model, messages, max_tokens, temperature, timeout)
        except Exception as exc:
            print(f"    [warmup {i+1}/{warmup_runs}] error: {exc}", file=sys.stderr)

    # Timed runs
    results: list[dict[str, object]] = []
    last_text = ""
    errors = 0
    for i in range(runs):
        try:
            r = call_chat_streaming(base_url, model, messages, max_tokens, temperature, timeout)
            results.append(r)
            last_text = str(r["text"])
            response_preview = last_text.replace("\n", " / ")
            print(
                f"    run {i+1}/{runs}  total={r['total_ms']:.0f}ms  "
                f"ttft={r['ttft_ms']:.0f}ms  "
                f"{r['tokens_per_sec']:.1f}tok/s",
                file=sys.stderr,
            )
            print(f"      └─ 응답: {response_preview}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"    run {i+1}/{runs} ERROR: {exc}", file=sys.stderr)

    if not results:
        return {
            "task": task["name"],
            "error": "all runs failed",
            "errors": errors,
            "last_response": "",
        }

    total_ms_vals = [float(r["total_ms"]) for r in results]
    ttft_ms_vals = [float(r["ttft_ms"]) for r in results]
    tps_vals = [float(r["tokens_per_sec"]) for r in results]

    def _avg(lst: list[float]) -> float:
        return round(sum(lst) / len(lst), 1)

    def _p50(lst: list[float]) -> float:
        s = sorted(lst)
        mid = len(s) // 2
        return round(s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2, 1)

    quality = score_quality(last_text, checks)

    return {
        "task": task["name"],
        "description": task["description"],
        "runs_ok": len(results),
        "errors": errors,
        # Speed
        "avg_total_ms": _avg(total_ms_vals),
        "min_total_ms": round(min(total_ms_vals), 1),
        "max_total_ms": round(max(total_ms_vals), 1),
        "p50_total_ms": _p50(total_ms_vals),
        "avg_ttft_ms": _avg(ttft_ms_vals),
        "avg_tokens_per_sec": _avg(tps_vals),
        # Quality
        "last_response": last_text,
        "quality": quality,
    }


# ---------------------------------------------------------------------------
# Per-model benchmark
# ---------------------------------------------------------------------------

def check_model_available(base_url: str, model: str, timeout: float) -> bool:
    """Try a minimal 1-token call to verify the model is loaded / available."""
    try:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "안녕"}],
            "max_tokens": 1,
            "stream": False,
        }
        req = _build_request(base_url, payload)
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except urllib.error.HTTPError as exc:
        print(f"  HTTP {exc.code} when probing {model}: {exc.reason}", file=sys.stderr)
        return False
    except Exception as exc:
        print(f"  Cannot reach {model}: {exc}", file=sys.stderr)
        return False


def benchmark_model(
    base_url: str,
    model: str,
    tasks: list[dict[str, object]],
    warmup_runs: int,
    runs: int,
    timeout: float,
) -> dict[str, object]:
    size_mb = MODEL_SIZE_MB.get(model)

    print(f"\n{'=' * 60}", file=sys.stderr)
    print(f"Model : {model}", file=sys.stderr)
    if size_mb:
        print(f"Size  : ~{size_mb:.0f} MB (Q4_K_M est.)", file=sys.stderr)
    print(f"{'=' * 60}", file=sys.stderr)

    if not check_model_available(base_url, model, timeout=30.0):
        return {
            "model": model,
            "size_mb_q4": size_mb,
            "available": False,
            "tasks": [],
        }

    task_results = []
    for task in tasks:
        print(f"\n  Task: {task['description']}", file=sys.stderr)
        result = run_task_benchmark(
            base_url=base_url,
            model=model,
            task=task,
            warmup_runs=warmup_runs,
            runs=runs,
            timeout=timeout,
        )
        task_results.append(result)

    return {
        "model": model,
        "size_mb_q4": size_mb,
        "available": True,
        "tasks": task_results,
    }


# ---------------------------------------------------------------------------
# Log formatter + writer
# ---------------------------------------------------------------------------

def _avg_across_tasks(model_result: dict[str, object], key: str) -> float:
    vals = [
        float(t[key])  # type: ignore[arg-type]
        for t in model_result["tasks"]  # type: ignore[index]
        if key in t and t.get("runs_ok", 0)  # type: ignore[operator]
    ]
    return round(sum(vals) / len(vals), 1) if vals else 0.0


def format_log(
    all_results: list[dict[str, object]],
    server: str,
    warmup_runs: int,
    runs: int,
    log_path: str,
) -> str:
    """Return a human-readable benchmark report string (written to .log file)."""
    W = 72
    lines: list[str] = []

    def ln(s: str = "") -> None:
        lines.append(s)

    available = [r for r in all_results if r.get("available")]

    # ── Header ──────────────────────────────────────────────────────────────
    ln(f"  log    : {log_path}")
    ln("=" * W)
    ln("  LLM Model Benchmark  –  Speed & Korean Quality Comparison")
    ln(f"  server  : {server}")
    ln(f"  models  : {', '.join(str(r['model']) for r in all_results)}")
    ln(f"  tasks   : {', '.join(t['name'] for t in TASKS)}")
    ln(f"  warmup  : {warmup_runs}  |  runs : {runs}")
    ln("=" * W)
    ln()

    # ── Per-model run details ────────────────────────────────────────────────
    for r in all_results:
        model = str(r["model"])
        size_mb = r.get("size_mb_q4")
        size_str = f"~{size_mb:.0f} MB" if size_mb else "? MB"
        ln(f"[{model}]  ({size_str})")
        if not r.get("available"):
            ln("    ✗  not available / not running")
            ln()
            continue

        for t in r["tasks"]:  # type: ignore[union-attr]
            task_name = str(t.get("description", t.get("task", "")))
            ln(f"  Task: {task_name}")
            if "error" in t:
                ln(f"    ✗  {t['error']}")
                continue
            ok = int(t.get("runs_ok", 0))  # type: ignore[arg-type]
            errs = int(t.get("errors", 0))  # type: ignore[arg-type]
            ln(
                f"    runs={ok}/{ok + errs}  "
                f"avg={t.get('avg_total_ms', 0):.0f}ms  "
                f"min={t.get('min_total_ms', 0):.0f}ms  "
                f"max={t.get('max_total_ms', 0):.0f}ms  "
                f"ttft={t.get('avg_ttft_ms', 0):.0f}ms  "
                f"{t.get('avg_tokens_per_sec', 0):.1f}tok/s"
            )
            resp = str(t.get("last_response", "")).strip()
            if resp:
                ln(f"    └─ 마지막 응답:")
                for resp_line in resp.splitlines():
                    ln(f"       {resp_line}")
            q = t.get("quality", {})
            if q:
                kr = float(q.get("korean_ratio", 0)) * 100  # type: ignore[arg-type]
                ln(
                    f"    └─ quality={q.get('score','?')}%  "
                    f"chars={q.get('char_count','?')}  "
                    f"korean={kr:.0f}%  "
                    f"emoji_free={q.get('no_emoji_ok','?')}"
                )
        ln()

    # ── Speed comparison table ───────────────────────────────────────────────
    ln("=" * W)
    ln("  속도 비교  (태스크 평균)")
    ln("=" * W)
    col_hdr = "{:<22} {:>8} {:>11} {:>11} {:>8}"
    col_row = "{:<22} {:>8} {:>11} {:>11} {:>8}"
    ln(col_hdr.format("Model", "Size(MB)", "AvgTot(ms)", "TTFT(ms)", "Tok/s"))
    ln("-" * W)

    # sort available models by avg speed
    def _sort_key(r: dict[str, object]) -> float:
        return _avg_across_tasks(r, "avg_total_ms") if r.get("available") else float("inf")

    sorted_results = sorted(all_results, key=_sort_key)
    fastest_model = next((str(r["model"]) for r in sorted_results if r.get("available")), "")

    for r in sorted_results:
        model = str(r["model"])
        size = f"{r['size_mb_q4']:.0f}" if r.get("size_mb_q4") else "?"
        if not r.get("available"):
            ln(col_row.format(model, size, "N/A", "N/A", "N/A"))
            continue
        avg_total = _avg_across_tasks(r, "avg_total_ms")
        avg_ttft = _avg_across_tasks(r, "avg_ttft_ms")
        avg_tps = _avg_across_tasks(r, "avg_tokens_per_sec")
        marker = " ◀ fastest" if model == fastest_model else ""
        ln(col_row.format(model, size, f"{avg_total:.0f}", f"{avg_ttft:.0f}", f"{avg_tps:.1f}") + marker)
    ln("=" * W)
    ln()

    # ── Quality comparison table ─────────────────────────────────────────────
    ln("=" * W)
    ln("  품질 비교  (태스크별 quality score & 한국어 비율)")
    ln("=" * W)

    task_names = [str(t["name"]) for t in TASKS]
    task_descs = [str(t["description"]) for t in TASKS]
    # header
    hdr_label = "Model"
    hdr_parts = [f"{hdr_label:<22}"]
    for desc in task_descs:
        short = desc[:12]
        hdr_parts.append(f"{short:>14}")
    ln("".join(hdr_parts))
    ln("-" * W)

    for r in all_results:
        model = str(r["model"])
        row_parts = [f"{model:<22}"]
        if not r.get("available"):
            for _ in task_names:
                row_parts.append(f"{'N/A':>14}")
        else:
            task_map = {str(t["task"]): t for t in r["tasks"]}  # type: ignore[union-attr]
            for name in task_names:
                t = task_map.get(name, {})
                if "quality" in t:
                    q = t["quality"]
                    kr = float(q.get("korean_ratio", 0)) * 100  # type: ignore[arg-type]
                    cell = f"{q.get('score','?')}% / kr{kr:.0f}%"
                else:
                    cell = "err"
                row_parts.append(f"{cell:>14}")
        ln("".join(row_parts))
    ln("=" * W)
    ln()

    # ── Per-task response examples (full text, all models) ───────────────────
    ln("=" * W)
    ln("  태스크별 응답 예시  (마지막 run 기준)")
    ln("=" * W)

    for t_def in TASKS:
        task_key = str(t_def["name"])
        task_desc = str(t_def["description"])
        ln()
        ln(f"  ▶ {task_desc}")
        ln(f"    질문: {t_def['messages'][-1]['content']}")
        ln("    " + "-" * 60)
        for r in all_results:
            model = str(r["model"])
            if not r.get("available"):
                ln(f"    [{model}]  N/A")
                continue
            task_map = {str(t["task"]): t for t in r["tasks"]}  # type: ignore[union-attr]
            t = task_map.get(task_key, {})
            resp = str(t.get("last_response", "(no response)")).strip()
            q = t.get("quality", {})
            quality_str = f"quality={q.get('score','?')}%  chars={q.get('char_count','?')}" if q else ""
            ln(f"    [{model}]  {quality_str}")
            for resp_line in resp.splitlines():
                ln(f"      {resp_line}")
        ln("    " + "-" * 60)

    ln()
    ln(f"Log saved to : {log_path}")
    return "\n".join(lines)


def write_log(
    all_results: list[dict[str, object]],
    server: str,
    warmup_runs: int,
    runs: int,
    timestamp: str | None = None,
) -> Path:
    """Write combined benchmark .log to scratch/llm_output/ and return the path."""
    import datetime

    if timestamp is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = Path(__file__).parent / "llm_output"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"benchmark_{timestamp}.log"

    content = format_log(
        all_results=all_results,
        server=server,
        warmup_runs=warmup_runs,
        runs=runs,
        log_path=str(log_path),
    )
    log_path.write_text(content, encoding="utf-8")
    return log_path


# ---------------------------------------------------------------------------
# Per-model log + save
# ---------------------------------------------------------------------------

def _model_safe_name(model: str) -> str:
    """Return filesystem-safe model name.  e.g. qwen2.5:1.5b → qwen2.5-1.5b"""
    return model.replace(":", "-").replace("/", "_")


def format_model_log(
    result: dict[str, object],
    server: str,
    warmup_runs: int,
    runs: int,
    log_path: str,
) -> str:
    """Return a human-readable log string for a single model run."""
    W = 72
    lines: list[str] = []

    def ln(s: str = "") -> None:
        lines.append(s)

    model = str(result["model"])
    size_mb = result.get("size_mb_q4")
    size_str = f"~{size_mb:.0f} MB" if size_mb else "? MB"

    ln(f"  log    : {log_path}")
    ln("=" * W)
    ln(f"  LLM Benchmark  \u2013  {model}  ({size_str})")
    ln(f"  server  : {server}")
    ln(f"  tasks   : {', '.join(t['name'] for t in TASKS)}")
    ln(f"  warmup  : {warmup_runs}  |  runs : {runs}")
    ln("=" * W)
    ln()

    if not result.get("available"):
        ln(f"[{model}]  \u2717  not available / not running")
        ln()
        ln(f"Log saved to : {log_path}")
        return "\n".join(lines)

    for t in result["tasks"]:  # type: ignore[union-attr]
        task_name = str(t.get("description", t.get("task", "")))
        ln(f"[{task_name}]")
        if "error" in t:
            ln(f"  \u2717  {t['error']}")
            ln()
            continue
        ok = int(t.get("runs_ok", 0))  # type: ignore[arg-type]
        errs = int(t.get("errors", 0))  # type: ignore[arg-type]
        ln(
            f"  runs={ok}/{ok + errs}  "
            f"avg={t.get('avg_total_ms', 0):.0f}ms  "
            f"min={t.get('min_total_ms', 0):.0f}ms  "
            f"max={t.get('max_total_ms', 0):.0f}ms  "
            f"ttft={t.get('avg_ttft_ms', 0):.0f}ms  "
            f"{t.get('avg_tokens_per_sec', 0):.1f}tok/s"
        )
        resp = str(t.get("last_response", "")).strip()
        if resp:
            ln("  \u2514\u2500 \uc751\ub2f5:")
            for resp_line in resp.splitlines():
                ln(f"     {resp_line}")
        q = t.get("quality", {})
        if q:
            kr = float(q.get("korean_ratio", 0)) * 100  # type: ignore[arg-type]
            ln(
                f"  \u2514\u2500 quality={q.get('score','?')}%  "
                f"chars={q.get('char_count','?')}  "
                f"korean={kr:.0f}%  "
                f"emoji_free={q.get('no_emoji_ok','?')}"
            )
        ln()

    # Per-model speed summary table
    ln("=" * W)
    ln(f"  {'Task':<30} {'Avg(ms)':>9} {'Min(ms)':>9} {'TTFT(ms)':>10} {'Tok/s':>7}")
    ln("-" * W)
    for t in result["tasks"]:  # type: ignore[union-attr]
        if "error" in t or not t.get("runs_ok"):
            continue
        desc = str(t.get("description", t.get("task", "")))[:28]
        ln(
            f"  {desc:<30} "
            f"{t.get('avg_total_ms', 0):>8.0f}ms "
            f"{t.get('min_total_ms', 0):>8.0f}ms "
            f"{t.get('avg_ttft_ms', 0):>9.0f}ms "
            f"{t.get('avg_tokens_per_sec', 0):>6.1f}"
        )
    ln("=" * W)
    ln()
    ln(f"Log saved to : {log_path}")
    return "\n".join(lines)


def write_model_result(
    result: dict[str, object],
    server: str,
    warmup_runs: int,
    runs: int,
    timestamp: str,
) -> tuple[Path, Path]:
    """Save per-model JSON + log immediately after each model finishes.

    Files written to scratch/llm_output/:
      model_{safe_name}_{timestamp}.json
      model_{safe_name}_{timestamp}.log

    Returns (json_path, log_path).
    """
    model = str(result["model"])
    safe = _model_safe_name(model)
    out_dir = Path(__file__).parent / "llm_output"
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / f"model_{safe}_{timestamp}.json"
    model_data: dict[str, object] = {
        "benchmark": "llm_speed_quality",
        "server": server,
        "warmup_runs": warmup_runs,
        "runs": runs,
        "timestamp": timestamp,
        "model": result,
    }
    json_path.write_text(json.dumps(model_data, ensure_ascii=False, indent=2), encoding="utf-8")

    log_path = out_dir / f"model_{safe}_{timestamp}.log"
    content = format_model_log(result, server, warmup_runs, runs, str(log_path))
    log_path.write_text(content, encoding="utf-8")
    return json_path, log_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

# ~2-3B models comparable to exaone3.5:2.4b (~1.6 GB)
DEFAULT_MODELS = [
    "gemma:2b",
    "llama3.2:3b",
    "qwen2.5:3b",
    "exaone3.5:2.4b",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark Ollama LLM models: speed + Korean quality.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=DEFAULT_MODELS,
        metavar="MODEL",
        help=f"Ollama model tags to benchmark (default: {DEFAULT_MODELS})",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:11434",
        help="Ollama server base URL (default: http://127.0.0.1:11434)",
    )
    parser.add_argument(
        "--warmup-runs",
        default=2,
        type=int,
        help="Warmup calls before timing (default: 2)",
    )
    parser.add_argument(
        "--runs",
        default=5,
        type=int,
        help="Timed runs per task (default: 5)",
    )
    parser.add_argument(
        "--timeout",
        default=60.0,
        type=float,
        help="Per-request timeout in seconds (default: 60)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write full JSON results",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="Print known model sizes and exit",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        metavar="TIMESTAMP",
        help="Fixed run-id (timestamp string) to group per-model files together. "
             "Auto-generated if not given. Use this when calling from a shell script "
             "that benchmarks one model at a time.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.list_models:
        print("\nKnown model sizes (Q4_K_M estimate):")
        print(f"  {'Model':<25} {'Size (MB)':>10}  {'Notes'}")
        print("  " + "-" * 55)
        notes = {
            "smollm2:360m":    "sub-1B, ultra-fast",
            "qwen2.5:0.5b":    "sub-1B, multilingual",
            "gemma:2b":        "2B, Google (ollama tag)  ◀ default",
            "llama3.2:1b":     "1B, Meta",
            "qwen2.5:1.5b":    "1.5B, good Korean",
            "llama3.2:3b":     "3B, Meta    ◀ default",
            "qwen2.5:3b":      "3B, Alibaba ◀ default",
            "phi3.5:mini":     "3.8B, MS",
            "exaone3.5:2.4b":  "2.4B, LG Korean-optimized  ◀ default",
            "phi4-mini:3.8b":  "3.8B, MS reasoning",
        }
        for model, mb in MODEL_SIZE_MB.items():
            print(f"  {model:<25} {mb:>8.0f} MB  {notes.get(model, '')}")
        print()
        return

    if args.runs <= 0:
        raise ValueError("--runs must be > 0")
    if args.warmup_runs < 0:
        raise ValueError("--warmup-runs must be >= 0")

    import datetime
    timestamp = args.run_id or datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"Benchmarking {len(args.models)} model(s) on {len(TASKS)} task(s)", file=sys.stderr)
    print(f"Server  : {args.base_url}", file=sys.stderr)
    print(f"Warmup  : {args.warmup_runs}  |  Runs : {args.runs}  |  Timeout : {args.timeout}s", file=sys.stderr)
    print(f"Run ID  : {timestamp}", file=sys.stderr)
    print(f"Per-model files will be saved to: scratch/llm_output/model_<name>_{timestamp}.(json|log)", file=sys.stderr)

    all_results: list[dict[str, object]] = []
    for model in args.models:
        result = benchmark_model(
            base_url=args.base_url,
            model=model,
            tasks=TASKS,
            warmup_runs=args.warmup_runs,
            runs=args.runs,
            timeout=args.timeout,
        )
        all_results.append(result)

        # Save per-model result immediately — partial results are never lost
        json_path, model_log = write_model_result(
            result=result,
            server=args.base_url,
            warmup_runs=args.warmup_runs,
            runs=args.runs,
            timestamp=timestamp,
        )
        print(f"\n  \u2192 model JSON : {json_path}", file=sys.stderr)
        print(f"  \u2192 model log  : {model_log}", file=sys.stderr)
        print(model_log.read_text(encoding="utf-8"), file=sys.stderr)

    # Combined comparison log (all models together)
    combined_log = write_log(
        all_results=all_results,
        server=args.base_url,
        warmup_runs=args.warmup_runs,
        runs=args.runs,
        timestamp=timestamp,
    )
    print(f"\nCombined log : {combined_log}", file=sys.stderr)
    print(combined_log.read_text(encoding="utf-8"), file=sys.stderr)

    output_data: dict[str, object] = {
        "benchmark": "llm_speed_quality",
        "server": args.base_url,
        "warmup_runs": args.warmup_runs,
        "runs": args.runs,
        "timeout": args.timeout,
        "timestamp": timestamp,
        "combined_log": str(combined_log),
        "models": all_results,
    }

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output_data, ensure_ascii=False, indent=2))
        print(f"JSON saved to : {args.output}", file=sys.stderr)

    print(json.dumps(output_data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
