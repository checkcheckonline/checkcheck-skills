# CheckCheck Skills

Скиллы для Claude и ChatGPT для работы с [ЧекЧеком](https://check-check.online):
сборка и валидация файлов импорта товаров из исходников поставщиков.

Скиллы сделаны в открытом формате [Agent Skills](https://agentskills.io)
(папка с `SKILL.md`), поэтому одна и та же папка подключается и в Claude,
и в ChatGPT.

## Скиллы

| Скилл | Что делает |
|---|---|
| `checkcheck-import` | Превращает Excel/CSV поставщика (бренды, маски, баллы) в готовый `.tsv` для импорта товаров и проверяет его по правилам импорта: ключевые слова колонок, маски с брендом без дублей, баллы XOR процент, защита от случайного снятия автоакций. |

Готовые zip-архивы скиллов лежат в [Releases](https://github.com/checkcheckonline/checkcheck-skills/releases/latest).

## Установка

### Claude Code (рекомендуется — с обновлениями)

```
/plugin marketplace add checkcheckonline/checkcheck-skills
/plugin install checkcheck@checkcheck
```

Скиллы станут доступны как `/checkcheck:<имя скилла>`; Claude также подхватывает
их автоматически по контексту задачи.

Обновление: `/plugin marketplace update checkcheck`.

### Claude.ai / Claude Desktop

1. Скачайте `checkcheck-import.zip` из [последнего релиза](https://github.com/checkcheckonline/checkcheck-skills/releases/latest).
2. Settings → Capabilities → Skills → Upload skill, выберите zip.
3. Убедитесь, что включено выполнение кода (Code execution) — скилл запускает
   Python-скрипты.

### ChatGPT

Нативные скиллы доступны в тарифах Business / Enterprise / Edu
(администратор workspace может их отключить):

1. Скачайте `checkcheck-import.zip` из [последнего релиза](https://github.com/checkcheckonline/checkcheck-skills/releases/latest).
2. Skills → Create → Upload from your computer, выберите zip.

Если раздела Skills нет (личные тарифы): создайте Project или Custom GPT,
вставьте содержимое `SKILL.md` в инструкции, а файлы из `references/` и
`scripts/` загрузите как файлы; включите Code Interpreter / анализ данных.

### Codex / Claude Code вручную (без обновлений)

```bash
git clone https://github.com/checkcheckonline/checkcheck-skills
cp -r checkcheck-skills/plugins/checkcheck/skills/checkcheck-import ~/.claude/skills/   # Claude Code
cp -r checkcheck-skills/plugins/checkcheck/skills/checkcheck-import ~/.codex/skills/    # Codex
```

## Структура

```
.claude-plugin/marketplace.json     # маркетплейс для Claude Code
plugins/checkcheck/
├── .claude-plugin/plugin.json
└── skills/<skill>/
    ├── SKILL.md                    # инструкция для модели
    ├── scripts/                    # детерминированные скрипты (python3, stdlib + openpyxl)
    └── references/                 # справочники, подгружаются по необходимости
```

Скиллы пишутся на русском. Скрипты — самостоятельные CLI на python3 без
зависимостей, кроме `openpyxl`.

Новый релиз с zip-архивами собирается автоматически при пуше тега `v*`.

## Лицензия

[MIT](LICENSE)
