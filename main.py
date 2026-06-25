import logging, random, json, os, re, asyncio, atexit, sqlite3, threading
from datetime import datetime, timedelta
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = "8968491013:AAEbpJkA2h8AS5Q7gim_o4sc5wBRerZLl5w"
DB_FILE = "travka.db"

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
OWNER_IDS = [5804145780]
AUTO_DELETE_DELAY = 30

# Config
BASE_CD = 180
MIN_CD = 30
CLOCK_CHANCE = 5
GRASS_PRICE, TOBACCO_PRICE = 2, 3
CIG_PRICE, CIGAR_PRICE = 50, 150
BAG_PRICE = 500
LOTTERY_PRICE = 50
EVENT_ACTIVE = False
EVENT_MULT = 3

LUCK = {"x2": {"p": 500, "m": 2, "e": "✨"}, "x3": {"p": 1200, "m": 3, "e": "🔥"},
        "x4": {"p": 2500, "m": 4, "e": "💎"}, "x5": {"p": 5000, "m": 5, "e": "👑"},
        "x10": {"p": 15000, "m": 10, "e": "🌟"}}

GRASS = {
    "обычная": {"e": "🌿", "xp": 1, "t": 1, "c": 2, "s": 2},
    "редкая": {"e": "🍀", "xp": 3, "t": 3, "c": 5, "s": 5},
    "эпическая": {"e": "🌲", "xp": 5, "t": 5, "c": 8, "s": 10},
    "легендарная": {"e": "🌳", "xp": 10, "t": 10, "c": 15, "s": 25},
    "божественная": {"e": "🌺", "xp": 25, "t": 25, "c": 30, "s": 50}}

DECL = {"обычная": ("обычную", "обычной"), "редкая": ("редкую", "редкой"),
        "эпическая": ("эпическую", "эпической"), "легендарная": ("легендарную", "легендарной"),
        "божественная": ("божественную", "божественной")}

SMOKE_TXT = ["охх, хорошо пошло...", "вот это кайф!", "ммм, божественно...", "уфф, вкуснятина!",
             "о дааа, это то что надо", "хмм, неплохо...", "вау, вкусно!", "ооо, заебись!",
             "классно курится!", "прям в точку!", "бля, вкусно!", "невероятно!", "пиздато!",
             "охуенно!", "круто!", "бомбезно!", "шикарно!", "превосходно!", "восхитительно!", "идеально!"]

CIG_FX = ["🔥 ЛЮТЫЙ ЭФФЕКТ! Мозг взорвался!", "💥 БА-БАХ! Удар по мозгу!", "🌪️ Поток... Всё замедлилось!",
          "⚡ ЭЛЕКТРИЧЕСКИЙ ШОК!", "🎆 Салют в голове!", "🚀 РАКЕТА! Выше облаков!", "🌋 ВУЛКАН!",
          "🎰 ДЖЕКПОТ!", "🌟 СУПЕРНОВА!", "🎢 МЕГА-ГОРКА!"]

TITLES = {1: "🌱 Новичок", 2: "🌿 Собиратель", 3: "🍀 Опытный", 4: "🌲 Травник",
          5: "🌳 Мастер", 6: "🌺 Легенда", 7: "👑 Бог травы", 8: "🔥 Повелитель дыма",
          9: "🌌 Космический", 10: "🧘‍♂️ Просветлённый"}

RACK_SHOP = {
    "благословение": {"p": 100, "e": "🙏", "d": "+50% XP 1ч"},
    "двойной_урожай": {"p": 200, "e": "🌾", "d": "x2 ферма 10 сборов"},
    "щит": {"p": 300, "e": "🛡️", "d": "Защита от воров 24ч"},
    "магнит": {"p": 500, "e": "🧲", "d": "+25% шанс часов 24ч"},
    "золотая_рука": {"p": 1000, "e": "✋", "d": "+50% к воровству 24ч"},
    "кристалл_удачи": {"p": 150, "e": "💎", "d": "+1 удача x2"},
    "портал_травы": {"p": 250, "e": "🌀", "d": "+50 травы мгновенно"},
    "копилка": {"p": 400, "e": "🏦", "d": "+200 монет мгновенно"},
    "взрыв_опыта": {"p": 350, "e": "💥", "d": "+50 XP мгновенно"},
    "легендарный_семя": {"p": 2000, "e": "🌺", "d": "Следующий сбор — божественная"},
    "бессмертие": {"p": 5000, "e": "👼", "d": "Не теряешь ресурсы при проигрыше 24ч"}}

LOTTERY = {
    "Джекпот": {"c": 1, "m": 10, "e": "💎"}, "Крупный": {"c": 5, "m": 5, "e": "🤑"},
    "Хороший": {"c": 15, "m": 3, "e": "💰"}, "Малый": {"c": 30, "m": 2, "e": "🪙"},
    "Утешительный": {"c": 49, "m": 1, "e": "🍀"}}

TRADE_STATE = {}
_db_lock = asyncio.Lock()

BOT_COMMANDS = [
    BotCommand("collect", "🌿 Собрать траву"), BotCommand("craft", "🔨 Скрафтить"),
    BotCommand("smoke", "🚬 Покурить"), BotCommand("profile", "📊 Профиль"),
    BotCommand("top", "🏆 Топы"), BotCommand("inventory", "📦 Инвентарь"),
    BotCommand("bonus", "🎁 Бонус"), BotCommand("sell", "💰 Продать"),
    BotCommand("farm", "🏡 Ферма"), BotCommand("rob", "🥷 Ограбить"),
    BotCommand("help", "❓ Помощь")]

# === SQLITE ===
def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        chat_id TEXT, user_id TEXT, name TEXT, grass INTEGER DEFAULT 0,
        smoked INTEGER DEFAULT 0, xp INTEGER DEFAULT 0, lvl INTEGER DEFAULT 1,
        last REAL DEFAULT 0, clocks INTEGER DEFAULT 0, bonus TEXT DEFAULT "",
        tobacco INTEGER DEFAULT 0, coins INTEGER DEFAULT 0, cigarettes INTEGER DEFAULT 0,
        cigars INTEGER DEFAULT 0, fast_farm INTEGER DEFAULT 0, fast_farm_last REAL DEFAULT 0,
        last_grass_type TEXT DEFAULT "обычная", is_bot INTEGER DEFAULT 0,
        luck_x2 INTEGER DEFAULT 0, luck_x3 INTEGER DEFAULT 0, luck_x4 INTEGER DEFAULT 0,
        luck_x5 INTEGER DEFAULT 0, luck_x10 INTEGER DEFAULT 0, active_luck TEXT,
        rackumar INTEGER DEFAULT 0, bag INTEGER DEFAULT 0, rob_lvl INTEGER DEFAULT 1,
        rob_last REAL DEFAULT 0, blessing_end REAL DEFAULT 0, double_harvest INTEGER DEFAULT 0,
        shield_end REAL DEFAULT 0, magnet_end REAL DEFAULT 0, golden_hand_end REAL DEFAULT 0,
        immortal_end REAL DEFAULT 0,
        PRIMARY KEY (chat_id, user_id))''')
    conn.commit(); conn.close()

init_db()

_local = threading.local()
def get_conn():
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    return _local.conn

def row_to_dict(row):
    keys = ["chat_id", "user_id", "name", "grass", "smoked", "xp", "lvl", "last", "clocks",
            "bonus", "tobacco", "coins", "cigarettes", "cigars", "fast_farm", "fast_farm_last",
            "last_grass_type", "is_bot", "luck_x2", "luck_x3", "luck_x4", "luck_x5", "luck_x10",
            "active_luck", "rackumar", "bag", "rob_lvl", "rob_last", "blessing_end",
            "double_harvest", "shield_end", "magnet_end", "golden_hand_end", "immortal_end"]
    return {k: row[i] for i, k in enumerate(keys)}

def get_user_db(cid, uid):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE chat_id=? AND user_id=?", (str(cid), str(uid)))
    row = c.fetchone()
    if row is None:
        c.execute('''INSERT INTO users (chat_id, user_id) VALUES (?, ?)''', (str(cid), str(uid)))
        conn.commit()
        c.execute("SELECT * FROM users WHERE chat_id=? AND user_id=?", (str(cid), str(uid)))
        row = c.fetchone()
    return row_to_dict(row)

def save_user_db(cid, uid, data):
    conn = get_conn()
    c = conn.cursor()
    fields = ["name", "grass", "smoked", "xp", "lvl", "last", "clocks", "bonus", "tobacco",
              "coins", "cigarettes", "cigars", "fast_farm", "fast_farm_last", "last_grass_type",
              "is_bot", "luck_x2", "luck_x3", "luck_x4", "luck_x5", "luck_x10", "active_luck",
              "rackumar", "bag", "rob_lvl", "rob_last", "blessing_end", "double_harvest",
              "shield_end", "magnet_end", "golden_hand_end", "immortal_end"]
    vals = [data.get(f, 0) if f not in ["name", "bonus", "last_grass_type", "active_luck"] else data.get(f, "") for f in fields]
    c.execute('''UPDATE users SET ''' + ", ".join([f"{f}=?" for f in fields]) + " WHERE chat_id=? AND user_id=?",
              vals + [str(cid), str(uid)])
    conn.commit()

def get_all_users_db(cid):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE chat_id=? AND is_bot=0", (str(cid),))
    return [row_to_dict(row) for row in c.fetchall()]

# === HELPERS ===
def get_cd(ud): return max(BASE_CD - (ud["lvl"] - 1) * 120, MIN_CD)
def rob_cd(ud): return max(600 - (ud["rob_lvl"] - 1) * 60, 60)
def rob_max(ud): return 5 + ud["rob_lvl"] * 3
def fmt(t):
    if t >= 3600: return f"{int(t//3600)}ч {int(t%3600//60)}м"
    elif t >= 60: return f"{int(t//60)}м {int(t%60)}с"
    return f"{int(t)}с"

def lvl_up(ud):
    while ud["xp"] >= ud["lvl"] * 10: ud["xp"] -= ud["lvl"] * 10; ud["lvl"] += 1
    return ud["lvl"]

def rank(cid, uid, key="smoked"):
    users = get_all_users_db(cid)
    s = sorted(users, key=lambda x: (x.get(key, 0), x.get("lvl", 1)), reverse=True)
    for i, u in enumerate(s, 1):
        if int(u["user_id"]) == uid: return f"#{i}"
    return "?"

def decl(n):
    if 11 <= n % 100 <= 14: return "грамм"
    elif n % 10 == 1: return "грамм"
    elif 2 <= n % 10 <= 4: return "грамма"
    return "грамм"

def decl_cig(n):
    if 11 <= n % 100 <= 14: return "сигарет"
    elif n % 10 == 1: return "сигарета"
    elif 2 <= n % 10 <= 4: return "сигареты"
    return "сигарет"

def decl_cigar(n):
    if 11 <= n % 100 <= 14: return "сигар"
    elif n % 10 == 1: return "сигара"
    elif 2 <= n % 10 <= 4: return "сигары"
    return "сигар"

def parse_num(t):
    m = re.search(r'(\d+)', t)
    return int(m.group(1)) if m else None

def is_owner(uid): return uid in OWNER_IDS

async def auto_del(msg, delay=AUTO_DELETE_DELAY):
    try: await asyncio.sleep(delay); await msg.delete()
    except: pass

async def reply_del(u, text, del_user=True):
    try:
        m = await u.message.reply_text(text)
    except Exception:
        try:
            m = await u.effective_chat.send_message(text)
        except Exception:
            return None
    asyncio.create_task(auto_del(m))
    if del_user and u.message: asyncio.create_task(auto_del(u.message, delay=AUTO_DELETE_DELAY))
    return m

async def check_group(u):
    if u.effective_chat.type == "private":
        await u.message.reply_text("🌿 Я бот для чатов! Добавляй в чат и становись миллионером")
        return False
    return True

# === COMMANDS ===
async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    await reply_del(u, "🌿 Собирай травку и становись миллионером 🌿\n\nКоманды: собрать, крафт, курить, профиль, инвентарь, бонус, ферма, роб, ставка, деп, лотерея, топ")

async def collect(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, u.effective_user.id)
        now = datetime.now().timestamp(); cd = get_cd(ud); passed = now - ud["last"]
        if passed < cd:
            await reply_del(u, f"Травка ещё растёт 🌿 {fmt(cd - passed)}!\nКулдаун: {fmt(cd)} (Lv.{ud['lvl']})")
            return
        r = random.randint(1, 100)
        gt = "обычная" if r <= 50 else "редкая" if r <= 80 else "эпическая" if r <= 95 else "легендарная" if r <= 99 else "божественная"
        g = GRASS[gt].copy(); amt = random.randint(1, 3)
        if EVENT_ACTIVE: amt *= EVENT_MULT; g["xp"] *= EVENT_MULT; g["t"] *= EVENT_MULT; g["c"] *= EVENT_MULT
        if ud.get("magnet_end", 0) > now and random.randint(1, 100) <= 25: ud["clocks"] += 1
        dh = ud.get("double_harvest", 0)
        if dh > 0: amt *= 2; ud["double_harvest"] = max(0, dh - 1)
        ud["grass"] += amt; ud["xp"] += g["xp"]; ud["last"] = now
        ud["name"] = u.effective_user.username or u.effective_user.first_name; ud["last_grass_type"] = gt
        old = ud["lvl"]; new = lvl_up(ud)
        clock_drop = ""
        if random.randint(1, 100) <= CLOCK_CHANCE:
            drop = EVENT_MULT if EVENT_ACTIVE else 1; ud["clocks"] += drop
            clock_drop = f"\n\n✨ РЕДКАЯ НАХОДКА!\n⏱️ +{drop} Часов!"
        save_user_db(u.effective_chat.id, u.effective_user.id, ud)
    ev = "\n\n🎉 ИВЕНТ АКТИВЕН! x3!" if EVENT_ACTIVE else ""
    msg = f"{g['e']} Собрал {DECL[gt][0]} траву!\n📦 +{amt} гр\n⭐ +{g['xp']} XP\n🎒 Всего: {ud['grass']} гр"
    if new > old: msg += f"\n\n🎉 УРОВЕНЬ ПОВЫШЕН!\n{TITLES.get(new, 'Lv.' + str(new))}!"
    msg += clock_drop + ev
    await reply_del(u, msg)

async def craft(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, u.effective_user.id)
        if ud["grass"] < 1:
            await reply_del(u, "😢 Нет травы! Напиши собрать 🌿")
            return
        crafted = ud["grass"]; total_t = 0; total_x = 0
        for _ in range(crafted): total_t += random.randint(1, 3); total_x += 1
        if EVENT_ACTIVE: total_t *= EVENT_MULT; total_x *= EVENT_MULT
        ud["tobacco"] += total_t; ud["grass"] = 0; ud["xp"] += total_x
        ud["name"] = u.effective_user.username or u.effective_user.first_name
        old = ud["lvl"]; new = lvl_up(ud)
        save_user_db(u.effective_chat.id, u.effective_user.id, ud)
    ev = "\n\n🎉 ИВЕНТ АКТИВЕН! x3!" if EVENT_ACTIVE else ""
    msg = f"🔨 Скрафчено!\n🌿 Использовано: {crafted} гр\n📦 Получено: {total_t} гр табака\n⭐ +{total_x} XP"
    if new > old: msg += f"\n\n🎉 УРОВЕНЬ ПОВЫШЕН!\n{TITLES.get(new, 'Lv.' + str(new))}!"
    msg += ev
    await reply_del(u, msg)

async def smoke(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    text = u.message.text.lower().strip(); now = datetime.now().timestamp()
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, u.effective_user.id)
        xp_mult = 1.5 if ud.get("blessing_end", 0) > now else 1
        ev = "\n\n🎉 ИВЕНТ АКТИВЕН! x3!" if EVENT_ACTIVE else ""

        if "всё" in text or "все" in text:
            if ud["tobacco"] < 1:
                await reply_del(u, "😢 Нет табака! Напиши крафт 🌿")
                return
            total = ud["tobacco"]; ud["smoked"] += total
            xp = int(total * xp_mult); coins = random.randint(total, total * 3)
            if EVENT_ACTIVE: xp *= EVENT_MULT; coins *= EVENT_MULT
            ud["xp"] += xp; ud["coins"] += coins; ud["tobacco"] = 0
            ud["name"] = u.effective_user.username or u.effective_user.first_name
            old = ud["lvl"]; new = lvl_up(ud)
            rack_gain = random.randint(3, 8)
            if EVENT_ACTIVE: rack_gain *= EVENT_MULT
            ud["rackumar"] += rack_gain
            save_user_db(u.effective_chat.id, u.effective_user.id, ud)
            fx = "\n".join(random.sample(SMOKE_TXT, min(3, len(SMOKE_TXT))))
            msg = f"🚬🚬🚬 ВЫКУРИЛ ВСЁ!!! 🚬🚬🚬\n\n📦 {total} гр\n\n{fx}\n\n⭐ +{xp} XP\n💰 +{coins}\n🌿 Раскумар: +{rack_gain}\n📊 Всего: {ud['smoked']} гр"
            if new > old: msg += f"\n\n🎉 УРОВЕНЬ ПОВЫШЕН!\n{TITLES.get(new, 'Lv.' + str(new))}!"
            msg += ev
            await reply_del(u, msg); return

        elif "сигарет" in text:
            if ud["cigarettes"] < 1:
                await reply_del(u, "😢 Нет сигарет! Купи: 'купить сигареты' 🚬")
                return
            ud["cigarettes"] -= 1; xp = int(random.randint(15, 25) * xp_mult); coins = random.randint(10, 20)
            ud["smoked"] += 5
            if EVENT_ACTIVE: xp *= EVENT_MULT; coins *= EVENT_MULT
            ud["xp"] += xp; ud["coins"] += coins
            rack_gain = random.randint(1, 2)
            if EVENT_ACTIVE: rack_gain *= EVENT_MULT
            ud["rackumar"] += rack_gain
            ud["name"] = u.effective_user.username or u.effective_user.first_name
            old = ud["lvl"]; new = lvl_up(ud)
            save_user_db(u.effective_chat.id, u.effective_user.id, ud)
            msg = f"🚬 Сигарета!\n\n{random.choice(CIG_FX)}\n\n⭐ +{xp} XP\n💰 +{coins}\n🌿 Раскумар: +{rack_gain}\n📊 Всего: {ud['smoked']} гр\n🚬 Осталось: {ud['cigarettes']} {decl_cig(ud['cigarettes'])}"
            if new > old: msg += f"\n\n🎉 УРОВЕНЬ ПОВЫШЕН!\n{TITLES.get(new, 'Lv.' + str(new))}!"
            msg += ev
            await reply_del(u, msg); return

        elif "сигар" in text:
            if ud["cigars"] < 1:
                await reply_del(u, "😢 Нет сигар! Купи: 'купить сигары' 🚬")
                return
            ud["cigars"] -= 1; xp = int(random.randint(40, 60) * xp_mult); coins = random.randint(30, 50)
            ud["smoked"] += 10
            if EVENT_ACTIVE: xp *= EVENT_MULT; coins *= EVENT_MULT
            ud["xp"] += xp; ud["coins"] += coins
            rack_gain = random.randint(2, 4)
            if EVENT_ACTIVE: rack_gain *= EVENT_MULT
            ud["rackumar"] += rack_gain
            ud["name"] = u.effective_user.username or u.effective_user.first_name
            old = ud["lvl"]; new = lvl_up(ud)
            save_user_db(u.effective_chat.id, u.effective_user.id, ud)
            msg = f"🚬🚬 Сигара! МЕГА!\n\n{random.choice(CIG_FX)}\n\n⭐ +{xp} XP\n💰 +{coins}\n🌿 Раскумар: +{rack_gain}\n📊 Всего: {ud['smoked']} гр\n🚬 Осталось: {ud['cigars']} {decl_cigar(ud['cigars'])}"
            if new > old: msg += f"\n\n🎉 УРОВЕНЬ ПОВЫШЕН!\n{TITLES.get(new, 'Lv.' + str(new))}!"
            msg += ev
            await reply_del(u, msg); return

        else:
            num = parse_num(text)
            if num and num > 0:
                if ud["tobacco"] < 1:
                    await reply_del(u, "😢 Нет табака! Напиши крафт 🌿")
                    return
                amt = min(num, ud["tobacco"]); ud["tobacco"] -= amt; ud["smoked"] += amt
                xp = int(amt * xp_mult)
                if EVENT_ACTIVE: xp *= EVENT_MULT
                ud["xp"] += xp
                rack_gain = random.randint(1, 2)
                if EVENT_ACTIVE: rack_gain *= EVENT_MULT
                ud["rackumar"] += rack_gain
                ud["name"] = u.effective_user.username or u.effective_user.first_name
                old = ud["lvl"]; new = lvl_up(ud)
                save_user_db(u.effective_chat.id, u.effective_user.id, ud)
                msg = f"🚬 Закурил {amt} {decl(amt)}...\n\n{random.choice(SMOKE_TXT)}\n\n📊 Всего: {ud['smoked']} гр\n🎒 Табака: {ud['tobacco']} гр\n🌿 Раскумар: +{rack_gain}"
                if new > old: msg += f"\n\n🎉 УРОВЕНЬ ПОВЫШЕН!\n{TITLES.get(new, 'Lv.' + str(new))}!"
                msg += ev
                await reply_del(u, msg); return

            if ud["tobacco"] < 1:
                await reply_del(u, "😢 Нет табака! Напиши крафт 🌿")
                return
            amt = random.randint(1, min(5, ud["tobacco"])); ud["tobacco"] -= amt; ud["smoked"] += amt
            xp = int(amt * xp_mult)
            if EVENT_ACTIVE: xp *= EVENT_MULT
            ud["xp"] += xp
            rack_gain = random.randint(1, 3)
            if EVENT_ACTIVE: rack_gain *= EVENT_MULT
            ud["rackumar"] += rack_gain
            ud["name"] = u.effective_user.username or u.effective_user.first_name
            old = ud["lvl"]; new = lvl_up(ud)
            save_user_db(u.effective_chat.id, u.effective_user.id, ud)
            msg = f"🚬 Закурил {amt} {decl(amt)}...\n\n{random.choice(SMOKE_TXT)}\n\n📊 Всего: {ud['smoked']} гр\n🎒 Табака: {ud['tobacco']} гр\n🌿 Раскумар: +{rack_gain}"
            if new > old: msg += f"\n\n🎉 УРОВЕНЬ ПОВЫШЕН!\n{TITLES.get(new, 'Lv.' + str(new))}!"
            msg += ev
            await reply_del(u, msg)

async def profile(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, u.effective_user.id)
        ud["name"] = u.effective_user.username or u.effective_user.first_name
        save_user_db(u.effective_chat.id, u.effective_user.id, ud)
    nx = ud["lvl"] * 10; pr = min(100, int(ud["xp"] / nx * 100))
    bar = "█" * (pr // 10) + "░" * (10 - pr // 10); cd = get_cd(ud)
    luck = f"✨x2:{ud['luck_x2']} 🔥x3:{ud['luck_x3']} 💎x4:{ud['luck_x4']} 👑x5:{ud['luck_x5']} 🌟x10:{ud['luck_x10']}"
    active = f"\n🍀 Активная: {ud['active_luck'].upper()}" if ud.get("active_luck") else ""
    ev = "\n\n🎉 ИВЕНТ АКТИВЕН! x3!" if EVENT_ACTIVE else ""
    now = datetime.now().timestamp(); buffs = ""
    if ud.get("blessing_end", 0) > now: buffs += "\n🙏 Благословение"
    if ud.get("shield_end", 0) > now: buffs += "\n🛡️ Щит"
    if ud.get("golden_hand_end", 0) > now: buffs += "\n✋ Золотая рука"
    if ud.get("magnet_end", 0) > now: buffs += "\n🧲 Магнит"
    if ud.get("double_harvest", 0) > 0: buffs += f"\n🌾 Двойной урожай: {ud['double_harvest']}"
    if ud.get("immortal_end", 0) > now: buffs += "\n👼 Бессмертие"
    msg = f"👤 {u.effective_user.first_name}\n\n{TITLES.get(ud['lvl'], 'Lv.' + str(ud['lvl']))}\n📊 Lv.{ud['lvl']}\n⭐ XP: {ud['xp']}/{nx}\n[{bar}] {pr}%\n\n🌿 Трава: {ud['grass']} гр\n📦 Табак: {ud['tobacco']} гр\n💰 Монеты: {ud['coins']}\n🚬 Сигареты: {ud['cigarettes']} {decl_cig(ud['cigarettes'])}\n🚬 Сигары: {ud['cigars']} {decl_cigar(ud['cigars'])}\n🌿 Раскумар: {ud['rackumar']}\n🚬 Всего: {ud['smoked']} гр\n⏱️ Часы: {ud['clocks']}\n⚡ Ферма: {'✅ Lv.' + str(ud['fast_farm']) if ud['fast_farm'] > 0 else '❌'}\n🥷 Вор: Lv.{ud['rob_lvl']}\n🎒 Мешочек: {'✅' if ud['bag'] else '❌'}\n\n🍀 Удача:\n{luck}{active}{buffs}\n\n⏱️ Кулдаун: {fmt(cd)}\n🥷 Кулдаун воровства: {fmt(rob_cd(ud))}\n\n🏆 Место: {rank(u.effective_chat.id, u.effective_user.id)}\n🌿 Раскумар: #{rank(u.effective_chat.id, u.effective_user.id, 'rackumar')}" + ev
    await reply_del(u, msg)

async def tops(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    users = get_all_users_db(u.effective_chat.id)
    if not users: return await reply_del(u, "😢 В чате ещё никто не играл!")
    text = u.message.text.lower().strip()
    key, emoji, title = "smoked", "🌿", "Травники"
    if "монет" in text or "coins" in text: key, emoji, title = "coins", "🪙", "Монетки"
    elif "трав" in text: key, emoji, title = "grass", "🌿", "Травка"
    elif "раскумар" in text: key, emoji, title = "rackumar", "🌿", "Раскумар"
    s = sorted(users, key=lambda x: (x.get(key, 0), x.get("lvl", 1)), reverse=True)[:20]
    m = f"{title}{emoji}\n"
    for i, v in enumerate(s, 1): m += f"\n{i}. {v.get('name', 'Без имени') or 'Без имени'} — {v.get(key, 0)}{emoji}"
    await reply_del(u, m)

async def inv(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, u.effective_user.id)
    cd = get_cd(ud); luck = f"✨x2:{ud['luck_x2']} 🔥x3:{ud['luck_x3']} 💎x4:{ud['luck_x4']} 👑x5:{ud['luck_x5']} 🌟x10:{ud['luck_x10']}"
    active = f"\n🍀 Активная: {ud['active_luck'].upper()}" if ud.get("active_luck") else ""
    msg = f"🎒 Инвентарь\n\n🌿 Трава: {ud['grass']} гр\n📦 Табак: {ud['tobacco']} гр\n💰 Монеты: {ud['coins']}\n🚬 Сигареты: {ud['cigarettes']} {decl_cig(ud['cigarettes'])}\n🚬 Сигары: {ud['cigars']} {decl_cigar(ud['cigars'])}\n🌿 Раскумар: {ud['rackumar']}\n⏱️ Часы: {ud['clocks']}\n⚡ Ферма: {'✅ Lv.' + str(ud['fast_farm']) if ud['fast_farm'] > 0 else '❌'}\n🥷 Вор: Lv.{ud['rob_lvl']}\n🎒 Мешочек: {'✅' if ud['bag'] else '❌'}\n\n🍀 Удача:\n{luck}{active}\n\n⏱️ Кулдаун: {fmt(cd)} (Lv.{ud['lvl']})"
    if ud["clocks"] > 0: msg += "\n\n💡 'использовать часы' — сбросить!"
    await reply_del(u, msg)

async def sell(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    text = u.message.text.lower().strip()
    is_tobacco = "табак" in text
    item_key = "tobacco" if is_tobacco else "grass"
    item_name = "табака" if is_tobacco else "травы"
    num = parse_num(text)
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, u.effective_user.id)
        price = 4 if is_tobacco else GRASS[ud.get("last_grass_type", "обычная")]["s"]
        if not num or num < 1:
            if ud[item_key] < 1:
                await reply_del(u, f"😢 Нет {item_name}! Напиши {'крафт' if is_tobacco else 'собрать'} 🌿")
                return
            earned = ud[item_key] * price
            if EVENT_ACTIVE: earned *= EVENT_MULT
            sold_amt = ud[item_key]; ud["coins"] += earned; ud[item_key] = 0
            ud["name"] = u.effective_user.username or u.effective_user.first_name
            save_user_db(u.effective_chat.id, u.effective_user.id, ud)
            ev = "\n\n🎉 ИВЕНТ АКТИВЕН! x3!" if EVENT_ACTIVE else ""
            await reply_del(u, f"💰 Продажа {item_name}!\n\n📦 Продано: {sold_amt} гр\n💰 Заработано: {earned}\n💰 Всего: {ud['coins']}" + ev)
            return
        if ud[item_key] < num:
            await reply_del(u, f"😢 Недостаточно {item_name}!\n📦 У тебя: {ud[item_key]} гр\n📦 Хочешь продать: {num} гр")
            return
        earned = num * price
        if EVENT_ACTIVE: earned *= EVENT_MULT
        ud["coins"] += earned; ud[item_key] -= num
        ud["name"] = u.effective_user.username or u.effective_user.first_name
        save_user_db(u.effective_chat.id, u.effective_user.id, ud)
    ev = "\n\n🎉 ИВЕНТ АКТИВЕН! x3!" if EVENT_ACTIVE else ""
    await reply_del(u, f"💰 Продажа {item_name}!\n\n📦 Продано: {num} гр\n💰 Заработано: {earned}\n💰 Всего: {ud['coins']}\n📦 Осталось: {ud[item_key]} гр" + ev)

async def buy(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    text = u.message.text.lower().strip()
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, u.effective_user.id)
        if "мешочек" in text or "мешок" in text or "bag" in text:
            if ud["bag"]:
                await reply_del(u, "🎒 У тебя уже есть мешочек!"); return
            if ud["coins"] < BAG_PRICE:
                await reply_del(u, f"😢 Недостаточно!\n🎒 Мешочек: {BAG_PRICE}\n💰 У тебя: {ud['coins']}"); return
            ud["coins"] -= BAG_PRICE; ud["bag"] = 1
            ud["name"] = u.effective_user.username or u.effective_user.first_name
            save_user_db(u.effective_chat.id, u.effective_user.id, ud)
            await reply_del(u, f"🎒 Мешочек куплен!\n💰 Потрачено: {BAG_PRICE}\n💰 Осталось: {ud['coins']}\n\n🥷 Теперь можешь воровать!")
            return
        if "раскумар" in text and ("магазин" in text or "купить" in text):
            shop = "🌿 Магазин раскумара\n\n"
            for name, data in RACK_SHOP.items():
                shop += f"{data['e']} {name} — {data['p']} раскумара\n   {data['d']}\n\n"
            shop += "💡 Напиши 'купить [название]'"
            await reply_del(u, shop); return
        for name, data in RACK_SHOP.items():
            if name.replace("_", " ") in text or name in text:
                if ud["rackumar"] < data["p"]:
                    await reply_del(u, f"😢 Недостаточно!\n{data['e']} {name}: {data['p']}\n🌿 У тебя: {ud['rackumar']}"); return
                ud["rackumar"] -= data["p"]; now = datetime.now().timestamp()
                if name == "благословение": ud["blessing_end"] = now + 3600; effect = "+50% XP 1ч!"
                elif name == "двойной_урожай": ud["double_harvest"] = 10; effect = "x2 ферма 10 сборов!"
                elif name == "щит": ud["shield_end"] = now + 86400; effect = "Защита 24ч!"
                elif name == "магнит": ud["magnet_end"] = now + 86400; effect = "+25% часы 24ч!"
                elif name == "золотая_рука": ud["golden_hand_end"] = now + 86400; effect = "+50% воровство 24ч!"
                elif name == "кристалл_удачи": ud["luck_x2"] += 1; effect = "+1 удача x2!"
                elif name == "портал_травы": ud["grass"] += 50; effect = "+50 травы!"
                elif name == "копилка": ud["coins"] += 200; effect = "+200 монет!"
                elif name == "взрыв_опыта": ud["xp"] += 50; oldx = ud["lvl"]; newx = lvl_up(ud); effect = f"+50 XP!{' УРОВЕНЬ ПОВЫШЕН!' if newx > oldx else ''}"
                elif name == "легендарный_семя": ud["last_grass_type"] = "божественная"; effect = "Следующий сбор — божественная!"
                elif name == "бессмертие": ud["immortal_end"] = now + 86400; effect = "Не теряешь ресурсы 24ч!"
                ud["name"] = u.effective_user.username or u.effective_user.first_name
                save_user_db(u.effective_chat.id, u.effective_user.id, ud)
                await reply_del(u, f"🌿 Куплено!\n\n{data['e']} {name}\n🌿 Потрачено: {data['p']}\n🌿 Осталось: {ud['rackumar']}\n\n✨ {effect}")
                return
        num = parse_num(text)
        if not num or num < 1:
            await reply_del(u, "❌ Укажи количество! Пример: 'купить траву 10'"); return
        if "трав" in text:
            cost = num * GRASS_PRICE
            if ud["coins"] < cost:
                await reply_del(u, f"😢 Недостаточно!\n🌿 {num} гр = {cost}\n💰 У тебя: {ud['coins']}"); return
            ud["coins"] -= cost; ud["grass"] += num; msg = f"🛒 Трава: +{num} гр\n💰 Потрачено: {cost}\n💰 Осталось: {ud['coins']}"
        elif "табак" in text:
            cost = num * TOBACCO_PRICE
            if ud["coins"] < cost:
                await reply_del(u, f"😢 Недостаточно!\n📦 {num} гр = {cost}\n💰 У тебя: {ud['coins']}"); return
            ud["coins"] -= cost; ud["tobacco"] += num; msg = f"🛒 Табак: +{num} гр\n💰 Потрачено: {cost}\n💰 Осталось: {ud['coins']}"
        elif "сигарет" in text:
            cost = CIG_PRICE * num
            if ud["coins"] < cost:
                await reply_del(u, f"😢 Недостаточно!\n🚬 {num} = {cost}\n💰 У тебя: {ud['coins']}"); return
            ud["coins"] -= cost; ud["cigarettes"] += num; msg = f"🛒 Сигареты: +{num}\n💰 Потрачено: {cost}\n💰 Осталось: {ud['coins']}"
        elif "сигар" in text:
            cost = CIGAR_PRICE * num
            if ud["coins"] < cost:
                await reply_del(u, f"😢 Недостаточно!\n🚬 {num} = {cost}\n💰 У тебя: {ud['coins']}"); return
            ud["coins"] -= cost; ud["cigars"] += num; msg = f"🛒 Сигары: +{num}\n💰 Потрачено: {cost}\n💰 Осталось: {ud['coins']}"
        else:
            await reply_del(u, "❌ Что купить? Примеры: 'купить траву 10', 'купить мешочек', 'купить благословение'"); return
        ud["name"] = u.effective_user.username or u.effective_user.first_name
        save_user_db(u.effective_chat.id, u.effective_user.id, ud)
    await reply_del(u, msg)

async def give(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    if not u.message.reply_to_message:
        await reply_del(u, "❌ Ответь на сообщение!"); return
    target = u.message.reply_to_message.from_user
    if target.id == u.effective_user.id:
        await reply_del(u, "🤡 Себе нельзя!"); return
    if target.is_bot:
        await reply_del(u, "🤖 Ботам нельзя!"); return
    text = u.message.text.lower().strip(); num = parse_num(text)
    if not num or num < 1:
        await reply_del(u, "❌ Укажи количество! Пример: 'дать траву 5'"); return
    item_map = {"трав": ("grass", "🌿", "травы"), "табак": ("tobacco", "📦", "табака"),
                "монет": ("coins", "💰", "монет"), "раскумар": ("rackumar", "🌿", "раскумара")}
    item_key = None
    for k, v in item_map.items():
        if k in text: item_key, emoji, name = v; break
    if not item_key:
        await reply_del(u, "❌ Что передать? Примеры: 'дать траву 5', 'дать монеты 100', 'дать раскумар 10'"); return
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, u.effective_user.id)
        if ud[item_key] < num:
            await reply_del(u, f"😢 Недостаточно!\n{emoji} У тебя: {ud[item_key]}\n📦 Хочешь: {num}"); return
        ud[item_key] -= num; td = get_user_db(u.effective_chat.id, target.id); td[item_key] += num
        ud["name"] = u.effective_user.username or u.effective_user.first_name
        td["name"] = target.username or target.first_name
        save_user_db(u.effective_chat.id, u.effective_user.id, ud)
        save_user_db(u.effective_chat.id, target.id, td)
    await reply_del(u, f"🎁 {u.effective_user.first_name} → {target.first_name}\n{emoji} {num} {name}")

async def farm(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, u.effective_user.id)
        if ud["fast_farm"] == 0:
            if ud["coins"] < 500:
                await reply_del(u, f"😢 Недостаточно!\n⚡ Ферма: 500\n💰 У тебя: {ud['coins']}"); return
            ud["coins"] -= 500; ud["fast_farm"] = 1; ud["fast_farm_last"] = datetime.now().timestamp()
            save_user_db(u.effective_chat.id, u.effective_user.id, ud)
            await reply_del(u, f"⚡ Ферма куплена!\n💰 Потрачено: 500\n✅ Lv.1!\n🌿 Сбор каждые 30с!"); return
        now = datetime.now().timestamp(); passed = now - ud["fast_farm_last"]; cd = 30
        if passed < cd:
            await reply_del(u, f"⚡ Ферма\n\n⏳ До сбора: {fmt(cd - passed)}\n📊 Lv.{ud['fast_farm']}"); return
        amt = random.randint(1, 2) * ud["fast_farm"]
        if EVENT_ACTIVE: amt *= EVENT_MULT
        dh = ud.get("double_harvest", 0)
        if dh > 0: amt *= 2; ud["double_harvest"] = max(0, dh - 1)
        rack = random.randint(1, 2)
        if EVENT_ACTIVE: rack *= EVENT_MULT
        ud["rackumar"] += rack
        ud["grass"] += amt; ud["fast_farm_last"] = now; ud["xp"] += ud["fast_farm"]
        ud["name"] = u.effective_user.username or u.effective_user.first_name
        old = ud["lvl"]; new = lvl_up(ud)
        save_user_db(u.effective_chat.id, u.effective_user.id, ud)
    ev = "\n\n🎉 ИВЕНТ АКТИВЕН! x3!" if EVENT_ACTIVE else ""
    msg = f"⚡ Ферма — сбор!\n\n🌿 +{amt} гр\n⭐ +{ud['fast_farm']} XP\n🌿 Раскумар: +{rack}\n🎒 Всего: {ud['grass']} гр"
    if new > old: msg += f"\n\n🎉 УРОВЕНЬ ПОВЫШЕН!\n{TITLES.get(new, 'Lv.' + str(new))}!"
    msg += ev + "\n\n💡 Улучшить: 'улучшить ферму' (200 монет)"
    await reply_del(u, msg)

async def upgrade(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, u.effective_user.id)
        if ud["fast_farm"] == 0:
            await reply_del(u, "❌ Нет фермы! Напиши 'ферма'!"); return
        c = 200 * ud["fast_farm"]
        if ud["coins"] < c:
            await reply_del(u, f"😢 Недостаточно!\n⚡ Ферма Lv.{ud['fast_farm']+1} = {c}\n💰 У тебя: {ud['coins']}"); return
        ud["coins"] -= c; ud["fast_farm"] += 1
        ud["name"] = u.effective_user.username or u.effective_user.first_name
        save_user_db(u.effective_chat.id, u.effective_user.id, ud)
    await reply_del(u, f"⚡ Ферма улучшена!\n\n📊 Lv.{ud['fast_farm']}\n💰 Потрачено: {c}")

async def check_clock(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, u.effective_user.id)
    cd = get_cd(ud); now = datetime.now().timestamp(); rem = max(0, cd - (now - ud["last"]))
    msg = f"⏱️ Часы\n\n{'✅ Можешь собирать!' if rem == 0 else f'🕐 До сбора: {fmt(rem)}'}\n⏱️ Кулдаун: {fmt(cd)} (Lv.{ud['lvl']})\n⏱️ В инвентаре: {ud['clocks']}"
    if ud["clocks"] > 0: msg += "\n\n💡 'использовать часы' — сбросить!"
    await reply_del(u, msg)

async def use_clock(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, u.effective_user.id)
        if ud["clocks"] < 1:
            await reply_del(u, "⏱️ Нет Часов! Выпадают при сборе (5%)"); return
        ud["clocks"] -= 1; ud["last"] = 0
        ud["name"] = u.effective_user.username or u.effective_user.first_name
        save_user_db(u.effective_chat.id, u.effective_user.id, ud)
    await reply_del(u, f"⏱️ Часы использованы!\n\n✅ Кулдаун сброшен!\n⏱️ Осталось: {ud['clocks']}")

async def bonus(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    today = datetime.now().strftime("%Y-%m-%d")
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, u.effective_user.id)
        if ud.get("bonus", "") == today:
            await reply_del(u, "🎁 Уже получал сегодня! Приходи завтра 😎"); return
        b = random.randint(5, 15)
        if EVENT_ACTIVE: b *= EVENT_MULT
        ud["grass"] += b; ud["bonus"] = today; ud["xp"] += 5
        rack = random.randint(1, 3)
        if EVENT_ACTIVE: rack *= EVENT_MULT
        ud["rackumar"] += rack
        ud["name"] = u.effective_user.username or u.effective_user.first_name
        old = ud["lvl"]; new = lvl_up(ud)
        save_user_db(u.effective_chat.id, u.effective_user.id, ud)
    ev = "\n\n🎉 ИВЕНТ АКТИВЕН! x3!" if EVENT_ACTIVE else ""
    msg = f"🎁 Бонус!\n\n🌿 +{b} гр\n⭐ +5 XP\n🌿 Раскумар: +{rack}\n🎒 Всего: {ud['grass']} гр"
    if new > old: msg += f"\n\n🎉 УРОВЕНЬ ПОВЫШЕН!\n{TITLES.get(new, 'Lv.' + str(new))}!"
    msg += ev
    await reply_del(u, msg)

async def buy_luck(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    text = u.message.text.lower().strip(); luck_type = None
    for key in ["x10", "x5", "x4", "x3", "x2"]:
        if key in text: luck_type = key; break
    if not luck_type:
        shop = "🍀 Магазин удачи\n\n"
        for key, data in LUCK.items(): shop += f"{data['e']} {key.upper()} — {data['p']} монет (x{data['m']})\n"
        shop += "\n💡 'купить удачу x2'"
        await reply_del(u, shop); return
    data = LUCK[luck_type]
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, u.effective_user.id)
        if ud["coins"] < data["p"]:
            await reply_del(u, f"😢 Недостаточно!\n{data['e']} {luck_type.upper()}: {data['p']}\n💰 У тебя: {ud['coins']}"); return
        ud["coins"] -= data["p"]; ud[f"luck_{luck_type}"] += 1
        ud["name"] = u.effective_user.username or u.effective_user.first_name
        save_user_db(u.effective_chat.id, u.effective_user.id, ud)
    await reply_del(u, f"🍀 Куплено!\n\n{data['e']} Удача {luck_type.upper()}\n💰 Потрачено: {data['p']}\n📦 Теперь: {ud[f'luck_{luck_type}']} шт.")

async def activate_luck(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    text = u.message.text.lower().strip(); luck_type = None
    for key in ["x10", "x5", "x4", "x3", "x2"]:
        if key in text: luck_type = key; break
    if not luck_type:
        msg = "🍀 Твоя удача:\n"
        for key, data in LUCK.items():
            active = " ✅" if ud.get("active_luck") == key else ""
            msg += f"\n{data['e']} {key.upper()}: {ud.get(f'luck_{key}', 0)} шт.{active}"
        msg += "\n\n💡 Напиши x3, x5 и т.д. чтобы активировать"
        await reply_del(u, msg); return
    lk = f"luck_{luck_type}"
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, u.effective_user.id)
        if ud.get(lk, 0) < 1:
            await reply_del(u, f"😢 Нет удачи {luck_type.upper()}!\n💡 Купи: 'купить удачу {luck_type}'"); return
        ud["active_luck"] = luck_type
        ud["name"] = u.effective_user.username or u.effective_user.first_name
        save_user_db(u.effective_chat.id, u.effective_user.id, ud)
    data = LUCK[luck_type]
    await reply_del(u, f"🍀 Удача {luck_type.upper()} активирована!\n\n{data['e']} Множитель x{data['m']}\n🎰 Работает на ставках, депе, воровстве и лотерее!\n\n💡 'выключить удачу' — отключить")

async def deactivate_luck(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, u.effective_user.id)
        if not ud.get("active_luck"):
            await reply_del(u, "🍀 Нет активной удачи!"); return
        old = ud["active_luck"]; ud["active_luck"] = None
        ud["name"] = u.effective_user.username or u.effective_user.first_name
        save_user_db(u.effective_chat.id, u.effective_user.id, ud)
    await reply_del(u, f"🍀 Удача {old.upper()} отключена!")

async def bet(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    text = u.message.text.lower().strip()
    is_tobacco = "табак" in text; is_coins = "монет" in text
    item_key = "tobacco" if is_tobacco else "coins" if is_coins else "grass"
    item_name = "табака" if is_tobacco else "монет" if is_coins else "травы"
    num = parse_num(text)
    if not num or num < 1:
        await reply_del(u, "❌ Укажи ставку! Пример:\n🃏 'ставка 5' — травы\n🃏 'ставка 10 табак' — табака\n🃏 'ставка 100 монет' — монет"); return
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, u.effective_user.id)
        if ud[item_key] < num:
            await reply_del(u, f"😢 Недостаточно {item_name}!\n📦 У тебя: {ud[item_key]}\n🃏 Ставка: {num}"); return
        luck_mult = 1; luck_emoji = ""
        if ud.get("active_luck") in LUCK:
            ld = LUCK[ud["active_luck"]]; luck_mult = ld["m"]; luck_emoji = ld["e"]
            lk = f"luck_{ud['active_luck']}"; ud[lk] -= 1
            if ud[lk] <= 0: ud["active_luck"] = None
        ud[item_key] -= num; ud["name"] = u.effective_user.username or u.effective_user.first_name
        save_user_db(u.effective_chat.id, u.effective_user.id, ud)
    dice = await u.message.reply_dice(emoji="🎲"); asyncio.create_task(auto_del(dice)); await asyncio.sleep(2)
    r = random.randint(1, 100)
    eff = luck_mult * (EVENT_MULT if EVENT_ACTIVE else 1)
    win_t = 30 * eff; draw_t = min(90, 30 + 30 * eff)
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, u.effective_user.id)
        if r <= win_t:
            w = int(num * 2 * eff); ud[item_key] += w
            msg = f"🎲 Ставка {num} {item_name}\n\n{luck_emoji} Удача x{eff}!\n🎰 Выпало: {r}\n🎉 ПОБЕДА!\n💰 +{w}"
        elif r <= draw_t:
            ud[item_key] += num
            msg = f"🎲 Ставка {num} {item_name}\n\n{luck_emoji} Удача x{eff}!\n🎰 Выпало: {r}\n😐 Ничья — возврат"
        else:
            if ud.get("immortal_end", 0) > datetime.now().timestamp():
                ud[item_key] += num
                msg = f"🎲 Ставка {num} {item_name}\n\n{luck_emoji} Удача x{eff}!\n🎰 Выпало: {r}\n😭 ПРОИГРЫШ!\n\n👼 Бессмертие спасло ресурсы!"
            else:
                msg = f"🎲 Ставка {num} {item_name}\n\n{luck_emoji} Удача x{eff}!\n🎰 Выпало: {r}\n😭 ПРОИГРЫШ!"
        msg += f"\n📦 Баланс: {ud[item_key]}"
        save_user_db(u.effective_chat.id, u.effective_user.id, ud)
    await reply_del(u, msg)

async def deposit_game(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    text = u.message.text.lower().strip(); num = parse_num(text)
    if not num or num < 1:
        await reply_del(u, "❌ Укажи деп! Пример: 'деп 100'"); return
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, u.effective_user.id)
        if ud["coins"] < num:
            await reply_del(u, f"😢 Недостаточно!\n💰 У тебя: {ud['coins']}\n💰 Хочешь: {num}"); return
        luck_mult = 1; luck_emoji = ""
        if ud.get("active_luck") in LUCK:
            ld = LUCK[ud["active_luck"]]; luck_mult = ld["m"]; luck_emoji = ld["e"]
            lk = f"luck_{ud['active_luck']}"; ud[lk] -= 1
            if ud[lk] <= 0: ud["active_luck"] = None
        ud["coins"] -= num; ud["name"] = u.effective_user.username or u.effective_user.first_name
        save_user_db(u.effective_chat.id, u.effective_user.id, ud)
    spin = await u.message.reply_text("🎰 Крутим...")
    for txt in ["🎰 Крутим..⭐..", "🎰 Крутим..💎..", "🎰 Крутим..🍀.."]:
        await asyncio.sleep(0.8); await spin.edit_text(txt)
    await asyncio.sleep(0.8)
    eff = luck_mult * (EVENT_MULT if EVENT_ACTIVE else 1); r = random.randint(1, 100)
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, u.effective_user.id)
        if r <= 10 * eff:
            w = int(num * 5 * eff); ud["coins"] += w
            result = f"🎰🎰🎰 ДЖЕКПОТ!!! 🎰🎰🎰\n\n{luck_emoji} Удача x{eff}!\n🎰 Выпало: {r}\n💰 ДЕП x5!\n💰 +{w}"
        elif r <= 25 * eff:
            w = int(num * 2 * eff); ud["coins"] += w
            result = f"🎉 ПОБЕДА!\n\n{luck_emoji} Удача x{eff}!\n🎰 Выпало: {r}\n💰 ДЕП x2!\n💰 +{w}"
        elif r <= 50:
            ud["coins"] += num
            result = f"😐 Ничья\n\n{luck_emoji} Удача x{eff}!\n🎰 Выпало: {r}\n💰 Деп возвращён"
        else:
            if ud.get("immortal_end", 0) > datetime.now().timestamp():
                ud["coins"] += num
                result = f"😭 ПРОИГРЫШ!\n\n{luck_emoji} Удача x{eff}!\n🎰 Выпало: {r}\n👼 Бессмертие спасло деп!"
            else:
                result = f"😭 ПРОИГРЫШ!\n\n{luck_emoji} Удача x{eff}!\n🎰 Выпало: {r}\n💰 Деп сожрало казино"
        result += f"\n💰 Баланс: {ud['coins']}"
        save_user_db(u.effective_chat.id, u.effective_user.id, ud)
    await spin.edit_text(result); asyncio.create_task(auto_del(spin))
    asyncio.create_task(auto_del(u.message, delay=AUTO_DELETE_DELAY))

async def lottery(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, u.effective_user.id)
        if ud["coins"] < LOTTERY_PRICE:
            await reply_del(u, f"😢 Недостаточно!\n🎰 Билет: {LOTTERY_PRICE}\n💰 У тебя: {ud['coins']}"); return
        ud["coins"] -= LOTTERY_PRICE; ud["name"] = u.effective_user.username or u.effective_user.first_name
        save_user_db(u.effective_chat.id, u.effective_user.id, ud)
    spin = await u.message.reply_text("🎰 Крутим...")
    for txt in ["🎰 Крутим..⭐..", "🎰 Крутим..💎..", "🎰 Крутим..🍀..", "🎰 Крутим..🎰.."]:
        await asyncio.sleep(0.8); await spin.edit_text(txt)
    await asyncio.sleep(0.8)
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, u.effective_user.id)
        luck_mult = 1; luck_emoji = ""
        if ud.get("active_luck") in LUCK:
            ld = LUCK[ud["active_luck"]]; luck_mult = ld["m"]; luck_emoji = ld["e"]
            lk = f"luck_{ud['active_luck']}"; ud[lk] -= 1
            if ud[lk] <= 0: ud["active_luck"] = None
        eff = luck_mult * (EVENT_MULT if EVENT_ACTIVE else 1)
        roll = random.randint(1, 100); cum = 0
        prize_name = "Утешительный"; prize_data = LOTTERY["Утешительный"]
        for name, data in LOTTERY.items():
            cum += data["c"]
            if roll <= cum: prize_name = name; prize_data = data; break
        win = LOTTERY_PRICE * prize_data["m"] * eff
        ud["coins"] += int(win); ud["xp"] += 2
        old = ud["lvl"]; new = lvl_up(ud)
        save_user_db(u.effective_chat.id, u.effective_user.id, ud)
    ev = "\n🎉 ИВЕНТ АКТИВЕН! x3!" if EVENT_ACTIVE else ""
    msg = f"🎰🎰🎰 ЛОТЕРЕЯ 🎰🎰🎰\n\n{prize_data['e']} {prize_name}!\n\n💰 Билет: {LOTTERY_PRICE}\n💰 Выигрыш: {int(win)} (x{prize_data['m']} x{eff})\n💰 Баланс: {ud['coins']}\n⭐ +2 XP"
    if new > old: msg += f"\n\n🎉 УРОВЕНЬ ПОВЫШЕН!\n{TITLES.get(new, 'Lv.' + str(new))}!"
    msg += ev
    await spin.edit_text(msg); asyncio.create_task(auto_del(spin))
    asyncio.create_task(auto_del(u.message, delay=AUTO_DELETE_DELAY))

async def admin_give_all(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    if not is_owner(u.effective_user.id):
        await reply_del(u, "❌ Только владелец!"); return
    target = u.effective_user
    if u.message.reply_to_message: target = u.message.reply_to_message.from_user
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, target.id)
        ud["grass"] = 100000000000000; ud["tobacco"] = 100000000000000; ud["coins"] = 100000000000000; ud["rackumar"] = 100000000000000
        ud["cigarettes"] = 99; ud["cigars"] = 99; ud["clocks"] = 99; ud["lvl"] = 10; ud["smoked"] = 9999
        ud["fast_farm"] = 10; ud["rob_lvl"] = 10; ud["bag"] = 1
        for k in ["x2", "x3", "x4", "x5", "x10"]: ud[f"luck_{k}"] = 99
        ud["name"] = target.username or target.first_name
        save_user_db(u.effective_chat.id, target.id, ud)
    await reply_del(u, f"👑 ВСЁ ВЫДАНО!\n\n👤 {target.first_name}\n🌿 Трава: 100T\n📦 Табак: 100T\n💰 Монеты: 100T\n🌿 Раскумар: 100T\n🚬 Сигареты: 99\n🚬 Сигары: 99\n⏱️ Часы: 99\n⚡ Ферма: 10\n🥷 Вор: 10\n🎒 Мешочек: ✅\n🍀 Удача x2-x10: 99\n📊 Lv.10")

async def event_on(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    if not is_owner(u.effective_user.id):
        await reply_del(u, "❌ Только владелец!"); return
    global EVENT_ACTIVE; EVENT_ACTIVE = True
    await reply_del(u, f"🎉 ИВЕНТ ВКЛЮЧЕН!\n\n🍀 Удача x{EVENT_MULT} на ВСЁ!\n🥷 На воровство: УДАЧА x50!\n⚡ Вперёд, травники!")

async def event_off(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    if not is_owner(u.effective_user.id):
        await reply_del(u, "❌ Только владелец!"); return
    global EVENT_ACTIVE; EVENT_ACTIVE = False
    await reply_del(u, "🔚 Ивент завершён!\n\nСледующий ивент скоро...")

async def trade_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, u.effective_user.id)
        if ud.get("clocks", 0) < 1:
            await reply_del(u, "⏱️ Нет Часов для обмена!"); return
    if not u.message.reply_to_message:
        await reply_del(u, "❌ Ответь на сообщение!"); return
    target = u.message.reply_to_message.from_user
    if target.id == u.effective_user.id:
        await reply_del(u, "🤡 Себе нельзя!"); return
    if target.is_bot:
        await reply_del(u, "🤖 Ботам нельзя!"); return
    cid = str(u.effective_chat.id); TRADE_STATE.setdefault(cid, {})
    TRADE_STATE[cid][str(u.effective_user.id)] = {"to_id": target.id, "clocks": 1}
    await reply_del(u, f"🤝 Трейд\n\nПредлагаешь 1 ⏱️ {target.first_name}!\n\n{target.first_name}, напиши 'принять трейд'!")

async def trade_accept(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    cid = str(u.effective_chat.id); uid = str(u.effective_user.id)
    if cid not in TRADE_STATE:
        await reply_del(u, "❌ Нет активных трейдов!"); return
    found = None
    for from_id, info in TRADE_STATE[cid].items():
        if str(info["to_id"]) == uid: found = (from_id, info); break
    if not found:
        await reply_del(u, "❌ Никто не предлагал трейд!"); return
    from_id, info = found
    async with _db_lock:
        fud = get_user_db(u.effective_chat.id, int(from_id)); tud = get_user_db(u.effective_chat.id, u.effective_user.id)
        if fud.get("clocks", 0) < info["clocks"]:
            await reply_del(u, "❌ У отправителя нет часов!"); del TRADE_STATE[cid][from_id]; return
        fud["clocks"] -= info["clocks"]; tud["clocks"] += info["clocks"]
        fud["name"] = fud.get("name", "Игрок"); tud["name"] = u.effective_user.username or u.effective_user.first_name
        del TRADE_STATE[cid][from_id]
        save_user_db(u.effective_chat.id, int(from_id), fud)
        save_user_db(u.effective_chat.id, u.effective_user.id, tud)
    await reply_del(u, f"🤝 Трейд завершён!\n\n{fud['name']} → {tud['name']}\n⏱️ Передано: 1 Часы")

async def trade_cancel(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    cid = str(u.effective_chat.id); uid = str(u.effective_user.id)
    if cid in TRADE_STATE and uid in TRADE_STATE[cid]:
        del TRADE_STATE[cid][uid]; await reply_del(u, "❌ Трейд отменён!")
    else:
        await reply_del(u, "❌ Нет активных трейдов!")

async def is_admin(chat, uid):
    try:
        member = await chat.get_member(uid)
        return member.status in ["creator", "administrator"]
    except: return False

async def ban(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    chat, user = u.effective_chat, u.effective_user
    if not await is_admin(chat, user.id): return await reply_del(u, "❌ Только админы!")
    if not u.message.reply_to_message: return await reply_del(u, "❌ Ответь на сообщение!")
    t = u.message.reply_to_message.from_user
    if t.id == user.id: return await reply_del(u, "🤡 Себя нельзя!")
    if t.is_bot: return await reply_del(u, "🤖 Ботов нельзя!")
    if await is_admin(chat, t.id): return await reply_del(u, "👮 Админа нельзя!")
    try:
        try:
            member = await chat.get_member(t.id)
            if member.status == "kicked": return await reply_del(u, f"⚠️ {t.first_name} уже забанен!")
        except: pass
        await chat.ban_member(t.id); await reply_del(u, f"🚫 {t.first_name} забанен! 🌿")
    except Exception as e: await reply_del(u, f"❌ Ошибка: {e}")

async def unban(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    chat, user = u.effective_chat, u.effective_user
    if not await is_admin(chat, user.id): return await reply_del(u, "❌ Только админы!")
    if not u.message.reply_to_message: return await reply_del(u, "❌ Ответь на сообщение!")
    t = u.message.reply_to_message.from_user
    if t.id == user.id: return await reply_del(u, "🤡 Себя нельзя!")
    if t.is_bot: return await reply_del(u, "🤖 Ботов нельзя!")
    try:
        try:
            member = await chat.get_member(t.id)
            if member.status != "kicked": return await reply_del(u, f"⚠️ {t.first_name} не забанен!")
        except: pass
        await chat.unban_member(t.id); await reply_del(u, f"✅ {t.first_name} разбанен! 🌿")
    except Exception as e: await reply_del(u, f"❌ Ошибка: {e}")

async def mute(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    chat, user = u.effective_chat, u.effective_user
    if not await is_admin(chat, user.id): return await reply_del(u, "❌ Только админы!")
    if not u.message.reply_to_message: return await reply_del(u, "❌ Ответь на сообщение!")
    t = u.message.reply_to_message.from_user
    if t.id == user.id: return await reply_del(u, "🤡 Себя нельзя!")
    if t.is_bot: return await reply_del(u, "🤖 Ботов нельзя!")
    if await is_admin(chat, t.id): return await reply_del(u, "👮 Админа нельзя!")
    try:
        member = await chat.get_member(t.id)
        if not member.permissions or not member.permissions.can_send_messages:
            return await reply_del(u, f"⚠️ {t.first_name} уже замучен!")
    except: pass
    dur = 3600; text = u.message.text.lower().strip()
    rest = text.replace("мут", "").replace("замутить", "").replace("заткнуть", "").strip()
    if rest:
        parsed = None
        m = re.match(r'(\d+)([чмсд]?)', rest.replace(" ", ""))
        if m:
            n, unit = int(m.group(1)), m.group(2)
            if unit == 'ч': parsed = n * 3600
            elif unit == 'д': parsed = n * 86400
            elif unit == 'с': parsed = n
            else: parsed = n * 60
        if parsed: dur = parsed
    try:
        await chat.restrict_member(t.id, until_date=datetime.now() + timedelta(seconds=dur),
            permissions={"can_send_messages": False, "can_send_media_messages": False,
                        "can_send_other_messages": False, "can_add_web_page_previews": False})
        await reply_del(u, f"🔇 {t.first_name} замучен на {fmt(dur)}! 🌿")
    except Exception as e: await reply_del(u, f"❌ Ошибка: {e}")

async def unmute(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    chat, user = u.effective_chat, u.effective_user
    if not await is_admin(chat, user.id): return await reply_del(u, "❌ Только админы!")
    if not u.message.reply_to_message: return await reply_del(u, "❌ Ответь на сообщение!")
    t = u.message.reply_to_message.from_user
    if t.id == user.id: return await reply_del(u, "🤡 Себя нельзя!")
    if t.is_bot: return await reply_del(u, "🤖 Ботов нельзя!")
    try:
        try:
            member = await chat.get_member(t.id)
            if member.permissions and member.permissions.can_send_messages:
                return await reply_del(u, f"⚠️ {t.first_name} не замучен!")
        except: pass
        await chat.restrict_member(t.id, permissions={"can_send_messages": True, "can_send_media_messages": True,
                                                        "can_send_other_messages": True, "can_add_web_page_previews": True})
        await reply_del(u, f"🔊 {t.first_name} размучен! 🗣️")
    except Exception as e: await reply_del(u, f"❌ Ошибка: {e}")


async def rob(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    text = u.message.text.lower().strip()
    target = None
    if u.message.reply_to_message:
        target = u.message.reply_to_message.from_user
    else:
        parts = text.split()
        if len(parts) >= 2:
            mention_text = parts[1].replace("@", "")
            users = get_all_users_db(u.effective_chat.id)
            for user in users:
                if user.get("name", "").lower() == mention_text.lower():
                    target = type('obj', (object,), {'id': int(user["user_id"]), 'first_name': user.get("name", "Игрок"), 'username': user.get("name", "Игрок"), 'is_bot': False})()
                    break
    if not target:
        await reply_del(u, "❌ Укажи жертву! Ответь на сообщение или напиши: 'роб @username'"); return
    if target.id == u.effective_user.id:
        await reply_del(u, "🤡 Себя нельзя ограбить!"); return
    if target.is_bot:
        await reply_del(u, "🤖 Ботов нельзя!"); return
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, u.effective_user.id)
        td = get_user_db(u.effective_chat.id, target.id)
        now = datetime.now().timestamp()
        if ud.get("bag", 0) == 0:
            await reply_del(u, "🎒 Нужен мешочек! Купи: 'купить мешочек'"); return
        passed = now - ud.get("rob_last", 0)
        cd = rob_cd(ud)
        if passed < cd:
            await reply_del(u, f"⏳ Подожди {fmt(cd - passed)}!\n🥷 Кулдаун: {fmt(cd)}"); return
        if td.get("shield_end", 0) > now:
            await reply_del(u, f"🛡️ {target.first_name} под щитом! Нельзя ограбить!"); return
        if td.get("grass", 0) < 1 and td.get("tobacco", 0) < 1 and td.get("coins", 0) < 1:
            await reply_del(u, f"😢 У {target.first_name} нет ничего ценного!"); return
        max_steal = rob_max(ud)
        if ud.get("golden_hand_end", 0) > now: max_steal = int(max_steal * 1.5)
        luck_mult = 1; luck_emoji = ""
        if ud.get("active_luck") in LUCK:
            ld = LUCK[ud["active_luck"]]; luck_mult = ld["m"]; luck_emoji = ld["e"]
            lk = f"luck_{ud['active_luck']}"; ud[lk] -= 1
            if ud[lk] <= 0: ud["active_luck"] = None
        eff = luck_mult * (EVENT_MULT if EVENT_ACTIVE else 1)
        items = []
        if td.get("grass", 0) > 0: items.append(("grass", "🌿", "травы"))
        if td.get("tobacco", 0) > 0: items.append(("tobacco", "📦", "табака"))
        if td.get("coins", 0) > 0: items.append(("coins", "💰", "монет"))
        item_key, emoji, item_name = random.choice(items)
        steal_amt = min(random.randint(1, max_steal), td.get(item_key, 0))
        steal_amt = max(1, int(steal_amt * eff))
        steal_amt = min(steal_amt, td.get(item_key, 0))
        success_chance = 50 + (ud["rob_lvl"] - 1) * 5
        if ud.get("golden_hand_end", 0) > now: success_chance += 25
        success_chance = min(95, int(success_chance * eff))
        ud["rob_last"] = now
        ud["name"] = u.effective_user.username or u.effective_user.first_name
        if random.randint(1, 100) <= success_chance:
            td[item_key] -= steal_amt; ud[item_key] += steal_amt
            ud["xp"] += 5; old = ud["lvl"]; new = lvl_up(ud)
            save_user_db(u.effective_chat.id, u.effective_user.id, ud)
            save_user_db(u.effective_chat.id, target.id, td)
            msg = f"🥷 ОГРАБЛЕНИЕ!\n\n{luck_emoji} Удача x{eff}!\n🎯 Цель: {target.first_name}\n{emoji} Украдено: {steal_amt} {item_name}\n⭐ +5 XP"
            if new > old: msg += f"\n\n🎉 УРОВЕНЬ ПОВЫШЕН!\n{TITLES.get(new, 'Lv.' + str(new))}!"
        else:
            penalty = random.randint(1, 3)
            if ud.get("immortal_end", 0) > now:
                save_user_db(u.effective_chat.id, u.effective_user.id, ud)
                msg = f"🥷 ОГРАБЛЕНИЕ ПРОВАЛИЛОСЬ!\n\n{luck_emoji} Удача x{eff}!\n🎯 Цель: {target.first_name}\n😭 Тебя поймали!\n👼 Бессмертие спасло ресурсы!"
            else:
                if ud.get("coins", 0) >= penalty: ud["coins"] -= penalty
                elif ud.get("grass", 0) >= penalty: ud["grass"] -= penalty
                elif ud.get("tobacco", 0) >= penalty: ud["tobacco"] -= penalty
                save_user_db(u.effective_chat.id, u.effective_user.id, ud)
                msg = f"🥷 ОГРАБЛЕНИЕ ПРОВАЛИЛОСЬ!\n\n{luck_emoji} Удача x{eff}!\n🎯 Цель: {target.first_name}\n😭 Тебя поймали!\n📦 Штраф: {penalty}"
        await reply_del(u, msg)

async def upgrade_rob(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, u.effective_user.id)
        if ud["rob_lvl"] >= 10:
            await reply_del(u, "👑 Максимальный уровень вора!"); return
        cost = 500 * ud["rob_lvl"]
        if ud["coins"] < cost:
            await reply_del(u, f"😢 Недостаточно!\n🥷 Вор Lv.{ud['rob_lvl']+1} = {cost}\n💰 У тебя: {ud['coins']}"); return
        ud["coins"] -= cost; ud["rob_lvl"] += 1
        ud["name"] = u.effective_user.username or u.effective_user.first_name
        save_user_db(u.effective_chat.id, u.effective_user.id, ud)
    await reply_del(u, f"🥷 Вор улучшен!\n\n📊 Lv.{ud['rob_lvl']}\n💰 Потрачено: {cost}\n⚡ Макс украсть: {rob_max(ud)}\n⏱️ Кулдаун: {fmt(rob_cd(ud))}")

async def admin_give(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    if not is_owner(u.effective_user.id):
        await reply_del(u, "❌ Только владелец!"); return
    if not u.message.reply_to_message:
        await reply_del(u, "❌ Ответь на сообщение!"); return
    target = u.message.reply_to_message.from_user
    text = u.message.text.lower().strip(); num = parse_num(text)
    if not num or num < 1:
        await reply_del(u, "❌ Укажи количество! Пример: 'выдать траву 100'"); return
    item_map = {"трав": ("grass", "🌿", "травы"), "табак": ("tobacco", "📦", "табака"),
                "монет": ("coins", "💰", "монет"), "раскумар": ("rackumar", "🌿", "раскумара"),
                "сигарет": ("cigarettes", "🚬", "сигарет"), "сигар": ("cigars", "🚬", "сигар")}
    item_key = None
    for k, v in item_map.items():
        if k in text: item_key, emoji, name = v; break
    if not item_key:
        await reply_del(u, "❌ Что выдать? Примеры: 'выдать траву 100', 'выдать монеты 1000'"); return
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, target.id)
        ud[item_key] += num; ud["name"] = target.username or target.first_name
        save_user_db(u.effective_chat.id, target.id, ud)
    await reply_del(u, f"👑 Выдача!\n\n👤 {target.first_name}\n{emoji} +{num} {name}\n📦 Теперь: {ud[item_key]}")

async def admin_reset(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not await check_group(u): return
    target = u.effective_user
    if u.message.reply_to_message: target = u.message.reply_to_message.from_user
    if target.id != u.effective_user.id and not is_owner(u.effective_user.id):
        await reply_del(u, "❌ Только владелец может сбрасывать других!"); return
    async with _db_lock:
        ud = get_user_db(u.effective_chat.id, target.id)
        for k in ["grass", "smoked", "xp", "lvl", "last", "clocks", "bonus", "tobacco", "coins",
                  "cigarettes", "cigars", "fast_farm", "fast_farm_last", "last_grass_type", "is_bot",
                  "luck_x2", "luck_x3", "luck_x4", "luck_x5", "luck_x10", "active_luck", "rackumar",
                  "bag", "rob_lvl", "rob_last", "blessing_end", "double_harvest", "shield_end",
                  "magnet_end", "golden_hand_end", "immortal_end"]:
            ud[k] = 0
        ud["lvl"] = 1; ud["name"] = target.username or target.first_name
        save_user_db(u.effective_chat.id, target.id, ud)
    await reply_del(u, f"🗑️ Сброс!\n\n👤 {target.first_name} обнулён!")

async def text(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not u.message or not u.message.text: return
    logger.info(f"MSG from {u.effective_user.id} in {u.effective_chat.id}: {u.message.text[:50]}")
    if u.effective_chat.type == "private":
        await u.message.reply_text("🌿 Я бот для чатов! Добавляй в чат и становись миллионером"); return
    t = u.message.text.lower().strip()

    if t in ["x2", "x3", "x4", "x5", "x10"]:
        await activate_luck(u, c); return

    cmds = {
        "собрать": collect, "сбор": collect, "собирать": collect, "собери": collect,
        "найти": collect, "нашёл": collect, "нашел": collect, "травка": collect,
        "траву": collect, "собираю": collect, "копать": collect, "копаю": collect,
        "сбор травы": collect, "собираю траву": collect, "собираю травку": collect,
        "курить": smoke, "курю": smoke, "дым": smoke, "затянуться": smoke,
        "закурить": smoke, "покурить": smoke, "бахнуть": smoke, "бахаю": smoke,
        "закуриваю": smoke, "курнул": smoke, "курну": smoke, "курить сигару": smoke,
        "скурить всё": smoke, "скурить все": smoke, "выкурить всё": smoke, "выкурить все": smoke,
        "крафт": craft, "табак": craft, "сделать табак": craft, "скрафтить": craft,
        "крафтить": craft, "заварить": craft, "завариваю": craft, "делаю табак": craft,
        "профиль": profile, "я": profile, "стата": profile, "статистика": profile,
        "инфо": profile, "информация": profile, "о себе": profile, "кто я": profile,
        "топ": tops, "рейтинг": tops, "лидеры": tops, "лидерборд": tops,
        "топчик": tops, "топы": tops,
        "топ монет": tops, "топ coins": tops, "лидеры монет": tops,
        "топ травы": tops, "топ трав": tops, "лидеры травы": tops,
        "топ раскумара": tops, "топ раскумар": tops,
        "инвентарь": inv, "инв": inv, "рюкзак": inv, "сумка": inv,
        "вещи": inv, "предметы": inv, "ресурсы": inv, "шмот": inv,
        "бонус": bonus, "ежедневный": bonus, "награда": bonus, "ежедневка": bonus,
        "дневной": bonus, "приз": bonus, "ежедневный бонус": bonus,
        "продать": sell, "продажа": sell, "продать траву": sell, "сбыть": sell,
        "продам": sell, "продаю": sell, "торговать": sell, "торгую": sell,
        "продать табак": sell, "продажа табака": sell, "сбыть табак": sell,
        "продам табак": sell, "продаю табак": sell,
        "выдать": admin_give, "give": admin_give, "выдача": admin_give,
        "сбросить": admin_reset, "reset": admin_reset, "обнулить": admin_reset, "удалить": admin_reset,
        "сбросить себя": admin_reset, "обнулить себя": admin_reset, "удалить себя": admin_reset,
        "выдать все": admin_give_all, "giveall": admin_give_all, "макс": admin_give_all,
        "часы": check_clock, "кулдаун": check_clock, "время": check_clock,
        "кд": check_clock, "таймер": check_clock, "когда собирать": check_clock,
        "использовать часы": use_clock, "юзать часы": use_clock, "применить часы": use_clock,
        "юзнуть часы": use_clock, "активировать часы": use_clock, "часы использовать": use_clock,
        "трейд": trade_start, "обмен": trade_start, "отправить часы": trade_start,
        "передать часы": trade_start, "отдать часы": trade_start, "обменять": trade_start,
        "принять трейд": trade_accept, "принять": trade_accept, "принимаю": trade_accept,
        "отменить трейд": trade_cancel, "отмена трейд": trade_cancel, "отмена": trade_cancel,
        "ферма": farm, "собрать ферма": farm, "ферму": farm, "грядка": farm,
        "плантация": farm, "поле": farm, "урожай": farm, "собрать урожай": farm,
        "быстрая": farm, "фаст ферма": farm, "fast farm": farm,
        "скоростная ферма": farm, "мини ферма": farm,
        "улучшить ферму": upgrade, "апгрейд фермы": upgrade,
        "прокачать ферму": upgrade, "улучшить": upgrade,
        "бан": ban, "забанить": ban, "блок": ban, "банhammer": ban, "заблокировать": ban,
        "анбан": unban, "разбан": unban, "разбанить": unban, "разблокировать": unban,
        "мут": mute, "замутить": mute, "заткнуть": mute, "замолчать": mute, "молчать": mute,
        "анмут": unmute, "размут": unmute, "размутить": unmute, "разговаривать": unmute,
        "помощь": start, "хелп": start, "команды": start, "старт": start, "начать": start,
        "help": start, "help me": start, "меню": start, "список команд": start, "что умеешь": start,
        "?": start, "!": start, "как играть": start, "гайд": start,
        "купить удачу": buy_luck, "удача": buy_luck, "магазин удачи": buy_luck,
        "включить удачу": activate_luck, "активировать удачу": activate_luck, "врубить удачу": activate_luck,
        "выключить удачу": deactivate_luck, "отключить удачу": deactivate_luck,
        "ивент": event_on, "врубить ивент": event_on, "включить ивент": event_on,
        "выключить ивент": event_off, "отключить ивент": event_off, "ивент офф": event_off,
        "деп": deposit_game, "депнуть": deposit_game, "казино": deposit_game, "крутить": deposit_game,
        "лотерея": lottery, "лотка": lottery, "лоток": lottery,
        "роб": rob, "ограбить": rob, "воровать": rob, "вор": rob, "украсть": rob,
        "улучшить вора": upgrade_rob, "прокачать вора": upgrade_rob, "апгрейд вора": upgrade_rob,
        "купить мешочек": buy, "купить мешок": buy, "купить bag": buy,
        "магазин раскумара": buy, "раскумар магазин": buy,
    }
    if t in cmds:
        await cmds[t](u, c); return

    if t.startswith("ставка монет"): await bet(u, c); return
    if t.startswith("ставка"): await bet(u, c); return
    if t.startswith("купить траву"): await buy(u, c); return
    if t.startswith("купить табак"): await buy(u, c); return
    if t.startswith("купить сигарет"): await buy(u, c); return
    if t.startswith("купить сигар"): await buy(u, c); return
    if t.startswith("дать "): await give(u, c); return
    if t.startswith("закурить сигарет"): await smoke(u, c); return
    if t.startswith("закурить сигар"): await smoke(u, c); return
    if t.startswith("курить сигарет"): await smoke(u, c); return
    if t.startswith("курить сигар"): await smoke(u, c); return
    if t.startswith("курить "): await smoke(u, c); return
    if t.startswith("деп "): await deposit_game(u, c); return
    if t.startswith("купить удачу"): await buy_luck(u, c); return
    if t.startswith("включить удачу"): await activate_luck(u, c); return
    if t.startswith("врубить удачу"): await activate_luck(u, c); return
    if t.startswith("роб "): await rob(u, c); return
    if t.startswith("ограбить "): await rob(u, c); return
    if t.startswith("улучшить вора"): await upgrade_rob(u, c); return
    if t.startswith("прокачать вора"): await upgrade_rob(u, c); return
    if t.startswith("продать траву"): await sell(u, c); return
    if t.startswith("продать табак"): await sell(u, c); return
    if t.startswith("продам траву"): await sell(u, c); return
    if t.startswith("продам табак"): await sell(u, c); return
    if t.startswith("продаю траву"): await sell(u, c); return
    if t.startswith("продаю табак"): await sell(u, c); return
    if t.startswith("сбыть траву"): await sell(u, c); return
    if t.startswith("сбыть табак"): await sell(u, c); return
    if t.startswith("купить благословение"): await buy(u, c); return
    if t.startswith("купить двойной"): await buy(u, c); return
    if t.startswith("купить щит"): await buy(u, c); return
    if t.startswith("купить магнит"): await buy(u, c); return
    if t.startswith("купить золотую"): await buy(u, c); return
    if t.startswith("купить кристалл"): await buy(u, c); return
    if t.startswith("купить портал"): await buy(u, c); return
    if t.startswith("купить копилку"): await buy(u, c); return
    if t.startswith("купить взрыв"): await buy(u, c); return
    if t.startswith("купить легендарное"): await buy(u, c); return
    if t.startswith("купить бессмертие"): await buy(u, c); return

    if t in ["привет", "здарова", "ку", "хай", "йо", "здравствуй", "прив", "хей",
             "хелоу", "хеллоу", "здрасьте", "добрый день", "добрый вечер", "доброе утро",
             "здаров", "здорово", "здравия", "салют", "хаюшки", "приветик", "куку"]:
        await reply_del(u, f"🌿 Здарова, {u.effective_user.first_name}! Напиши помощь для команд!")
    elif t in ["пока", "бай", "до связи", "прощай", "до свидания", "до встречи",
               "покеда", "пока-пока", "бб", "bb", "bye", "goodbye", "спокойной ночи",
               "доброй ночи", "споки", "спок"]:
        await reply_del(u, f"👋 Пока, {u.effective_user.first_name}! Не забудь собрать травку 🌿")

async def post_init(app: Application):
    await app.bot.set_my_commands(BOT_COMMANDS)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)

def main():
    while True:
        try:
            app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
            app.add_handler(CommandHandler("start", start))
            app.add_handler(CommandHandler("help", start))
            app.add_handler(CommandHandler("collect", collect))
            app.add_handler(CommandHandler("craft", craft))
            app.add_handler(CommandHandler("smoke", smoke))
            app.add_handler(CommandHandler("profile", profile))
            app.add_handler(CommandHandler("top", tops))
            app.add_handler(CommandHandler("inventory", inv))
            app.add_handler(CommandHandler("bonus", bonus))
            app.add_handler(CommandHandler("sell", sell))
            app.add_handler(CommandHandler("farm", farm))
            app.add_handler(CommandHandler("rob", rob))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text))
            app.add_error_handler(error_handler)
            print("🌿 Травка Бот v10 (SQLite) запущен!")
            app.run_polling(
                poll_interval=1.0,
                timeout=30,
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES
            )
        except Exception as e:
            logger.error(f"Bot crashed: {e}", exc_info=True)
            print(f"💥 Бот упал: {e}. Перезапуск через 10 сек...")
            import time
            time.sleep(10)

if __name__ == "__main__": main()
