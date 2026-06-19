#!/usr/bin/env python3
"""
council_ask.py — спрашивает НЕСКОЛЬКО разных моделей ОДНИМ И ТЕМ ЖЕ вопросом,
параллельно, и отдаёт чистые ответы в JSON.

Идея: один ключ OpenRouter → много моделей разных СЕМЕЙСТВ (GPT, Gemini,
DeepSeek, Qwen, Llama...). Разные семейства = честная защита от галлюцинаций
(не один и тот же «мозг» в пяти лицах). Claude (председатель совета) свой ответ
добавляет сам — этот скрипт только про ВНЕШНИЕ модели для перекрёстной сверки.

НАСТРОЙКА (один раз):
  1. Ключ OpenRouter: https://openrouter.ai/keys
  2. Положи его в файл ~/.openrouter_key  (chmod 600)
     либо в переменную окружения OPENROUTER_API_KEY.
  3. Всё. Никакие CLI (codex/qwen) больше не нужны.

ИСПОЛЬЗОВАНИЕ:
  python3 council_ask.py --prompt-file /tmp/q.txt
  python3 council_ask.py --prompt "короткий вопрос"
  # свои модели (любые с openrouter.ai/models):
  python3 council_ask.py --prompt-file q.txt --models "openai/gpt-4o,google/gemini-pro-1.5,deepseek/deepseek-chat"
  # у кого есть локальные CLI — можно подмешать:
  python3 council_ask.py --prompt-file q.txt --models "openai/gpt-4o-mini,codex,qwen"

ВЫВОД (stdout) — JSON:
  {"answers": {"openai/gpt-4o-mini": "...", ...}, "errors": {...}, "elapsed": {...}}
"""
import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

PER_MODEL_TIMEOUT = 240  # сек на одну модель

# Совет по умолчанию: три РАЗНЫХ семейства моделей через один ключ OpenRouter.
# Дёшево и разнообразно. Сменить можно флагом --models или переменной OPENROUTER_MODELS.
# Хочешь сильнее (дороже): openai/gpt-4o, google/gemini-pro-1.5, deepseek/deepseek-chat, qwen/qwen-2.5-72b-instruct.
DEFAULT_MODELS = os.environ.get(
    "OPENROUTER_MODELS",
    "openai/gpt-4o-mini,google/gemini-flash-1.5,deepseek/deepseek-chat,qwen/qwen-2.5-72b-instruct",
)


# ─── OpenRouter (один ключ → много моделей) ──────────────────────────────────

def _openrouter_key():
    p = os.path.expanduser("~/.openrouter_key")
    if os.path.exists(p):
        with open(p) as f:
            k = f.read().strip()
            if k:
                return k
    return os.environ.get("OPENROUTER_API_KEY", "").strip()


def run_openrouter(prompt, model):
    key = _openrouter_key()
    if not key:
        raise RuntimeError(
            "нет ключа OpenRouter: положи его в ~/.openrouter_key "
            "или переменную OPENROUTER_API_KEY (взять на https://openrouter.ai/keys)"
        )
    body = json.dumps({
        "model": model,
        "max_tokens": 1500,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/aipedagog/alena-council",
            "X-Title": "alena-council",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=PER_MODEL_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"HTTP {e.code}: {detail}")
    return ((data.get("choices") or [{}])[0].get("message", {}) or {}).get("content", "").strip()


# ─── Опционально: локальные CLI (если у тебя есть codex / qwen) ───────────────
# По умолчанию НЕ нужны — совет работает на одном ключе OpenRouter. Оставлены
# для тех, у кого уже стоят и авторизованы codex (ChatGPT Pro) и qwen.

def _clean_codex(out):
    marker = "\ntokens used\n"
    if marker in out:
        tail = out.split(marker, 1)[1]
        lines = tail.splitlines()
        while lines and lines[0].strip().replace(" ", "").replace(",", "").isdigit():
            lines.pop(0)
        ans = "\n".join(lines).strip()
        if ans:
            return ans
    if "\ncodex\n" in out:
        seg = out.rsplit("\ncodex\n", 1)[1]
        seg = seg.split("\ntokens used", 1)[0]
        return seg.strip()
    return out.strip()


def _clean_qwen(out):
    lines = [
        ln for ln in out.splitlines()
        if not ln.startswith("You are running Qwen Code")
        and "home directory" not in ln
    ]
    return "\n".join(lines).strip()


def run_codex(prompt):
    p = subprocess.run(
        ["codex", "exec", "--skip-git-repo-check", prompt],
        capture_output=True, text=True,
        stdin=subprocess.DEVNULL, timeout=PER_MODEL_TIMEOUT,
    )
    return _clean_codex(p.stdout or p.stderr)


def run_qwen(prompt):
    p = subprocess.run(
        ["qwen", "-p", prompt],
        capture_output=True, text=True,
        stdin=subprocess.DEVNULL, timeout=PER_MODEL_TIMEOUT,
    )
    return _clean_qwen(p.stdout or p.stderr)


def resolve_runner(name):
    """name → callable(prompt). 'codex'/'qwen' = локальный CLI; всё остальное
    (вида 'openai/gpt-4o-mini') = модель через OpenRouter."""
    if name == "codex":
        return run_codex
    if name == "qwen":
        return run_qwen
    return lambda prompt: run_openrouter(prompt, name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt")
    ap.add_argument("--prompt-file")
    ap.add_argument("--models", default=DEFAULT_MODELS,
                    help="через запятую: модели OpenRouter (openai/gpt-4o-mini, "
                         "google/gemini-flash-1.5, ...) и/или локальные codex, qwen")
    args = ap.parse_args()

    if args.prompt_file:
        with open(os.path.expanduser(args.prompt_file)) as f:
            prompt = f.read()
    elif args.prompt:
        prompt = args.prompt
    else:
        sys.exit("Нужен --prompt или --prompt-file")

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    answers, errors, elapsed = {}, {}, {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(models))) as ex:
        futs = {}
        for m in models:
            t0 = time.time()
            futs[ex.submit(resolve_runner(m), prompt)] = (m, t0)
        for fut in concurrent.futures.as_completed(futs):
            m, t0 = futs[fut]
            elapsed[m] = round(time.time() - t0, 1)
            try:
                ans = fut.result()
                if ans:
                    answers[m] = ans
                else:
                    errors[m] = "пустой ответ"
            except subprocess.TimeoutExpired:
                errors[m] = f"таймаут ({PER_MODEL_TIMEOUT}с)"
            except FileNotFoundError:
                errors[m] = "CLI не установлен (нужен только для codex/qwen)"
            except Exception as e:
                errors[m] = str(e)

    print(json.dumps(
        {"answers": answers, "errors": errors, "elapsed": elapsed},
        ensure_ascii=False, indent=2,
    ))


if __name__ == "__main__":
    main()
