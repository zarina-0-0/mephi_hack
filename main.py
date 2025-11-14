from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from openai import OpenAI
from dotenv import load_dotenv
from config import token
from city_info import CITY_DB
from result_gen import api_get_result

load_dotenv()

bot = Bot(token=token)
dp = Dispatcher(storage=MemoryStorage())


class ContentGen(StatesGroup):
    city = State()
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
            [types.InlineKeyboardButton(text="🚀 Начать", callback_data="start_flow")]
        ]
    )

    await message.answer(
        "👋 Привет! Я помогу создать контент для соцсетей вашей НКО.\n\n"
        "Нажмите кнопку ниже, когда будете готовы начать пройти опрос для создания классного и полезного контента!",
        reply_markup=start_keyboard
    )


@dp.callback_query(lambda c: c.data == "start_flow")
async def start_flow(callback: types.CallbackQuery, state: FSMContext):

    keyboard = make_inline_keyboard(
        list(CITY_DB.keys()),
        prefix="city"
    )

    await callback.message.edit_text(
        "Для начала выберите закрытый город в котором ваше НКО:",
        reply_markup=keyboard
    )
    await state.set_state(ContentGen.city)


@dp.callback_query(lambda c: c.data.startswith("city:"))
async def set_city(callback: types.CallbackQuery, state: FSMContext):
    city = callback.data.split(":", 1)[1]
    await state.update_data(city=city)

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

    await callback.message.edit_text(
        f"Вы выбрали город {city}.\nТеперь выберите цель контента:",
        reply_markup=keyboard
    )
    await state.set_state(ContentGen.goal)


# --- Цель затем аудитория ---
@dp.callback_query(lambda c: c.data.startswith("goal:"))
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


# --- Аудитория затем тон ---
@dp.callback_query(lambda c: c.data.startswith("aud:"))
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


# --- Тон затем формат ---
@dp.callback_query(lambda c: c.data.startswith("tone:"))
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


# --- Формат затем детали ---
@dp.callback_query(lambda c: c.data.startswith("fmt:"))
async def set_format(callback: types.CallbackQuery, state: FSMContext):
    format_ = callback.data.split(":", 1)[1]
    await state.update_data(format=format_)

    await callback.message.edit_text(
        "Что конкретно нужно рассказать?\n\n"
        "Напишите в одном сообщении"
    )
    await state.set_state(ContentGen.details)


# --- Призыв к действию ---
@dp.message(ContentGen.details)
async def set_details(message: types.Message, state: FSMContext):
    await state.update_data(details=message.text)

    await message.answer(
        "Какой призыв к действию вы хотите использовать? (например: «поддержите проект», «присоединяйтесь», «узнайте больше»)"
    )

    await state.set_state(ContentGen.cta)


@dp.message(ContentGen.cta)
async def set_cta(message: types.Message, state: FSMContext):
    await state.update_data(cta=message.text)

    await message.answer("Есть ли важные нюансы, которые нужно учесть? Если нет — напишите «нет».")
    await state.set_state(ContentGen.nuances)


# --- Генерация ---
@dp.message(ContentGen.nuances)
async def generate_content(message: types.Message, state: FSMContext):
    await state.update_data(nuances=message.text)
    data = await state.get_data()

    city = data["city"]
    city_context = CITY_DB.get(city, "характеристика города не найдена")

    prompt = f"""
Ты копирайтер-профи, специализирующийся на социальных проектах.\nСоздай {data['format']} для НКО в закрытом городе {city}. Учти контекст города: {city_context}.\n
Цель контента: {data['goal']}
Аудитория: {data['audience']}
Тон: {data['tone']}
Ключевые тезисы: {data['details']}
Призыв к действию: {data['cta']}
Учти нюансы: {data['nuances']}

- Не используй шаблонные фразы
- Удели внимание уникальности города, атмосфере
- Излагай четко и структурированно
    """

    # await message.answer(prompt)
    await message.answer(api_get_result(prompt))
    await state.clear()


# --- Запуск ---
if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))
