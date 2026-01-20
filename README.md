# onepiece
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command

TOKEN = "ВАШ_BOT_TOKEN"  # Вставь свой токен
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- Простая база данных для беты (в памяти)
players = {}  # user_id: данные
pvp_queue = []  # очередь игроков на PvP
ongoing_matches = {}  # match_id: данные матча

# --- Мини-колода для теста
cards = {
    "Луффи": {"rarity": "Йонко", "atk": 400, "def": 310},
    "Зоро": {"rarity": "Мифический", "atk": 370, "def": 290},
    "Нами": {"rarity": "Обычная", "atk": 130, "def": 130},
    "Усопп": {"rarity": "Обычная", "atk": 120, "def": 120},
}

# --- Главное меню
def main_menu(user_name):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("Мои карты 🃏", callback_data="my_cards"),
        InlineKeyboardButton("Сыграть PvP ⚔️", callback_data="play_pvp"),
        InlineKeyboardButton("Баланс 💰", callback_data="balance"),
        InlineKeyboardButton("Пак/Открыть пак 🎁", callback_data="packs")
    )
    return keyboard

# --- Команда /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    players.setdefault(message.from_user.id, {"coins": 0, "wins": 0, "losses": 0, "timeout": 0})
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\nВыберите действие:",
        reply_markup=main_menu(message.from_user.first_name)
    )

# --- Обработка кнопок главного меню
@dp.callback_query()
async def handle_menu(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    action = callback_query.data

    if user_id not in players:
        players[user_id] = {"coins": 0, "wins": 0, "losses": 0, "timeout": 0}

    if action == "my_cards":
        msg = "Ваши карты:\n"
        for name, data in cards.items():
            msg += f"{name} | {data['rarity']} | ATK: {data['atk']} | DEF: {data['def']}\n"
        await bot.send_message(user_id, msg)
    elif action == "balance":
        coins = players[user_id]["coins"]
        wins = players[user_id]["wins"]
        losses = players[user_id]["losses"]
        await bot.send_message(user_id, f"Монеты: {coins}\nПобеды: {wins}\nПоражения: {losses}")
    elif action == "packs":
        await bot.send_message(user_id, "Паки пока в разработке 😉")
    elif action == "play_pvp":
        await start_pvp(user_id)

# --- Функция начала PvP
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

# --- Старт раунда
async def start_round(match_id):
    match = ongoing_matches[match_id]
    round_num = match["round"]
    for player_id in match["players"]:
        await send_card_choices(player_id, match_id, round_num)
    asyncio.create_task(round_timer(match_id, 90))

# --- Выбор карт игроком
async def send_card_choices(player_id, match_id, round_num):
    keyboard = InlineKeyboardMarkup()
    for name in cards.keys():
        keyboard.add(InlineKeyboardButton(name, callback_data=f"{match_id}|{name}"))
    await bot.send_message(player_id, f"Раунд {round_num}/3. Выберите 2 карты:", reply_markup=keyboard)

# --- Таймер 90 секунд на ход
async def round_timer(match_id, seconds):
    await asyncio.sleep(seconds)
    match = ongoing_matches.get(match_id)
    if match is None:
        return
    for player_id in match["players"]:
        if player_id not in match["choices"]:
            selected = list(cards.keys())[:2]
            match["choices"][player_id] = selected
            await bot.send_message(player_id, f"Вы не выбрали карты вовремя. Автовыбор: {', '.join(selected)}")
    await resolve_round(match_id)

# --- Обработка выбора карты
@dp.callback_query()
async def process_card_choice(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if "|" not in callback_query.data:
        return  # пропускаем кнопки главного меню
    match_id, card_name = callback_query.data.split("|")
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
        await bot.send_message(pid, "Возврат в главное меню:", reply_markup=main_menu("Игрок"))

    # Подготовка к следующему раунду
    match["round"] += 1
    match["choices"] = {}
    if match["round"] > 3:
        del ongoing_matches[match_id]
    else:
        await start_round(match_id)

# --- Запуск бота
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))
