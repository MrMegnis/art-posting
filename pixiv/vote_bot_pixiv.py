import json
import csv
import os
from dotenv import load_dotenv
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

load_dotenv()

ALLOWED_USERS_FILE = "allowed_users.txt"

API_TOKEN = os.getenv('API_TOKEN')
SECRET_AUTH_PASS = os.getenv('SECRET')

DATA_DIR = "data"

def load_allowed_users():
    if not os.path.exists(ALLOWED_USERS_FILE):
        return set()
    with open(ALLOWED_USERS_FILE, "r") as f:
        return set(int(line.strip()) for line in f if line.strip().isdigit())

def save_allowed_users(users_set):
    with open(ALLOWED_USERS_FILE, "w") as f:
        for uid in users_set:
            f.write(f"{uid}\n")

ALLOWED_USERS = load_allowed_users()

# Фильтр доступа
def is_allowed_user(handler):
    async def wrapper(event, *args, **kwargs):
        user_id = getattr(event.from_user, "id", None)
        if user_id not in ALLOWED_USERS:
            text = "У вас нет доступа к этому боту. Авторизуйтесь командой /auth <пароль>"
            if hasattr(event, "answer"):
                await event.answer(text)
            elif hasattr(event, "reply"):
                await event.reply(text)
            return
        return await handler(event, *args, **kwargs)
    return wrapper

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Хранилище пользовательских сессий
users_data = {}

@dp.message(Command("auth"))
async def auth_user(message: types.Message):
    try:
        password = message.text.split(maxsplit=1)[1].strip()
    except IndexError:
        await message.reply("Отправьте пароль так: /auth <пароль>")
        return
    if password == SECRET_AUTH_PASS:
        user_id = message.from_user.id
        if user_id not in ALLOWED_USERS:
            ALLOWED_USERS.add(user_id)
            save_allowed_users(ALLOWED_USERS)
            await message.reply("Вы успешно авторизованы! Теперь у вас есть доступ ко всем функциям бота.")
        else:
            await message.reply("Вы уже авторизованы.")
    else:
        await message.reply("Неверный пароль.")


@dp.message(Command("choose_file"))
@is_allowed_user
async def choose_file(message: types.Message, **kwargs):
    files = [f for f in os.listdir(DATA_DIR) if f.endswith('.json')]
    if not files:
        await message.answer("В папке data нет JSON файлов.")
        return
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f, callback_data=f"choosefile_{f}")]
            for f in files
        ]
    )
    await message.answer("Выберите файл для работы:", reply_markup=keyboard)


@dp.callback_query(lambda c: c.data.startswith("choosefile_"))
@is_allowed_user
async def process_file_choice(callback: types.CallbackQuery, state: FSMContext, **kwargs):
    file_path = callback.data[len("choosefile_"):]
    full_json_path = os.path.join(DATA_DIR, file_path)
    try:
        with open(full_json_path, "r", encoding="utf-8") as f:
            artworks = json.load(f)
    except Exception as e:
        await callback.message.answer(f"Ошибка открытия файла: {e}")
        return

    user_id = callback.from_user.id
    csv_file_path = os.path.join(DATA_DIR, f"{file_path}_votes.csv")
    users_data[user_id] = {
        "artworks": artworks,
        "index": 0,
        "file": file_path,
        "csv_file": csv_file_path
    }
    await callback.answer(f"Файл {file_path} выбран")
    await send_artwork(callback.message, user_id)


async def send_artwork(message, user_id):
    data = users_data[user_id]
    idx = data["index"]
    artworks = data["artworks"]

    if idx >= len(artworks):
        await message.answer(
            "Вы просмотрели все арты в этом файле! Для начала заново — выберите файл командой /choose_file")
        return

    art = artworks[idx]
    caption = (
        f"<b>ID:</b> {art['id']}\n"
        f"<b>Title:</b> {art['title']}\n"
        f"<b>User:</b> {art['user_name']} (id: {art['user_id']})\n"
        f"<b>Tags:</b> {', '.join(art['tags'])}\n"
        f"<b>Bookmarks:</b> {art['total_bookmarks']}\n"
        f"<b>Views:</b> {art['total_view']}\n"
        f"<b>Status:</b> <b>{idx + 1}/{len(artworks)}</b>"
    )

    image_url = art.get("image_urls", {}).get("original") \
                or art.get("image_urls", {}).get("large") \
                or art.get("image_urls", {}).get("medium") \
                or art.get("image_urls", {}).get("square_medium")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="😍 beauty", callback_data="vote_beauty"),
                InlineKeyboardButton(text="🤮 ugly", callback_data="vote_ugly")
            ]
        ]
    )

    try:
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=image_url,
            caption=caption,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    except Exception as e:
        await message.answer(f"Ошибка при отправке изображения: {e}\n{caption}", reply_markup=keyboard)


@dp.message(Command("start"))
@dp.message(Command("next"))
@is_allowed_user
async def next_art(message: types.Message, **kwargs):
    user_id = message.from_user.id
    if user_id not in users_data or "artworks" not in users_data[user_id]:
        await message.answer("Сначала выберите файл с помощью /choose_file")
        return
    await send_artwork(message, user_id)


@dp.callback_query(lambda c: c.data.startswith("vote_"))
@is_allowed_user
async def vote_callback(callback: types.CallbackQuery, **kwargs):
    user_id = callback.from_user.id
    data = users_data[user_id]
    idx = data["index"]
    artworks = data["artworks"]
    art = artworks[idx]

    vote = "beauty" if callback.data == "vote_beauty" else "ugly"
    csv_file = data["csv_file"]

    is_new = not os.path.exists(csv_file)
    with open(csv_file, "a", encoding="utf-8", newline='') as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["id", "class"])
        writer.writerow([art["id"], vote])

    users_data[user_id]["index"] += 1
    await callback.answer(f"Голос '{vote}' записан!")
    await send_artwork(callback.message, user_id)

# --- Загрузка нового JSON файла ---
@dp.message(Command("upload_json"))
@is_allowed_user
async def upload_json(message: types.Message, state: FSMContext, **kwargs):
    await message.answer("Пришлите JSON-файл в виде документа.")
    await state.set_state("waiting_for_json")

@dp.message(lambda msg, state=None: state and state.get_state() == "waiting_for_json",
            flags={"content_types": ["document"]})
@is_allowed_user
async def process_upload_json(message: types.Message, state: FSMContext, **kwargs):
    document = message.document
    if not document.file_name.endswith('.json'):
        await message.answer("Файл должен быть с расширением .json!")
        return
    file_path = os.path.join(DATA_DIR, document.file_name)
    await bot.download(document, destination=file_path)
    await message.answer(f"Файл {document.file_name} успешно загружен в папку data.")
    await state.clear()

# --- Выгрузка любого доступного CSV файла ---
@dp.message(Command("get_csv"))
@is_allowed_user
async def get_csv(message: types.Message, **kwargs):
    files = [f for f in os.listdir(DATA_DIR) if f.endswith('.csv')]
    if not files:
        await message.answer("В папке data нет CSV файлов.")
        return
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f, callback_data=f"sendcsv_{f}")]
            for f in files
        ]
    )
    await message.answer("Выберите CSV-файл для скачивания:", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data.startswith("sendcsv_"))
@is_allowed_user
async def send_csv(callback: types.CallbackQuery, **kwargs):
    file_name = callback.data[len("sendcsv_"):]
    file_path = os.path.join(DATA_DIR, file_name)
    if not os.path.exists(file_path):
        await callback.message.answer("Файл не найден.")
        return
    doc = FSInputFile(file_path)
    await bot.send_document(callback.message.chat.id, doc)
    await callback.answer("Файл отправлен!")

@dp.message(Command("delete_file"))
@is_allowed_user
async def delete_file(message: types.Message, **kwargs):
    files = [f for f in os.listdir(DATA_DIR) if f.endswith('.json') or f.endswith('.csv')]
    if not files:
        await message.answer("В папке data нет файлов для удаления.")
        return
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f, callback_data=f"deletefile_{f}")]
            for f in files
        ]
    )
    await message.answer("Выберите файл для удаления (он сначала отправится вам, затем будет удалён):",
                         reply_markup=keyboard)

@dp.callback_query(lambda c: c.data.startswith("deletefile_"))
@is_allowed_user
async def delete_file_confirm(callback: types.CallbackQuery, **kwargs):
    file_name = callback.data[len("deletefile_"):]
    file_path = os.path.join(DATA_DIR, file_name)
    if not os.path.exists(file_path):
        await callback.message.answer("Файл не найден или уже удалён.")
        return
    # Отправляем файл пользователю
    doc = FSInputFile(file_path)
    await bot.send_document(callback.message.chat.id, doc)
    # Удаляем файл
    try:
        os.remove(file_path)
        await callback.message.answer(f"Файл <b>{file_name}</b> успешно удалён.", parse_mode="HTML")
    except Exception as e:
        await callback.message.answer(f"Ошибка при удалении файла: {e}")
    await callback.answer("Файл отправлен и удалён.")


async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
