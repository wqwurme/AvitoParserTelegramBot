import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN, CHECK_INTERVAL
from parser import parse_avito
from storage import load_seen, save_seen, load_user_data, save_user_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler()


# ──────────────────────────────────────────
# Состояния FSM
# ──────────────────────────────────────────

class SetupStates(StatesGroup):
    waiting_for_url = State()


# ──────────────────────────────────────────
# Вспомогательные функции
# ──────────────────────────────────────────

def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔗 Установить ссылку")],
            [KeyboardButton(text="▶️ Запустить мониторинг"), KeyboardButton(text="⏹ Остановить")],
            [KeyboardButton(text="📋 Статус")],
        ],
        resize_keyboard=True,
    )


async def check_and_notify(chat_id: int, url: str):
    """Парсит Avito и отправляет новые объявления пользователю."""
    logging.info(f"[{chat_id}] Проверяю новые объявления...")

    seen = load_seen(chat_id)
    ads = parse_avito(url)
    new_ads = [ad for ad in ads if ad["link"] not in seen]

    if not new_ads:
        logging.info(f"[{chat_id}] Новых объявлений нет.")
        return

    logging.info(f"[{chat_id}] Новых: {len(new_ads)}")

    for ad in new_ads:
        text = (
            f"🏷 <b>{ad['title']}</b>\n"
            f"💰 {ad['price']}\n"
            f"🔗 <a href='{ad['link']}'>Открыть на Avito</a>"
        )
        try:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
            seen.add(ad["link"])
        except Exception as e:
            logging.error(f"Ошибка отправки: {e}")

    save_seen(chat_id, seen)


# ──────────────────────────────────────────
# Хэндлеры
# ──────────────────────────────────────────

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Я слежу за объявлениями на Avito и присылаю новые.\n\n"
        "Нажми <b>🔗 Установить ссылку</b>, чтобы начать.",
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


@dp.message(F.text == "🔗 Установить ссылку")
async def ask_for_url(message: Message, state: FSMContext):
    await state.set_state(SetupStates.waiting_for_url)
    await message.answer(
        "📎 Открой Avito, настрой фильтры поиска и скопируй ссылку из браузера.\n\n"
        "Вставь её сюда 👇",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message(SetupStates.waiting_for_url)
async def receive_url(message: Message, state: FSMContext):
    url = message.text.strip()

    if "avito.ru" not in url:
        await message.answer("❌ Это не похоже на ссылку Avito. Попробуй ещё раз.")
        return

    user_data = load_user_data()
    chat_id = message.chat.id
    user_data[str(chat_id)] = {"url": url, "active": False}
    save_user_data(user_data)

    await state.clear()
    await message.answer(
        f"✅ Ссылка сохранена!\n\n<code>{url}</code>\n\n"
        "Теперь нажми <b>▶️ Запустить мониторинг</b>.",
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


@dp.message(F.text == "▶️ Запустить мониторинг")
async def start_monitoring(message: Message):
    chat_id = message.chat.id
    user_data = load_user_data()
    entry = user_data.get(str(chat_id))

    if not entry or not entry.get("url"):
        await message.answer("⚠️ Сначала установи ссылку — нажми 🔗 Установить ссылку.")
        return

    if entry.get("active"):
        await message.answer("▶️ Мониторинг уже запущен.")
        return

    user_data[str(chat_id)]["active"] = True
    save_user_data(user_data)

    url = entry["url"]
    job_id = f"monitor_{chat_id}"

    if not scheduler.get_job(job_id):
        scheduler.add_job(
            check_and_notify,
            "interval",
            seconds=CHECK_INTERVAL,
            id=job_id,
            args=[chat_id, url],
        )

    await message.answer(
        f"✅ Мониторинг запущен! Проверяю каждые {CHECK_INTERVAL // 60} минут.\n\n"
        "Первая проверка — прямо сейчас 👇"
    )
    await check_and_notify(chat_id, url)


@dp.message(F.text == "⏹ Остановить")
async def stop_monitoring(message: Message):
    chat_id = message.chat.id
    user_data = load_user_data()
    entry = user_data.get(str(chat_id))

    if not entry or not entry.get("active"):
        await message.answer("⏹ Мониторинг и так не запущен.")
        return

    user_data[str(chat_id)]["active"] = False
    save_user_data(user_data)

    job_id = f"monitor_{chat_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    await message.answer("⏹ Мониторинг остановлен.")


@dp.message(F.text == "📋 Статус")
async def show_status(message: Message):
    chat_id = message.chat.id
    user_data = load_user_data()
    entry = user_data.get(str(chat_id))

    if not entry:
        await message.answer("❌ Ссылка не установлена.")
        return

    url = entry.get("url", "не установлена")
    active = entry.get("active", False)
    status = "✅ Запущен" if active else "⏹ Остановлен"

    await message.answer(
        f"📋 <b>Статус мониторинга:</b> {status}\n\n"
        f"🔗 <b>Ссылка:</b>\n<code>{url}</code>",
        parse_mode="HTML",
    )


# ──────────────────────────────────────────
# Запуск
# ──────────────────────────────────────────

async def main():
    logging.info("Бот запущен...")
    scheduler.start()

    # Восстанавливаем активные задачи после перезапуска
    user_data = load_user_data()
    for chat_id_str, entry in user_data.items():
        if entry.get("active") and entry.get("url"):
            job_id = f"monitor_{chat_id_str}"
            scheduler.add_job(
                check_and_notify,
                "interval",
                seconds=CHECK_INTERVAL,
                id=job_id,
                args=[int(chat_id_str), entry["url"]],
            )
            logging.info(f"Восстановлен мониторинг для {chat_id_str}")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
