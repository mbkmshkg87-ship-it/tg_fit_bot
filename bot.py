import asyncio
import logging
import random
from datetime import date, datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from config import ADMIN_IDS, BOT_TOKEN, TZ, WEEKDAYS_RU
from data import (
    CYCLE_HELP,
    HORMONES,
    NUTRITION,
    TIPS,
    WORKOUTS,
    calc_kbju,
    cycle_info,
    format_subs,
    format_workout,
    get_exercise,
)
from db import (
    add_weight,
    count_videos,
    get_user,
    get_videos,
    init_db,
    list_weight,
    save_video,
    upsert_user,
    users_with_reminders,
)
from keyboards import (
    activity_ikb,
    cycle_ikb,
    day_extra_ikb,
    days_ikb,
    goal_ikb,
    hormones_ikb,
    main_kb,
    nutrition_ikb,
    remind_ikb,
    sex_ikb,
    video_action_ikb,
    video_days_ikb,
    video_ex_ikb,
    weight_ikb,
    workouts_ikb,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("fitbot")


class Profile(StatesGroup):
    age = State()
    height = State()
    weight = State()


class Extra(StatesGroup):
    weight_log = State()
    remind_time = State()
    cycle_start = State()
    cycle_len = State()
    video_file = State()
    video_url = State()


WELCOME = (
    "<b>FIT CORE</b> — тренировки, еда, вес, цикл и техника на видео.\n\n"
    "• 4 дня + замены упражнений\n"
    "• питание и калькулятор БЖУ\n"
    "• лог веса и напоминания\n"
    "• фазы цикла и нагрузка\n"
    "• библиотека видео: свои ролики и ссылки YouTube/VK\n\n"
    "Гормоны и цикл — образование, не лечение."
)

WEEK = (
    "<b>Неделя</b>\n"
    "Пн — День 1 (грудь + бицепс)\n"
    "Вт — День 2 (спина + трицепс)\n"
    "Ср — отдых / ходьба 40–60 мин\n"
    "Чт — День 3 (ноги + плечи)\n"
    "Пт — День 4 (круговая всё тело)\n"
    "Сб — активность без отказа\n"
    "Вс — полный отдых\n\n"
    "Не восстановился — День 4 меняешь на прогулку."
)


def parse_date(text: str) -> date | None:
    text = text.strip()
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def fmt_days(raw: str) -> str:
    chosen = [WEEKDAYS_RU[int(x)] for x in (raw or "").split(",") if x.isdigit()]
    return ", ".join(chosen) or "не выбраны"


async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await upsert_user(message.from_user.id, name=message.from_user.full_name)
    await message.answer(WELCOME, reply_markup=main_kb(), parse_mode="HTML")


async def cmd_help(message: Message):
    await message.answer(
        "/start — меню\n"
        "/help — команды\n\n"
        "Видео: открой «🎬 Видео» → день → упражнение → загрузи ролик или ссылку.\n"
        "Админ: свой file_id пишется как общий шаблон техники (owner_id=0), "
        "если твой Telegram id в ADMIN_IDS."
    )


async def show_workouts(message: Message):
    await message.answer(
        "День целиком. Потом замены или видео техники.",
        reply_markup=workouts_ikb(),
    )


async def show_nutrition(message: Message):
    await message.answer("Питание — выбери блок.", reply_markup=nutrition_ikb())


async def show_hormones(message: Message):
    await message.answer(f"{HORMONES['disclaimer']}\n\nЧто разобрать?", reply_markup=hormones_ikb())


async def show_tip(message: Message):
    await message.answer("💡 " + random.choice(TIPS))


def profile_text(row) -> str:
    if not row:
        return "Профиль пустой. Пройди калькулятор."
    sex = {"m": "муж", "f": "жен"}.get(row["sex"] or "", "—")
    goal = {"cut": "сушка", "keep": "поддержание", "bulk": "набор"}.get(row["goal"] or "", "—")
    act = {
        "low": "сидячий",
        "mid": "лёгкая",
        "high": "тренировки 3–5×",
        "sport": "тяжёлые тренировки",
    }.get(row["activity"] or "", "—")
    rem = "вкл" if row["remind_on"] else "выкл"
    return (
        f"<b>Профиль</b>\n"
        f"Имя: {row['name'] or '—'}\n"
        f"Пол: {sex}\n"
        f"Возраст: {row['age'] or '—'}\n"
        f"Рост: {row['height'] or '—'} см\n"
        f"Вес: {row['weight'] or '—'} кг\n"
        f"Активность: {act}\n"
        f"Цель: {goal}\n"
        f"Напоминания: {rem}, {row['remind_time'] or '—'} ({fmt_days(row['remind_days'])})\n"
        f"Цикл: {row['cycle_start'] or 'не задан'}, {row['cycle_len'] or 28} дн."
    )


async def show_profile(message: Message):
    row = await get_user(message.from_user.id)
    await message.answer(profile_text(row), parse_mode="HTML")


async def start_calc(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Пол:", reply_markup=sex_ikb())


async def on_sex(cb: CallbackQuery, state: FSMContext):
    sex = cb.data.rsplit("_", 1)[-1]
    await state.update_data(sex=sex)
    await upsert_user(cb.from_user.id, sex=sex)
    await cb.message.edit_text("Возраст (числом, лет):")
    await state.set_state(Profile.age)
    await cb.answer()


async def on_age(message: Message, state: FSMContext):
    if not message.text.isdigit() or not (14 <= int(message.text) <= 80):
        await message.answer("Возраст числом от 14 до 80.")
        return
    await state.update_data(age=int(message.text))
    await upsert_user(message.from_user.id, age=int(message.text))
    await message.answer("Рост в см, например 178:")
    await state.set_state(Profile.height)


async def on_height(message: Message, state: FSMContext):
    try:
        h = float(message.text.replace(",", "."))
        if not (140 <= h <= 230):
            raise ValueError
    except ValueError:
        await message.answer("Рост числом, см.")
        return
    await state.update_data(height=h)
    await upsert_user(message.from_user.id, height=h)
    await message.answer("Вес в кг, например 82.5:")
    await state.set_state(Profile.weight)


async def on_weight(message: Message, state: FSMContext):
    try:
        w = float(message.text.replace(",", "."))
        if not (40 <= w <= 250):
            raise ValueError
    except ValueError:
        await message.answer("Вес числом, кг.")
        return
    await state.update_data(weight=w)
    await upsert_user(message.from_user.id, weight=w)
    await add_weight(message.from_user.id, w)
    await message.answer("Активность:", reply_markup=activity_ikb())
    await state.set_state(None)


async def on_activity(cb: CallbackQuery, state: FSMContext):
    act = cb.data.rsplit("_", 1)[-1]
    await state.update_data(activity=act)
    await upsert_user(cb.from_user.id, activity=act)
    await cb.message.answer("Цель:", reply_markup=goal_ikb())
    await cb.answer()


async def on_goal(cb: CallbackQuery, state: FSMContext):
    goal = cb.data.rsplit("_", 1)[-1]
    await upsert_user(cb.from_user.id, goal=goal)
    data = await state.get_data()
    row = await get_user(cb.from_user.id)
    sex = data.get("sex") or (row["sex"] if row else None)
    age = data.get("age") or (row["age"] if row else None)
    height = data.get("height") or (row["height"] if row else None)
    weight = data.get("weight") or (row["weight"] if row else None)
    activity = data.get("activity") or (row["activity"] if row else None)
    await state.clear()
    if not all([sex, age, height, weight, activity]):
        await cb.message.answer("Данных не хватает. Пройди калькулятор заново.")
        await cb.answer()
        return
    await cb.message.answer(
        calc_kbju(float(weight), float(height), int(age), sex, activity, goal),
        parse_mode="HTML",
    )
    await cb.answer("Готово")


async def on_workout_cb(cb: CallbackQuery):
    key = cb.data.replace("w_", "")
    if key == "week":
        await cb.message.answer(WEEK, parse_mode="HTML")
    else:
        await cb.message.answer(
            format_workout(key),
            parse_mode="HTML",
            reply_markup=day_extra_ikb(key),
        )
    await cb.answer()


async def on_subs(cb: CallbackQuery):
    day = cb.data.replace("sub_", "")
    await cb.message.answer(format_subs(day), parse_mode="HTML")
    await cb.answer()


async def on_nutrition_cb(cb: CallbackQuery):
    mapping = {
        "n_principles": NUTRITION["principles"],
        "n_mass": NUTRITION["meals_mass"],
        "n_cut": NUTRITION["meals_cut"],
        "n_prepost": NUTRITION["prepost"],
    }
    await cb.message.answer(mapping[cb.data])
    await cb.answer()


async def on_hormone_cb(cb: CallbackQuery):
    key = cb.data.replace("h_", "")
    await cb.message.answer(HORMONES["disclaimer"] + "\n\n" + HORMONES[key])
    await cb.answer()


async def show_weight_menu(message: Message):
    rows = await list_weight(message.from_user.id, 3)
    last = f"Последний: {rows[0]['weight']} кг ({rows[0]['day']})" if rows else "Записей ещё нет."
    await message.answer(f"<b>Лог веса</b>\n{last}", parse_mode="HTML", reply_markup=weight_ikb())


async def on_wt_add(cb: CallbackQuery, state: FSMContext):
    await state.set_state(Extra.weight_log)
    await cb.message.answer("Вес в кг, например 74.6")
    await cb.answer()


async def on_weight_log(message: Message, state: FSMContext):
    try:
        w = float(message.text.replace(",", "."))
        if not (30 <= w <= 250):
            raise ValueError
    except ValueError:
        await message.answer("Число, кг.")
        return
    await add_weight(message.from_user.id, w)
    await state.clear()
    hist = await list_weight(message.from_user.id, 8)
    delta = ""
    if len(hist) >= 2:
        d = hist[0]["weight"] - hist[-1]["weight"]
        delta = f"\nЗа период лога: {d:+.1f} кг"
    await message.answer(f"Записал {w} кг.{delta}", reply_markup=main_kb())


async def on_wt_hist(cb: CallbackQuery):
    rows = await list_weight(cb.from_user.id, 14)
    if not rows:
        await cb.message.answer("Пусто. Сначала запиши вес.")
        await cb.answer()
        return
    lines = ["<b>История веса</b>"]
    for r in rows:
        lines.append(f"{r['day']}: {r['weight']} кг")
    if len(rows) >= 2:
        lines.append(f"\nΔ {rows[0]['weight'] - rows[-1]['weight']:+.1f} кг за показанные точки")
    await cb.message.answer("\n".join(lines), parse_mode="HTML")
    await cb.answer()


async def show_cycle(message: Message):
    row = await get_user(message.from_user.id)
    start = row["cycle_start"] if row else None
    length = row["cycle_len"] if row else 28
    await message.answer(cycle_info(start, length), parse_mode="HTML", reply_markup=cycle_ikb())


async def on_cy_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(Extra.cycle_start)
    await cb.message.answer("Дата начала последних месячных: 28.08.2026")
    await cb.answer()


async def on_cycle_start(message: Message, state: FSMContext):
    d = parse_date(message.text)
    if not d:
        await message.answer("Формат ДД.ММ.ГГГГ")
        return
    await upsert_user(message.from_user.id, cycle_start=d.isoformat())
    await state.clear()
    row = await get_user(message.from_user.id)
    await message.answer(cycle_info(row["cycle_start"], row["cycle_len"]), parse_mode="HTML")


async def on_cy_len(cb: CallbackQuery, state: FSMContext):
    await state.set_state(Extra.cycle_len)
    await cb.message.answer("Длина цикла в днях, обычно 28.")
    await cb.answer()


async def on_cycle_len(message: Message, state: FSMContext):
    if not message.text.isdigit() or not (21 <= int(message.text) <= 40):
        await message.answer("Число от 21 до 40.")
        return
    await upsert_user(message.from_user.id, cycle_len=int(message.text))
    await state.clear()
    row = await get_user(message.from_user.id)
    await message.answer(cycle_info(row["cycle_start"], row["cycle_len"]), parse_mode="HTML")


async def on_cy_today(cb: CallbackQuery):
    await upsert_user(cb.from_user.id, cycle_start=date.today().isoformat())
    row = await get_user(cb.from_user.id)
    await cb.message.answer(cycle_info(row["cycle_start"], row["cycle_len"]), parse_mode="HTML")
    await cb.answer("Старт записан")


async def show_remind(message: Message):
    row = await get_user(message.from_user.id)
    on = bool(row["remind_on"]) if row else False
    t = row["remind_time"] if row else "19:00"
    days = fmt_days(row["remind_days"] if row else "0,1,3,4")
    await message.answer(
        f"<b>Напоминания</b>\n"
        f"Статус: {'вкл' if on else 'выкл'}\n"
        f"Время ({TZ.key}): {t}\n"
        f"Дни: {days}\n\n"
        f"Бот должен быть запущен в этот момент (VPS / ПК).",
        parse_mode="HTML",
        reply_markup=remind_ikb(on),
    )


async def on_rm_toggle(cb: CallbackQuery):
    row = await get_user(cb.from_user.id)
    on = 0 if (row and row["remind_on"]) else 1
    await upsert_user(cb.from_user.id, remind_on=on)
    await cb.message.answer("Напоминания включены." if on else "Напоминания выключены.")
    await cb.answer()


async def on_rm_time(cb: CallbackQuery, state: FSMContext):
    await state.set_state(Extra.remind_time)
    await cb.message.answer("Время в формате 19:30")
    await cb.answer()


async def on_remind_time(message: Message, state: FSMContext):
    try:
        datetime.strptime(message.text.strip(), "%H:%M")
    except ValueError:
        await message.answer("Формат ЧЧ:ММ, например 07:30")
        return
    await upsert_user(message.from_user.id, remind_time=message.text.strip())
    await state.clear()
    await message.answer(f"Поставил {message.text.strip()}")


async def on_rm_days(cb: CallbackQuery):
    row = await get_user(cb.from_user.id)
    raw = row["remind_days"] if row and row["remind_days"] else "0,1,3,4"
    await cb.message.answer("Отметь дни:", reply_markup=days_ikb(raw))
    await cb.answer()


async def on_rmd_toggle(cb: CallbackQuery):
    idx = cb.data.replace("rmd_", "")
    row = await get_user(cb.from_user.id)
    chosen = set((row["remind_days"] or "").split(",")) if row else set()
    chosen.discard("")
    if idx in chosen:
        chosen.remove(idx)
    else:
        chosen.add(idx)
    raw = ",".join(sorted(chosen, key=lambda x: int(x)))
    await upsert_user(cb.from_user.id, remind_days=raw)
    await cb.message.edit_reply_markup(reply_markup=days_ikb(raw))
    await cb.answer()


async def on_rmd_ok(cb: CallbackQuery):
    row = await get_user(cb.from_user.id)
    await cb.message.answer("Дни: " + fmt_days(row["remind_days"] if row else ""))
    await cb.answer()


async def show_videos(message: Message):
    n = await count_videos(message.from_user.id)
    await message.answer(
        "<b>Библиотека техники</b>\n"
        f"Роликов у тебя и общих: {n}\n\n"
        "Выбери день → упражнение. Можно прислать видео из галереи "
        "или ссылку YouTube/VK. Админ может залить общий ролик для всех.",
        parse_mode="HTML",
        reply_markup=video_days_ikb(),
    )


async def on_vd(cb: CallbackQuery):
    key = cb.data.replace("vd_", "")
    if key == "home":
        await cb.message.answer("День:", reply_markup=video_days_ikb())
        await cb.answer()
        return
    await cb.message.answer(
        f"Видео · {WORKOUTS[key]['title']}\nКакое упражнение?",
        reply_markup=video_ex_ikb(key),
    )
    await cb.answer()


async def on_vx(cb: CallbackQuery):
    eid = cb.data.replace("vx_", "")
    _, ex = get_exercise(eid)
    if not ex:
        await cb.answer("Нет такого")
        return
    await cb.message.answer(
        f"<b>{ex['name']}</b>\n{ex['reps']}\n{ex['cue']}\n\nЗамены: {', '.join(ex['alts'])}",
        parse_mode="HTML",
        reply_markup=video_action_ikb(eid),
    )
    await cb.answer()


async def on_vw(cb: CallbackQuery):
    eid = cb.data.replace("vw_", "")
    _, ex = get_exercise(eid)
    clips = await get_videos(eid, cb.from_user.id)
    if not clips:
        await cb.message.answer("Пока пусто. Загрузи ролик или кинь ссылку.")
        await cb.answer()
        return
    await cb.message.answer(f"Нашлось {len(clips)} для «{ex['name']}»:")
    for v in clips:
        tag = "общее" if v["owner_id"] == 0 else "твоё"
        if v["file_id"]:
            await cb.message.answer_video(v["file_id"], caption=f"{ex['name']} · {tag}")
        elif v["url"]:
            await cb.message.answer(f"{ex['name']} · {tag}\n{v['url']}")
    await cb.answer()


async def on_vu(cb: CallbackQuery, state: FSMContext):
    eid = cb.data.replace("vu_", "")
    await state.update_data(exercise_id=eid)
    await state.set_state(Extra.video_file)
    await cb.message.answer("Пришли видео файлом (не кружок). Можно сжать, до ~50 МБ.")
    await cb.answer()


async def on_vl(cb: CallbackQuery, state: FSMContext):
    eid = cb.data.replace("vl_", "")
    await state.update_data(exercise_id=eid)
    await state.set_state(Extra.video_url)
    await cb.message.answer("Ссылка на ролик:")
    await cb.answer()


async def on_video_file(message: Message, state: FSMContext):
    if not message.video:
        await message.answer("Нужен именно video, не документ и не кружок.")
        return
    data = await state.get_data()
    eid = data.get("exercise_id")
    owner = 0 if message.from_user.id in ADMIN_IDS else message.from_user.id
    await save_video(owner, eid, message.video.file_id, None)
    await state.clear()
    who = "в общую библиотеку" if owner == 0 else "в твою библиотеку"
    await message.answer(f"Сохранил {who}.")


async def on_video_url(message: Message, state: FSMContext):
    url = (message.text or "").strip()
    if not url.startswith("http"):
        await message.answer("Ссылка должна начинаться с http")
        return
    data = await state.get_data()
    eid = data.get("exercise_id")
    owner = 0 if message.from_user.id in ADMIN_IDS else message.from_user.id
    await save_video(owner, eid, None, url)
    await state.clear()
    await message.answer("Ссылку сохранил.")


async def reminder_loop(bot: Bot):
    while True:
        try:
            now = datetime.now(TZ)
            stamp = now.strftime("%Y-%m-%d %H:%M")
            hhmm = now.strftime("%H:%M")
            wd = str(now.weekday())
            for row in await users_with_reminders():
                if (row["remind_time"] or "19:00") != hhmm:
                    continue
                days = (row["remind_days"] or "").split(",")
                if wd not in days:
                    continue
                if row["last_remind"] == stamp:
                    continue
                plan = {0: "day1", 1: "day2", 3: "day3", 4: "day4"}.get(now.weekday())
                extra = ""
                if plan:
                    extra = f"\nСегодня по сетке: {WORKOUTS[plan]['title']}"
                cyc = ""
                if row["cycle_start"]:
                    cyc = "\n" + cycle_info(row["cycle_start"], row["cycle_len"]).split("\n")[0]
                try:
                    await bot.send_message(
                        row["user_id"],
                        "⏰ Тренировка. Собирайся, разминка 5 минут, потом рабочий день."
                        f"{extra}{cyc}",
                    )
                    await upsert_user(row["user_id"], last_remind=stamp)
                except Exception as e:
                    log.warning("remind fail %s: %s", row["user_id"], e)
        except Exception:
            log.exception("reminder loop")
        await asyncio.sleep(25)


async def main():
    if not BOT_TOKEN or "REPLACE" in BOT_TOKEN:
        raise SystemExit("Нет токена. Скопируй .env.example → .env и вставь BOT_TOKEN.")
    await init_db()
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()
    dp.message.register(cmd_start, CommandStart())
    dp.message.register(cmd_help, Command("help"))
    dp.message.register(show_workouts, F.text == "🏋️ Тренировки")
    dp.message.register(show_nutrition, F.text == "🍽 Питание")
    dp.message.register(show_hormones, F.text == "🧬 Гормоны")
    dp.message.register(start_calc, F.text == "🧮 Калькулятор")
    dp.message.register(show_profile, F.text == "👤 Профиль")
    dp.message.register(show_tip, F.text == "💡 Совет дня")
    dp.message.register(show_weight_menu, F.text == "⚖️ Вес")
    dp.message.register(show_cycle, F.text == "🌙 Цикл")
    dp.message.register(show_remind, F.text == "⏰ Напоминания")
    dp.message.register(show_videos, F.text == "🎬 Видео")
    dp.message.register(on_age, Profile.age)
    dp.message.register(on_height, Profile.height)
    dp.message.register(on_weight, Profile.weight)
    dp.message.register(on_weight_log, Extra.weight_log)
    dp.message.register(on_remind_time, Extra.remind_time)
    dp.message.register(on_cycle_start, Extra.cycle_start)
    dp.message.register(on_cycle_len, Extra.cycle_len)
    dp.message.register(on_video_file, Extra.video_file, F.video)
    dp.message.register(on_video_url, Extra.video_url)
    dp.callback_query.register(on_sex, F.data.startswith("p_sex_"))
    dp.callback_query.register(on_activity, F.data.startswith("p_act_"))
    dp.callback_query.register(on_goal, F.data.startswith("p_goal_"))
    dp.callback_query.register(on_workout_cb, F.data.startswith("w_"))
    dp.callback_query.register(on_subs, F.data.startswith("sub_"))
    dp.callback_query.register(on_nutrition_cb, F.data.startswith("n_"))
    dp.callback_query.register(on_hormone_cb, F.data.startswith("h_"))
    dp.callback_query.register(on_wt_add, F.data == "wt_add")
    dp.callback_query.register(on_wt_hist, F.data == "wt_hist")
    dp.callback_query.register(on_cy_start, F.data == "cy_start")
    dp.callback_query.register(on_cy_len, F.data == "cy_len")
    dp.callback_query.register(on_cy_today, F.data == "cy_today")
    dp.callback_query.register(on_rm_toggle, F.data == "rm_toggle")
    dp.callback_query.register(on_rm_time, F.data == "rm_time")
    dp.callback_query.register(on_rm_days, F.data == "rm_days")
    dp.callback_query.register(on_rmd_ok, F.data == "rmd_ok")
    dp.callback_query.register(on_rmd_toggle, F.data.startswith("rmd_"))
    dp.callback_query.register(on_vd, F.data.startswith("vd_"))
    dp.callback_query.register(on_vx, F.data.startswith("vx_"))
    dp.callback_query.register(on_vw, F.data.startswith("vw_"))
    dp.callback_query.register(on_vu, F.data.startswith("vu_"))
    dp.callback_query.register(on_vl, F.data.startswith("vl_"))
    asyncio.create_task(reminder_loop(bot))
    log.info("FIT CORE started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
