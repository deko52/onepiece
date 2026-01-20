import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = "8402739187:AAHzABjYMj0G0hd-Ww7zGLiNHAbx9H6dNVo"
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- База данных для беты
players = {}  # user_id: данные игрока
pvp_queue = []  # очередь игроков на PvP
ongoing_matches = {}  # активные матчи

# --- Мини-колода для теста
cards = {
    "Луффи": {"rarity": "Йонко", "atk": 400, "def": 310},
    "Зоро": {"rarity": "Мифический", "atk": 370, "def": 290},
    "Нами": {"rarity": "Обычная", "atk": 130, "def": 130},
    "Усопп": {"rarity": "Обычная", "atk": 120, "def": 120},
}

# --- Главное меню (с inline_keyboard)
def main_menu():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Мои карты 🃏", callback_data="my_cards"),
                InlineKeyboardButton(text="Сыграть PvP ⚔️", callback_data="play_pvp")
            ],
            [
                InlineKeyboardButton(text="Баланс 💰", callback_data="balance"),
                InlineKeyboardButton(text="Пак/Открыть пак 🎁", callback_data="packs")
            ]
        ]
    )
    return keyboard

# --- /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    players.setdefault(message.from_user.id, {"coins": 0, "wins": 0, "losses": 0, "timeout": 0})
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\nВыберите действие:",
        reply_markup=main_menu()
    )

# --- Обработка всех callback
@dp.callback_query()
async def handle_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    data = callback_query.data

    if user_id not in players:
        players[user_id] = {"coins": 0, "wins": 0, "losses": 0, "timeout": 0}

    # --- PvP выбор карты
    if "|" in data:
        match_id, card_name = data.split("|")
        match = ongoing_matches.get(match_id)
        if match is None:
            await callback_query.answer("Матч уже завершён")
            return
        if user_id not in match["choices"]:
            match["choices"][user_id] = []
        if card_name not in match["choices"][user_id]:
            match["choices"][user_id].append(card_name)
        await callback_query.answer(f"Вы выбрали: {card_name}")

        if all(len(match["choices"].get(pid, [])) == 2 for pid in match["players"]):
            await resolve_round(match_id)
        return

    # --- Главное меню
    if data == "my_cards":
        msg = "Ваши карты:\n"
        for name, info in cards.items():
            msg += f"{name} | {info['rarity']} | ATK: {info['atk']} | DEF: {info['def']}\n"
        await bot.send_message(user_id, msg)

    elif data == "balance":
        info = players[user_id]
        await bot.send_message(user_id, f"Монеты: {info['coins']}\nПобеды: {info['wins']}\nПоражения: {info['losses']}")

    elif data == "packs":
        await bot.send_message(user_id, "Паки пока в разработке 😉")

    elif data == "play_pvp":
        await start_pvp(user_id)

# --- PvP
async def start_pvp(user_id):
    if players[user_id]["timeout"] > 0:
        await bot.send_message(user_id, f"Вы заблокированы {players[user_id]['timeout']} сек.")
        return

    if user_id not in pvp_queue:
        pvp_queue.append(user_id)
        await bot.send_message(user_id, "Вы добавлены в PvP очередь. Ожидайте оппонента...")

    if len(pvp_queue) >= 2:
        player1 = pvp_queue.pop(0)
        player2 = pvp_queue.pop(0)
        match_id = f"{player1}_{player2}"
        ongoing_matches[match_id] = {
            "players": [player1, player2],
            "round": 1,
            "choices": {},
            "scores": {player1: 0, player2: 0}
        }
        await start_round(match_id)

# --- Раунд
async def start_round(match_id):
    match = ongoing_matches[match_id]
    round_num = match["round"]
    for player_id in match["players"]:
        await send_card_choices(player_id, match_id, round_num)
    asyncio.create_task(round_timer(match_id, 90))

async def send_card_choices(player_id, match_id, round_num):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f"{match_id}|{name}")] for name in cards.keys()
        ]
    )
    await bot.send_message(player_id, f"Раунд {round_num}/3. Выберите 2 карты:", reply_markup=keyboard)

# --- Таймер
async def round_timer(match_id, seconds):
    await asyncio.sleep(seconds)
    match = ongoing_matches.get(match_id)
    if match is None:
        return
    for pid in match["players"]:
        if pid not in match["choices"]:
            selected = list(cards.keys())[:2]
            match["choices"][pid] = selected
            await bot.send_message(pid, f"Автовыбор карт: {', '.join(selected)}")
    await resolve_round(match_id)

# --- Разрешение раунда
async def resolve_round(match_id):
    match = ongoing_matches[match_id]
    scores = {}
    for pid, chosen in match["choices"].items():
        atk = sum(cards[c]["atk"] for c in chosen)
        df = sum(cards[c]["def"] for c in chosen)
        scores[pid] = atk - df

    p1, p2 = match["players"]
    result_msg = f"Раунд {match['round']} результаты:\n"
    result_msg += f"Игрок1: {scores[p1]}\nИгрок2: {scores[p2]}\n"

    if scores[p1] > scores[p2]:
        winner = p1
        result_msg += "Победа Игрока 1\n"
        players[winner]["coins"] += 50
        players[winner]["wins"] += 1
        players[p2]["losses"] += 1
    elif scores[p1] < scores[p2]:
        winner = p2
        result_msg += "Победа Игрока 2\n"
        players[winner]["coins"] += 50
        players[winner]["wins"] += 1
        players[p1]["losses"] += 1
    else:
        result_msg += "Ничья!\n"

    for pid in match["players"]:
        await bot.send_message(pid, result_msg)
        await bot.send_message(pid, "Возврат в главное меню:", reply_markup=main_menu())

    match["round"] += 1
    match["choices"] = {}
    if match["round"] > 3:
        del ongoing_matches[match_id]
    else:
        await start_round(match_id)

# --- Запуск
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot, skip_updates=True))
