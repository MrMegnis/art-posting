import json
import csv
import os
from dotenv import load_dotenv
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Хранилище пользовательских сессий
users_data = {}

@dp.message(Command("choose_file"))
async def choose_file(message: types.Message):
    files = [f for f in os.listdir('.') if f.endswith('.json')]
    if not files:
        await message.answer("В этой папке нет JSON файлов.")
        return
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f, callback_data=f"choosefile_{f}")]
            for f in files
        ]
    )
    await message.answer("Выберите файл для работы:", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data.startswith("choosefile_"))
async def process_file_choice(callback: types.CallbackQuery, state: FSMContext):
    file_path = callback.data[len("choosefile_") :]
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            artworks = json.load(f)
    except Exception as e:
        await callback.message.answer(f"Ошибка открытия файла: {e}")
        return

    user_id = callback.from_user.id
    users_data[user_id] = {
        "artworks": artworks,
        "index": 0,
        "file": file_path,
        "csv_file": f"{file_path}_votes.csv"
    }
    await callback.answer(f"Файл {file_path} выбран")
    await send_artwork(callback.message, user_id)

async def send_artwork(message, user_id):
    data = users_data[user_id]
    idx = data["index"]
    artworks = data["artworks"]

    if idx >= len(artworks):
        await message.answer("Вы просмотрели все арты в этом файле! Для начала заново — выберите файл командой /choose_file")
        return

    art = artworks[idx]
    caption = (
        f"<b>ID:</b> {art['id']}\n"
        f"<b>Title:</b> {art['title']}\n"
        f"<b>User:</b> {art['user_name']} (id: {art['user_id']})\n"
        f"<b>Tags:</b> {', '.join(art['tags'])}\n"
        f"<b>Bookmarks:</b> {art['total_bookmarks']}\n"
        f"<b>Views:</b> {art['total_view']}\n"
        f"<b>Status:</b> <b>{idx+1}/{len(artworks)}</b>"
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
async def next_art(message: types.Message):
    user_id = message.from_user.id
    if user_id not in users_data or "artworks" not in users_data[user_id]:
        await message.answer("Сначала выберите файл с помощью /choose_file")
        return
    await send_artwork(message, user_id)

@dp.callback_query(lambda c: c.data.startswith("vote_"))
async def vote_callback(callback: types.CallbackQuery):
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

async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
