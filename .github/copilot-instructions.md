# Copilot / AI agent instructions for kini_events_v2

Короткие и практичные указания для AI-агентов, которые будут править или расширять этот проект.

- Проект: Django-приложение (легковесный events manager). Точка входа — `manage.py`.
- Основные модули:
  - `events/` — бизнес-логика: модели (`models.py`), представления (`views.py`), шаблоны (`templates/events/`) и статика (`static/`).
  - `eventsystem/` — конфигурация Django (settings, urls, wsgi/asgi).
  - `db.sqlite3` — локальная БД (dev). Учтите, что данные находятся в корне.

Ключевые концепции и паттерны (взять за основу при правках)
- Таймзона: код активно использует `django.utils.timezone`. При сборке datetime всегда делать aware через
  `timezone.make_aware(datetime.combine(date, time_part), timezone.get_current_timezone())`.
  Многие места используют `datetime.min.time()` как fallback если `event.time` отсутствует — сохраняйте этот подход.
- Регистрации и защита от дублей: `Registration.objects.create(...)` обёрнут в `try/except IntegrityError` — есть уникальный индекс на запись.
- Напоминания/уведомления:
  - `generate_reminders_for_user` и `reminders_json` в `events/views.py` формируют тексты и создают `Notification`.
  - После создания уведомления в некоторых местах код помечает `Notification` как прочитанные (`is_read=True`) при отдаче JSON.
- Пользовательские сообщения: проект широко использует Django messages framework (`messages.info`, `messages.error`, `messages.success`) для UX-уведомлений.
- Права доступа: большинство view'шек помечены `@login_required(login_url='/login/')`; отчёты ограничены `user.is_staff`.

Файлы, которые стоит прочитать при изменениях логики
- `events/views.py` — основная логика регистрации, напоминаний, JSON API (примеры: `events_json`, `reminders_json`, `register_for_event`).
- `events/models.py` — модельный слой (Event, Registration, Notification, Feedback). Меняйте миграции аккуратно.
- `events/templates/events/` — шаблоны фронта (dashboard, home, reports, feedback_form).
- `eventsystem/settings.py` — настройки, timezone, подключение static/media.

Рабочие команды (dev)
- Запустить сервер: `python3 manage.py runserver`
- Миграции: `python3 manage.py makemigrations` / `python3 manage.py migrate`
- Создать суперпользователя: `python3 manage.py createsuperuser`
- Тесты: `python3 manage.py test` (проект использует стандартный Django test runner)
- Консоль: `python3 manage.py shell`

Проектные конвенции/ограничения
- Не менять формат хранения дат/времени без согласования: представления и JSON-эндпойнты ожидают `date` и `time` поля (строки). При изменении API обновите шаблоны JS/календарь.
- Уведомления и напоминания зависят от полей модели `Registration.last_reminded_on` — изменения в логике напоминаний должны учитывать поле и не спамить (в коде ограничение: максимум 2 сообщений за вход).
- При изменении логики регистрации учитывайте проверки:
  - событие не в прошлом (сравнение aware datetime с `timezone.localtime()`),
  - свободная вместимость (`Event.is_full()`),
  - защита от дублирующих регистраций (IntegrityError).

Примеры полезных подсказок для агента (copy-paste-ready)
- "Когда меняешь обработку даты/времени события, обнови `events_json`, `reminders_json` и `generate_reminders_for_user` — все три места создают aware datetime через `timezone.make_aware(datetime.combine(...))`."
- "Если добавляешь поле в `Registration` — не забудь добавить миграцию и проверить, что `Registration.objects.create(...)` не ломает IntegrityError-логику в `register_for_event`."

Короткий чек-лист перед PR
1. Запустил `python3 manage.py test` — тесты не упали.
2. Проверил локально `runserver` и основные страницы: /, /dashboard, /login, /reports (если is_staff).
3. При изменении API JSON — обновил шаблоны в `templates/events/` и JS, использующий данные (календарь, мои события).

Если что-то непонятно — спросите: укажите файл и строку (например, `events/views.py:generate_reminders_for_user`) и желаемое поведение.

---
Если нужно, могу сократить/перевести этот файл в английский или расширить раздел про миграции и тесты.
