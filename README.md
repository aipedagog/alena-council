# conclave — совет ИИ-советников (один ключ → много моделей)

Скилл для **Claude Code**: важный вопрос уходит **нескольким разным моделям** (GPT, Gemini,
DeepSeek, Qwen) через **один ключ OpenRouter**. Они отвечают независимо и сверяют друг друга —
защита от **галлюцинаций** (где модели сошлись, надёжно; где разошлись, красный флаг) и от
**подхалимажа** (5 намеренно конфликтующих «линз» зрения ищут дыры в идее).

Два режима: **ПРОВЕРКА** (факты/цифры, ищем консенсус) и **WAR-ROOM** (решения: модели +
5 линз + анонимное перекрёстное ревью → вердикт председателя).

## Настройка (один раз)
1. Ключ OpenRouter: https://openrouter.ai/keys (пополни на пару долларов).
2. Положи в `~/.openrouter_key` (или переменную `OPENROUTER_API_KEY`).
3. Всё. CLI и VPN не нужны.

По умолчанию совет = 4 семейства: `gpt-4o-mini`, `gemini-2.5-flash`, `deepseek-chat`,
`qwen-2.5-72b`. Сменить: `--models "openai/gpt-4o,..."` или переменная `OPENROUTER_MODELS`
(актуальный список моделей — [openrouter.ai/models](https://openrouter.ai/models)).

## Установка
```bash
git clone https://github.com/aipedagog/conclave ~/.claude/skills/conclave
```

## Источник
По мотивам [llm-council Андрея Карпатого](https://github.com/karpathy/llm-council) (разные
модели сверяют друг друга) и Council-скилла Ole Lehmann (5 линз против подхалимажа).

## Автор
Скилл из набора **Алёны Быковской / KeyBrain** (курс по Claude Code). Лицензия — MIT.
