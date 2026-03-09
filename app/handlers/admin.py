from __future__ import annotations

from datetime import UTC, datetime

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy import text

from app.config import get_settings
from app.db import AsyncSessionLocal
from app.handlers.states import EventCreateStates, EventEditStates, PublishScheduleStates
from app.keyboards.admin import (
    edit_event_fields_kb,
    events_admin_list_kb,
    export_kind_kb,
    publish_mode_kb,
)
from app.keyboards.common import (
    ADMIN_BTN_ADMINS,
    ADMIN_BTN_CREATE_EVENT,
    ADMIN_BTN_DELETE_EVENT,
    ADMIN_BTN_EDIT_EVENT,
    ADMIN_BTN_EVENTS_LIST,
    ADMIN_BTN_EXPORT,
    ADMIN_BTN_PUBLISH,
    ADMIN_BTN_REGISTRATIONS,
    ADMIN_BTN_SETTINGS,
    ADMIN_BTN_WAITLIST,
    admin_menu_kb,
)
from app.keyboards.events import event_type_kb, yes_no_kb
from app.models.enums import EventStatus, RegistrationStatus
from app.repositories.registrations import RegistrationRepository
from app.services.admin_service import AdminService
from app.services.event_service import EventService
from app.services.exceptions import NotFoundError, ValidationError
from app.services.export_service import ExportService
from app.services.publication_service import PublicationService
from app.services.schemas import EventCreateInput
from app.utils.datetime import parse_dt
from app.utils.text import NOT_MIPT_REG_NOTE, format_dt_tz

admin_router = Router(name="admin")
settings = get_settings()


def _is_true(value: str) -> bool:
    return value.lower().strip() in {"1", "yes", "y", "да", "true"}


def _event_type_label(event_type: str) -> str:
    return "Командное (team)" if event_type == "team" else "Индивидуальное (solo)"


def _event_status_label(status: EventStatus) -> str:
    labels = {
        EventStatus.draft: "черновик",
        EventStatus.published: "опубликовано",
        EventStatus.archived: "архив",
    }
    return labels.get(status, status.value)


def _registration_status_label(status: RegistrationStatus) -> str:
    labels = {
        RegistrationStatus.registered: "зарегистрирован",
        RegistrationStatus.waitlist: "в листе ожидания",
        RegistrationStatus.invited_from_waitlist: "приглашен из листа ожидания",
        RegistrationStatus.confirmed: "подтвердил участие",
        RegistrationStatus.declined: "отказ",
        RegistrationStatus.auto_declined: "автоотказ (таймаут)",
        RegistrationStatus.cancelled_by_user: "отменено пользователем",
    }
    return labels.get(status, status.value)


EVENT_EDIT_FIELD_LABELS = {
    "title": "название",
    "description": "описание",
    "registration_start_at": "начало регистрации",
    "registration_end_at": "конец регистрации",
    "start_at": "дату/время события",
    "location": "место",
    "capacity": "лимит мест",
    "team_min_size": "минимальный размер команды",
    "team_max_size": "максимальный размер команды",
    "photo_file_id": "фото",
}


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
    await message.answer(
        "🔧 Панель администратора.\nВыбери действие в меню ниже.",
        reply_markup=admin_menu_kb(),
    )


@admin_router.message(F.text == ADMIN_BTN_CREATE_EVENT)
async def create_event_start(message: Message, state: FSMContext) -> None:
    if not await _ensure_admin(message):
        return
    await state.clear()
    await state.set_state(EventCreateStates.type)
    await message.answer("1/9 Выберите тип мероприятия:", reply_markup=event_type_kb())


@admin_router.callback_query(EventCreateStates.type, F.data.startswith("event_type:"))
async def create_event_type(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _ensure_admin_cb(callback):
        return
    event_type = callback.data.split(":", maxsplit=1)[1]
    await state.update_data(type=event_type)
    await state.set_state(EventCreateStates.title)
    await callback.message.answer("2/9 Введите название мероприятия:")
    await callback.answer()


@admin_router.message(EventCreateStates.title)
async def create_event_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(EventCreateStates.description)
    await message.answer("3/9 Введите описание или отправьте `-`, чтобы пропустить.")


@admin_router.message(EventCreateStates.description)
async def create_event_description(message: Message, state: FSMContext) -> None:
    value = message.text.strip()
    await state.update_data(description=None if value == "-" else value)
    await state.set_state(EventCreateStates.reg_start)
    await message.answer(
        f"4/9 Введите начало регистрации ({settings.timezone})\n"
        "Формат: YYYY-MM-DD HH:MM"
    )


@admin_router.message(EventCreateStates.reg_start)
async def create_event_reg_start(message: Message, state: FSMContext) -> None:
    try:
        reg_start = parse_dt(message.text, settings.timezone)
    except ValueError:
        await message.answer("Не могу распознать дату/время. Формат: YYYY-MM-DD HH:MM")
        return
    await state.update_data(registration_start_at=reg_start.isoformat())
    await state.set_state(EventCreateStates.reg_end)
    await message.answer(
        f"5/9 Введите конец регистрации ({settings.timezone})\n"
        "Формат: YYYY-MM-DD HH:MM"
    )


@admin_router.message(EventCreateStates.reg_end)
async def create_event_reg_end(message: Message, state: FSMContext) -> None:
    try:
        reg_end = parse_dt(message.text, settings.timezone)
    except ValueError:
        await message.answer("Не могу распознать дату/время. Формат: YYYY-MM-DD HH:MM")
        return
    await state.update_data(registration_end_at=reg_end.isoformat())
    await state.set_state(EventCreateStates.start_at)
    await message.answer(
        f"6/9 Введите дату и время начала события ({settings.timezone})\n"
        "Формат: YYYY-MM-DD HH:MM"
    )


@admin_router.message(EventCreateStates.start_at)
async def create_event_start_at(message: Message, state: FSMContext) -> None:
    try:
        start_at = parse_dt(message.text, settings.timezone)
    except ValueError:
        await message.answer("Не могу распознать дату/время. Формат: YYYY-MM-DD HH:MM")
        return
    await state.update_data(start_at=start_at.isoformat())
    await state.set_state(EventCreateStates.location)
    await message.answer("7/9 Укажите место проведения:")


@admin_router.message(EventCreateStates.location)
async def create_event_location(message: Message, state: FSMContext) -> None:
    await state.update_data(location=message.text.strip())
    await state.set_state(EventCreateStates.capacity)
    data = await state.get_data()
    if data.get("type") == "team":
        await message.answer("8/9 Укажите общий лимит участников (человек, целое число):")
    else:
        await message.answer("8/9 Укажите лимит участников (целое число):")


@admin_router.message(EventCreateStates.capacity)
async def create_event_capacity(message: Message, state: FSMContext) -> None:
    try:
        capacity = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число.")
        return
    await state.update_data(capacity=capacity)

    data = await state.get_data()
    if data.get("type") == "team":
        await state.set_state(EventCreateStates.team_min)
        await message.answer("8.1/9 Минимальный размер команды (целое число):")
    else:
        await state.set_state(EventCreateStates.photo)
        await message.answer(
            "9/9 Отправьте фото мероприятия сообщением.\n"
            "Если фото не нужно, отправьте `-`.\n"
            "Можно также вставить готовый `file_id`."
        )


@admin_router.message(EventCreateStates.team_min)
async def create_event_team_min(message: Message, state: FSMContext) -> None:
    try:
        team_min = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число.")
        return
    await state.update_data(team_min_size=team_min)
    await state.set_state(EventCreateStates.team_max)
    await message.answer("8.2/9 Максимальный размер команды (целое число):")


@admin_router.message(EventCreateStates.team_max)
async def create_event_team_max(message: Message, state: FSMContext) -> None:
    try:
        team_max = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число.")
        return
    await state.update_data(team_max_size=team_max)
    await state.set_state(EventCreateStates.photo)
    await message.answer(
        "9/9 Отправьте фото мероприятия сообщением.\n"
        "Если фото не нужно, отправьте `-`.\n"
        "Можно также вставить готовый `file_id`."
    )


async def _send_event_preview(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    reg_start = format_dt_tz(datetime.fromisoformat(data["registration_start_at"]))
    reg_end = format_dt_tz(datetime.fromisoformat(data["registration_end_at"]))
    start_at = format_dt_tz(datetime.fromisoformat(data["start_at"]))

    preview = (
        "👀 Предпросмотр мероприятия\n\n"
        f"🎯 Название: {data['title']}\n"
        f"🧩 Тип: {_event_type_label(data['type'])}\n"
        f"📝 Регистрация: {reg_start} — {reg_end}\n"
        f"🗓 Старт события: {start_at}\n"
        f"📍 Место: {data['location']}\n"
        f"👥 Лимит: {data['capacity']} чел."
    )
    if data.get("type") == "team":
        preview += f"\n👨‍👩‍👧‍👦 Размер команды: {data.get('team_min_size')}–{data.get('team_max_size')}"
    preview += f"\n\n{NOT_MIPT_REG_NOTE}"

    await state.set_state(EventCreateStates.preview)
    await message.answer(
        preview + "\n\nСохранить это мероприятие как черновик?",
        reply_markup=yes_no_kb("draft_save_yes", "draft_save_no", yes_text="Да", no_text="Нет"),
    )


@admin_router.message(EventCreateStates.photo, F.photo)
async def create_event_photo_by_upload(message: Message, state: FSMContext) -> None:
    photo_file_id = message.photo[-1].file_id
    await state.update_data(photo_file_id=photo_file_id)
    await _send_event_preview(message, state)


@admin_router.message(EventCreateStates.photo)
async def create_event_photo(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Отправьте фото, `file_id` или `-`, если фото не нужно.")
        return

    value = message.text.strip()
    await state.update_data(photo_file_id=None if value == "-" else value)
    await _send_event_preview(message, state)


async def _save_event_from_state(message: Message, state: FSMContext) -> None:
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
    await message.answer(
        f"✅ Черновик создан: мероприятие #{event.id}.\n"
        "Откройте раздел «🚀 Запустить мероприятие», когда будете готовы к публикации."
    )


@admin_router.callback_query(EventCreateStates.preview, F.data.in_({"draft_save_yes", "draft_save_no"}))
async def create_event_preview_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data == "draft_save_no":
        await state.clear()
        await callback.message.answer("Создание мероприятия отменено.")
        await callback.answer()
        return

    await _save_event_from_state(callback.message, state)
    await callback.answer()


@admin_router.message(EventCreateStates.preview)
async def create_event_preview_message_fallback(message: Message, state: FSMContext) -> None:
    if not _is_true(message.text):
        await message.answer("Пожалуйста, нажмите кнопку «Да» или «Нет» ниже.")
        return
    await _save_event_from_state(message, state)


def _event_edit_prompt(event_type: str, field: str, current_value: str) -> str:
    if field in {"registration_start_at", "registration_end_at", "start_at"}:
        return (
            f"Введите {EVENT_EDIT_FIELD_LABELS[field]} ({settings.timezone}).\n"
            "Формат: YYYY-MM-DD HH:MM\n"
            f"Сейчас: {current_value}"
        )
    if field in {"capacity", "team_min_size", "team_max_size"}:
        return (
            f"Введите {EVENT_EDIT_FIELD_LABELS[field]} (целое число > 0).\n"
            f"Сейчас: {current_value}"
        )
    if field == "description":
        return (
            "Введите новое описание.\n"
            "Отправьте `-`, чтобы очистить поле.\n"
            f"Сейчас: {current_value}"
        )
    if field == "photo_file_id":
        return (
            "Отправьте новое фото сообщением или укажите `file_id`.\n"
            "Отправьте `-`, чтобы удалить фото.\n"
            f"Сейчас: {current_value}"
        )
    return f"Введите {EVENT_EDIT_FIELD_LABELS[field]}.\nСейчас: {current_value}"


def _event_field_current_value(event: object, field: str) -> str:
    value = getattr(event, field)
    if value is None:
        return "—"
    if field in {"registration_start_at", "registration_end_at", "start_at"}:
        return format_dt_tz(value)
    return str(value)


def _event_field_is_allowed_for_type(event_type: str, field: str) -> bool:
    if event_type == "team":
        return field in EVENT_EDIT_FIELD_LABELS
    return field in (set(EVENT_EDIT_FIELD_LABELS) - {"team_min_size", "team_max_size"})


async def _apply_event_edit(
    message: Message,
    state: FSMContext,
    field: str,
    parsed_value: object,
) -> None:
    data = await state.get_data()
    event_id = data.get("edit_event_id")
    if not event_id:
        await state.clear()
        await message.answer("Не выбрано мероприятие для редактирования. Нажмите «✏️ Изменить мероприятие».")
        return

    async with AsyncSessionLocal() as session:
        service = EventService(session)
        try:
            event = await service.update_fields(int(event_id), {field: parsed_value})
            await session.commit()
        except NotFoundError:
            await state.clear()
            await message.answer("Мероприятие не найдено.")
            return
        except ValidationError as exc:
            await message.answer(f"Не удалось сохранить изменение: {exc}")
            return

    await state.set_state(EventEditStates.field_pick)
    await message.answer(
        f"✅ Поле «{EVENT_EDIT_FIELD_LABELS[field]}» обновлено.\n"
        f"Событие: #{event.id} • {event.title}\n"
        f"Текущее значение: {_event_field_current_value(event, field)}",
        reply_markup=edit_event_fields_kb(is_team=event.type.value == "team"),
    )


@admin_router.message(F.text == ADMIN_BTN_EVENTS_LIST)
async def admin_events_list(message: Message) -> None:
    if not await _ensure_admin(message):
        return

    async with AsyncSessionLocal() as session:
        events = await EventService(session).list_all()

    if not events:
        await message.answer("Пока нет ни одного мероприятия.")
        return

    lines = ["📋 Все мероприятия:"]
    for event in events:
        block = [
            f"#{event.id} • {event.title}",
            f"Статус: {_event_status_label(event.status)}",
            f"Дата события: {format_dt_tz(event.start_at)}",
        ]
        if event.planned_publish_at:
            block.append(f"Автозапуск: {format_dt_tz(event.planned_publish_at)}")
        lines.append("\n".join(block))

    await message.answer("\n".join(lines))


@admin_router.message(F.text == ADMIN_BTN_EDIT_EVENT)
async def edit_event_pick(message: Message, state: FSMContext) -> None:
    if not await _ensure_admin(message):
        return

    await state.clear()
    async with AsyncSessionLocal() as session:
        events = await EventService(session).list_all()

    if not events:
        await message.answer("Пока нет мероприятий для редактирования.")
        return

    await message.answer(
        "Выберите мероприятие для редактирования:",
        reply_markup=events_admin_list_kb(events, prefix="edit_event"),
    )


@admin_router.callback_query(F.data.startswith("edit_event:"))
async def edit_event_choose_field(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _ensure_admin_cb(callback):
        return

    event_id = int(callback.data.split(":", maxsplit=1)[1])
    async with AsyncSessionLocal() as session:
        event = await EventService(session).get(event_id)
    if not event:
        await callback.message.answer("Мероприятие не найдено.")
        await callback.answer()
        return

    await state.clear()
    await state.update_data(edit_event_id=event.id)
    await state.set_state(EventEditStates.field_pick)
    await callback.message.answer(
        f"✏️ Редактирование события #{event.id} • {event.title}\n"
        "Выберите поле, которое хотите изменить:",
        reply_markup=edit_event_fields_kb(is_team=event.type.value == "team"),
    )
    await callback.answer()


@admin_router.callback_query(EventEditStates.field_pick, F.data == "edit_done")
async def edit_event_done(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _ensure_admin_cb(callback):
        return
    await state.clear()
    await callback.message.answer("Редактирование завершено.")
    await callback.answer()


@admin_router.callback_query(EventEditStates.field_pick, F.data.startswith("edit_field:"))
async def edit_event_field_pick(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _ensure_admin_cb(callback):
        return

    field = callback.data.split(":", maxsplit=1)[1]
    if field not in EVENT_EDIT_FIELD_LABELS:
        await callback.answer("Неизвестное поле", show_alert=True)
        return

    data = await state.get_data()
    event_id = data.get("edit_event_id")
    if not event_id:
        await state.clear()
        await callback.message.answer("Не выбрано мероприятие. Нажмите «✏️ Изменить мероприятие».")
        await callback.answer()
        return

    async with AsyncSessionLocal() as session:
        event = await EventService(session).get(int(event_id))
    if not event:
        await state.clear()
        await callback.message.answer("Мероприятие не найдено.")
        await callback.answer()
        return

    if not _event_field_is_allowed_for_type(event.type.value, field):
        await callback.answer("Это поле недоступно для текущего типа события", show_alert=True)
        return

    await state.update_data(edit_field=field)
    await state.set_state(EventEditStates.value)
    await callback.message.answer(
        _event_edit_prompt(
            event_type=event.type.value,
            field=field,
            current_value=_event_field_current_value(event, field),
        )
    )
    await callback.answer()


@admin_router.message(EventEditStates.value, F.photo)
async def edit_event_value_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    field = data.get("edit_field")
    if field != "photo_file_id":
        await message.answer("Для этого поля нужно отправить текстовое значение.")
        return

    await _apply_event_edit(
        message=message,
        state=state,
        field=field,
        parsed_value=message.photo[-1].file_id,
    )


@admin_router.message(EventEditStates.value)
async def edit_event_value_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    field = data.get("edit_field")
    if field not in EVENT_EDIT_FIELD_LABELS:
        await state.clear()
        await message.answer("Сценарий редактирования сброшен. Нажмите «✏️ Изменить мероприятие».")
        return
    if not message.text:
        await message.answer("Отправьте текстовое значение.")
        return

    value = message.text.strip()
    if field in {"registration_start_at", "registration_end_at", "start_at"}:
        try:
            parsed_value = parse_dt(value, settings.timezone)
        except ValueError:
            await message.answer("Неверный формат даты/времени. Используйте YYYY-MM-DD HH:MM")
            return
    elif field in {"capacity", "team_min_size", "team_max_size"}:
        try:
            parsed_value = int(value)
        except ValueError:
            await message.answer("Введите целое число.")
            return
    elif field in {"description", "photo_file_id"}:
        parsed_value = None if value == "-" else value
    else:
        parsed_value = value

    await _apply_event_edit(
        message=message,
        state=state,
        field=field,
        parsed_value=parsed_value,
    )


@admin_router.message(F.text == ADMIN_BTN_DELETE_EVENT)
async def delete_event_pick(message: Message) -> None:
    if not await _ensure_admin(message):
        return

    async with AsyncSessionLocal() as session:
        events = await EventService(session).list_all()

    if not events:
        await message.answer("Пока нет мероприятий для удаления.")
        return

    await message.answer(
        "Выберите мероприятие для удаления:",
        reply_markup=events_admin_list_kb(events, prefix="delete_event"),
    )


@admin_router.callback_query(F.data.startswith("delete_event:"))
async def delete_event_confirm(callback: CallbackQuery) -> None:
    if not await _ensure_admin_cb(callback):
        return

    event_id = int(callback.data.split(":", maxsplit=1)[1])
    async with AsyncSessionLocal() as session:
        event = await EventService(session).get(event_id)

    if not event:
        await callback.message.answer("Мероприятие не найдено.")
        await callback.answer()
        return

    await callback.message.answer(
        (
            f"⚠️ Удалить мероприятие #{event.id} «{event.title}»?\n"
            "Будут удалены все связанные регистрации и записи уведомлений."
        ),
        reply_markup=yes_no_kb(
            yes_data=f"delete_event_yes:{event.id}",
            no_data=f"delete_event_no:{event.id}",
            yes_text="Да, удалить",
            no_text="Нет",
        ),
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("delete_event_no:"))
async def delete_event_cancel(callback: CallbackQuery) -> None:
    if not await _ensure_admin_cb(callback):
        return

    await callback.message.answer("Удаление отменено.")
    await callback.answer()


@admin_router.callback_query(F.data.startswith("delete_event_yes:"))
async def delete_event_apply(callback: CallbackQuery) -> None:
    if not await _ensure_admin_cb(callback):
        return

    event_id = int(callback.data.split(":", maxsplit=1)[1])
    async with AsyncSessionLocal() as session:
        service = EventService(session)
        event = await service.get(event_id)
        if not event:
            await callback.message.answer("Мероприятие не найдено или уже удалено.")
            await callback.answer()
            return
        title = event.title
        await service.delete(event_id)
        await session.commit()

    await callback.message.answer(f"🗑️ Мероприятие #{event_id} «{title}» удалено.")
    await callback.answer()


@admin_router.message(F.text == ADMIN_BTN_PUBLISH)
async def publish_pick_event(message: Message) -> None:
    if not await _ensure_admin(message):
        return

    async with AsyncSessionLocal() as session:
        events = await EventService(session).list_all()

    draft_events = [event for event in events if event.status == EventStatus.draft]
    if not draft_events:
        await message.answer("Нет черновиков для запуска. Сначала создайте мероприятие.")
        return

    await message.answer(
        "Выберите черновик, который нужно запустить:",
        reply_markup=events_admin_list_kb(draft_events, prefix="publish_event"),
    )


@admin_router.callback_query(F.data.startswith("publish_event:"))
async def publish_event_pick_mode(callback: CallbackQuery) -> None:
    if not await _ensure_admin_cb(callback):
        return

    event_id = int(callback.data.split(":", maxsplit=1)[1])
    await callback.message.answer(
        "Как запустить мероприятие?",
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
            "✅ Мероприятие запущено.\n"
            f"Личных уведомлений отправлено: {outcome.notifications_sent}."
        )
    else:
        await callback.message.answer("Это мероприятие уже было запущено ранее.")
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
        f"Введите дату и время запуска в {settings.timezone}\n"
        "Формат: YYYY-MM-DD HH:MM",
    )
    await callback.answer()


@admin_router.message(PublishScheduleStates.publish_at)
async def publish_event_later_save(message: Message, state: FSMContext) -> None:
    if not await _ensure_admin(message):
        return

    try:
        publish_at = parse_dt(message.text, settings.timezone)
    except ValueError:
        await message.answer(
            f"Не могу распознать дату/время. Формат: YYYY-MM-DD HH:MM ({settings.timezone})."
        )
        return

    if publish_at <= datetime.now(tz=UTC):
        await message.answer("Дата запуска должна быть в будущем.")
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
        f"✅ Запуск события #{event.id} запланирован на {format_dt_tz(publish_at)}.",
    )


@admin_router.message(F.text == ADMIN_BTN_REGISTRATIONS)
async def admin_regs_pick(message: Message) -> None:
    if not await _ensure_admin(message):
        return

    async with AsyncSessionLocal() as session:
        events = await EventService(session).list_all()
    if not events:
        await message.answer("Пока нет мероприятий.")
        return

    await message.answer(
        "Выберите мероприятие, чтобы посмотреть заявки:",
        reply_markup=events_admin_list_kb(events, prefix="admin_regs"),
    )


@admin_router.callback_query(F.data.startswith("admin_regs:"))
async def admin_regs_show(callback: CallbackQuery) -> None:
    if not await _ensure_admin_cb(callback):
        return

    event_id = int(callback.data.split(":", maxsplit=1)[1])
    async with AsyncSessionLocal() as session:
        event = await EventService(session).get(event_id)
        regs = await RegistrationRepository(session).list_by_event(event_id)

    if not regs:
        await callback.message.answer("На это мероприятие пока нет заявок.")
        await callback.answer()
        return

    status_counts: dict[str, int] = {}
    for reg in regs:
        status_counts[reg.status.value] = status_counts.get(reg.status.value, 0) + 1

    header = (
        f"🧾 Регистрации на событие #{event_id}"
        + (f": {event.title}" if event else "")
        + "\n"
    )
    if event:
        header += (
            f"📍 Место: {event.location}\n"
            f"🗓 Время: {format_dt_tz(event.start_at)}\n"
        )
    header += f"👥 Всего: {len(regs)}"
    if status_counts:
        header += " | " + ", ".join(
            f"{_registration_status_label(RegistrationStatus(status))}: {count}"
            for status, count in sorted(status_counts.items())
        )

    blocks: list[str] = []
    for reg in regs[:50]:
        captain = next((p for p in reg.people if p.role.value in {"captain", "solo"}), None)
        who = f"{captain.last_name} {captain.first_name}" if captain else f"user:{reg.user_id}"
        mipt_flag = "🚧 есть не с Физтеха" if reg.has_not_mipt_members else "🏫 все с Физтеха"
        team = reg.team_name or "—"
        team_size = reg.team_size if reg.team_size is not None else "—"

        blocks.append(
            "\n".join(
                [
                    f"#{reg.id} | {_registration_status_label(reg.status)}",
                    f"👤 {who}",
                    f"👥 Команда: {team} (размер: {team_size})",
                    f"{mipt_flag}",
                    f"🕒 Создано: {format_dt_tz(reg.created_at)}",
                ]
            )
        )

    tail = ""
    if len(regs) > 50:
        tail = f"\n\nПоказаны первые 50 заявок из {len(regs)}."

    await callback.message.answer(header + "\n\n" + "\n\n".join(blocks) + tail)
    await callback.answer()


@admin_router.message(F.text == ADMIN_BTN_WAITLIST)
async def admin_waitlist_pick(message: Message) -> None:
    if not await _ensure_admin(message):
        return

    async with AsyncSessionLocal() as session:
        events = await EventService(session).list_all()

    if not events:
        await message.answer("Пока нет мероприятий.")
        return

    await message.answer(
        "Выберите мероприятие, чтобы посмотреть лист ожидания:",
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
        await callback.message.answer("Лист ожидания по этому мероприятию пуст.")
        await callback.answer()
        return

    lines = [f"⏳ Лист ожидания (FIFO), событие #{event_id}:"]
    for idx, reg in enumerate(waitlist, start=1):
        lines.append(
            f"{idx}. заявка #{reg.id} | user_id={reg.user_id} | {format_dt_tz(reg.created_at)}"
        )
    await callback.message.answer("\n".join(lines))
    await callback.answer()


@admin_router.message(F.text == ADMIN_BTN_EXPORT)
async def admin_export_pick(message: Message) -> None:
    if not await _ensure_admin(message):
        return

    async with AsyncSessionLocal() as session:
        events = await EventService(session).list_all()

    if not events:
        await message.answer("Пока нет мероприятий для выгрузки.")
        return

    await message.answer(
        "Выберите мероприятие для выгрузки:",
        reply_markup=events_admin_list_kb(events, prefix="admin_export"),
    )


@admin_router.callback_query(F.data.startswith("admin_export:"))
async def admin_export_show(callback: CallbackQuery) -> None:
    if not await _ensure_admin_cb(callback):
        return

    event_id = int(callback.data.split(":", maxsplit=1)[1])
    await callback.message.answer(
        "Выберите вариант выгрузки:",
        reply_markup=export_kind_kb(event_id),
    )
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


@admin_router.message(F.text == ADMIN_BTN_SETTINGS)
async def settings_info(message: Message) -> None:
    if not await _ensure_admin(message):
        return

    await message.answer(
        "⚙️ Текущие настройки:\n"
        f"• Часовой пояс: {settings.timezone}\n"
        f"• CHANNEL_ID: {settings.channel_id}\n"
        "• Тексты уведомлений меняются в коде (`app/services`)."
    )


@admin_router.message(F.text == ADMIN_BTN_ADMINS)
async def admins_info(message: Message) -> None:
    if not await _ensure_admin(message):
        return

    async with AsyncSessionLocal() as session:
        admins = await AdminService(session).repo.list_admins()

    lines = ["👮 Администраторы:"]
    lines.extend(str(item.tg_id) for item in admins)
    lines.append(f"ADMIN_IDS из .env: {settings.admin_ids}")
    lines.append("Команды: /add_admin <tg_id> и /remove_admin <tg_id>")
    await message.answer("\n".join(lines))


@admin_router.message(Command("add_admin"))
async def add_admin(message: Message) -> None:
    if not await _ensure_admin(message):
        return

    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Формат команды: /add_admin <tg_id>")
        return

    async with AsyncSessionLocal() as session:
        admin_service = AdminService(session)
        if not await admin_service.is_super_admin(message.from_user.id):
            await message.answer("Добавлять админов может только super-admin.")
            return

        await admin_service.add_admin(int(parts[1]), message.from_user.id)
        await session.commit()

    await message.answer("✅ Администратор добавлен.")


@admin_router.message(Command("remove_admin"))
async def remove_admin(message: Message) -> None:
    if not await _ensure_admin(message):
        return

    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Формат команды: /remove_admin <tg_id>")
        return

    async with AsyncSessionLocal() as session:
        admin_service = AdminService(session)
        if not await admin_service.is_super_admin(message.from_user.id):
            await message.answer("Удалять админов может только super-admin.")
            return

        removed = await admin_service.remove_admin(int(parts[1]))
        await session.commit()

    await message.answer(
        "✅ Администратор удален." if removed else "Админ не найден или это super-admin."
    )


@admin_router.message(Command("health"))
async def healthcheck(message: Message) -> None:
    if not await _ensure_admin(message):
        return

    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT 1"))
    await message.answer("✅ Healthcheck: DB доступна, бот работает.")


@admin_router.message(Command("rebuild_scheduler"))
async def rebuild_scheduler(message: Message) -> None:
    if not await _ensure_admin(message):
        return
    await message.answer(
        "Планировщик Celery Beat подхватывает события автоматически.\n"
        "Ручная пересборка сейчас не требуется."
    )


@admin_router.message(Command("reschedule_event"))
async def reschedule_event(message: Message) -> None:
    if not await _ensure_admin(message):
        return
    await message.answer(
        "Планировщик использует динамический подбор по времени.\n"
        "Ручная перепланировка события не нужна."
    )


@admin_router.message(Command("backup_db"))
async def backup_info(message: Message) -> None:
    if not await _ensure_admin(message):
        return
    await message.answer(
        "📦 Бэкап БД можно сделать так:\n"
        "`docker compose exec db pg_dump -U postgres hb_bot > backup.sql`"
    )
