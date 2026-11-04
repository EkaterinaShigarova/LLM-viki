# Работа с GitHub

Актуальный репозиторий: https://github.com/EkaterinaShigarova/LLM-viki. Рабочая ветка feat/baikal-llm-wiki. Не изменять main и не переписывать историю.

```bash
git switch feat/baikal-llm-wiki
git status
```

Перед сохранением изменений запустить тесты и Wiki lint, проверить источники и заметки. Затем обычные commit/push конкретных проверенных файлов. data/raw и data/processed отдельно резервируются, в публичный Git не добавляются.

Историю содержания читать в wiki/LOG.md и Git Commits. Создание Pull Request не является научным одобрением. Отсутствие доступа к push нужно явно сообщать; не выдавать локальный commit за отправленный.
