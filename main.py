from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, BaseFilter
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from config import token
from city_info import CITY_DB
from result_gen import api_get_result, split_message
from aiogram.types import CallbackQuery

bot = Bot(token=token)
dp = Dispatcher(storage=MemoryStorage())


class PrefixFilter(BaseFilter):
    def __init__(self, prefix: str):
        self.prefix = prefix

    async def __call__(self, callback: CallbackQuery) -> bool:
        return callback.data.startswith(self.prefix)


class ContentGen(StatesGroup):
    city = State()
    name = State()
    goal = State()
    audience = State()
    tone = State()
    format = State()
    details = State()
    cta = State()
    nuances = State()


def make_inline_keyboard(options: list, prefix: str):
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text=opt, callback_data=f"{prefix}:{opt}")]
            for opt in options
        ]
    )


# --- Старт ---
@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await state.clear()

    start_keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Начнем!", callback_data="start_flow")]
        ]
    )

    await message.answer(
        "👋 Привет! Я помогу создать контент для соцсетей вашей НКО.\n\n"
        "Нажмите кнопку ниже, когда будете готовы начать пройти опрос!",
        reply_markup=start_keyboard
    )


@dp.callback_query(PrefixFilter("start_flow"))
async def start_flow(callback: types.CallbackQuery, state: FSMContext):

    keyboard = make_inline_keyboard(
        list(CITY_DB.keys()),
        prefix="city"
    )

    await callback.message.edit_text(
        "Для начала выберите закрытый город, в котором работает ваше НКО:",
        reply_markup=keyboard
    )
    await state.set_state(ContentGen.city)


# --- Выбор города ---
@dp.callback_query(PrefixFilter("city:"))
async def set_city(callback: types.CallbackQuery, state: FSMContext):
    city = callback.data.split(":", 1)[1]
    await state.update_data(city=city)

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Без указания названия", callback_data="name:none")]
        ]
    )

    await callback.message.edit_text(
        f"Вы выбрали город {city}.\nТеперь укажите название НКО или выберите анонимный вариант:",
        reply_markup=keyboard
    )

    await state.set_state(ContentGen.name)


# --- Название НКО ---
@dp.callback_query(PrefixFilter("name:"))
async def set_name_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(name=None)
    await ask_goal(callback.message, state)


@dp.message(ContentGen.name)
async def set_name_text(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await ask_goal(message, state)


# --- Цель ---
async def ask_goal(msg_obj, state):
    keyboard = make_inline_keyboard(
        [
            "Рассказать о событии",
            "Собрать средства",
            "Найти партнёров / спонсоров",
            "Повысить осведомлённость",
            "Отчитаться о проделанной работе",
        ],
        prefix="goal"
    )

    await msg_obj.answer(
        "Отлично! Теперь выберите цель контента:",
        reply_markup=keyboard
    )
    await state.set_state(ContentGen.goal)


# --- ЦА ---
@dp.callback_query(PrefixFilter("goal:"))
async def set_goal(callback: types.CallbackQuery, state: FSMContext):
    goal = callback.data.split(":", 1)[1]
    await state.update_data(goal=goal)

    keyboard = make_inline_keyboard(
        ["Жители города", "Молодёжь", "Семьи", "Ветераны", "Предприятия / компании"],
        prefix="aud"
    )

    await callback.message.edit_text(
        "Кто ваша целевая аудитория?",
        reply_markup=keyboard
    )
    await state.set_state(ContentGen.audience)


# --- Аудитория ---
@dp.callback_query(PrefixFilter("aud:"))
async def set_audience(callback: types.CallbackQuery, state: FSMContext):
    audience = callback.data.split(":", 1)[1]
    await state.update_data(audience=audience)

    keyboard = make_inline_keyboard(
        ["Нейтральный", "Дружелюбный", "Воодушевляющий", "Деловой", "С энтузиазмом"],
        prefix="tone"
    )

    await callback.message.edit_text(
        "Выберите тон подачи:",
        reply_markup=keyboard
    )
    await state.set_state(ContentGen.tone)


# --- Тон ---
@dp.callback_query(PrefixFilter("tone:"))
async def set_tone(callback: types.CallbackQuery, state: FSMContext):
    tone = callback.data.split(":", 1)[1]
    await state.update_data(tone=tone)

    keyboard = make_inline_keyboard(
        ["Текст поста", "Контент-план на неделю", "Сценарий видео", "Идеи для серии постов"],
        prefix="fmt"
    )

    await callback.message.edit_text(
        "Какой формат контента нужен?",
        reply_markup=keyboard
    )
    await state.set_state(ContentGen.format)


# --- Формат ---
@dp.callback_query(PrefixFilter("fmt:"))
async def set_format(callback: types.CallbackQuery, state: FSMContext):
    format_ = callback.data.split(":", 1)[1]
    await state.update_data(format=format_)

    await callback.message.edit_text(
        "Что конкретно нужно рассказать?\n\nНапишите в одном сообщении:"
    )
    await state.set_state(ContentGen.details)


# --- Детали ---
@dp.message(ContentGen.details)
async def set_details(message: types.Message, state: FSMContext):
    await state.update_data(details=message.text)

    await message.answer("Какой призыв к действию вы хотите использовать?")
    await state.set_state(ContentGen.cta)


# --- CTA ---
@dp.message(ContentGen.cta)
async def set_cta(message: types.Message, state: FSMContext):
    await state.update_data(cta=message.text)

    await message.answer("Есть ли важные нюансы? Если нет — напишите «нет».")
    await state.set_state(ContentGen.nuances)


# --- Генерация контента ---
@dp.message(ContentGen.nuances)
async def generate_content(message: types.Message, state: FSMContext):
    await state.update_data(nuances=message.text)
    data = await state.get_data()

    city = data["city"]
    city_context = CITY_DB.get(city, "характеристика города не найдена")

    prompt = f"""
Ты копирайтер-профи, специализирующийся на социальных проектах.
Создай {data['format']} для НКО в закрытом городе {city}.
Учитывай контекст города: {city_context}.

Название НКО: {data['name']}
Цель: {data['goal']}
Аудитория: {data['audience']}
Тон: {data['tone']}
Ключевые тезисы: {data['details']}
Призыв к действию: {data['cta']}
Нюансы: {data['nuances']}

Требования:
- избегай шаблонов
- отрази атмосферу закрытого города
"""

    await message.answer("✨ Генерирую контент ✨")
    result = api_get_result(prompt)

    parts = split_message(result)

    for part in parts:
        await message.answer(part)
    await state.clear()


if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))
