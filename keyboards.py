from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from config import WEEKDAYS_RU
from data import WORKOUTS


def main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏋️ Тренировки"), KeyboardButton(text="🍽 Питание")],
            [KeyboardButton(text="🧬 Гормоны"), KeyboardButton(text="🧮 Калькулятор")],
            [KeyboardButton(text="⚖️ Вес"), KeyboardButton(text="🌙 Цикл")],
            [KeyboardButton(text="⏰ Напоминания"), KeyboardButton(text="🎬 Видео")],
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="💡 Совет дня")],
        ],
        resize_keyboard=True,
    )


def workouts_ikb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="День 1 · Грудь + бицепс", callback_data="w_day1")],
            [InlineKeyboardButton(text="День 2 · Спина + трицепс", callback_data="w_day2")],
            [InlineKeyboardButton(text="День 3 · Ноги + плечи", callback_data="w_day3")],
            [InlineKeyboardButton(text="День 4 · Всё тело", callback_data="w_day4")],
            [InlineKeyboardButton(text="📅 Как чередовать неделю", callback_data="w_week")],
        ]
    )


def day_extra_ikb(day: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔁 Замены", callback_data=f"sub_{day}"),
                InlineKeyboardButton(text="🎬 Видео дня", callback_data=f"vd_{day}"),
            ]
        ]
    )


def nutrition_ikb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Принципы", callback_data="n_principles")],
            [InlineKeyboardButton(text="Меню на набор", callback_data="n_mass")],
            [InlineKeyboardButton(text="Меню на сушку", callback_data="n_cut")],
            [InlineKeyboardButton(text="До и после тренировки", callback_data="n_prepost")],
        ]
    )


def hormones_ikb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Тестостерон", callback_data="h_testosterone")],
            [InlineKeyboardButton(text="Кортизол", callback_data="h_cortisol")],
            [InlineKeyboardButton(text="Инсулин", callback_data="h_insulin")],
            [InlineKeyboardButton(text="Щитовидка и сон", callback_data="h_thyroid_sleep")],
        ]
    )


def sex_ikb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Мужской", callback_data="p_sex_m"),
                InlineKeyboardButton(text="Женский", callback_data="p_sex_f"),
            ]
        ]
    )


def activity_ikb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Сидячий", callback_data="p_act_low")],
            [InlineKeyboardButton(text="Лёгкая активность", callback_data="p_act_mid")],
            [InlineKeyboardButton(text="Тренировки 3–5×/нед", callback_data="p_act_high")],
            [InlineKeyboardButton(text="Тяжёлые тренировки", callback_data="p_act_sport")],
        ]
    )


def goal_ikb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Сушка", callback_data="p_goal_cut")],
            [InlineKeyboardButton(text="Поддержание", callback_data="p_goal_keep")],
            [InlineKeyboardButton(text="Набор", callback_data="p_goal_bulk")],
        ]
    )


def weight_ikb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Записать вес", callback_data="wt_add")],
            [InlineKeyboardButton(text="📈 История", callback_data="wt_hist")],
        ]
    )


def cycle_ikb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Начало цикла", callback_data="cy_start")],
            [InlineKeyboardButton(text="🔢 Длина цикла", callback_data="cy_len")],
            [InlineKeyboardButton(text="Сегодня первый день", callback_data="cy_today")],
        ]
    )


def remind_ikb(on: bool) -> InlineKeyboardMarkup:
    toggle = "Выключить" if on else "Включить"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{'🔔' if on else '🔕'} {toggle}", callback_data="rm_toggle")],
            [InlineKeyboardButton(text="🕐 Время", callback_data="rm_time")],
            [InlineKeyboardButton(text="📆 Дни недели", callback_data="rm_days")],
        ]
    )


def days_ikb(selected: str) -> InlineKeyboardMarkup:
    chosen = set((selected or "").split(","))
    rows = []
    row = []
    for i, name in enumerate(WEEKDAYS_RU):
        mark = "✓ " if str(i) in chosen else ""
        row.append(InlineKeyboardButton(text=f"{mark}{name}", callback_data=f"rmd_{i}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="Готово", callback_data="rmd_ok")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def video_days_ikb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=WORKOUTS[d]["title"].split("—")[0].strip(), callback_data=f"vd_{d}")]
            for d in ("day1", "day2", "day3", "day4")
        ]
    )


def video_ex_ikb(day: str) -> InlineKeyboardMarkup:
    rows = []
    for ex in WORKOUTS[day]["exercises"]:
        rows.append([InlineKeyboardButton(text=ex["name"], callback_data=f"vx_{ex['id']}")])
    rows.append([InlineKeyboardButton(text="← К дням", callback_data="vd_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def video_action_ikb(eid: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👁 Смотреть", callback_data=f"vw_{eid}")],
            [InlineKeyboardButton(text="📤 Загрузить своё", callback_data=f"vu_{eid}")],
            [InlineKeyboardButton(text="🔗 Прислать ссылку", callback_data=f"vl_{eid}")],
        ]
    )
