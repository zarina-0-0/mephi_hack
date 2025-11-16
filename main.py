from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, BaseFilter
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from config import token
from result_gen import api_get_result, split_message
from aiogram.types import CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from createbd import create_tables
import sqlite3
from aiogram.enums import ParseMode
import re

bot = Bot(token=token)
dp = Dispatcher(storage=MemoryStorage())


class PrefixFilter(BaseFilter):
    def __init__(self, prefix: str):
        self.prefix = prefix

    async def __call__(self, callback: CallbackQuery) -> bool:
        return callback.data.startswith(self.prefix)


class ContentGen(StatesGroup):
    social_network = State()
    name = State()
    description = State()
    examples = State()
    task_type = State()
    goal = State()
    event_date = State()
    audience = State()
    tone = State()
    format = State()
    details = State()
    cta = State()
    nuances = State()
    edit_text = State()


# --- для создания инлайн клавиатуры ---
def make_inline_keyboard(options: list, prefix: str):
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text=opt, callback_data=f"{prefix}:{opt}")]
            for opt in options
        ]
    )


# --- для создания обычной клавиатуры ---
def make_reply_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/start"), KeyboardButton(text="В главное меню")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )


@dp.message(F.text == "В главное меню")
async def back_to_main_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await show_main_menu(message)


async def show_main_menu(message: types.Message):
    keyboard = make_inline_keyboard(
        ['Перейти к выбору задачи', 'Вывести список НКО', 'Создать новое НКО'],
        prefix="nko_action"
    )

    await message.answer(
        '''🥸 Сначала давай проверим, помогала ли я вашей НКО раньше с созданием контента.\n\nЕсли мы еще не знакомы — выберите "Создать новую НКО"\n\nА если не хотите загружать историю постов — просто переходите сразу к выбору задачи для создания!''',
        reply_markup=keyboard
    )


# --- Старт ---
async def hello(message: types.Message):
    await message.answer(
        '''❤️ Привет! Я — твой личный контент-создатель, заряженный на добро.\n\nТвоя работа меняет мир к лучшему, и об этом должны знать все! Но я также знаю, что иногда на создание постов просто не остается сил, так что давай я возьму контент на себя.\n\nМогу написать пост, поправить твой текст, создать картинку или накидать идей для контент-плана.''')


@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    await hello(message)

    con = sqlite3.connect('nko.db')
    cur = con.cursor()
    try:
        create_tables(cur)
        con.commit()
    except sqlite3.Error as e:
        await message.answer(f"❌ Ошибка при создании таблиц: {e}")
        return
    finally:
        con.close()

    kb = [
        [types.KeyboardButton(text="В главное меню")],
        [types.KeyboardButton(text="/start")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=False)
    await message.answer("Благодаря кнопкам снизу ты всегда можешь перейти в главное меню✨", reply_markup=keyboard)

    await show_main_menu(message)


@dp.callback_query(PrefixFilter("start_flow"))
async def start_flow(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_main_menu(callback.message)


# --- Функция для показа списка НКО ---
async def show_nko_list(message: types.Message, state: FSMContext):
    with sqlite3.connect('nko.db') as con:
        cur = con.cursor()
        try:
            create_tables(cur)
            con.commit()
        except sqlite3.Error as e:
            await message.answer(f"❌ Ошибка при создании таблиц: {e}")
            return

    with sqlite3.connect('nko.db') as con:
        cur = con.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM nko_info")
            count = cur.fetchone()[0]

            if count == 0:
                keyboard = make_inline_keyboard(
                    ['Создать новое НКО', 'Перейти к выбору задачи'],
                    prefix="nko_action"
                )
                await message.answer(
                    "📋 В нашей базе пока нет зарегистрированных НКО.\n\n"
                    "Вы можете создать новое НКО или сразу перейти к созданию контента:",
                    reply_markup=keyboard
                )
            else:
                cur.execute("SELECT nko_id, name, description FROM nko_info")
                nko_list = cur.fetchall()

                response = "📋 Список НКО:\n\n"
                for nko in nko_list:
                    nko_id, name, description = nko
                    response += f"{name}\n"
                    if description:
                        response += f"   📝 {description}\n"
                    response += "\n"

                keyboard = make_inline_keyboard(
                    ['Выбрать НКО', 'Создать новое НКО', 'Перейти к выбору задачи'],
                    prefix="nko_action"
                )

                await message.answer(
                    response + "Выберите действие:",
                    reply_markup=keyboard
                )

        except sqlite3.Error as e:
            await message.answer(f"❌ Произошла ошибка при работе с базой данных: {e}")


# --- обработка действий ---
@dp.callback_query(PrefixFilter("nko_action:"))
async def handle_nko_list_action(callback: types.CallbackQuery, state: FSMContext):
    action = callback.data.split(":", 1)[1]

    if action == "Вывести список НКО":  # ДОБАВИТЬ ЭТУ ВЕТКУ
        await show_nko_list(callback.message, state)
    elif action == "Выбрать НКО":
        await select_nko_from_list(callback.message, state)
    elif action == "Создать новое НКО":
        await create_new_nko(callback.message, state)
    elif action == "Перейти к выбору задачи":
        await start_content_generation(callback.message, state)


# --- для выбора НКО из базы ---
async def select_nko_from_list(message: types.Message, state: FSMContext):
    con = sqlite3.connect('nko.db')
    cur = con.cursor()

    try:
        cur.execute("SELECT nko_id, name FROM nko_info")
        nko_list = cur.fetchall()

        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                                [types.InlineKeyboardButton(text=name, callback_data=f"select_nko:{nko_id}")]
                                for nko_id, name in nko_list
                            ] + [
                                [types.InlineKeyboardButton(text="Назад",
                                                            callback_data="nko_action:Вывести список НКО")]
                            ]
        )

        await message.answer(
            "Выберите НКО из списка:",
            reply_markup=keyboard
        )

    except sqlite3.Error as e:
        await message.answer(f"❌ Произошла ошибка при работе с базой данных: {e}")

    finally:
        con.close()


# --- выбор конкретного НКО ---
@dp.callback_query(PrefixFilter("select_nko:"))
async def handle_nko_selection(callback: types.CallbackQuery, state: FSMContext):
    nko_id = callback.data.split(":", 1)[1]

    con = sqlite3.connect('nko.db')
    cur = con.cursor()

    try:
        cur.execute("SELECT name FROM nko_info WHERE nko_id = ?", (nko_id,))
        result = cur.fetchone()
        if result:
            nko_name = result[0]
            await state.update_data(
                selected_nko_id=nko_id,
                name=nko_name,
                from_task_selection=True
            )

            await callback.message.answer(
                f"Вы выбрали НКО: {nko_name}\n"
                f"Теперь переходим к созданию контента!"
            )

            await ask_task_type(callback.message, state)
        else:
            await callback.message.answer("❌ НКО не найдено")

    except sqlite3.Error as e:
        await callback.message.answer(f"❌ Произошла ошибка при выборе НКО: {e}")

    finally:
        con.close()


# --- для создания нового НКО ---
async def create_new_nko(message: types.Message, state: FSMContext):
    await state.update_data(selected_nko_id=None)  # Сбрасываем выбранное НКО
    await message.answer(
        "Супер! Давай создадим новое НКО.\n\n"
        "Пожалуйста, введите название вашей НКО:"
    )
    await state.set_state(ContentGen.name)


# --- название НКО ---
@dp.message(ContentGen.name)
async def set_name_text(message: types.Message, state: FSMContext):
    data = await state.get_data()

    if data.get('selected_nko_id') is None and message.text and message.text.strip():
        name = message.text.strip()
        await state.update_data(name=name)

        await message.answer(
            "Отлично! Теперь введите описание вашей НКО:\n"
            "(чем занимается ваша организация, её миссия и цели)"
        )
        await state.set_state(ContentGen.description)
    else:
        await state.update_data(name=message.text)
        await ask_goal(message, state)


# --- описание НКО ---
@dp.message(ContentGen.description)
async def set_description(message: types.Message, state: FSMContext):
    description = message.text.strip()
    await state.update_data(description=description)

    # Предлагаем ввести примеры постов (не обязательно)
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Пропустить ввод примеров", callback_data="skip_examples")]
        ]
    )

    await message.answer(
        "📝 Теперь вы можете добавить примеры постов вашей НКО (это поможет мне лучше понять стиль вашего контента).\n\n"
        "Пришлите примеры постов одним сообщением (можно несколько постов в одном сообщении) или нажмите кнопку чтобы пропустить:",
        reply_markup=keyboard
    )
    await state.set_state(ContentGen.examples)


@dp.callback_query(PrefixFilter("skip_examples"))
async def skip_examples(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(examples=None)
    await callback.message.edit_text("✅ Ввод примеров пропущен.")

    await save_new_nko(callback.message, state)


# --- примеры постов ---
@dp.message(ContentGen.examples)
async def set_examples(message: types.Message, state: FSMContext):
    examples = message.text.strip()
    await state.update_data(examples=examples)

    await save_new_nko(message, state)


# --- сохранение нового НКО в базу ---
async def save_new_nko(msg_obj, state: FSMContext):
    data = await state.get_data()
    name = data.get('name')
    description = data.get('description')
    examples = data.get('examples')

    con = sqlite3.connect('nko.db')
    cur = con.cursor()
    try:
        cur.execute(
            "INSERT INTO nko_info (name, description) VALUES (?, ?)",
            (name, description)
        )
        nko_id = cur.lastrowid

        if examples:
            cur.execute(
                "INSERT INTO posts (post_type, nko_id, content) VALUES (?, ?, ?)",
                ('example', nko_id, examples)  # Сохраняем весь текст как один пост
            )

        con.commit()
        await state.update_data(selected_nko_id=nko_id)

        success_message = f"✅ НКО '{name}' успешно создано и сохранено в базе!"
        if examples:
            success_message += f"\n\nПример поста сохранен!"

        if isinstance(msg_obj, types.Message):
            await msg_obj.answer(success_message)
        else:
            await msg_obj.message.answer(success_message)

        await ask_task_type(msg_obj, state)

    except sqlite3.Error as e:
        error_msg = f"❌ Ошибка при сохранении НКО в базу: {e}"
        if isinstance(msg_obj, types.Message):
            await msg_obj.answer(error_msg)
        else:
            await msg_obj.message.answer(error_msg)
    finally:
        con.close()


# --- Создание контента ---
async def start_content_generation(message: types.Message, state: FSMContext):
    await message.answer(
        "Переходим к выбору задачи для создания контента.\n\n"
    )
    await ask_task_type(message, state)


# --- соц сеть ---
async def ask_social_network(message: types.Message, state: FSMContext):
    keyboard = make_inline_keyboard(
        ["Телеграм", "ВК"],
        prefix="social"
    )

    await message.answer(
        "Выберите социальную сеть для которой создаем контент:",
        reply_markup=keyboard
    )
    await state.set_state(ContentGen.social_network)


# --- выбор соцсети обрабатываем ---
@dp.callback_query(PrefixFilter("social:"))
async def set_social_network(callback: types.CallbackQuery, state: FSMContext):
    social = callback.data.split(":", 1)[1]
    await state.update_data(social_network=social)

    await ask_goal(callback.message, state)


# --- текстовый ввод названия ---
@dp.message(ContentGen.name)
async def set_name_text(message: types.Message, state: FSMContext):
    data = await state.get_data()

    if data.get('creating_new_nko'):
        name = message.text.strip()
        await state.update_data(name=name)

        await message.answer(
            "Супер! Теперь введите краткое описание вашей НКО:\n"
            "(чем занимается организация, миссия и цели)"
        )
        await state.set_state(ContentGen.description)
    else:

        await state.update_data(name=message.text)
        await ask_goal(message, state)


# --- для запроса типа задачи ---
async def ask_task_type(msg_obj, state: FSMContext):
    keyboard = make_inline_keyboard(
        [
            "Создание текста",
            "Создание картинки",
            "Создание контент плана"
        ],
        prefix="task_type"
    )

    text = "🎯 Выберите тип задачи:"
    if isinstance(msg_obj, types.Message):
        await msg_obj.answer(text, reply_markup=keyboard)
    else:
        await msg_obj.message.edit_text(text, reply_markup=keyboard)

    await state.set_state(ContentGen.task_type)


# --- выбор типа задачи ---
@dp.callback_query(PrefixFilter("task_type:"))
async def set_task_type(callback: types.CallbackQuery, state: FSMContext):
    task_type = callback.data.split(":", 1)[1]
    await state.update_data(task_type=task_type)

    if task_type == "Создание текста":
        await ask_social_network(callback.message, state)
    elif task_type == "Создание картинки":
        await callback.message.answer("🎨 Создание картинок пока в разработке")
    elif task_type == "Создание контент плана":
        await callback.message.answer("📅 Создание контент-планов пока в разработке")


# --- цель контента ---
async def ask_goal(msg_obj, state):
    keyboard = make_inline_keyboard(
        [
            "Анонс события",
            "Рассказать о прошедшем событии",
            "Создать темы поста",
            "Подвести итоги и статистику",
            "Сбор средств",
            "Повысить осведомлённость",
            "Отчитаться о проделанной работе",
        ],
        prefix="goal"
    )

    text = "Теперь выберите цель контента:"
    if isinstance(msg_obj, types.Message):
        await msg_obj.answer(text, reply_markup=keyboard)
    else:
        await msg_obj.message.edit_text(text, reply_markup=keyboard)

    await state.set_state(ContentGen.goal)


@dp.callback_query(PrefixFilter("goal:"))
async def set_goal(callback: types.CallbackQuery, state: FSMContext):
    goal = callback.data.split(":", 1)[1]
    await state.update_data(goal=goal)

    if goal in ["Анонс события", "Рассказать о прошедшем событии"]:
        await ask_event_dates(callback.message, state)
    else:
        await ask_audience(callback.message, state)


# --- дата время и место ---
async def ask_event_dates(msg_obj, state: FSMContext):
    data = await state.get_data()
    goal = data.get('goal')

    if goal == "Анонс события":
        text = "📅 Укажите дату, время и место предстоящего события:\n(например: 15 декабря 2024, 14:00, ул. Пушкина д.3)"
    else:
        text = "📅 Укажите дату прошедшего события:\n(например: 10 декабря 2024)"

    if isinstance(msg_obj, types.Message):
        await msg_obj.answer(text)
    else:
        await msg_obj.message.edit_text(text)

    await state.set_state(ContentGen.event_date)


@dp.message(ContentGen.event_date)
async def set_event_date(message: types.Message, state: FSMContext):
    event_date = message.text.strip()
    await state.update_data(event_date=event_date)

    await ask_audience(message, state)


# --- ца ---
async def ask_audience(msg_obj, state: FSMContext):
    keyboard = make_inline_keyboard(
        ["Жители города", "Молодёжь", "Семьи", "Ветераны", "Предприятия / компании", "Пропустить"],
        prefix="aud"
    )

    text = "Кто ваша целевая аудитория? Напишите или выберите из предложенных"
    if isinstance(msg_obj, types.Message):
        await msg_obj.answer(text, reply_markup=keyboard)
    else:
        await msg_obj.message.edit_text(text, reply_markup=keyboard)

    await state.set_state(ContentGen.audience)


@dp.callback_query(PrefixFilter("aud:"))
async def set_audience_callback(callback: types.CallbackQuery, state: FSMContext):
    audience = callback.data.split(":", 1)[1]

    if audience == "Пропустить":
        await state.update_data(audience=None)
        await callback.message.edit_text("✅ Выбор аудитории пропущен")
    else:
        await state.update_data(audience=audience)
        await callback.message.edit_text(f"🎯 Целевая аудитория: {audience}")

    await ask_tone(callback.message, state)


@dp.message(ContentGen.audience)
async def set_audience_text(message: types.Message, state: FSMContext):
    audience = message.text.strip()

    if audience in ["/start", "В главное меню"]:
        return

    await state.update_data(audience=audience)
    await message.answer(f"🎯 Целевая аудитория: {audience}")

    await ask_tone(message, state)


@dp.callback_query(PrefixFilter("aud:"))
async def set_audience(callback: types.CallbackQuery, state: FSMContext):
    audience = callback.data.split(":", 1)[1]
    await state.update_data(audience=audience)

    await ask_tone(callback.message, state)


# --- тон ---
async def ask_tone(msg_obj, state: FSMContext):
    keyboard = make_inline_keyboard(
        ["Нейтральный", "Дружелюбный", "Воодушевляющий", "Деловой", "С энтузиазмом", "Тон не важен"],
        prefix="tone"
    )

    text = "Выберите тон подачи:"
    if isinstance(msg_obj, types.Message):
        await msg_obj.answer(text, reply_markup=keyboard)
    else:
        await msg_obj.message.edit_text(text, reply_markup=keyboard)

    await state.set_state(ContentGen.tone)


@dp.callback_query(PrefixFilter("tone:"))
async def set_tone(callback: types.CallbackQuery, state: FSMContext):
    tone = callback.data.split(":", 1)[1]
    await state.update_data(tone=tone)

    await callback.message.edit_text(
        "Что конкретно нужно рассказать?\n\nНапишите в одном сообщении:"
    )
    await state.set_state(ContentGen.details)


# --- призыв к действию ---
@dp.message(ContentGen.details)
async def set_details(message: types.Message, state: FSMContext):
    await state.update_data(details=message.text)

    await message.answer("Какой призыв к действию вы хотите использовать?")
    await state.set_state(ContentGen.cta)


# --- нюансы ---
@dp.message(ContentGen.cta)
async def set_cta(message: types.Message, state: FSMContext):
    await state.update_data(cta=message.text)

    await message.answer("Есть ли важные нюансы? Если нет — напишите «нет».")
    await state.set_state(ContentGen.nuances)


# --- очень важная функция генерации контента и промптов ---
@dp.message(ContentGen.nuances)
async def generate_content(message: types.Message, state: FSMContext):
    await state.update_data(nuances=message.text)
    data = await state.get_data()

    nko_name = data.get('name')
    nko_description = ""
    examples_text = ""

    if data.get('selected_nko_id'):
        con = sqlite3.connect('nko.db')
        cur = con.cursor()
        try:
            cur.execute("SELECT name, description FROM nko_info WHERE nko_id = ?", (data.get('selected_nko_id'),))
            result = cur.fetchone()
            if result:
                nko_name, nko_description = result

            cur.execute("SELECT content FROM posts WHERE nko_id = ? AND post_type = 'example'",
                        (data.get('selected_nko_id'),))
            examples = cur.fetchall()
            if examples:
                examples_text = "\n".join([example[0] for example in examples])

        except sqlite3.Error:
            pass
        finally:
            con.close()

    if not nko_name:
        nko_name = "Без указания названия"

    organization_context = ""
    if nko_description:
        organization_context = f"Миссия и деятельность: {nko_description}"
    else:
        organization_context = f"Название организации: {nko_name}"

    event_info = ""
    if data.get('event_date'):
        goal = data.get('goal', '')
        if goal == "Анонс события":
            event_info = f"Дата и место события: {data['event_date']}"
        elif goal == "Рассказать о прошедшем событии":
            event_info = f"Дата прошедшего события: {data['event_date']}"

    if data.get('task_type') == "Создание текста":
        prompt = f"""
Ты — опытный копирайтер и редактор благотворительной организации: {organization_context}

Напиши текст поста для социальных сетей на основе следующих данных:
Цель поста: {data.get('goal', '')}
{event_info}
Целевая аудитория поста: {data.get('audience', '')}
Основная информация поста: {data.get('details', '')}
Призыв к действию: {data.get('cta', '')}
Дополнительные пожелания: {data.get('nuances', '')}

{"Стилистический референс, пиши в аналогичном стиле с этими постами:" + examples_text if examples_text else ""}

Требования к тексту:
Соответствует цели поста.
{"Учитывает дату и место события." if event_info else ""}
Написан в стиле, близком к референсу и глобальному контексту (стиль, интонация, уровень языка). Текст не должен выглядеть сгенерированным нейросетью, пиши так, как писал бы человек.
{"Побуждает к действию (прийти, помочь, поделиться)." if data.get('goal') == "Анонс события" else ""}
{"Содержит результаты в удобочитаемом виде, избегает большого количества цифр." if data.get('goal') in ["Подвести итоги и статистику", "Отчитаться о проделанной работе"] else ""}
{"Вызывает доверие, конкретизирует цель (зачем нужны деньги, кому помогут)." if data.get('goal') == "Сбор средств" else ""}
{"Уважительно, без рекламного тона, с акцентом на вклад и ценность поддержки." if data.get('goal') == "Рассказать о спонсоре" else ""}

Учитывай специфику социальной сети: {"Короткий и понятный текст с яркими заголовками. Эмоциональная подача, стимулирующая обсуждение и активное комментирование." if data.get('social_network') == "ВК" else "Качественный и структурированный материал с четкими выводами. Лаконичный стиль, минимум графического оформления, максимальная информативность." if data.get('social_network') == "Телеграм" else ""}

Стиль:
Естественный, живой, внимание к деталям. Избегай клише, канцеляризмов и морализаторства.

Формат вывода:
Готовый текст поста. Без пояснений, заголовков вроде «[Текст поста]» или комментариев.
Добавь 4-5 хештегов в конце по тематике поста для социальных сетей.
"""
    elif data.get('task_type') == "":
        pass
    else:
        pass

    await message.answer("✨ Создаю контент ✨")

    try:
        result = api_get_result(prompt)
    except ConnectionError:
        await message.answer("Ошибка соединения с сервером ИИ. Проверьте интернет-соединение и попробуйте еще раз.")
        return
    except TimeoutError:
        await message.answer("Превышено время ожидания ответа от ИИ. Попробуйте еще раз.")
        return
    except Exception as e:
        await message.answer("Произошла непредвиденная ошибка при создании контента. Попробуйте еще раз.")
        print(f"API error: {e}")
        return

    await state.update_data(generated_text=result)

    parts = split_message(result)

    for part in parts:
        await message.answer(part)

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="✏️ Отредактировать текст", callback_data="edit_text")],
            [types.InlineKeyboardButton(text="✅ Сохранить как есть", callback_data="save_text")],
            [types.InlineKeyboardButton(text="🔄 Создать заново", callback_data="regenerate_text")]
        ]
    )

    await message.answer(
        "Что вы хотите сделать с этим текстом?",
        reply_markup=keyboard
    )


@dp.callback_query(PrefixFilter("regenerate_text"))
async def regenerate_text(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()

    nko_name = data.get('name')
    nko_description = ""
    examples_text = ""

    if data.get('selected_nko_id'):
        con = sqlite3.connect('nko.db')
        cur = con.cursor()
        try:
            cur.execute("SELECT name, description FROM nko_info WHERE nko_id = ?", (data.get('selected_nko_id'),))
            result = cur.fetchone()
            if result:
                nko_name, nko_description = result

            cur.execute("SELECT content FROM posts WHERE nko_id = ? AND post_type = 'example'",
                        (data.get('selected_nko_id'),))
            examples = cur.fetchall()
            if examples:
                examples_text = "\n".join([example[0] for example in examples])

        except sqlite3.Error:
            pass
        finally:
            con.close()

    if not nko_name:
        nko_name = "Без указания названия"

    organization_context = ""
    if nko_description:
        organization_context = f"Миссия и деятельность: {nko_description}"
    else:
        organization_context = f"Название организации: {nko_name}"

    event_info = ""
    if data.get('event_date'):
        goal = data.get('goal', '')
        if goal == "Анонс события":
            event_info = f"Дата и место события: {data['event_date']}"
        elif goal == "Рассказать о прошедшем событии":
            event_info = f"Дата прошедшего события: {data['event_date']}"

    prompt = f"""
Ты — опытный копирайтер и редактор благотворительной организации: {organization_context}

Напиши текст поста для социальных сетей на основе следующих данных:
Цель поста: {data.get('goal', '')}
{event_info}
Целевая аудитория поста: {data.get('audience', '')}
Основная информация поста: {data.get('details', '')}
Призыв к действию: {data.get('cta', '')}
Дополнительные пожелания: {data.get('nuances', '')}

{"Стилистический референс, пиши в аналогичном стиле с этими постами:" + examples_text if examples_text else ""}

Требования к тексту:
Соответствует цели поста.
{"Учитывает дату и место события." if event_info else ""}
Написан в стиле, близком к референсу и глобальному контексту (стиль, интонация, уровень языка). Текст не должен выглядеть сгенерированным нейросетью, пиши так, как писал бы человек.
{"Побуждает к действию (прийти, помочь, поделиться)." if data.get('goal') == "Анонс события" else ""}
{"Содержит результаты в удобочитаемом виде, избегает большого количества цифр." if data.get('goal') in ["Подвести итоги и статистику", "Отчитаться о проделанной работе"] else ""}
{"Вызывает доверие, конкретизирует цель (зачем нужны деньги, кому помогут)." if data.get('goal') == "Сбор средств" else ""}

Учитывай специфику социальной сети: {"Короткий и понятный текст с яркими заголовками. Эмоциональная подача, стимулирующая обсуждение и активное комментирование." if data.get('social_network') == "ВК" else "Качественный и структурированный материал с четкими выводами. Лаконичный стиль, минимум графического оформления, максимальная информативность." if data.get('social_network') == "Телеграм" else ""}

Стиль:
Естественный, живой, внимание к деталям. Избегай клише, канцеляризмов и морализаторства.

Формат вывода:
Готовый текст поста. Без пояснений, заголовков вроде «[Текст поста]» или комментариев.
Добавь 4-5 хештегов в конце по тематике поста для социальных сетей.
"""

    await callback.message.answer("✨ Создаю новый вариант...")

    try:
        result = api_get_result(prompt)
        await state.update_data(generated_text=result)

        parts = split_message(result)
        for part in parts:
            await callback.message.answer(part, parse_mode=ParseMode.MARKDOWN)

        success = False
        if data.get('selected_nko_id'):
            success = await save_post_to_db(callback.message, state, result, 'regenerated')

        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="✏️ Отредактировать текст", callback_data="edit_text")],
                [types.InlineKeyboardButton(text="✅ Сохранить как есть", callback_data="save_text")],
                [types.InlineKeyboardButton(text="🔄 Создать заново", callback_data="regenerate_text")]
            ]
        )

        if success:
            await callback.message.answer(
                "Новый вариант создан и сохранен в базу! Что вы хотите сделать?",
                reply_markup=keyboard
            )
        else:
            await callback.message.answer(
                "Новый вариант создан!" + (" (не сохранен в базу - НКО не выбрано)" if not data.get('selected_nko_id') else ""),
                reply_markup=keyboard
            )

    except Exception as e:
        await callback.message.answer("❌ Ошибка при повторного создания. Попробуйте еще раз.")
        print(f"Regeneration error: {e}")

    await callback.answer()


# --- сохранение поста в базу ---
async def save_post_to_db(msg_obj, state: FSMContext, post_content: str, post_type: str = 'generated'):
    data = await state.get_data()
    nko_id = data.get('selected_nko_id')

    if not nko_id:
        return False

    con = sqlite3.connect('nko.db')
    cur = con.cursor()
    try:
        cur.execute(
            "INSERT INTO posts (post_type, nko_id, content, goal, audience, tone, details, cta, nuances) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (post_type, nko_id, post_content, data.get('goal'), data.get('audience'),
             data.get('tone'), data.get('details'), data.get('cta'), data.get('nuances'))
        )
        con.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error saving post to DB: {e}")
        return False
    finally:
        con.close()


@dp.callback_query(PrefixFilter("save_text"))
async def save_text(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    generated_text = data.get('generated_text', '')

    # выбрано ли НКО
    if not data.get('selected_nko_id'):
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="Начать заново с выбором НКО", callback_data="start_with_nko")],
                [types.InlineKeyboardButton(text="Посмотреть список НКО",
                                            callback_data="nko_action:Вывести список НКО")]
            ]
        )
        await callback.message.answer(
            "❌ Вы не выбрали НКО для привязки текста.\n\n"
            "Чтобы сохранить текст, нужно выбрать существующее НКО или создать новое.\n"
            "Вы можете:",
            reply_markup=keyboard
        )
        await callback.answer()
        return

    success = await save_post_to_db(callback.message, state, generated_text, 'generated')

    if success:
        await callback.message.answer("✅ Текст сохранен в базу данных!")
        await state.clear()
        await show_main_menu(callback.message)
    else:
        await callback.message.answer("❌ Произошла ошибка при сохранении текста.")

    await callback.answer()


@dp.callback_query(PrefixFilter("save_edited"))
async def save_edited_text(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    edited_text = data.get('edited_text', '')

    if not data.get('selected_nko_id'):
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="Начать заново с выбором НКО", callback_data="start_with_nko")],
                [types.InlineKeyboardButton(text="Посмотреть список НКО",
                                            callback_data="nko_action:Вывести список НКО")]
            ]
        )
        await callback.message.answer(
            "❌ Вы не выбрали НКО для привязки текста.\n\n"
            "Чтобы сохранить текст, нужно выбрать существующее НКО или создать новое.\n"
            "Вы можете:",
            reply_markup=keyboard
        )
        await callback.answer()
        return

    success = await save_post_to_db(callback.message, state, edited_text, 'edited')

    if success:
        await callback.message.answer("✅ Исправленный текст сохранен в базу данных!")
        await state.clear()
        await show_main_menu(callback.message)
    else:
        await callback.message.answer("❌ Произошла ошибка при сохранении текста.")

    await callback.answer()


@dp.callback_query(PrefixFilter("start_with_nko"))
async def start_with_nko(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("🔙 Начинаем заново с выбора НКО...")
    await show_main_menu(callback.message)
    await callback.answer()


@dp.callback_query(PrefixFilter("ai_refine"))
async def ai_refine_text(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    edited_text = data.get('edited_text', '')

    original_data = data

    prompt = f"""
        Пользователь отредактировал текст и просит его доработать.

        Оригинальный контекст:
        - НКО: {original_data.get('name', 'Без названия')}
        - Цель: {original_data.get('goal', '')}
        - Аудитория: {original_data.get('audience', '')}
        - Тон: {original_data.get('tone', '')}

        Отредактированный текст пользователя:
        {edited_text}

        Задача: улучшить текст, сохранив смысл правок пользователя, сделать его более профессиональным и соответствующим исходным требованиям.
        """

    await callback.message.answer(" Дорабатываю текст...")

    try:
        refined_text = api_get_result(prompt)
        await state.update_data(generated_text=refined_text)

        parts = split_message(refined_text)
        for part in parts:
            await callback.message.answer(part)

        # сохраняем текст в базу только если есть НКО
        success = False
        if data.get('selected_nko_id'):
            success = await save_post_to_db(callback.message, state, refined_text, 'ai_refined')

        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="✏️ Отредактировать текст", callback_data="edit_text")],
                [types.InlineKeyboardButton(text="✅ Сохранить как есть", callback_data="save_text")],
                [types.InlineKeyboardButton(text="🔄 Создать заново", callback_data="regenerate_text")]
            ]
        )

        if success:
            await callback.message.answer(
                "Текст доработан и сохранен в базу! Что вы хотите сделать?",
                reply_markup=keyboard
            )
        else:
            await callback.message.answer(
                "Текст доработан!" + (" (не сохранен в базу - НКО не выбрано)" if not data.get('selected_nko_id') else ""),
                reply_markup=keyboard
            )

    except Exception as e:
        await callback.message.answer("❌ Ошибка при доработке текста. Попробуйте еще раз.")
        print(f"AI refine error: {e}")

    await callback.answer()


@dp.callback_query(PrefixFilter("edit_text"))
async def start_editing(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    generated_text = data.get('generated_text', '')

    await callback.message.answer(
        f"✏️ Отправьте исправленный текст:\n\n{generated_text}"
    )
    await state.set_state(ContentGen.edit_text)
    await callback.answer()


@dp.message(ContentGen.edit_text)
async def process_edited_text(message: types.Message, state: FSMContext):
    edited_text = message.text.strip()
    await state.update_data(edited_text=edited_text)

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="🤖 Отправить ИИ на доработку", callback_data="ai_refine")],
            [types.InlineKeyboardButton(text="✅ Сохранить исправленный текст", callback_data="save_edited")]
        ]
    )

    await message.answer(
        f"Ваш отредактированный текст:\n\n{edited_text}\n\nЧто делать дальше?",
        reply_markup=keyboard
    )

if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))
