from __future__ import annotations

from datetime import UTC, datetime

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy import text

from app.config import get_settings
from app.db import AsyncSessionLocal
from app.handlers.states import EventCreateStates, PublishScheduleStates
from app.keyboards.admin import events_admin_list_kb, export_kind_kb, publish_mode_kb
from app.keyboards.common import admin_menu_kb
from app.keyboards.events import event_type_kb
from app.models.enums import EventStatus, RegistrationStatus
from app.repositories.registrations import RegistrationRepository
from app.services.admin_service import AdminService
from app.services.event_service import EventService
from app.services.export_service import ExportService
from app.services.publication_service import PublicationService
from app.services.schemas import EventCreateInput
from app.utils.datetime import parse_dt

admin_router = Router(name="admin")
settings = get_settings()


def _is_true(value: str) -> bool:
    return value.lower().strip() in {"1", "yes", "y", "да", "true"}


async def _ensure_admin(message: Message) -> bool:
    async with AsyncSessionLocal() as session:
        admin_service = AdminService(session)
        is_admin = await admin_service.is_admin(message.from_user.id)
    if not is_admin:
        await message.answer("Недостаточно прав.")
        return False
    return True


async def _ensure_admin_cb(callback: CallbackQuery) -> bool:
    async with AsyncSessionLocal() as session:
        admin_service = AdminService(session)
        is_admin = await admin_service.is_admin(callback.from_user.id)
    if not is_admin:
        await callback.answer("Недостаточно прав", show_alert=True)
        return False
    return True


@admin_router.message(Command("admin"))
async def admin_panel(message: Message) -> None:
    if not await _ensure_admin(message):
        return
    await message.answer("Админ-панель", reply_markup=admin_menu_kb())


@admin_router.message(F.text == "➕ Создать мероприятие")
async def create_event_start(message: Message, state: FSMContext) -> None:
    if not await _ensure_admin(message):
        return
    await state.clear()
    await state.set_state(EventCreateStates.type)
    await message.answer("Тип мероприятия:", reply_markup=event_type_kb())


@admin_router.callback_query(EventCreateStates.type, F.data.startswith("event_type:"))
async def create_event_type(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _ensure_admin_cb(callback):
        return
    event_type = callback.data.split(":", maxsplit=1)[1]
    await state.update_data(type=event_type)
    await state.set_state(EventCreateStates.title)
    await callback.message.answer("Название:")
    await callback.answer()


@admin_router.message(EventCreateStates.title)
async def create_event_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(EventCreateStates.description)
    await message.answer("Описание (или '-'): ")


@admin_router.message(EventCreateStates.description)
async def create_event_description(message: Message, state: FSMContext) -> None:
    value = message.text.strip()
    await state.update_data(description=None if value == "-" else value)
    await state.set_state(EventCreateStates.reg_start)
    await message.answer("Старт регистрации UTC (YYYY-MM-DD HH:MM):")


@admin_router.message(EventCreateStates.reg_start)
async def create_event_reg_start(message: Message, state: FSMContext) -> None:
    try:
        reg_start = parse_dt(message.text)
    except ValueError:
        await message.answer("Неверный формат времени.")
        return
    await state.update_data(registration_start_at=reg_start.isoformat())
    await state.set_state(EventCreateStates.reg_end)
    await message.answer("Конец регистрации UTC (YYYY-MM-DD HH:MM):")


@admin_router.message(EventCreateStates.reg_end)
async def create_event_reg_end(message: Message, state: FSMContext) -> None:
    try:
        reg_end = parse_dt(message.text)
    except ValueError:
        await message.answer("Неверный формат времени.")
        return
    await state.update_data(registration_end_at=reg_end.isoformat())
    await state.set_state(EventCreateStates.start_at)
    await message.answer("Дата/время события UTC (YYYY-MM-DD HH:MM):")


@admin_router.message(EventCreateStates.start_at)
async def create_event_start_at(message: Message, state: FSMContext) -> None:
    try:
        start_at = parse_dt(message.text)
    except ValueError:
        await message.answer("Неверный формат времени.")
        return
    await state.update_data(start_at=start_at.isoformat())
    await state.set_state(EventCreateStates.location)
    await message.answer("Место:")


@admin_router.message(EventCreateStates.location)
async def create_event_location(message: Message, state: FSMContext) -> None:
    await state.update_data(location=message.text.strip())
    await state.set_state(EventCreateStates.capacity)
    await message.answer("Лимит capacity (целое):")


@admin_router.message(EventCreateStates.capacity)
async def create_event_capacity(message: Message, state: FSMContext) -> None:
    try:
        capacity = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число")
        return
    await state.update_data(capacity=capacity)

    data = await state.get_data()
    if data.get("type") == "team":
        await state.set_state(EventCreateStates.team_min)
        await message.answer("team_min_size:")
    else:
        await state.set_state(EventCreateStates.photo)
        await message.answer("photo_file_id (или '-'): ")


@admin_router.message(EventCreateStates.team_min)
async def create_event_team_min(message: Message, state: FSMContext) -> None:
    try:
        team_min = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число")
        return
    await state.update_data(team_min_size=team_min)
    await state.set_state(EventCreateStates.team_max)
    await message.answer("team_max_size:")


@admin_router.message(EventCreateStates.team_max)
async def create_event_team_max(message: Message, state: FSMContext) -> None:
    try:
        team_max = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число")
        return
    await state.update_data(team_max_size=team_max)
    await state.set_state(EventCreateStates.photo)
    await message.answer("photo_file_id (или '-'): ")


async def _send_event_preview(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    preview = (
        f"{data['title']}\n"
        f"Тип: {data['type']}\n"
        f"Регистрация: {data['registration_start_at']} - {data['registration_end_at']}\n"
        f"Старт: {data['start_at']}\n"
        f"Место: {data['location']}\n"
        f"capacity: {data['capacity']}"
    )
    if data.get("type") == "team":
        preview += f"\nКоманда: {data.get('team_min_size')}-{data.get('team_max_size')}"

    await state.set_state(EventCreateStates.preview)
    await message.answer(preview + "\n\nСохранить как draft? (yes/no)")


@admin_router.message(EventCreateStates.photo, F.photo)
async def create_event_photo_by_upload(message: Message, state: FSMContext) -> None:
    photo_file_id = message.photo[-1].file_id
    await state.update_data(photo_file_id=photo_file_id)
    await _send_event_preview(message, state)


@admin_router.message(EventCreateStates.photo)
async def create_event_photo(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Отправьте фото, file_id или '-' без фото.")
        return

    value = message.text.strip()
    await state.update_data(photo_file_id=None if value == "-" else value)
    await _send_event_preview(message, state)


@admin_router.message(EventCreateStates.preview)
async def create_event_preview(message: Message, state: FSMContext) -> None:
    if not _is_true(message.text):
        await state.clear()
        await message.answer("Создание отменено.")
        return

    data = await state.get_data()
    payload = EventCreateInput(
        type=data["type"],
        title=data["title"],
        description=data.get("description"),
        registration_start_at=datetime.fromisoformat(data["registration_start_at"]),
        registration_end_at=datetime.fromisoformat(data["registration_end_at"]),
        start_at=datetime.fromisoformat(data["start_at"]),
        location=data["location"],
        capacity=int(data["capacity"]),
        team_min_size=data.get("team_min_size"),
        team_max_size=data.get("team_max_size"),
        photo_file_id=data.get("photo_file_id"),
    )

    async with AsyncSessionLocal() as session:
        event = await EventService(session).create_draft(payload)
        await session.commit()

    await state.clear()
    await message.answer(f"Событие создано в draft: id={event.id}")


@admin_router.message(F.text == "📋 Список мероприятий")
async def admin_events_list(message: Message) -> None:
    if not await _ensure_admin(message):
        return

    async with AsyncSessionLocal() as session:
        events = await EventService(session).list_all()

    if not events:
        await message.answer("Событий нет.")
        return

    lines = [
        (
            f"{event.id}. {event.title} | {event.status.value} | {event.start_at:%d.%m.%Y %H:%M}"
            + (
                f" | publish_at={event.planned_publish_at:%d.%m.%Y %H:%M}"
                if event.planned_publish_at
                else ""
            )
        )
        for event in events
    ]
    await message.answer("\n".join(lines))


@admin_router.message(F.text == "📣 Опубликовать в канал")
async def publish_pick_event(message: Message) -> None:
    if not await _ensure_admin(message):
        return

    async with AsyncSessionLocal() as session:
        events = await EventService(session).list_all()

    draft_events = [event for event in events if event.status == EventStatus.draft]
    if not draft_events:
        await message.answer("Нет draft-событий.")
        return

    await message.answer(
        "Выберите событие для публикации:",
        reply_markup=events_admin_list_kb(draft_events, prefix="publish_event"),
    )


@admin_router.callback_query(F.data.startswith("publish_event:"))
async def publish_event_pick_mode(callback: CallbackQuery) -> None:
    if not await _ensure_admin_cb(callback):
        return

    event_id = int(callback.data.split(":", maxsplit=1)[1])
    await callback.message.answer(
        "Выберите режим публикации:",
        reply_markup=publish_mode_kb(event_id),
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("publish_now:"))
async def publish_event_now(callback: CallbackQuery, bot: Bot) -> None:
    if not await _ensure_admin_cb(callback):
        return

    event_id = int(callback.data.split(":", maxsplit=1)[1])
    async with AsyncSessionLocal() as session:
        outcome = await PublicationService(session, bot).publish_event(event_id=event_id)
        await session.commit()

    if outcome.published_now:
        await callback.message.answer(
            f"Событие опубликовано. Уведомлений отправлено: {outcome.notifications_sent}"
        )
    else:
        await callback.message.answer("Событие уже опубликовано ранее.")
    await callback.answer()


@admin_router.callback_query(F.data.startswith("publish_later:"))
async def publish_event_later(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _ensure_admin_cb(callback):
        return

    event_id = int(callback.data.split(":", maxsplit=1)[1])
    await state.clear()
    await state.update_data(publish_event_id=event_id)
    await state.set_state(PublishScheduleStates.publish_at)
    await callback.message.answer(
        "Введите дату и время публикации в UTC в формате YYYY-MM-DD HH:MM",
    )
    await callback.answer()


@admin_router.message(PublishScheduleStates.publish_at)
async def publish_event_later_save(message: Message, state: FSMContext) -> None:
    if not await _ensure_admin(message):
        return

    try:
        publish_at = parse_dt(message.text)
    except ValueError:
        await message.answer("Неверный формат. Ожидается YYYY-MM-DD HH:MM (UTC).")
        return

    if publish_at <= datetime.now(tz=UTC):
        await message.answer("Время публикации должно быть в будущем.")
        return

    data = await state.get_data()
    event_id = int(data["publish_event_id"])
    async with AsyncSessionLocal() as session:
        event = await EventService(session).schedule_publish(
            event_id=event_id,
            publish_at=publish_at,
        )
        await session.commit()

    await state.clear()
    await message.answer(
        f"Публикация для события #{event.id} запланирована на {publish_at:%d.%m.%Y %H:%M} UTC.",
    )


@admin_router.message(F.text == "🧾 Регистрации по мероприятию")
async def admin_regs_pick(message: Message) -> None:
    if not await _ensure_admin(message):
        return

    async with AsyncSessionLocal() as session:
        events = await EventService(session).list_all()
    if not events:
        await message.answer("Событий нет")
        return

    await message.answer(
        "Выберите событие:",
        reply_markup=events_admin_list_kb(events, prefix="admin_regs"),
    )


@admin_router.callback_query(F.data.startswith("admin_regs:"))
async def admin_regs_show(callback: CallbackQuery) -> None:
    if not await _ensure_admin_cb(callback):
        return

    event_id = int(callback.data.split(":", maxsplit=1)[1])
    async with AsyncSessionLocal() as session:
        regs = await RegistrationRepository(session).list_by_event(event_id)

    if not regs:
        await callback.message.answer("Регистраций пока нет.")
        await callback.answer()
        return

    lines = ["Регистрации:"]
    for reg in regs[:50]:
        captain = next((p for p in reg.people if p.role.value in {"captain", "solo"}), None)
        not_mipt = "not_mipt" if reg.has_not_mipt_members else "mipt"
        who = f"{captain.last_name} {captain.first_name}" if captain else f"user:{reg.user_id}"
        lines.append(f"#{reg.id} {reg.status.value} {not_mipt} {who} team={reg.team_name or '-'}")

    await callback.message.answer("\n".join(lines))
    await callback.answer()


@admin_router.message(F.text == "🕒 Очередь ожидания")
async def admin_waitlist_pick(message: Message) -> None:
    if not await _ensure_admin(message):
        return

    async with AsyncSessionLocal() as session:
        events = await EventService(session).list_all()

    if not events:
        await message.answer("Событий нет")
        return

    await message.answer(
        "Выберите событие:",
        reply_markup=events_admin_list_kb(events, prefix="admin_waitlist"),
    )


@admin_router.callback_query(F.data.startswith("admin_waitlist:"))
async def admin_waitlist_show(callback: CallbackQuery) -> None:
    if not await _ensure_admin_cb(callback):
        return

    event_id = int(callback.data.split(":", maxsplit=1)[1])
    async with AsyncSessionLocal() as session:
        regs = await RegistrationRepository(session).list_by_event(event_id)

    waitlist = [r for r in regs if r.status == RegistrationStatus.waitlist]
    if not waitlist:
        await callback.message.answer("Очередь ожидания пуста.")
        await callback.answer()
        return

    lines = ["Очередь ожидания (FIFO):"]
    for idx, reg in enumerate(waitlist, start=1):
        lines.append(f"{idx}. reg#{reg.id} user={reg.user_id} created={reg.created_at:%d.%m %H:%M}")
    await callback.message.answer("\n".join(lines))
    await callback.answer()


@admin_router.message(F.text == "📤 Экспорт CSV/Excel")
async def admin_export_pick(message: Message) -> None:
    if not await _ensure_admin(message):
        return

    async with AsyncSessionLocal() as session:
        events = await EventService(session).list_all()

    if not events:
        await message.answer("Событий нет")
        return

    await message.answer("Выберите событие:", reply_markup=events_admin_list_kb(events, prefix="admin_export"))


@admin_router.callback_query(F.data.startswith("admin_export:"))
async def admin_export_show(callback: CallbackQuery) -> None:
    if not await _ensure_admin_cb(callback):
        return

    event_id = int(callback.data.split(":", maxsplit=1)[1])
    await callback.message.answer("Выберите формат выгрузки:", reply_markup=export_kind_kb(event_id))
    await callback.answer()


@admin_router.callback_query(F.data.startswith("export_all_csv:"))
@admin_router.callback_query(F.data.startswith("export_confirmed_csv:"))
@admin_router.callback_query(F.data.startswith("export_passes_csv:"))
@admin_router.callback_query(F.data.startswith("export_all_xlsx:"))
async def export_data(callback: CallbackQuery) -> None:
    if not await _ensure_admin_cb(callback):
        return

    action, event_id_s = callback.data.split(":", maxsplit=1)
    event_id = int(event_id_s)

    async with AsyncSessionLocal() as session:
        regs = await RegistrationRepository(session).list_by_event(event_id)

    exporter = ExportService()
    if action == "export_all_csv":
        payload = exporter.export_csv(regs)
        filename = f"event_{event_id}_all.csv"
    elif action == "export_confirmed_csv":
        payload = exporter.export_csv(regs, only_confirmed=True)
        filename = f"event_{event_id}_confirmed.csv"
    elif action == "export_passes_csv":
        payload = exporter.export_passes_csv(regs)
        filename = f"event_{event_id}_passes.csv"
    else:
        payload = exporter.export_xlsx(regs)
        filename = f"event_{event_id}_all.xlsx"

    await callback.message.answer_document(BufferedInputFile(payload, filename=filename))
    await callback.answer()


@admin_router.message(F.text == "⚙️ Настройки")
async def settings_info(message: Message) -> None:
    if not await _ensure_admin(message):
        return

    await message.answer(
        "Текущие настройки:\n"
        f"timezone={settings.timezone}\n"
        f"channel_id={settings.channel_id}\n"
        "Шаблоны сообщений редактируются в коде/services."
    )


@admin_router.message(F.text == "👮 Админы")
async def admins_info(message: Message) -> None:
    if not await _ensure_admin(message):
        return

    async with AsyncSessionLocal() as session:
        admins = await AdminService(session).repo.list_admins()

    lines = ["Админы из БД:"]
    lines.extend(str(item.tg_id) for item in admins)
    lines.append(f"ADMIN_IDS env: {settings.admin_ids}")
    lines.append("Команды: /add_admin <tg_id>, /remove_admin <tg_id>")
    await message.answer("\n".join(lines))


@admin_router.message(Command("add_admin"))
async def add_admin(message: Message) -> None:
    if not await _ensure_admin(message):
        return

    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: /add_admin <tg_id>")
        return

    async with AsyncSessionLocal() as session:
        admin_service = AdminService(session)
        if not await admin_service.is_super_admin(message.from_user.id):
            await message.answer("Добавлять админов может только super-admin")
            return

        await admin_service.add_admin(int(parts[1]), message.from_user.id)
        await session.commit()

    await message.answer("Админ добавлен.")


@admin_router.message(Command("remove_admin"))
async def remove_admin(message: Message) -> None:
    if not await _ensure_admin(message):
        return

    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: /remove_admin <tg_id>")
        return

    async with AsyncSessionLocal() as session:
        admin_service = AdminService(session)
        if not await admin_service.is_super_admin(message.from_user.id):
            await message.answer("Удалять админов может только super-admin")
            return

        removed = await admin_service.remove_admin(int(parts[1]))
        await session.commit()

    await message.answer("Удалено." if removed else "Админ не найден или это super-admin.")


@admin_router.message(Command("health"))
async def healthcheck(message: Message) -> None:
    if not await _ensure_admin(message):
        return

    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT 1"))
    await message.answer("OK")


@admin_router.message(Command("rebuild_scheduler"))
async def rebuild_scheduler(message: Message) -> None:
    if not await _ensure_admin(message):
        return
    await message.answer(
        "Планировщик Celery beat работает периодически и сам подхватывает события. "
        "Команда принята: отдельная перепланировка не требуется."
    )


@admin_router.message(Command("reschedule_event"))
async def reschedule_event(message: Message) -> None:
    if not await _ensure_admin(message):
        return
    await message.answer(
        "Beat использует динамический подбор событий по времени, поэтому ручная перепланировка не нужна."
    )


@admin_router.message(Command("backup_db"))
async def backup_info(message: Message) -> None:
    if not await _ensure_admin(message):
        return
    await message.answer(
        "Бэкап БД: используйте команду из README\n"
        "docker compose exec db pg_dump -U postgres hb_bot > backup.sql"
    )
