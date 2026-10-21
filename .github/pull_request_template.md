## Що змінено · What changed

<!-- Коротко, що і навіщо · Briefly, what and why -->

## Перевірки · Checks

- [ ] `python -m pytest tests` проходить · passes
- [ ] Нові рядки інтерфейсу є українською, російською й англійською · New strings exist in uk, ru and en
- [ ] Кожна зміна системи потрапляє в журнал відкату · Every system change goes to the rollback journal
- [ ] Якщо змінювались твіки — `python tools/gen_docs.py` · If tweaks changed, `python tools/gen_docs.py`
- [ ] Скрипти `.bat` лише ASCII з CRLF · `.bat` scripts are ASCII with CRLF
