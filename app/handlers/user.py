from __future__ import annotations

from datetime import UTC, date, datetime

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.db import AsyncSessionLocal
from app.handlers.states import ProfileStates, RegistrationStates
from app.keyboards.common import main_menu_kb
from app.keyboards.events import event_card_kb, events_list_kb, group_choice_kb, pd_consent_kb, yes_no_kb
from app.models import RegistrationStatus
from app.repositories.events import EventRepository
from app.repositories.registrations import RegistrationRepository
from app.repositories.users import UserRepository
from app.services.exceptions import ValidationError
from app.services.profile_service import ProfileService
from app.services.registration_service import RegistrationService
from app.services.schemas import PassportInput, PersonInput, RegistrationInput
from app.utils.text import format_dt_tz, render_event_card

user_router = Router(name="user")

HELP_TEXT = (
    "🤝 Я помогу зарегистрироваться на мероприятия ФПМИ.\n\n"
    "Что умею:\n"
    "• показываю актуальные мероприятия\n"
    "• регистрирую и снимаю с регистрации\n"
    "• веду лист ожидания\n"
    "• храню профиль для автозаполнения\n\n"
    "💡 Важно: отменить регистрацию можно в любое время."
)

PD_CONSENT_TEXT = (
    "🔐 Нажимая «Согласен(на)», вы даёте согласие организаторам на обработку "
    "ваших персональных данных, включая паспортные данные, исключительно для "
    "оформления пропуска на территорию кампуса и организации участия в мероприятии. "
    "Доступ к данным имеют только администраторы."
)


def _parse_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def _fmt_profile_hint(value: str | None) -> str:
    if value:
        return f" или '-' для сохранённого ({value})"
    return ""


def _auto_contact_from_username(username: str | None) -> str | None:
    return f"@{username}" if username else None


def _passport_review_kb(event_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Ок", callback_data=f"passport_ok:{event_id}")],
            [InlineKeyboardButton(text="✍️ Заполнить заново", callback_data=f"passport_refill:{event_id}")],
        ]
    )


def _refill_help_kb(event_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть мероприятие", callback_data=f"event_open:{event_id}")],
            [InlineKeyboardButton(text="Мои регистрации", callback_data="my_regs")],
        ]
    )


async def _continue_captain_flow(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    profile = data.get("profile", {})
    captain = data.get("captain", {})

    if not captain.get("last_name"):
        saved = profile.get("last_name")
        if saved:
            captain["last_name"] = saved
            await state.update_data(captain=captain)
        else:
            await state.set_state(RegistrationStates.last_name)
            await message.answer("📝 Фамилия капитана/участника:")
            return

    if not captain.get("first_name"):
        saved = profile.get("first_name")
        if saved:
            captain["first_name"] = saved
            await state.update_data(captain=captain)
        else:
            await state.set_state(RegistrationStates.first_name)
            await message.answer("🙂 Имя:")
            return

    if "middle_name" not in captain:
        saved = profile.get("middle_name")
        if saved:
            captain["middle_name"] = saved
            await state.update_data(captain=captain)
        else:
            await state.set_state(RegistrationStates.middle_name)
            await message.answer("📝 Отчество (опционально, '-' если нет):")
            return

    if not captain.get("contact"):
        saved_contact = (
            profile.get("contact")
            or _auto_contact_from_username(message.from_user.username)
            or f"id:{message.from_user.id}"
        )
        captain["contact"] = saved_contact
        await state.update_data(captain=captain)

    if captain.get("is_not_mipt") is None and profile.get("is_not_mipt") is not None:
        captain["is_not_mipt"] = bool(profile.get("is_not_mipt"))
        if captain["is_not_mipt"]:
            if (
                profile.get("passport_series")
                and profile.get("passport_number")
                and profile.get("passport_issue_date")
            ):
                captain["passport"] = {
                    "series": profile["passport_series"],
                    "number": profile["passport_number"],
                    "issue_date": profile["passport_issue_date"],
                }
        else:
            if profile.get("group_name"):
                captain["group_name"] = profile["group_name"]
        await state.update_data(captain=captain)

    if captain.get("is_not_mipt") is True:
        captain["group_name"] = None
        pending_after_consent = "captain_ready" if captain.get("passport") else "captain_passport"
        await state.update_data(captain=captain, pending_after_consent=pending_after_consent)
        await state.set_state(RegistrationStates.pd_consent)
        await message.answer(PD_CONSENT_TEXT, reply_markup=pd_consent_kb())
        return

    if captain.get("group_name"):
        captain["is_not_mipt"] = False
        await state.update_data(captain=captain)
        await _after_captain_ready(message, state)
        return

    saved_group = profile.get("group_name")
    if saved_group:
        captain["group_name"] = saved_group
        captain["is_not_mipt"] = False
        await state.update_data(captain=captain)
        await _after_captain_ready(message, state)
        return

    await state.set_state(RegistrationStates.group_or_not_mipt)
    await message.answer(
        "🏫 Укажите, участник с Физтеха или нет:",
        reply_markup=group_choice_kb(),
    )


@user_router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    async with AsyncSessionLocal() as session:
        repo = UserRepository(session)
        await repo.ensure_user(
            tg_id=message.from_user.id,
            username=message.from_user.username,
        )
        await session.commit()

    await message.answer(
        "👋 Привет! Рад видеть тебя в системе регистрации ФПМИ.\nВыбери нужный раздел в меню ниже.",
        reply_markup=main_menu_kb(),
    )


@user_router.message(F.text == "ℹ️ Помощь")
async def help_message(message: Message) -> None:
    await message.answer(HELP_TEXT)


@user_router.message(F.text == "📅 Мероприятия")
async def list_events(message: Message) -> None:
    async with AsyncSessionLocal() as session:
        events = await EventRepository(session).list_published(datetime.now(tz=UTC))

    if not events:
        await message.answer("📭 Пока нет активных мероприятий. Как только появятся — я сразу покажу.")
        return

    await message.answer("📌 Вот что доступно сейчас:", reply_markup=events_list_kb(events))


@user_router.callback_query(F.data == "events_back")
async def events_back(callback: CallbackQuery) -> None:
    await callback.message.answer("↩️ Нажми «📅 Мероприятия», чтобы снова открыть список.")
    await callback.answer()


@user_router.callback_query(F.data.startswith("event_open:"))
async def open_event(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split(":", maxsplit=1)[1])

    async with AsyncSessionLocal() as session:
        event = await EventRepository(session).get(event_id)
        user = await UserRepository(session).get_by_tg_id(callback.from_user.id)
        if not event or not user:
            await callback.answer("⚠️ Событие не найдено", show_alert=True)
            return

        existing = await RegistrationRepository(session).active_registration_for_user_event(
            user_id=user.id,
            event_id=event.id,
        )

    now = datetime.now(tz=UTC)
    can_register = (
        event.registration_start_at <= now <= event.registration_end_at
        and event.status.value == "published"
        and not existing
    )
    can_cancel = existing is not None
    if can_cancel:
        reg_note = "✅ У тебя уже есть активная регистрация."
    elif now < event.registration_start_at:
        reg_note = (
            "⏳ Регистрация еще не открыта.\n"
            f"Старт: {format_dt_tz(event.registration_start_at)}."
        )
    elif now > event.registration_end_at:
        reg_note = "🚫 Регистрация уже закрыта."
    else:
        reg_note = "🟢 Регистрация открыта."

    await callback.message.answer(
        render_event_card(event) + "\n\n" + reg_note,
        reply_markup=event_card_kb(event.id, can_register=can_register, can_cancel=can_cancel),
    )
    await callback.answer()


@user_router.callback_query(F.data == "my_regs")
@user_router.message(F.text == "🧾 Мои регистрации")
async def my_regs(update: Message | CallbackQuery) -> None:
    if isinstance(update, CallbackQuery):
        tg_id = update.from_user.id
        send = update.message.answer
    else:
        tg_id = update.from_user.id
        send = update.answer

    async with AsyncSessionLocal() as session:
        user = await UserRepository(session).get_by_tg_id(tg_id)
        if not user:
            await send("ℹ️ Сначала отправь /start, чтобы активировать профиль.")
            return

        regs = await RegistrationRepository(session).list_by_user(user.id)

    if not regs:
        await send("🧾 Пока нет регистраций. Загляни в «📅 Мероприятия».")
        return

    event_blocks = []
    for reg in regs:
        block = (
            f"#{reg.id} | {reg.event.title} | {reg.status.value}\n"
            f"\t📍 {reg.event.location}\n"
            f"\t🗓 {format_dt_tz(reg.event.start_at)}"
        )
        if reg.team_name:
            block += f"\n\t👥 команда: {reg.team_name}"
        event_blocks.append(block)
    await send("🗂 Твои регистрации:\n\n" + "\n\n".join(event_blocks))

    if isinstance(update, CallbackQuery):
        await update.answer()


@user_router.message(F.text == "🕒 Лист ожидания")
async def my_waitlist(message: Message) -> None:
    async with AsyncSessionLocal() as session:
        user = await UserRepository(session).get_by_tg_id(message.from_user.id)
        if not user:
            await message.answer("ℹ️ Сначала отправь /start, чтобы активировать профиль.")
            return

        regs = await RegistrationRepository(session).list_by_user(user.id)

    waitlist_regs = [r for r in regs if r.status == RegistrationStatus.waitlist]
    if not waitlist_regs:
        await message.answer("🕒 Сейчас ты не в листе ожидания.")
        return

    lines = ["🕒 Лист ожидания:"]
    for reg in waitlist_regs:
        lines.append(f"#{reg.id} | {reg.event.title}")
    await message.answer("\n".join(lines))


@user_router.callback_query(F.data.startswith("passport_check:"))
async def passport_check(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split(":", maxsplit=1)[1])

    async with AsyncSessionLocal() as session:
        user = await UserRepository(session).get_by_tg_id(callback.from_user.id)
        if not user:
            await callback.answer("ℹ️ Сначала отправь /start", show_alert=True)
            return

        regs = await RegistrationRepository(session).list_by_user(user.id)

    reg = next(
        (
            item for item in regs
            if item.event_id == event_id
            and item.status in (
                RegistrationStatus.registered,
                RegistrationStatus.invited_from_waitlist,
                RegistrationStatus.confirmed,
            )
        ),
        None,
    )
    if not reg:
        await callback.answer("⚠️ Активная регистрация не найдена", show_alert=True)
        return

    not_mipt_people = [p for p in reg.people if p.is_not_mipt]
    if not not_mipt_people:
        await callback.answer("⚠️ Для этой регистрации нет данных для проходки", show_alert=True)
        return

    lines = ["🛂 Паспортные данные для проходки:"]
    for idx, person in enumerate(not_mipt_people, start=1):
        fio = " ".join(part for part in [person.last_name, person.first_name, person.middle_name] if part)
        lines.append(
            "\n".join(
                [
                    f"{idx}. {fio}",
                    f"\tСерия: {person.passport_series or '-'}",
                    f"\tНомер: {person.passport_number or '-'}",
                    f"\tДата выдачи: {person.passport_issue_date:%d.%m.%Y}" if person.passport_issue_date else "\tДата выдачи: -",
                ]
            )
        )

    await callback.message.answer(
        "\n\n".join(lines),
        reply_markup=_passport_review_kb(event_id),
    )
    await callback.answer()


@user_router.callback_query(F.data.startswith("passport_ok:"))
async def passport_ok(callback: CallbackQuery) -> None:
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await callback.answer("Принято ✅")


@user_router.callback_query(F.data.startswith("passport_refill:"))
async def passport_refill(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split(":", maxsplit=1)[1])
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await callback.message.answer(
        "Чтобы заполнить данные заново, нужно отменить текущую регистрацию и зарегистрироваться снова.",
        reply_markup=_refill_help_kb(event_id),
    )
    await callback.answer()


@user_router.callback_query(F.data.startswith("cancel_event:"))
async def cancel_event(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split(":", maxsplit=1)[1])
    async with AsyncSessionLocal() as session:
        user = await UserRepository(session).get_by_tg_id(callback.from_user.id)
        if not user:
            await callback.answer("ℹ️ Сначала отправь /start", show_alert=True)
            return

        reg_repo = RegistrationRepository(session)
        reg = await reg_repo.active_registration_for_user_event(user.id, event_id)
        if not reg:
            await callback.answer("⚠️ Активная регистрация не найдена", show_alert=True)
            return

        service = RegistrationService(session)
        await service.cancel_registration(user.id, reg.id)
        await session.commit()

    await callback.message.answer("✅ Готово, регистрация отменена.")
    await callback.answer()


@user_router.callback_query(F.data.startswith("register_event:"))
async def register_event_start(callback: CallbackQuery, state: FSMContext) -> None:
    event_id = int(callback.data.split(":", maxsplit=1)[1])

    async with AsyncSessionLocal() as session:
        event = await EventRepository(session).get(event_id)
        user = await UserRepository(session).get_by_tg_id(callback.from_user.id)
        if not event or not user:
            await callback.answer("⚠️ Событие не найдено", show_alert=True)
            return

        existing = await RegistrationRepository(session).active_registration_for_user_event(user.id, event_id)
        if existing:
            await callback.answer("ℹ️ У тебя уже есть активная регистрация", show_alert=True)
            return

        profile = {
            "last_name": user.last_name,
            "first_name": user.first_name,
            "middle_name": user.middle_name,
            "contact": user.contact or (f"@{user.username}" if user.username else None),
            "is_not_mipt": user.is_not_mipt,
            "group_name": user.group_name,
            "passport_series": user.passport_series,
            "passport_number": user.passport_number,
            "passport_issue_date": user.passport_issue_date.isoformat() if user.passport_issue_date else None,
        }

    await state.clear()
    await state.update_data(
        event_id=event.id,
        event_type=event.type.value,
        team_min_size=event.team_min_size,
        team_max_size=event.team_max_size,
        profile=profile,
        captain={},
        not_mipt_members=[],
        pd_consent=False,
    )
    await _continue_captain_flow(callback.message, state)
    await callback.answer()


@user_router.message(RegistrationStates.last_name)
async def reg_last_name(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    value = message.text.strip()
    if not value:
        await message.answer("⚠️ Фамилия обязательна.")
        return
    captain = data["captain"]
    captain["last_name"] = value
    await state.update_data(captain=captain)
    await _continue_captain_flow(message, state)


@user_router.message(RegistrationStates.first_name)
async def reg_first_name(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    value = message.text.strip()
    if not value:
        await message.answer("⚠️ Имя обязательно.")
        return
    captain = data["captain"]
    captain["first_name"] = value
    await state.update_data(captain=captain)
    await _continue_captain_flow(message, state)


@user_router.message(RegistrationStates.middle_name)
async def reg_middle_name(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    value = message.text.strip()
    captain = data["captain"]
    captain["middle_name"] = value if value and value != "-" else None
    await state.update_data(captain=captain)
    await _continue_captain_flow(message, state)


@user_router.message(RegistrationStates.contact)
async def reg_contact(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    value = message.text.strip()
    if not value and message.from_user.username:
        value = f"@{message.from_user.username}"
    if not value:
        await message.answer("⚠️ Контакт обязателен.")
        return
    captain = data["captain"]
    captain["contact"] = value
    await state.update_data(captain=captain)
    await _continue_captain_flow(message, state)


@user_router.callback_query(RegistrationStates.group_or_not_mipt, F.data.in_({"group_mipt", "group_not_mipt"}))
async def reg_group_choice(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    captain = data["captain"]

    if callback.data == "group_mipt":
        captain["is_not_mipt"] = False
        captain["passport"] = None
        saved_group = data.get("profile", {}).get("group_name")
        if saved_group:
            captain["group_name"] = saved_group
            await state.update_data(captain=captain)
            await _after_captain_ready(callback.message, state)
        else:
            await state.update_data(captain=captain)
            await state.set_state(RegistrationStates.group_name)
            await callback.message.answer("🏫 Группа (например, Б01-...):")
    else:
        captain["is_not_mipt"] = True
        captain["group_name"] = None
        saved_profile = data.get("profile", {})
        if (
            saved_profile.get("passport_series")
            and saved_profile.get("passport_number")
            and saved_profile.get("passport_issue_date")
        ):
            captain["passport"] = {
                "series": saved_profile["passport_series"],
                "number": saved_profile["passport_number"],
                "issue_date": saved_profile["passport_issue_date"],
            }
            pending_after_consent = "captain_ready"
        else:
            pending_after_consent = "captain_passport"
        await state.update_data(captain=captain, pending_after_consent=pending_after_consent)
        await state.set_state(RegistrationStates.pd_consent)
        await callback.message.answer(PD_CONSENT_TEXT, reply_markup=pd_consent_kb())

    await callback.answer()


@user_router.message(RegistrationStates.group_name)
async def reg_group_name(message: Message, state: FSMContext) -> None:
    value = message.text.strip()
    if not value:
        await message.answer("⚠️ Группа обязательна для участников с Физтеха.")
        return

    data = await state.get_data()
    captain = data["captain"]
    captain["group_name"] = value
    captain["is_not_mipt"] = False
    captain["passport"] = None
    await state.update_data(captain=captain)

    await _after_captain_ready(message, state)


@user_router.callback_query(RegistrationStates.pd_consent, F.data == "pd_consent_yes")
async def reg_pd_consent(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.update_data(pd_consent=True)

    pending = data.get("pending_after_consent")
    if pending == "captain_passport":
        await state.update_data(passport_target="captain", passport_data={})
        await state.set_state(RegistrationStates.passport_series)
        await callback.message.answer("🛂 Паспорт: серия")
    elif pending == "captain_ready":
        await _after_captain_ready(callback.message, state)
    elif pending == "team_members":
        await state.update_data(current_member_idx=0, current_member={})
        await state.set_state(RegistrationStates.member_last_name)
        await callback.message.answer("👤 Участник 1 (не с Физтеха): фамилия")
    else:
        await callback.message.answer("✅ Согласие сохранено.")

    await callback.answer()


async def _after_captain_ready(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data["event_type"] == "team":
        await state.set_state(RegistrationStates.team_name)
        await message.answer("🏷 Название команды:")
        return

    await _finalize_registration(message, state)


@user_router.message(RegistrationStates.team_name)
async def reg_team_name(message: Message, state: FSMContext) -> None:
    value = message.text.strip()
    if not value:
        await message.answer("⚠️ Название команды обязательно.")
        return
    await state.update_data(team_name=value)
    await state.set_state(RegistrationStates.team_size)

    data = await state.get_data()
    team_min = data.get("team_min_size")
    team_max = data.get("team_max_size")
    await message.answer(f"👥 Размер команды ({team_min}-{team_max}):")


@user_router.message(RegistrationStates.team_size)
async def reg_team_size(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    try:
        size = int(message.text.strip())
    except ValueError:
        await message.answer("🔢 Введите целое число.")
        return

    team_min = data.get("team_min_size")
    team_max = data.get("team_max_size")
    if (team_min and size < team_min) or (team_max and size > team_max):
        await message.answer(f"⚠️ Размер команды должен быть в диапазоне {team_min}-{team_max}.")
        return

    await state.update_data(team_size=size)
    await state.set_state(RegistrationStates.team_has_not_mipt)
    await message.answer(
        "❓ Есть ли участники не с Физтеха?",
        reply_markup=yes_no_kb("team_not_mipt_yes", "team_not_mipt_no"),
    )


@user_router.callback_query(RegistrationStates.team_has_not_mipt, F.data.in_({"team_not_mipt_yes", "team_not_mipt_no"}))
async def reg_team_not_mipt(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data == "team_not_mipt_no":
        await _finalize_registration(callback.message, state)
    else:
        await state.set_state(RegistrationStates.not_mipt_count)
        await callback.message.answer("🔢 Сколько участников не с Физтеха? (целое число)")
    await callback.answer()


@user_router.message(RegistrationStates.not_mipt_count)
async def reg_not_mipt_count(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    try:
        count = int(message.text.strip())
    except ValueError:
        await message.answer("🔢 Введите целое число.")
        return

    team_size = int(data.get("team_size") or 0)
    if count <= 0 or count > team_size:
        await message.answer("⚠️ Количество должно быть > 0 и не больше размера команды.")
        return

    await state.update_data(member_target_count=count)
    if not data.get("pd_consent"):
        await state.update_data(pending_after_consent="team_members")
        await state.set_state(RegistrationStates.pd_consent)
        await message.answer(PD_CONSENT_TEXT, reply_markup=pd_consent_kb())
        return

    await state.update_data(current_member_idx=0, current_member={})
    await state.set_state(RegistrationStates.member_last_name)
    await message.answer("👤 Участник 1 (не с Физтеха): фамилия")


@user_router.message(RegistrationStates.member_last_name)
async def member_last_name(message: Message, state: FSMContext) -> None:
    value = message.text.strip()
    if not value:
        await message.answer("⚠️ Фамилия обязательна.")
        return
    data = await state.get_data()
    member = data.get("current_member", {})
    member["last_name"] = value
    await state.update_data(current_member=member)
    await state.set_state(RegistrationStates.member_first_name)
    await message.answer("🙂 Имя:")


@user_router.message(RegistrationStates.member_first_name)
async def member_first_name(message: Message, state: FSMContext) -> None:
    value = message.text.strip()
    if not value:
        await message.answer("⚠️ Имя обязательно.")
        return
    data = await state.get_data()
    member = data.get("current_member", {})
    member["first_name"] = value
    await state.update_data(current_member=member)
    await state.set_state(RegistrationStates.member_middle_name)
    await message.answer("📝 Отчество (опционально, '-' если нет):")


@user_router.message(RegistrationStates.member_middle_name)
async def member_middle_name(message: Message, state: FSMContext) -> None:
    value = message.text.strip()
    data = await state.get_data()
    member = data.get("current_member", {})
    member["middle_name"] = None if value == "-" else value
    await state.update_data(current_member=member, passport_target="member", passport_data={})
    await state.set_state(RegistrationStates.passport_series)
    await message.answer("🛂 Паспорт участника: серия")


@user_router.message(RegistrationStates.passport_series)
async def passport_series(message: Message, state: FSMContext) -> None:
    value = message.text.strip()
    if not value:
        await message.answer("⚠️ Серия обязательна.")
        return
    data = await state.get_data()
    passport = data.get("passport_data", {})
    passport["series"] = value
    await state.update_data(passport_data=passport)
    await state.set_state(RegistrationStates.passport_number)
    await message.answer("🛂 Номер паспорта:")


@user_router.message(RegistrationStates.passport_number)
async def passport_number(message: Message, state: FSMContext) -> None:
    value = message.text.strip()
    if not value:
        await message.answer("⚠️ Номер обязателен.")
        return
    data = await state.get_data()
    passport = data.get("passport_data", {})
    passport["number"] = value
    await state.update_data(passport_data=passport)
    await state.set_state(RegistrationStates.passport_issue_date)
    await message.answer("📅 Дата выдачи (YYYY-MM-DD):")


@user_router.message(RegistrationStates.passport_issue_date)
async def passport_issue_date(message: Message, state: FSMContext) -> None:
    value = message.text.strip()
    try:
        parsed = _parse_date(value)
    except ValueError:
        await message.answer("⚠️ Ожидается формат YYYY-MM-DD.")
        return

    data = await state.get_data()
    passport = data.get("passport_data", {})
    passport["issue_date"] = parsed.isoformat()
    await state.update_data(passport_data=passport)

    target = data.get("passport_target")
    if target == "captain":
        captain = data["captain"]
        captain["passport"] = passport
        await state.update_data(captain=captain, passport_data={})
        await _after_captain_ready(message, state)
        return

    if target == "member":
        member = data.get("current_member", {})
        member["passport"] = passport

        not_mipt_members = data.get("not_mipt_members", [])
        not_mipt_members.append(member)

        current_idx = int(data.get("current_member_idx", 0)) + 1
        target_count = int(data.get("member_target_count", 0))

        await state.update_data(
            not_mipt_members=not_mipt_members,
            current_member_idx=current_idx,
            current_member={},
            passport_data={},
        )

        if current_idx < target_count:
            await state.set_state(RegistrationStates.member_last_name)
            await message.answer(f"Участник {current_idx + 1} (не с Физтеха): фамилия")
            return

        await _finalize_registration(message, state)
        return

    await message.answer("⚠️ Внутренняя ошибка сценария регистрации. Начните заново.")
    await state.clear()


async def _finalize_registration(message: Message, state: FSMContext) -> None:
    data = await state.get_data()

    captain = data["captain"]
    captain_passport = captain.get("passport")
    captain_input = PersonInput(
        last_name=captain["last_name"],
        first_name=captain["first_name"],
        middle_name=captain.get("middle_name"),
        contact=captain.get("contact"),
        group_name=captain.get("group_name"),
        is_not_mipt=bool(captain.get("is_not_mipt")),
        passport=(
            PassportInput(
                series=captain_passport["series"],
                number=captain_passport["number"],
                issue_date=_parse_date(captain_passport["issue_date"]),
            )
            if captain_passport
            else None
        ),
    )

    members_input: list[PersonInput] = []
    for member in data.get("not_mipt_members", []):
        passport = member["passport"]
        members_input.append(
            PersonInput(
                last_name=member["last_name"],
                first_name=member["first_name"],
                middle_name=member.get("middle_name"),
                contact=None,
                group_name=None,
                is_not_mipt=True,
                passport=PassportInput(
                    series=passport["series"],
                    number=passport["number"],
                    issue_date=_parse_date(passport["issue_date"]),
                ),
            )
        )

    registration_input = RegistrationInput(
        captain_or_solo=captain_input,
        team_name=data.get("team_name"),
        team_size=data.get("team_size"),
        not_mipt_members=members_input,
        pd_consent=bool(data.get("pd_consent")),
        pd_consent_version="v1",
    )

    async with AsyncSessionLocal() as session:
        user = await UserRepository(session).get_by_tg_id(message.from_user.id)
        if not user:
            await message.answer("ℹ️ Сначала отправь /start, чтобы активировать профиль.")
            return

        service = RegistrationService(session)
        try:
            reg = await service.create_registration(
                user_id=user.id,
                event_id=int(data["event_id"]),
                data=registration_input,
            )
        except ValidationError as exc:
            await message.answer(f"Ошибка регистрации: {exc}")
            return

        await session.commit()

    if reg.status == RegistrationStatus.waitlist:
        await message.answer(
            "Все места уже заняты, но ты в листе ожидания.\n"
            "Если освободится место, сразу напишу."
        )
    else:
        await message.answer("✅ Готово! Регистрация успешно создана.")

    await state.clear()


@user_router.callback_query(F.data.in_({"waitlist_yes", "waitlist_no"}))
async def legacy_waitlist_handler(callback: CallbackQuery) -> None:
    await callback.answer()


@user_router.callback_query(F.data.startswith("waitlist_yes:"))
@user_router.callback_query(F.data.startswith("waitlist_no:"))
async def waitlist_response(callback: CallbackQuery) -> None:
    registration_id = int(callback.data.split(":", maxsplit=1)[1])
    accepted = callback.data.startswith("waitlist_yes:")

    async with AsyncSessionLocal() as session:
        service = RegistrationService(session)
        try:
            await service.respond_waitlist_invite(registration_id=registration_id, accepted=accepted)
            await session.commit()
        except ValidationError as exc:
            await callback.answer(str(exc), show_alert=True)
            return

    await callback.message.answer("✅ Ответ сохранён. Спасибо!")
    await callback.answer()


@user_router.callback_query(F.data.startswith("confirm_yes:"))
@user_router.callback_query(F.data.startswith("confirm_no:"))
async def confirmation_response(callback: CallbackQuery) -> None:
    registration_id = int(callback.data.split(":", maxsplit=1)[1])
    going = callback.data.startswith("confirm_yes:")

    async with AsyncSessionLocal() as session:
        service = RegistrationService(session)
        try:
            await service.respond_confirmation(registration_id=registration_id, going=going)
            await session.commit()
        except ValidationError as exc:
            await callback.answer(str(exc), show_alert=True)
            return

    await callback.message.answer("✅ Ответ на подтверждение сохранён.")
    await callback.answer()


@user_router.message(F.text == "👤 Профиль")
async def profile_view(message: Message) -> None:
    async with AsyncSessionLocal() as session:
        user = await UserRepository(session).get_by_tg_id(message.from_user.id)
        if not user:
            await message.answer("ℹ️ Сначала отправь /start, чтобы активировать профиль.")
            return
        if not user.contact:
            auto_contact = _auto_contact_from_username(user.username)
            if auto_contact:
                user.contact = auto_contact
                await session.commit()

    if user.is_not_mipt is True:
        issue_date_text = user.passport_issue_date.strftime("%d.%m.%Y") if user.passport_issue_date else "-"
        extra = (
            "Статус: Не с Физтеха\n"
            f"Серия паспорта: {user.passport_series or '-'}\n"
            f"Номер паспорта: {user.passport_number or '-'}\n"
            f"Дата выдачи: {issue_date_text}"
        )
    elif user.is_not_mipt is False:
        extra = (
            "Статус: С Физтеха\n"
            f"Группа: {user.group_name or '-'}"
        )
    else:
        extra = "Статус: не указан"

    text = (
        "👤 Твой профиль:\n"
        f"Фамилия: {user.last_name or '-'}\n"
        f"Имя: {user.first_name or '-'}\n"
        f"Отчество: {user.middle_name or '-'}\n"
        f"Контакт: {user.contact or '-'}\n"
        f"{extra}"
    )
    await message.answer(
        text,
        reply_markup=yes_no_kb("profile_edit", "profile_clear", yes_text="Изменить профиль", no_text="Очистить"),
    )


@user_router.callback_query(F.data == "profile_edit")
async def profile_edit_start(callback: CallbackQuery, state: FSMContext) -> None:
    async with AsyncSessionLocal() as session:
        user = await UserRepository(session).get_by_tg_id(callback.from_user.id)
        if user and not user.contact:
            auto_contact = _auto_contact_from_username(user.username)
            if auto_contact:
                user.contact = auto_contact
                await session.commit()
    if not user:
        await callback.answer("ℹ️ Сначала отправь /start", show_alert=True)
        return

    await state.clear()
    await state.update_data(
        profile={
            "last_name": user.last_name,
            "first_name": user.first_name,
            "middle_name": user.middle_name,
            "contact": user.contact,
            "is_not_mipt": user.is_not_mipt,
            "group_name": user.group_name,
            "passport_series": user.passport_series,
            "passport_number": user.passport_number,
            "passport_issue_date": user.passport_issue_date.isoformat() if user.passport_issue_date else None,
        }
    )
    await state.set_state(ProfileStates.last_name)
    await callback.message.answer("📝 Фамилия" + _fmt_profile_hint(user.last_name) + ":")
    await callback.answer()


@user_router.callback_query(F.data == "profile_clear")
async def profile_clear(callback: CallbackQuery) -> None:
    async with AsyncSessionLocal() as session:
        user = await UserRepository(session).get_by_tg_id(callback.from_user.id)
        if not user:
            await callback.answer("ℹ️ Сначала отправь /start", show_alert=True)
            return

        await ProfileService(session).clear(user.id)
        await session.commit()

    await callback.message.answer("🧹 Профиль очищен.")
    await callback.answer()


@user_router.message(ProfileStates.last_name)
async def profile_last_name(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    value = message.text.strip()
    if value == "-":
        value = data["profile"].get("last_name")
    if not value:
        await message.answer("⚠️ Фамилия обязательна.")
        return

    profile = data["profile"]
    profile["last_name"] = value
    await state.update_data(profile=profile)
    await state.set_state(ProfileStates.first_name)
    await message.answer("🙂 Имя" + _fmt_profile_hint(profile.get("first_name")) + ":")


@user_router.message(ProfileStates.first_name)
async def profile_first_name(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    value = message.text.strip()
    if value == "-":
        value = data["profile"].get("first_name")
    if not value:
        await message.answer("⚠️ Имя обязательно.")
        return

    profile = data["profile"]
    profile["first_name"] = value
    await state.update_data(profile=profile)
    await state.set_state(ProfileStates.middle_name)
    await message.answer("📝 Отчество (опционально, '-' чтобы пропустить):")


@user_router.message(ProfileStates.middle_name)
async def profile_middle_name(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    value = message.text.strip()
    profile = data["profile"]
    profile["middle_name"] = None if value == "-" else value
    profile["contact"] = (
        profile.get("contact")
        or _auto_contact_from_username(message.from_user.username)
        or f"id:{message.from_user.id}"
    )
    await state.update_data(profile=profile)
    await state.set_state(ProfileStates.group_or_not_mipt)
    await message.answer(
        "🏫 Укажи, ты с Физтеха или нет:",
        reply_markup=group_choice_kb(),
    )


@user_router.message(ProfileStates.contact)
async def profile_contact(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    value = message.text.strip()
    if value == "-":
        value = data["profile"].get("contact")
    if not value:
        value = _auto_contact_from_username(message.from_user.username)
    if not value:
        await message.answer("⚠️ Контакт обязателен.")
        return

    profile = data["profile"]
    profile["contact"] = value
    await state.update_data(profile=profile)
    await state.set_state(ProfileStates.group_or_not_mipt)
    await message.answer(
        "🏫 Укажи, ты с Физтеха или нет:",
        reply_markup=group_choice_kb(),
    )


async def _save_profile(message: Message, state: FSMContext, profile: dict) -> None:
    async with AsyncSessionLocal() as session:
        user = await UserRepository(session).get_by_tg_id(message.from_user.id)
        if not user:
            await message.answer("ℹ️ Сначала отправь /start, чтобы активировать профиль.")
            return

        passport = None
        if profile.get("is_not_mipt"):
            passport = PassportInput(
                series=profile["passport_series"],
                number=profile["passport_number"],
                issue_date=_parse_date(profile["passport_issue_date"]),
            )

        await ProfileService(session).update(
            user.id,
            PersonInput(
                last_name=profile["last_name"],
                first_name=profile["first_name"],
                middle_name=profile.get("middle_name"),
                contact=profile["contact"],
                group_name=profile.get("group_name"),
                is_not_mipt=bool(profile.get("is_not_mipt")),
                passport=passport,
            ),
        )
        await session.commit()

    await state.clear()
    await message.answer("✅ Профиль обновлён. В следующий раз часть данных подставлю автоматически.")


@user_router.callback_query(ProfileStates.group_or_not_mipt, F.data.in_({"group_mipt", "group_not_mipt"}))
async def profile_group_choice(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    profile = data["profile"]

    if callback.data == "group_mipt":
        profile["is_not_mipt"] = False
        profile["passport_series"] = None
        profile["passport_number"] = None
        profile["passport_issue_date"] = None
        await state.update_data(profile=profile)
        await state.set_state(ProfileStates.group_name)
        await callback.message.answer("🏫 Группа:")
    else:
        profile["is_not_mipt"] = True
        profile["group_name"] = None
        await state.update_data(profile=profile)
        await state.set_state(ProfileStates.passport_series)
        await callback.message.answer("🛂 Серия паспорта:")

    await callback.answer()


@user_router.message(ProfileStates.group_name)
async def profile_group_name(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    value = message.text.strip()
    if not value:
        await message.answer("⚠️ Группа обязательна.")
        return

    profile = data["profile"]
    profile["group_name"] = value
    profile["is_not_mipt"] = False
    await state.update_data(profile=profile)
    await _save_profile(message, state, profile)


@user_router.message(ProfileStates.passport_series)
async def profile_passport_series(message: Message, state: FSMContext) -> None:
    value = message.text.strip()
    if not value:
        await message.answer("⚠️ Серия обязательна.")
        return
    data = await state.get_data()
    profile = data["profile"]
    profile["passport_series"] = value
    await state.update_data(profile=profile)
    await state.set_state(ProfileStates.passport_number)
    await message.answer("🛂 Номер паспорта:")


@user_router.message(ProfileStates.passport_number)
async def profile_passport_number(message: Message, state: FSMContext) -> None:
    value = message.text.strip()
    if not value:
        await message.answer("⚠️ Номер обязателен.")
        return
    data = await state.get_data()
    profile = data["profile"]
    profile["passport_number"] = value
    await state.update_data(profile=profile)
    await state.set_state(ProfileStates.passport_issue_date)
    await message.answer("📅 Дата выдачи (YYYY-MM-DD):")


@user_router.message(ProfileStates.passport_issue_date)
async def profile_passport_issue_date(message: Message, state: FSMContext) -> None:
    value = message.text.strip()
    try:
        parsed = _parse_date(value)
    except ValueError:
        await message.answer("⚠️ Ожидается формат YYYY-MM-DD.")
        return

    data = await state.get_data()
    profile = data["profile"]
    profile["passport_issue_date"] = parsed.isoformat()
    profile["is_not_mipt"] = True
    await state.update_data(profile=profile)
    await _save_profile(message, state, profile)
