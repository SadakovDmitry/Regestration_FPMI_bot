# Telegram-бот регистрации на мероприятия (aiogram 3.x)

Production-ready каркас Telegram-бота регистрации на мероприятия (`solo`/`team`) с:
- админ-панелью в Telegram;
- публикацией событий в канал;
- отложенной публикацией первого поста о мероприятии;
- очередью ожидания (FIFO) + приглашения/таймауты 12h;
- подтверждением за 24h + таймаут 12h;
- пингами за 4 дня (проходки) и 2 часа;
- авто-постом о старте регистрации и авто-постом за 1 час до закрытия регистрации;
- личными рассылками всем пользователям (`/start`) при публикации события, старте регистрации и за 1 час до конца регистрации;
- экспортами CSV/XLSX;
- Celery + Redis для надёжного планировщика;
- PostgreSQL + Alembic.

## 1. Технологии
- Python 3.11+
- aiogram 3.x
- SQLAlchemy 2.x async + asyncpg
- Alembic
- Celery + Redis + Celery Beat
- Docker / docker-compose
- pytest + pytest-asyncio

## 2. Быстрый старт

### 2.1 Создать бота
1. Через `@BotFather` создать бота.
2. Скопировать токен в `.env`.

### 2.2 Подготовить `.env`
```bash
cp .env.example .env
```
Заполнить:
- `BOT_TOKEN`
- `ADMIN_IDS` и `SUPER_ADMIN_IDS` (через запятую)
- `CHANNEL_ID` (например `-100...`)
- `MASS_SEND_DELAY_SECONDS` (задержка между сообщениями массовой рассылки)

### 2.3 Поднять инфраструктуру
```bash
docker compose up -d db redis
```

### 2.4 Применить миграции
```bash
docker compose run --rm bot alembic upgrade head
```

### 2.5 Запуск бота и воркеров
```bash
docker compose up -d bot worker beat
```

## 3. Права в канале
Для публикаций в канал:
1. Добавьте бота админом канала.
2. Дайте право на публикацию сообщений и фото.
3. Укажите `CHANNEL_ID` в `.env`.

## 4. Команды пользователя
- `/start`
- `📅 Мероприятия`
- `🧾 Мои регистрации`
- `🕒 Лист ожидания`
- `👤 Профиль`
- `ℹ️ Помощь`

## 5. Команды админа
- `/admin`
- `/health`
- `/add_admin <tg_id>` (super-admin)
- `/remove_admin <tg_id>` (super-admin)
- `/backup_db`
- `/rebuild_scheduler`
- `/reschedule_event`

`📣 Опубликовать в канал` поддерживает два режима:
- публикация сразу;
- отложенная публикация (дата/время в `TIMEZONE` из `.env`, внутри хранится в UTC).

## 6. Бизнес-правила (реализовано)
- Окно регистрации: только при `status=published` и `registration_start_at <= now <= registration_end_at`.
- Ограничения:
  - `solo`: одна активная регистрация на пользователя.
  - `team`: капитан только в одной активной регистрации.
- Waitlist FIFO:
  - при нехватке мест -> `waitlist`;
  - при освобождении -> `invited_from_waitlist` и 12h на ответ;
  - `Да` -> `registered`, `Нет` -> `declined`, timeout -> `auto_declined`.
- Подтверждение за 24h:
  - запрос + 12h таймер;
  - `Пойду` -> `confirmed`, `Не пойду` -> `declined`, timeout -> `auto_declined`.
- Пинг за 2h: только `confirmed`.
- Пинг за 4 дня: только регистрации с `not_mipt`.

## 7. Экспорты
Админ-меню поддерживает:
- все регистрации CSV;
- только confirmed CSV;
- проходки (not_mipt) CSV;
- все регистрации XLSX.

Примеры лежат в `examples/exports/`.

## 8. Тесты
```bash
pip install -e .[dev]
pytest -q
```

Покрыто:
- лимиты + создание waitlist;
- перевод из waitlist + 12h timeout;
- подтверждение -24h + 12h timeout;
- отмена и освобождение мест;
- smoke интеграция статусов.

## 9. Бэкап/восстановление БД
Бэкап:
```bash
docker compose exec db pg_dump -U postgres hb_bot > backup.sql
```
Восстановление:
```bash
docker compose exec -T db psql -U postgres hb_bot < backup.sql
```

## 10. Структура
```text
app/
  handlers/
  services/
  repositories/
  models/
  jobs/
  utils/
migrations/
tests/
```

## 11. Безопасность ПДн
- Паспортные поля хранятся в БД и доступны только админам.
- Логи не должны содержать паспортные данные.
- Факт согласия хранится: `pd_consent_at`, `pd_consent_version`.
