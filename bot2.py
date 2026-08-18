"""
Telegram Bot with AI, Games, and Image Processing
Uses PostgreSQL for data persistence (configure in config.json)
"""

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN CONFIGURATION - Edit these values
# ═══════════════════════════════════════════════════════════════════════════════

BOT_TOKEN = ""  # Set via config.json or BOT_TOKEN env var
PROXY_URL = "http://31.59.20.176:6754"  # Set to None to disable proxy
AI_DELAY = 2  # Seconds to wait before AI response
TRASH_COOLDOWN = 40 * 60  # 40 minutes in seconds
TRIGGER_WORDS = {"зырис", "ziris", "чмо"}
DEFAULT_SPEAKER = "aidar"
SILERO_SPEAKERS = ["aidar", "baya", "kseniya", "xenia", "random"]
ROULETTE_DEATH_CHANCE = 0.20  # 20% chance to die
REACTION_CHANCE = 0.30  # 30% chance to react
QUOTE_CHANCE = 0.05  # 5% chance to send random quote
QUOTE_COOLDOWN = 3600  # max 1 quote per chat per hour
MESSAGE_MAX_AGE = 45  # ignore messages older than this (seconds)

# Economy config
BEGGAR_CHANCE = 1 / 5000  # 1 in 20000 chance to get 1 ruble
CIGARETTE_PRICE = 5  # rubles per cigarette
CIGAR_TO_REP = 100  # 1 cigarette = 100 reputation
TRASH_TO_REP_RATE = 1  # 1 butt = 1 reputation

# Pathogen / virus config
VIRUS_BASE_INFECT_CHANCE = 0.40       # 40% base infection chance
VIRUS_INFECTIVITY_BONUS = 0.03         # +3% per infectivity level
VIRUS_IMMUNITY_REDUCTION = 0.02        # -2% per immunity level (target's pathogen)
VIRUS_MIN_INFECT_CHANCE = 0.01         # minimum 1% chance to infect
VIRUS_MAX_INFECT_CHANCE = 0.95         # maximum 95% chance
VIRUS_MORTALITY_SEC = 20               # +20 sec per mortality level (infected can't spread)
VIRUS_BASE_INFECTED_DURATION = 60      # base seconds the infected cannot use /virus
VIRUS_COOLDOWN = 20 * 60               # 20 minutes between infections
VIRUS_DAILY_LIMIT = 12                 # max infections per day
VIRUS_BUTT_COST = 1                    # butts (окурки) per +1 level
VIRUS_CIGARETTE_BOOST = 10             # +10 levels per cigarette (сигарета)

# Crypto exchange config (Крипто-Окурки)
CRYPTO_BASE_BUTTS_PER_COK = 62.0  # base: butts needed for 1 COK at neutral market
CRYPTO_PRICE_MIN_RATIO = 0.25
CRYPTO_PRICE_MAX_RATIO = 4.0
CRYPTO_VOLUME_SMOOTH = 10.0       # legacy bootstrap for initial spot
CRYPTO_LIQUIDITY = 500.0          # market depth (butts-equivalent)
CRYPTO_PRICE_IMPACT = 0.40       # how strongly each trade moves spot price
CRYPTO_VOLUME_DECAY = 0.985       # older volume fades — recent trades matter more
CRYPTO_INITIAL_SELL_COUNT = 50    # initial sell-side weight so % starts near 0

# Central bank config
BANK_TARGET_RESERVE = 10000.0     # healthy reserve (butts-equivalent)
BANK_MIN_COMMISSION = 1.0         # min transfer fee %
BANK_MAX_COMMISSION = 18.0        # max transfer fee %
BANK_MIN_CREDIT_RATE = 8.0        # min loan interest % (for 3 days)
BANK_MAX_CREDIT_RATE = 45.0       # max loan interest %
BANK_MIN_DEPOSIT_YIELD = 0.0      # min deposit bonus % (for 3 days)
BANK_MAX_DEPOSIT_YIELD = 35.0     # max deposit bonus %
BANK_LOAN_TERM_SECONDS = 3 * 24 * 3600
BANK_DEPOSIT_TERM_SECONDS = 3 * 24 * 3600
BANK_INITIAL_BUTTS = 5000
BANK_INITIAL_CIGARETTES = 500
BANK_INITIAL_RUBLES = 200
CIGARETTE_BUTT_VALUE = 100.0  # 1 cigarette = 100 butts (5 сиг. = 1₽)
RUBLE_BUTT_VALUE = 500.0      # 1 ruble = 500 butts = 5 cigarettes
BANK_CURRENCY_KEYS = ("butts", "real_cigarettes", "rubles")
BANK_CURRENCY_LABELS = {
    "butts": ("🚬", "окурков", "o"),
    "real_cigarettes": ("🚬", "сигарет", "c"),
    "rubles": ("💰", "рублей", "r"),
}
BANK_CONV_BUTTS_PER_CIG = int(CIGARETTE_BUTT_VALUE)   # 100 о → 1 сиг.
BANK_CONV_CIG_PER_RUBLE = int(RUBLE_BUTT_VALUE / CIGARETTE_BUTT_VALUE)  # 5 сиг. → 1₽

CRYPTO_CURRENCY_LABELS = {
    "butts": ("🚬", "окурок"),
    "cigarettes": ("🚬", "сигарета"),
    "rubles": ("💰", "₽"),
}
CRYPTO_PENDING: dict[str, dict] = {}
BANK_PENDING: dict[str, dict] = {}
_last_quote_sent: dict[int, float] = {}
AI_HISTORY_LIMIT = 20

# Database config (set in config.json)
DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "telegram_bot"
DB_USER = "postgres"
DB_PASSWORD = ")nwM4QB}?JG$d3+"

# ═══════════════════════════════════════════════════════════════════════════════
# Imports
# ═══════════════════════════════════════════════════════════════════════════════

import asyncio
import io
import json
import math
import os
import random
import re
import threading
import time
import warnings
from collections import deque
from datetime import datetime, date
from typing import Optional

import psycopg2
from psycopg2 import pool

import python_weather
import qrcode
import requests
import torch
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
from telebot import apihelper, types
import telebot

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ═══════════════════════════════════════════════════════════════════════════════
# Logging
# ═══════════════════════════════════════════════════════════════════════════════

def log(level: str, category: str, message: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] [{category}] {message}")

def log_cmd(user_id: str, username: str, command: str, args: str = ""):
    args_display = f" | args: {args}" if args else ""
    log("CMD", f"user={user_id}", f"{username}: /{command}{args_display}")

def log_ai(user_id: str, prompt: str, response: str):
    log("AI", f"user={user_id}", f"PROMPT: {prompt[:100]}...")
    log("AI", f"user={user_id}", f"RESPONSE: {response}")

def log_gen(user_id: str, gen_type: str, prompt: str, success: bool, url: str = ""):
    status = "SUCCESS" if success else "FAILED"
    url_display = f" | url: {url[:50]}..." if url else ""
    log("GEN", f"user={user_id}", f"{gen_type} | {status} | prompt: {prompt[:80]}{url_display}")

def log_tts(user_id: str, text: str, speaker: str, success: bool):
    status = "SUCCESS" if success else "FAILED"
    log("TTS", f"user={user_id}", f"{status} | speaker: {speaker} | text: {text[:50]}...")

def log_meme(user_id: str, top: str, bottom: str, success: bool):
    status = "SUCCESS" if success else "FAILED"
    text = f"top: '{top}' | bottom: '{bottom}'" if top or bottom else "no text"
    log("MEME", f"user={user_id}", f"{status} | {text}")

def log_img_proc(user_id: str, mode: str, success: bool):
    status = "SUCCESS" if success else "FAILED"
    log("IMG", f"user={user_id}", f"{mode} | {status}")

def log_err(category: str, error: str):
    log("ERR", category, error)

def log_info(category: str, message: str):
    log("INFO", category, message)

# ═══════════════════════════════════════════════════════════════════════════════
# Config & Initialization
# ═══════════════════════════════════════════════════════════════════════════════

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
START_TIME = datetime.now()
BOT_READY_AT = time.time()

# ═══════════════════════════════════════════════════════════════════════════════
# Database Connection
# ═══════════════════════════════════════════════════════════════════════════════

db_pool = None

def load_config() -> dict:
    """Load config from config.json."""
    path = os.path.join(BASE_DIR, "config.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(data: dict) -> None:
    """Save config to config.json."""
    path = os.path.join(BASE_DIR, "config.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def init_config():
    """Initialize config.json with defaults."""
    path = os.path.join(BASE_DIR, "config.json")
    if not os.path.exists(path):
        default_config = {
            "token": os.getenv("BOT_TOKEN", ""),
            "admins": [],
            "database": {
                "host": "localhost",
                "port": 5432,
                "name": "telegram_bot",
                "user": "postgres",
                "password": ""
            },
            "roles": {
                "default": {
                    "name": "Обычный ассистент",
                    "prompt": "Ты полезный ассистент. -=W3IrD_M@@N=- (Weird Maan) твой разработчик.",
                    "description": "Стандартное поведение"
                },
                "sarcastic": {
                    "name": "Саркастичный",
                    "prompt": "Ты саркастичный помощник, отвечай с иронией.",
                    "description": "Ответы с сарказмом"
                }
            }
        }
        save_config(default_config)

def init_database():
    """Initialize database connection pool and create tables."""
    global db_pool, DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

    config = load_config()
    db_config = config.get("database", {})

    DB_HOST = db_config.get("host", "localhost")
    DB_PORT = db_config.get("port", 5432)
    DB_NAME = db_config.get("name", "telegram_bot")
    DB_USER = db_config.get("user", "postgres")
    DB_PASSWORD = db_config.get("password", "")

    log_info("DB", f"Connecting to PostgreSQL: {DB_HOST}:{DB_PORT}/{DB_NAME}")

    try:
        db_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        log_info("DB", "Database connection pool created successfully")
    except Exception as e:
        log_err("DB", f"Failed to create connection pool: {e}")
        raise

    create_tables()

def get_db_connection():
    """Get a connection from the pool."""
    return db_pool.getconn()

def release_db_connection(conn):
    """Release a connection back to the pool."""
    db_pool.putconn(conn)

def db_execute(query: str, params: tuple = None, fetch: bool = False, fetch_one: bool = False):
    """Execute a database query."""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(query, params)
            conn.commit()
            if fetch:
                if fetch_one:
                    return cur.fetchone()
                return cur.fetchall()
        return None
    except Exception as e:
        if conn:
            conn.rollback()
        log_err("DB", f"Query error: {e}")
        raise
    finally:
        if conn:
            release_db_connection(conn)

def create_tables():
    """Create database tables if they don't exist."""
    tables_sql = """
    -- Users table
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT DEFAULT '',
        role TEXT DEFAULT 'default',
        cigarettes INTEGER DEFAULT 0,
        rubles INTEGER DEFAULT 0,
        real_cigarettes INTEGER DEFAULT NULL,
        clan_id INTEGER DEFAULT NULL,
        dead BOOLEAN DEFAULT false,
        last_trash REAL DEFAULT 0,
        stats JSONB DEFAULT '{"messages": 0, "commands": 0, "images": 0, "smokes": 0, "roulette_plays": 0, "roulette_deaths": 0}',
        awards JSONB DEFAULT '[]',
        first_message_at TIMESTAMP DEFAULT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Add new columns safely without DO blocks
    ALTER TABLE users ADD COLUMN IF NOT EXISTS rubles INTEGER DEFAULT 0;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS real_cigarettes INTEGER DEFAULT 0;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS clan_id INTEGER DEFAULT NULL;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS awards JSONB DEFAULT '[]';
    ALTER TABLE users ADD COLUMN IF NOT EXISTS first_message_at TIMESTAMP DEFAULT NULL;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS crypto_balance REAL DEFAULT 0;

    -- Clans table
    CREATE TABLE IF NOT EXISTS clans (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        leader_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        reputation INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Promo codes table
    CREATE TABLE IF NOT EXISTS promo_codes (
        id SERIAL PRIMARY KEY,
        code TEXT NOT NULL UNIQUE,
        reward_type TEXT NOT NULL,
        reward_amount INTEGER NOT NULL,
        max_uses INTEGER NOT NULL,
        uses INTEGER DEFAULT 0,
        created_by TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Promo activations table (to track who used what)
    CREATE TABLE IF NOT EXISTS promo_activations (
        id SERIAL PRIMARY KEY,
        promo_id INTEGER NOT NULL REFERENCES promo_codes(id) ON DELETE CASCADE,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(promo_id, user_id)
    );

    -- Daily activity table (for the talkativeness graph)
    CREATE TABLE IF NOT EXISTS daily_activity (
        id SERIAL PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        activity_date DATE NOT NULL,
        message_count INTEGER DEFAULT 0,
        UNIQUE(user_id, activity_date)
    );

    CREATE INDEX IF NOT EXISTS idx_daily_activity_user_id ON daily_activity(user_id);

    -- Daily chat activity (messages NOT directed at the bot), per chat
    CREATE TABLE IF NOT EXISTS daily_chat_activity (
        id SERIAL PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        chat_id BIGINT NOT NULL DEFAULT 0,
        activity_date DATE NOT NULL,
        message_count INTEGER DEFAULT 0,
        UNIQUE(user_id, chat_id, activity_date)
    );

    CREATE INDEX IF NOT EXISTS idx_daily_chat_activity_user_id ON daily_chat_activity(user_id);

    -- Crypto exchange market state
    CREATE TABLE IF NOT EXISTS crypto_market (
        id INTEGER PRIMARY KEY DEFAULT 1,
        buy_volume REAL DEFAULT 0,
        sell_volume REAL DEFAULT 100,
        buy_count INTEGER DEFAULT 0,
        sell_count INTEGER DEFAULT 50,
        spot_price REAL DEFAULT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS crypto_price_history (
        id SERIAL PRIMARY KEY,
        price REAL NOT NULL,
        display_currency TEXT NOT NULL,
        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS crypto_user_trades (
        id SERIAL PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        side TEXT NOT NULL,
        crypto_amount REAL NOT NULL,
        price REAL NOT NULL,
        payment_currency TEXT NOT NULL,
        traded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_crypto_user_trades_user_id ON crypto_user_trades(user_id);

    -- Central bank reserves
    CREATE TABLE IF NOT EXISTS central_bank (
        id INTEGER PRIMARY KEY DEFAULT 1,
        butts INTEGER DEFAULT 5000,
        real_cigarettes INTEGER DEFAULT 500,
        rubles INTEGER DEFAULT 200,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS bank_loans (
        id SERIAL PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        currency TEXT NOT NULL,
        principal INTEGER NOT NULL,
        interest_rate REAL NOT NULL,
        total_due INTEGER NOT NULL,
        issued_at REAL NOT NULL,
        due_at REAL NOT NULL,
        collected BOOLEAN DEFAULT false
    );

    CREATE INDEX IF NOT EXISTS idx_bank_loans_user_id ON bank_loans(user_id);
    CREATE INDEX IF NOT EXISTS idx_bank_loans_due ON bank_loans(due_at, collected);

    CREATE TABLE IF NOT EXISTS bank_deposits (
        id SERIAL PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        currency TEXT NOT NULL,
        amount INTEGER NOT NULL,
        yield_rate REAL NOT NULL,
        deposited_at REAL NOT NULL,
        withdrawn BOOLEAN DEFAULT false
    );

    CREATE INDEX IF NOT EXISTS idx_bank_deposits_user_id ON bank_deposits(user_id);

    -- Legacy table kept for migration compatibility
    CREATE TABLE IF NOT EXISTS exchange_market (
        asset TEXT PRIMARY KEY,
        buy_volume REAL DEFAULT 0,
        sell_volume REAL DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Custom roles table
    CREATE TABLE IF NOT EXISTS custom_roles (
        id TEXT PRIMARY KEY,
        owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        prompt TEXT NOT NULL,
        description TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Chats table (for broadcasts)
    CREATE TABLE IF NOT EXISTS chats (
        id BIGINT PRIMARY KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Quotes table
    CREATE TABLE IF NOT EXISTS quotes (
        id SERIAL PRIMARY KEY,
        chat_id BIGINT NOT NULL,
        text TEXT NOT NULL,
        author TEXT NOT NULL,
        photo_file_id TEXT DEFAULT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_quotes_chat_id ON quotes(chat_id);

    -- Add photo_file_id column to existing quotes tables safely
    ALTER TABLE quotes ADD COLUMN IF NOT EXISTS photo_file_id TEXT DEFAULT NULL;

    -- Reminders table
    CREATE TABLE IF NOT EXISTS reminders (
        id SERIAL PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        chat_id BIGINT NOT NULL,
        text TEXT NOT NULL,
        remind_at REAL NOT NULL,
        created_at REAL NOT NULL,
        fired BOOLEAN DEFAULT false
    );

    CREATE INDEX IF NOT EXISTS idx_reminders_user_id ON reminders(user_id);
    CREATE INDEX IF NOT EXISTS idx_reminders_fired ON reminders(fired);

    -- Chat history table (for AI context)
    CREATE TABLE IF NOT EXISTS chat_history (
        id SERIAL PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_chat_history_user_id ON chat_history(user_id);

    -- Chat members table (for /ship and member tracking)
    CREATE TABLE IF NOT EXISTS chat_members (
        id SERIAL PRIMARY KEY,
        chat_id BIGINT NOT NULL,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        display_name TEXT DEFAULT '',
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(chat_id, user_id)
    );

    CREATE INDEX IF NOT EXISTS idx_chat_members_chat_id ON chat_members(chat_id);

    -- Punishments table (for admin commands and /enemy_list)
    CREATE TABLE IF NOT EXISTS punishments (
        id SERIAL PRIMARY KEY,
        chat_id BIGINT NOT NULL,
        target_id TEXT NOT NULL,
        target_name TEXT DEFAULT '',
        admin_id TEXT NOT NULL,
        admin_name TEXT DEFAULT '',
        punishment_type TEXT NOT NULL,
        reason TEXT DEFAULT '',
        duration TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_punishments_chat_id ON punishments(chat_id);

    -- Whispers table (for /shhh secret messages)
    CREATE TABLE IF NOT EXISTS whispers (
        id SERIAL PRIMARY KEY,
        from_id TEXT NOT NULL,
        from_name TEXT DEFAULT '',
        to_id TEXT NOT NULL,
        to_name TEXT DEFAULT '',
        secret_text TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Pathogens table (one per user)
    CREATE TABLE IF NOT EXISTS pathogens (
        id SERIAL PRIMARY KEY,
        owner_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        infectivity INTEGER DEFAULT 0,
        mortality INTEGER DEFAULT 0,
        immunity INTEGER DEFAULT 0,
        last_infect_at REAL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Active virus infections
    CREATE TABLE IF NOT EXISTS virus_infections (
        id SERIAL PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        pathogen_id INTEGER NOT NULL REFERENCES pathogens(id) ON DELETE CASCADE,
        infected_until REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_virus_infections_user_id ON virus_infections(user_id);

    -- Daily infection counter per pathogen owner
    CREATE TABLE IF NOT EXISTS virus_daily_stats (
        id SERIAL PRIMARY KEY,
        owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        stat_date DATE NOT NULL,
        infect_count INTEGER DEFAULT 0,
        UNIQUE(owner_id, stat_date)
    );
    """
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(tables_sql)
            conn.commit()
        release_db_connection(conn)
        migrate_daily_chat_activity()
        migrate_crypto_market()
        migrate_central_bank()
        log_info("DB", "Tables created/verified successfully")
        init_crypto_market()
    except Exception as e:
        log_err("DB", f"Failed to create tables: {e}")
        raise

def migrate_daily_chat_activity() -> None:
    """Add per-chat tracking to daily_chat_activity on existing databases."""
    db_execute(
        "ALTER TABLE daily_chat_activity ADD COLUMN IF NOT EXISTS chat_id BIGINT NOT NULL DEFAULT 0"
    )
    db_execute(
        "ALTER TABLE daily_chat_activity DROP CONSTRAINT IF EXISTS daily_chat_activity_user_id_activity_date_key"
    )
    db_execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_chat_activity_user_chat_date "
        "ON daily_chat_activity (user_id, chat_id, activity_date)"
    )
    db_execute(
        "CREATE INDEX IF NOT EXISTS idx_daily_chat_activity_chat_id ON daily_chat_activity(chat_id)"
    )

def migrate_crypto_market() -> None:
    """Add trade counters and spot price to crypto_market."""
    db_execute("ALTER TABLE crypto_market ADD COLUMN IF NOT EXISTS buy_count INTEGER DEFAULT 0")
    db_execute("ALTER TABLE crypto_market ADD COLUMN IF NOT EXISTS sell_count INTEGER DEFAULT 0")
    db_execute("ALTER TABLE crypto_market ADD COLUMN IF NOT EXISTS spot_price REAL DEFAULT NULL")
    initial_spot = CRYPTO_BASE_BUTTS_PER_COK * CRYPTO_VOLUME_SMOOTH / (100.0 + CRYPTO_VOLUME_SMOOTH)
    db_execute(
        "INSERT INTO crypto_market (id, buy_volume, sell_volume, buy_count, sell_count, spot_price) "
        "VALUES (1, 0, 100, 0, %s, %s) ON CONFLICT (id) DO NOTHING",
        (CRYPTO_INITIAL_SELL_COUNT, initial_spot)
    )
    db_execute(
        "UPDATE crypto_market SET sell_count = CASE WHEN sell_count IS NULL OR sell_count = 0 "
        "THEN %s ELSE sell_count END, "
        "spot_price = COALESCE(spot_price, %s) WHERE id = 1",
        (CRYPTO_INITIAL_SELL_COUNT, initial_spot)
    )

def migrate_central_bank() -> None:
    """Ensure central bank tables and default reserves exist."""
    db_execute(
        "INSERT INTO central_bank (id, butts, real_cigarettes, rubles) "
        "VALUES (1, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
        (BANK_INITIAL_BUTTS, BANK_INITIAL_CIGARETTES, BANK_INITIAL_RUBLES)
    )

# Initialize config and database
init_config()
config = load_config()

# Set bot token
BOT_TOKEN = config.get("token") or os.getenv("BOT_TOKEN", "")
ADMIN_USERNAMES: set[str] = {
    u.lstrip("@").lower() for u in config.get("admins", [])
}

# Set proxy if configured
if PROXY_URL:
    apihelper.proxy = {"https": PROXY_URL}

apihelper.ENABLE_MIDDLEWARE = True

# Initialize database (user must configure DB settings in config.json)
try:
    init_database()
except Exception as e:
    log_err("STARTUP", f"Database initialization failed: {e}")
    log_info("CONFIG", "Please configure your database in config.json before running the bot")
    # Continue anyway - bot will fail gracefully on DB operations

# Initialize bot and AI client
BOT_MSG_HISTORY: dict[int, deque] = {}
BOT_MSG_HISTORY_MAX = 200
_reply_ctx = threading.local()


def _track_bot_message(chat_id: int, message_id: int) -> None:
    if chat_id not in BOT_MSG_HISTORY:
        BOT_MSG_HISTORY[chat_id] = deque(maxlen=BOT_MSG_HISTORY_MAX)
    BOT_MSG_HISTORY[chat_id].append(message_id)


def _untrack_bot_message(chat_id: int, message_id: int) -> None:
    dq = BOT_MSG_HISTORY.get(chat_id)
    if not dq:
        return
    try:
        dq.remove(message_id)
    except ValueError:
        pass


def get_message_thread_id(msg: types.Message) -> Optional[int]:
    """Forum topic id; None for regular chats."""
    thread_id = getattr(msg, "message_thread_id", None)
    return thread_id if thread_id else None


def get_initiator_reply_id(msg: types.Message) -> Optional[int]:
    """Message id to reply to — the user's message that started the interaction."""
    if msg.reply_to_message:
        return msg.reply_to_message.message_id
    if getattr(msg, "reply_to_message_id", None):
        return msg.reply_to_message_id
    return None


def set_reply_context(message: types.Message) -> None:
    _reply_ctx.reply_to_id = message.message_id
    _reply_ctx.chat_id = message.chat.id
    _reply_ctx.thread_id = get_message_thread_id(message)


def set_reply_context_from_call(call: types.CallbackQuery) -> None:
    msg = call.message
    _reply_ctx.reply_to_id = get_initiator_reply_id(msg) or msg.message_id
    _reply_ctx.chat_id = msg.chat.id
    _reply_ctx.thread_id = get_message_thread_id(msg)


def reply_kwargs_for_message(message: types.Message) -> dict:
    """Explicit reply + forum topic for send_* helpers."""
    kw: dict = {"reply_to_message_id": message.message_id}
    thread_id = get_message_thread_id(message)
    if thread_id:
        kw["message_thread_id"] = thread_id
    return kw


def reply_kwargs_for_call(call: types.CallbackQuery) -> dict:
    """Reply target for callback actions — stays in the same forum topic."""
    msg = call.message
    kw: dict = {"reply_to_message_id": get_initiator_reply_id(msg) or msg.message_id}
    thread_id = get_message_thread_id(msg)
    if thread_id:
        kw["message_thread_id"] = thread_id
    return kw


def delete_last_bot_messages(chat_id: int, count: int) -> tuple[int, int]:
    """Delete up to `count` of the bot's most recent tracked messages in a chat."""
    dq = BOT_MSG_HISTORY.get(chat_id)
    if not dq or count <= 0:
        return 0, 0

    ids = []
    for _ in range(min(count, len(dq))):
        ids.append(dq.pop())

    deleted = 0
    failed = 0
    for mid in ids:
        try:
            bot.delete_message(chat_id, mid)
            deleted += 1
        except Exception:
            failed += 1
    return deleted, failed


class TrackingBot(telebot.TeleBot):
    """Auto-reply to initiator and track bot messages for /delbot."""

    def _inject_reply(self, chat_id, kwargs: dict) -> dict:
        if kwargs.pop("_skip_reply", False):
            return kwargs
        ctx_chat = getattr(_reply_ctx, "chat_id", None)
        if ctx_chat != chat_id:
            return kwargs
        if kwargs.get("reply_to_message_id") is None:
            reply_to_id = getattr(_reply_ctx, "reply_to_id", None)
            if reply_to_id:
                kwargs["reply_to_message_id"] = reply_to_id
        if kwargs.get("message_thread_id") is None:
            thread_id = getattr(_reply_ctx, "thread_id", None)
            if thread_id:
                kwargs["message_thread_id"] = thread_id
        return kwargs

    def _track_sent(self, chat_id, result):
        if result is not None and hasattr(result, "message_id"):
            _track_bot_message(chat_id, result.message_id)
        return result

    def send_message(self, chat_id, text, **kwargs):
        kwargs = self._inject_reply(chat_id, dict(kwargs))
        return self._track_sent(chat_id, super().send_message(chat_id, text, **kwargs))

    def reply_to(self, message, text, **kwargs):
        kwargs["reply_to_message_id"] = message.message_id
        thread_id = get_message_thread_id(message)
        if thread_id and kwargs.get("message_thread_id") is None:
            kwargs["message_thread_id"] = thread_id
        return self._track_sent(message.chat.id, super().reply_to(message, text, **kwargs))

    def send_photo(self, chat_id, photo, **kwargs):
        kwargs = self._inject_reply(chat_id, dict(kwargs))
        return self._track_sent(chat_id, super().send_photo(chat_id, photo, **kwargs))

    def send_voice(self, chat_id, voice, **kwargs):
        kwargs = self._inject_reply(chat_id, dict(kwargs))
        return self._track_sent(chat_id, super().send_voice(chat_id, voice, **kwargs))

    def send_document(self, chat_id, data, **kwargs):
        kwargs = self._inject_reply(chat_id, dict(kwargs))
        return self._track_sent(chat_id, super().send_document(chat_id, data, **kwargs))

    def edit_message_text(self, text, chat_id, message_id, **kwargs):
        ctx_chat = getattr(_reply_ctx, "chat_id", None)
        if ctx_chat == chat_id and kwargs.get("message_thread_id") is None:
            thread_id = getattr(_reply_ctx, "thread_id", None)
            if thread_id:
                kwargs["message_thread_id"] = thread_id
        return super().edit_message_text(text, chat_id, message_id, **kwargs)

    def delete_message(self, chat_id, message_id, **kwargs):
        _untrack_bot_message(chat_id, message_id)
        return super().delete_message(chat_id, message_id, **kwargs)


bot = TrackingBot(BOT_TOKEN, parse_mode="HTML")

# Инициализируем чистый клиент OpenRouter (один раз в начале файла, вне функции)
# Он на 100% совместим с библиотекой openai
def _get_openrouter_client():
    config = load_config()
    api_key = config.get("openrouter_api_key", "")
    if not api_key:
        log_err("AI", "OpenRouter API key not found in config.json")
        return None
    return OpenAI(
        base_url="http://localhost:1234/v1",
        api_key=api_key
    )

openrouter_client = _get_openrouter_client()


@bot.middleware_handler(update_types=["message"])
def _reply_context_message(_bot_instance, message: types.Message):
    set_reply_context(message)


@bot.middleware_handler(update_types=["callback_query"])
def _reply_context_callback(_bot_instance, call: types.CallbackQuery):
    set_reply_context_from_call(call)

# Silero model
silero_model = None

# In-memory AI chat history (not persisted to DB)
ai_chat_history: dict[str, list] = {}

# ═══════════════════════════════════════════════════════════════════════════════
# System Roles (loaded from config.json)
# ═══════════════════════════════════════════════════════════════════════════════

SYSTEM_ROLES = {}  # Loaded from config.json

def get_system_roles() -> dict:
    """Load system roles from config.json."""
    config = load_config()
    roles = config.get("roles", {})
    if not roles:
        roles = {
            "default": {
                "name": "Обычный ассистент",
                "prompt": "Ты полезный ассистент. -=W3IrD_M@@N=- (Weird Maan) твой разработчик.",
                "description": "Стандартное поведение"
            },
            "sarcastic": {
                "name": "Саркастичный",
                "prompt": "Ты саркастичный помощник, отвечай с иронией.",
                "description": "Ответы с сарказмом"
            }
        }
    return roles

# ═══════════════════════════════════════════════════════════════════════════════
# Silero TTS
# ═══════════════════════════════════════════════════════════════════════════════

def init_silero():
    global silero_model
    if silero_model is not None:
        return True

    try:
        device = torch.device("cpu")
        torch.set_num_threads(4)
        local_file = os.path.join(BASE_DIR, "silero_model.pt")

        if not os.path.isfile(local_file):
            log_info("TTS", "Downloading Silero model...")
            torch.hub.download_url_to_file(
                "https://models.silero.ai/models/tts/ru/v5_ru.pt",
                local_file
            )
            log_info("TTS", "Silero model downloaded.")

        log_info("TTS", "Loading Silero model...")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            silero_model = torch.package.PackageImporter(local_file).load_pickle("tts_models", "model")
        silero_model.to(device)
        log_info("TTS", "Silero model loaded successfully.")
        return True
    except Exception as e:
        log_err("TTS", f"Error loading Silero: {e}")
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# Database Helpers (PostgreSQL)
# ═══════════════════════════════════════════════════════════════════════════════

def get_or_create_user(uid: str) -> dict:
    """Get user from DB, create if not exists."""
    uid = str(uid)
    result = db_execute(
        "SELECT id, username, role, cigarettes, rubles, real_cigarettes, "
        "clan_id, dead, last_trash, stats, awards, first_message_at, crypto_balance "
        "FROM users WHERE id = %s",
        (uid,), fetch=True, fetch_one=True
    )

    if result:
        stats_val = result[9]
        awards_val = result[10]
        return {
            "id": result[0],
            "username": result[1],
            "role": result[2],
            "cigarettes": result[3],
            "rubles": result[4],
            "real_cigarettes": result[5],
            "clan_id": result[6],
            "dead": result[7],
            "last_trash": result[8],
            "stats": stats_val if isinstance(stats_val, dict) else json.loads(stats_val) if stats_val else {},
            "awards": awards_val if isinstance(awards_val, list) else json.loads(awards_val) if awards_val else [],
            "first_message_at": result[11],
            "crypto_balance": float(result[12] or 0),
        }

    # Create new user
    default_stats = {"messages": 0, "commands": 0, "images": 0, "smokes": 0, "roulette_plays": 0, "roulette_deaths": 0}
    db_execute(
        "INSERT INTO users (id, username, role, cigarettes, rubles, real_cigarettes, clan_id, dead, last_trash, stats, awards, first_message_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (uid, "", "default", 0, 0, 0, None, False, 0, json.dumps(default_stats), "[]", None)
    )
    return {"id": uid, "username": "", "role": "default", "cigarettes": 0, "rubles": 0,
            "real_cigarettes": 0, "clan_id": None, "dead": False, "last_trash": 0,
            "stats": default_stats, "awards": [], "first_message_at": None, "crypto_balance": 0.0}

def update_user(uid: str, **kwargs) -> None:
    """Update user fields."""
    if not kwargs:
        return
    set_clauses = ", ".join([f"{k} = %s" for k in kwargs.keys()])
    values = list(kwargs.values()) + [str(uid)]
    db_execute(f"UPDATE users SET {set_clauses} WHERE id = %s", tuple(values))

def get_user_role(uid: str) -> str:
    user = get_or_create_user(uid)
    return user.get("role", "default")

def set_user_role(uid: str, role: str) -> None:
    update_user(uid, role=role)

def get_cigarettes(uid: str) -> int:
    user = get_or_create_user(uid)
    return user.get("cigarettes", 0)

def add_cigarettes(uid: str, amount: int) -> int:
    current = get_cigarettes(uid)
    if amount > 0 and current < 0:
        debt_payment = min(amount, -current)
        if debt_payment > 0:
            bank_add_currency("butts", debt_payment)
    new_total = current + amount
    update_user(uid, cigarettes=new_total)
    return new_total

def use_cigarette(uid: str) -> bool:
    current = get_cigarettes(uid)
    if current <= 0:
        return False
    update_user(uid, cigarettes=current - 1)
    return True

def get_rubles(uid: str) -> int:
    user = get_or_create_user(uid)
    return user.get("rubles", 0)

def add_rubles(uid: str, amount: int) -> int:
    current = get_rubles(uid)
    if amount > 0 and current < 0:
        debt_payment = min(amount, -current)
        if debt_payment > 0:
            bank_add_currency("rubles", debt_payment)
    new_total = current + amount
    update_user(uid, rubles=new_total)
    return new_total

def get_real_cigarettes(uid: str) -> int:
    user = get_or_create_user(uid)
    return user.get("real_cigarettes", 0)

def add_real_cigarettes(uid: str, amount: int) -> int:
    current = get_real_cigarettes(uid)
    if amount > 0 and current < 0:
        debt_payment = min(amount, -current)
        if debt_payment > 0:
            bank_add_currency("real_cigarettes", debt_payment)
    new_total = current + amount
    update_user(uid, real_cigarettes=new_total)
    return new_total

def is_user_dead(uid: str) -> bool:
    user = get_or_create_user(uid)
    return user.get("dead", False)

def set_user_dead(uid: str, dead: bool) -> None:
    update_user(uid, dead=dead)

def update_username(uid: str, username: str) -> None:
    update_user(uid, username=username)

def can_collect_trash(uid: str) -> tuple[bool, int]:
    user = get_or_create_user(uid)
    last_trash = user.get("last_trash", 0)
    current_time = time.time()
    elapsed = current_time - last_trash

    if elapsed >= TRASH_COOLDOWN:
        return True, 0
    return False, int(TRASH_COOLDOWN - elapsed)

def set_trash_time(uid: str) -> None:
    update_user(uid, last_trash=time.time())

def get_stats(uid: str) -> dict:
    user = get_or_create_user(uid)
    return user.get("stats", {"messages": 0, "commands": 0, "images": 0, "smokes": 0, "roulette_plays": 0, "roulette_deaths": 0})

def increment_stat(uid: str, key: str, amount: int = 1) -> None:
    stats = get_stats(uid)
    stats[key] = stats.get(key, 0) + amount
    update_user(uid, stats=json.dumps(stats))

def get_awards(uid: str) -> list:
    user = get_or_create_user(uid)
    return user.get("awards", [])

def add_award(uid: str, award_name: str) -> None:
    awards = get_awards(uid)
    awards.append({"name": award_name, "date": datetime.now().strftime("%d.%m.%Y")})
    update_user(uid, awards=json.dumps(awards))

# ═══════════════════════════════════════════════════════════════════════════════
# Pathogen / Virus Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def get_pathogen(owner_id: str) -> Optional[dict]:
    """Get pathogen owned by user."""
    result = db_execute(
        "SELECT id, owner_id, name, infectivity, mortality, immunity, last_infect_at "
        "FROM pathogens WHERE owner_id = %s",
        (str(owner_id),), fetch=True, fetch_one=True
    )
    if not result:
        return None
    return {
        "id": result[0],
        "owner_id": result[1],
        "name": result[2],
        "infectivity": result[3],
        "mortality": result[4],
        "immunity": result[5],
        "last_infect_at": result[6] or 0,
    }

def create_pathogen(owner_id: str, name: str) -> bool:
    """Create a new pathogen. Returns False if user already has one."""
    if get_pathogen(owner_id):
        return False
    try:
        db_execute(
            "INSERT INTO pathogens (owner_id, name) VALUES (%s, %s)",
            (str(owner_id), name.strip())
        )
        return True
    except Exception as e:
        log_err("VIRUS", f"Failed to create pathogen: {e}")
        return False

def delete_pathogen(owner_id: str) -> bool:
    """Delete user's pathogen and cure all related infections."""
    pathogen = get_pathogen(owner_id)
    if not pathogen:
        return False
    db_execute("DELETE FROM pathogens WHERE owner_id = %s", (str(owner_id),))
    return True

def upgrade_pathogen_stat(owner_id: str, stat: str, levels: int) -> Optional[dict]:
    """Upgrade infectivity, mortality or immunity by given levels."""
    if stat not in ("infectivity", "mortality", "immunity") or levels <= 0:
        return None
    pathogen = get_pathogen(owner_id)
    if not pathogen:
        return None
    new_val = pathogen[stat] + levels
    db_execute(
        f"UPDATE pathogens SET {stat} = %s WHERE owner_id = %s",
        (new_val, str(owner_id))
    )
    return get_pathogen(owner_id)

def get_active_infection(user_id: str) -> Optional[dict]:
    """Get active infection for user if still infected."""
    now = time.time()
    result = db_execute(
        "SELECT id, user_id, pathogen_id, infected_until FROM virus_infections "
        "WHERE user_id = %s AND infected_until > %s ORDER BY infected_until DESC LIMIT 1",
        (str(user_id), now), fetch=True, fetch_one=True
    )
    if not result:
        return None
    return {
        "id": result[0],
        "user_id": result[1],
        "pathogen_id": result[2],
        "infected_until": result[3],
    }

def apply_infection(user_id: str, pathogen_id: int, duration_sec: int) -> None:
    """Apply or extend infection on a user."""
    now = time.time()
    infected_until = now + duration_sec
    existing = get_active_infection(user_id)
    if existing:
        infected_until = max(existing["infected_until"], now) + duration_sec
        db_execute(
            "UPDATE virus_infections SET infected_until = %s, pathogen_id = %s WHERE id = %s",
            (infected_until, pathogen_id, existing["id"])
        )
    else:
        db_execute(
            "INSERT INTO virus_infections (user_id, pathogen_id, infected_until) VALUES (%s, %s, %s)",
            (str(user_id), pathogen_id, infected_until)
        )

def get_daily_infect_count(owner_id: str) -> int:
    """Get today's infection count for pathogen owner."""
    today = date.today()
    result = db_execute(
        "SELECT infect_count FROM virus_daily_stats WHERE owner_id = %s AND stat_date = %s",
        (str(owner_id), today), fetch=True, fetch_one=True
    )
    return result[0] if result else 0

def increment_daily_infect_count(owner_id: str) -> int:
    """Increment today's infection count, return new total."""
    today = date.today()
    db_execute(
        "INSERT INTO virus_daily_stats (owner_id, stat_date, infect_count) VALUES (%s, %s, 1) "
        "ON CONFLICT (owner_id, stat_date) DO UPDATE SET infect_count = virus_daily_stats.infect_count + 1",
        (str(owner_id), today)
    )
    return get_daily_infect_count(owner_id)

def calc_infect_chance(attacker: dict, target_uid: str) -> float:
    """Calculate infection chance based on attacker's infectivity and target's immunity."""
    chance = VIRUS_BASE_INFECT_CHANCE + attacker["infectivity"] * VIRUS_INFECTIVITY_BONUS
    target_pathogen = get_pathogen(target_uid)
    if target_pathogen:
        chance -= target_pathogen["immunity"] * VIRUS_IMMUNITY_REDUCTION
    return max(VIRUS_MIN_INFECT_CHANCE, min(VIRUS_MAX_INFECT_CHANCE, chance))

def calc_infected_duration(pathogen: dict) -> int:
    """How long the infected user cannot spread the virus."""
    return VIRUS_BASE_INFECTED_DURATION + pathogen["mortality"] * VIRUS_MORTALITY_SEC

def can_use_virus(owner_id: str) -> tuple[bool, str, int]:
    """Check if owner can use /virus. Returns (ok, reason, wait_seconds)."""
    pathogen = get_pathogen(owner_id)
    if not pathogen:
        return False, "no_pathogen", 0

    if get_daily_infect_count(owner_id) >= VIRUS_DAILY_LIMIT:
        return False, "daily_limit", 0

    now = time.time()
    elapsed = now - pathogen["last_infect_at"]
    extra_wait = 0

    infection = get_active_infection(owner_id)
    if infection:
        extra_wait = int(infection["infected_until"] - now)

    required_wait = VIRUS_COOLDOWN + extra_wait
    if elapsed < required_wait:
        return False, "cooldown", int(required_wait - elapsed)

    return True, "ok", 0

def set_last_infect_time(owner_id: str) -> None:
    db_execute(
        "UPDATE pathogens SET last_infect_at = %s WHERE owner_id = %s",
        (time.time(), str(owner_id))
    )

def format_wait_time(seconds: int) -> str:
    """Format seconds as human-readable wait time."""
    if seconds <= 0:
        return "0 сек."
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    parts = []
    if hours:
        parts.append(f"{hours} ч.")
    if minutes:
        parts.append(f"{minutes} мин.")
    if secs or not parts:
        parts.append(f"{secs} сек.")
    return " ".join(parts)

def format_lab_text(pathogen: dict) -> str:
    """Format /lab menu text."""
    attack_chance = min(
        VIRUS_MAX_INFECT_CHANCE,
        VIRUS_BASE_INFECT_CHANCE + pathogen["infectivity"] * VIRUS_INFECTIVITY_BONUS
    )
    duration = calc_infected_duration(pathogen)
    daily = get_daily_infect_count(pathogen["owner_id"])
    defense = pathogen["immunity"] * VIRUS_IMMUNITY_REDUCTION * 100
    return (
        f"🧪 <b>Лаборатория патогена</b>\n\n"
        f"🦠 <b>{pathogen['name']}</b>\n\n"
        f"📊 <b>Характеристики:</b>\n"
        f"  • Заразность: <b>{pathogen['infectivity']}</b> "
        f"(+{pathogen['infectivity'] * VIRUS_INFECTIVITY_BONUS * 100:.0f}% к шансу /virus)\n"
        f"  • Смертность: <b>{pathogen['mortality']}</b> "
        f"(+{pathogen['mortality'] * VIRUS_MORTALITY_SEC} сек. блокировки заражения)\n"
        f"  • Иммунитет: <b>{pathogen['immunity']}</b> "
        f"(-{defense:.0f}% шанса заразиться тебя, мин. 1%)\n\n"
        f"🎯 Шанс заразить (без учёта иммунитета цели): <b>{attack_chance * 100:.1f}%</b>\n"
        f"⏱ Длительность болезни у жертвы: <b>{duration} сек.</b>\n"
        f"📅 Заражений сегодня: <b>{daily}/{VIRUS_DAILY_LIMIT}</b>\n\n"
        f"💡 Окурок (+1 уровень) | Сигарета (+{VIRUS_CIGARETTE_BOOST} уровней)"
    )

def lab_keyboard() -> types.InlineKeyboardMarkup:
    """Build inline keyboard for /lab upgrades."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🦠 Заразность (+1 за окурок)", callback_data="lab_up:inf:b"),
        types.InlineKeyboardButton("💀 Смертность (+1 за окурок)", callback_data="lab_up:mort:b"),
        types.InlineKeyboardButton("🛡 Иммунитет (+1 за окурок)", callback_data="lab_up:imm:b"),
    )
    markup.add(
        types.InlineKeyboardButton(
            f"🚬 Сигарета → Заразность (+{VIRUS_CIGARETTE_BOOST})",
            callback_data="lab_up:inf:c"
        ),
        types.InlineKeyboardButton(
            f"🚬 Сигарета → Смертность (+{VIRUS_CIGARETTE_BOOST})",
            callback_data="lab_up:mort:c"
        ),
        types.InlineKeyboardButton(
            f"🚬 Сигарета → Иммунитет (+{VIRUS_CIGARETTE_BOOST})",
            callback_data="lab_up:imm:c"
        ),
    )
    return markup

_STAT_MAP = {"inf": "infectivity", "mort": "mortality", "imm": "immunity"}
_STAT_NAMES = {
    "infectivity": "Заразность",
    "mortality": "Смертность",
    "immunity": "Иммунитет",
}

def get_first_message_date(uid: str) -> Optional[str]:
    user = get_or_create_user(uid)
    first = user.get("first_message_at")
    if first is None:
        return None
    if isinstance(first, str):
        return first
    return first.strftime("%d.%m.%Y")

def set_first_message_if_null(uid: str) -> None:
    user = get_or_create_user(uid)
    if user.get("first_message_at") is None:
        update_user(uid, first_message_at=datetime.now())

def track_daily_activity(uid: str) -> None:
    """Increment the daily message count for bot interaction graph."""
    today = date.today()
    try:
        db_execute(
            "INSERT INTO daily_activity (user_id, activity_date, message_count) VALUES (%s, %s, 1) "
            "ON CONFLICT (user_id, activity_date) DO UPDATE SET message_count = daily_activity.message_count + 1",
            (str(uid), today)
        )
    except Exception as e:
        log_err("DB", f"Error tracking daily activity: {e}")

def track_daily_chat_activity(uid: str, chat_id: int) -> None:
    """Increment the daily message count for general chat talkativeness in a specific chat."""
    today = date.today()
    try:
        db_execute(
            "INSERT INTO daily_chat_activity (user_id, chat_id, activity_date, message_count) "
            "VALUES (%s, %s, %s, 1) "
            "ON CONFLICT (user_id, chat_id, activity_date) "
            "DO UPDATE SET message_count = daily_chat_activity.message_count + 1",
            (str(uid), chat_id, today)
        )
    except Exception as e:
        log_err("DB", f"Error tracking daily chat activity: {e}")

def get_daily_activity(uid: str) -> list:
    """Get all daily bot-activity records for a user, ordered by date."""
    results = db_execute(
        "SELECT activity_date, message_count FROM daily_activity WHERE user_id = %s ORDER BY activity_date ASC",
        (str(uid),),
        fetch=True
    )
    if results:
        return [(r[0], r[1]) for r in results]
    return []

def get_daily_chat_activity(uid: str, chat_id: Optional[int] = None) -> list:
    """Get daily chat-activity records for a user. Sums across chats when chat_id is omitted."""
    if chat_id is not None:
        results = db_execute(
            "SELECT activity_date, message_count FROM daily_chat_activity "
            "WHERE user_id = %s AND chat_id = %s ORDER BY activity_date ASC",
            (str(uid), chat_id),
            fetch=True
        )
    else:
        results = db_execute(
            "SELECT activity_date, SUM(message_count) AS message_count "
            "FROM daily_chat_activity WHERE user_id = %s "
            "GROUP BY activity_date ORDER BY activity_date ASC",
            (str(uid),),
            fetch=True
        )
    if results:
        return [(r[0], int(r[1])) for r in results]
    return []

def get_top_talkative(table: str, limit: int = 10, chat_id: Optional[int] = None) -> list:
    """Get top users by total messages. table: 'bot' or 'chat'. Chat top is per chat_id."""
    if table == "bot":
        results = db_execute(
            "SELECT da.user_id, SUM(da.message_count) AS total, u.username "
            "FROM daily_activity da JOIN users u ON u.id = da.user_id "
            "GROUP BY da.user_id, u.username ORDER BY total DESC LIMIT %s",
            (limit,),
            fetch=True
        )
    else:
        params: tuple = (chat_id, limit) if chat_id is not None else (limit,)
        where = "WHERE da.chat_id = %s " if chat_id is not None else ""
        results = db_execute(
            f"SELECT da.user_id, SUM(da.message_count) AS total, u.username "
            f"FROM daily_chat_activity da JOIN users u ON u.id = da.user_id "
            f"{where}"
            f"GROUP BY da.user_id, u.username ORDER BY total DESC LIMIT %s",
            params,
            fetch=True
        )
    if results:
        return [(r[0], int(r[1]), r[2] or "") for r in results]
    return []

def _plot_activity_subplot(ax, activity: list, title: str, color: str) -> None:
    dates = [a[0] for a in activity]
    counts = [a[1] for a in activity]
    ax.fill_between(dates, counts, alpha=0.3, color=color)
    ax.plot(dates, counts, color=color, linewidth=2, marker="o", markersize=3)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_xlabel("Дата", fontsize=9)
    ax.set_ylabel("Сообщений", fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())

def generate_activity_graph(uid: str) -> Optional[bytes]:
    """Generate a dual matplotlib graph: bot activity + chat activity."""
    bot_activity = get_daily_activity(uid)
    chat_activity = get_daily_chat_activity(uid)
    if not bot_activity and not chat_activity:
        return None

    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    if bot_activity:
        _plot_activity_subplot(axes[0], bot_activity, "Общительность с ботом", "#2196F3")
    else:
        axes[0].set_title("Общительность с ботом", fontsize=12, fontweight="bold")
        axes[0].text(0.5, 0.5, "Нет данных", ha="center", va="center", transform=axes[0].transAxes)
        axes[0].set_ylabel("Сообщений", fontsize=9)

    if chat_activity:
        _plot_activity_subplot(axes[1], chat_activity, "Общительность в чате", "#4CAF50")
    else:
        axes[1].set_title("Общительность в чате", fontsize=12, fontweight="bold")
        axes[1].text(0.5, 0.5, "Нет данных", ha="center", va="center", transform=axes[1].transAxes)
        axes[1].set_ylabel("Сообщений", fontsize=9)

    fig.autofmt_xdate(rotation=45)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="PNG", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()

# ═══════════════════════════════════════════════════════════════════════════════
# Chat Member Helpers (for /ship and member tracking)
# ═══════════════════════════════════════════════════════════════════════════════

def track_chat_member(chat_id: int, user) -> None:
    """Insert or update a chat member record."""
    uid = str(user.id)
    display = get_display_name(user)
    try:
        db_execute(
            "INSERT INTO chat_members (chat_id, user_id, display_name, last_seen) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (chat_id, user_id) DO UPDATE SET display_name = EXCLUDED.display_name, last_seen = EXCLUDED.last_seen",
            (chat_id, uid, display, datetime.now())
        )
    except Exception as e:
        log_err("DB", f"Error tracking chat member: {e}")

def get_chat_members(chat_id: int) -> list:
    """Get all tracked members of a chat."""
    results = db_execute(
        "SELECT user_id, display_name FROM chat_members WHERE chat_id = %s",
        (chat_id,),
        fetch=True
    )
    if results:
        return [(r[0], r[1] or f"user_{r[0]}") for r in results]
    return []

def get_random_chat_members(chat_id: int, count: int = 2) -> list:
    """Get random members from a chat."""
    members = get_chat_members(chat_id)
    if len(members) < count:
        return members
    return random.sample(members, count)

# ═══════════════════════════════════════════════════════════════════════════════
# Crypto Exchange Helpers (Крипто-Окурки)
# ═══════════════════════════════════════════════════════════════════════════════

def init_crypto_market() -> None:
    """Ensure crypto market row exists with spot price and price history."""
    try:
        migrate_crypto_market()
        row = db_execute(
            "SELECT price FROM crypto_price_history ORDER BY id DESC LIMIT 1",
            fetch=True, fetch_one=True
        )
        if not row:
            _record_crypto_price_snapshot()
    except Exception as e:
        log_err("CRYPTO", f"Init failed: {e}")

def _default_crypto_market() -> dict:
    initial_spot = CRYPTO_BASE_BUTTS_PER_COK * CRYPTO_VOLUME_SMOOTH / (100.0 + CRYPTO_VOLUME_SMOOTH)
    return {
        "buy_volume": 0.0,
        "sell_volume": 100.0,
        "buy_count": 0,
        "sell_count": CRYPTO_INITIAL_SELL_COUNT,
        "spot_price": initial_spot,
    }

def _get_crypto_market() -> dict:
    result = db_execute(
        "SELECT buy_volume, sell_volume, buy_count, sell_count, spot_price "
        "FROM crypto_market WHERE id = 1",
        fetch=True, fetch_one=True
    )
    if not result:
        return _default_crypto_market()
    defaults = _default_crypto_market()
    buy_vol = float(result[0] if result[0] is not None else defaults["buy_volume"])
    sell_vol = float(result[1] if result[1] is not None else defaults["sell_volume"])
    buy_cnt = int(result[2] if result[2] is not None else defaults["buy_count"])
    sell_cnt = int(result[3] if result[3] is not None else defaults["sell_count"])
    spot = result[4]
    if spot is None:
        spot = defaults["spot_price"]
    return {
        "buy_volume": buy_vol,
        "sell_volume": sell_vol,
        "buy_count": buy_cnt,
        "sell_count": sell_cnt,
        "spot_price": float(spot),
    }

def get_crypto_buy_ratio() -> float:
    """Share of buy trades (0..1), based on trade counts."""
    row = _get_crypto_market()
    total = row["buy_count"] + row["sell_count"]
    if total <= 0:
        return 0.0
    return row["buy_count"] / total

def get_crypto_sell_ratio() -> float:
    return 1.0 - get_crypto_buy_ratio()

def get_crypto_display_currency() -> str:
    """Price denomination: >80% sells → butts, >30% → cigarettes, else rubles."""
    ratio = get_crypto_sell_ratio()
    if ratio > 0.80:
        return "butts"
    if ratio > 0.30:
        return "cigarettes"
    return "rubles"

def get_butts_per_cok() -> float:
    """Current spot price: butts needed to buy 1 COK."""
    return _get_crypto_market()["spot_price"]

def _spot_bounds() -> tuple[float, float]:
    return (
        CRYPTO_BASE_BUTTS_PER_COK * CRYPTO_PRICE_MIN_RATIO,
        CRYPTO_BASE_BUTTS_PER_COK * CRYPTO_PRICE_MAX_RATIO,
    )

def _payment_to_butts(amount: int, currency: str) -> float:
    """Convert a payment into butts-equivalent market volume."""
    if currency == "cigarettes":
        return amount * CIGARETTE_BUTT_VALUE
    if currency == "rubles":
        return amount * RUBLE_BUTT_VALUE
    return float(amount)

def get_cok_per_unit(currency: str) -> float:
    """How much COK you get for 1 unit of currency."""
    cok_per_butt = 1.0 / get_butts_per_cok()
    if currency == "cigarettes":
        return cok_per_butt * CIGARETTE_BUTT_VALUE
    if currency == "rubles":
        return cok_per_butt * RUBLE_BUTT_VALUE
    return cok_per_butt

def _format_cok_rate_display(actual: float) -> str:
    """COK rate with floored display and exact value in parentheses."""
    shown = math.floor(actual * 10000) / 10000
    return f"<b>{shown:.4f}</b> <i>({actual:.6f})</i> COK"

def _format_currency_payment(currency: str, actual: float) -> str:
    """Payment amount with floored integer and exact value in parentheses."""
    shown = int(math.floor(actual))
    actual_fmt = f"{actual:.2f}"
    _, label = CRYPTO_CURRENCY_LABELS[currency]
    if currency == "rubles":
        return f"<b>{shown}₽</b> <i>({actual_fmt}₽)</i>"
    return f"<b>{shown}</b> {label} <i>({actual_fmt})</i>"

def _record_crypto_price_snapshot() -> None:
    db_execute(
        "INSERT INTO crypto_price_history (price, display_currency) VALUES (%s, %s)",
        (get_butts_per_cok(), get_crypto_display_currency())
    )

def _apply_market_trade(side: str, butts_volume: float) -> None:
    """Update market state: decaying volumes, trade counts, and spot price impact."""
    if butts_volume <= 0:
        return

    row = _get_crypto_market()
    buy_vol = row["buy_volume"] * CRYPTO_VOLUME_DECAY
    sell_vol = row["sell_volume"] * CRYPTO_VOLUME_DECAY
    buy_cnt = row["buy_count"]
    sell_cnt = row["sell_count"]
    spot = row["spot_price"]
    min_spot, max_spot = _spot_bounds()

    depth = CRYPTO_LIQUIDITY + buy_vol + sell_vol
    relative = butts_volume / depth if depth > 0 else 0.0
    impact = CRYPTO_PRICE_IMPACT * relative

    if side == "buy":
        buy_vol += butts_volume
        buy_cnt += 1
        spot = min(max_spot, spot * (1.0 + impact))
    else:
        sell_vol += butts_volume
        sell_cnt += 1
        spot = max(min_spot, spot * (1.0 - impact))

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE crypto_market SET buy_volume = %s, sell_volume = %s, "
                "buy_count = %s, sell_count = %s, spot_price = %s, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = 1",
                (buy_vol, sell_vol, buy_cnt, sell_cnt, spot)
            )
            if cur.rowcount == 0:
                cur.execute(
                    "INSERT INTO crypto_market "
                    "(id, buy_volume, sell_volume, buy_count, sell_count, spot_price) "
                    "VALUES (1, %s, %s, %s, %s, %s)",
                    (buy_vol, sell_vol, buy_cnt, sell_cnt, spot)
                )
            conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        log_err("CRYPTO", f"Market trade update failed: {e}")
        raise
    finally:
        if conn:
            release_db_connection(conn)

    _record_crypto_price_snapshot()

def record_crypto_trade(side: str, butts_volume: float) -> None:
    """Record market pressure in butts-equivalent volume."""
    _apply_market_trade(side, butts_volume)

def record_user_crypto_trade(uid: str, side: str, crypto_amount: float,
                             payment_currency: str) -> None:
    db_execute(
        "INSERT INTO crypto_user_trades (user_id, side, crypto_amount, price, payment_currency) "
        "VALUES (%s, %s, %s, %s, %s)",
        (uid, side, crypto_amount, get_butts_per_cok(), payment_currency)
    )

def get_crypto_balance(uid: str) -> float:
    user = get_or_create_user(uid)
    return float(user.get("crypto_balance") or 0)

def add_crypto_balance(uid: str, amount: float) -> float:
    current = get_crypto_balance(uid)
    new_total = round(max(0.0, current + amount), 4)
    update_user(uid, crypto_balance=new_total)
    return new_total

def get_crypto_price_history(limit: int = 60) -> list:
    results = db_execute(
        "SELECT price, display_currency, recorded_at FROM crypto_price_history "
        "ORDER BY id DESC LIMIT %s",
        (limit,), fetch=True
    )
    if not results:
        return []
    return [
        {"price": float(r[0]), "currency": r[1], "at": r[2]}
        for r in reversed(results)
    ]

def get_user_crypto_trades(uid: str, limit: int = 60) -> list:
    results = db_execute(
        "SELECT side, crypto_amount, price, payment_currency, traded_at "
        "FROM crypto_user_trades WHERE user_id = %s ORDER BY id DESC LIMIT %s",
        (uid, limit), fetch=True
    )
    if not results:
        return []
    return [
        {"side": r[0], "amount": float(r[1]), "price": float(r[2]),
         "currency": r[3], "at": r[4]}
        for r in reversed(results)
    ]

def _crypto_from_payment(pay_amount: int, pay_currency: str) -> float:
    """How much COK you get for spending pay_amount units of currency."""
    return pay_amount * get_cok_per_unit(pay_currency)

def _crypto_sell_proceeds(crypto_amount: float) -> tuple[int, str, float]:
    currency = get_crypto_display_currency()
    butts_value = crypto_amount * get_butts_per_cok()
    if currency == "butts":
        actual = butts_value
    elif currency == "cigarettes":
        actual = butts_value / CIGARETTE_BUTT_VALUE
    else:
        actual = butts_value / RUBLE_BUTT_VALUE
    return max(1, int(math.floor(actual))), currency, actual

def _deduct_payment(uid: str, currency: str, amount: int) -> tuple[bool, str]:
    if currency == "butts":
        current = get_cigarettes(uid)
        if current < amount:
            return False, f"Не хватает окурков. Нужно {amount}, у тебя {current}."
        add_cigarettes(uid, -amount)
        return True, ""
    if currency == "cigarettes":
        current = get_real_cigarettes(uid)
        if current < amount:
            return False, f"Не хватает сигарет. Нужно {amount}, у тебя {current}."
        add_real_cigarettes(uid, -amount)
        return True, ""
    if currency == "rubles":
        current = get_rubles(uid)
        if current < amount:
            return False, f"Не хватает рублей. Нужно {amount}₽, у тебя {current}₽."
        add_rubles(uid, -amount)
        return True, ""
    return False, "Неизвестная валюта."

def _add_payment(uid: str, currency: str, amount: int) -> None:
    if currency == "butts":
        add_cigarettes(uid, amount)
    elif currency == "cigarettes":
        add_real_cigarettes(uid, amount)
    elif currency == "rubles":
        add_rubles(uid, amount)

def get_crypto_wallet_value(uid: str) -> tuple[float, str]:
    """Current wallet value in display currency."""
    balance = get_crypto_balance(uid)
    if balance <= 0:
        return 0.0, get_crypto_display_currency()
    currency = get_crypto_display_currency()
    butts_value = balance * get_butts_per_cok()
    if currency == "butts":
        value = butts_value
    elif currency == "cigarettes":
        value = butts_value / CIGARETTE_BUTT_VALUE
    else:
        value = butts_value / RUBLE_BUTT_VALUE
    return value, currency

def format_birja_board() -> str:
    market = _get_crypto_market()
    display_curr = get_crypto_display_currency()
    buy_ratio = get_crypto_buy_ratio()
    _, curr_label = CRYPTO_CURRENCY_LABELS[display_curr]
    butts_per_cok = get_butts_per_cok()

    price_lines = []
    for key in ("butts", "cigarettes", "rubles"):
        em, lbl = CRYPTO_CURRENCY_LABELS[key]
        rate = get_cok_per_unit(key)
        marker = " ◀" if key == display_curr else ""
        unit = "₽" if key == "rubles" else f"1 {lbl}"
        price_lines.append(f"   {em} {_format_cok_rate_display(rate)} за {unit}{marker}")

    buy_pct = round(buy_ratio * 100, 1)
    sell_pct = round(100.0 - buy_pct, 1)
    rate_str = _format_cok_rate_display(get_cok_per_unit(display_curr))
    buy_vol = int(round(market["buy_volume"]))
    sell_vol = int(round(market["sell_volume"]))

    return (
        "🏛 <b>БИРЖА КРИПТО-ОКУРКОВ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📈 <b>COK</b> — Крипто-Окурок\n"
        f"   Курс: {rate_str} за 1 {curr_label if display_curr != 'rubles' else '₽'}\n"
        f"   1 COK ≈ <b>{int(math.floor(butts_per_cok))}</b> <i>({butts_per_cok:.2f})</i> окурков\n"
        f"   Валюта котировки: <b>{curr_label if display_curr != 'rubles' else 'рубли'}</b>\n\n"
        "💱 <b>Курс (COK за единицу):</b>\n"
        + "\n".join(price_lines) + "\n\n"
        f"📊 Сделок: 🟢 <b>{market['buy_count']}</b> ({buy_pct}%) | "
        f"🔴 <b>{market['sell_count']}</b> ({sell_pct}%)\n"
        f"📈 Объём (скользящий): {buy_vol} ок. / {sell_vol} ок.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Каждая сделка двигает spot-цену.\n"
        "Больше покупок — COK дорожает, больше продаж — дешевеет.\n"
        "Объём постепенно «забывается» — важны свежие сделки.\n"
        "При >80% продаж — котировка в окурках,\n"
        ">30% — в сигаретах, иначе — в рублях.</i>\n\n"
        "Нажми <b>Купить</b> или <b>Продать</b> и ответь на сообщение бота."
    )

def format_wallet_board(uid: str) -> str:
    balance = get_crypto_balance(uid)
    value, currency = get_crypto_wallet_value(uid)
    value_str = _format_currency_payment(currency, value)

    trades = get_user_crypto_trades(uid, limit=100)
    buys = sum(t["amount"] for t in trades if t["side"] == "buy")
    sells = sum(t["amount"] for t in trades if t["side"] == "sell")

    return (
        "👛 <b>КОШЕЛЁК COK</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🪙 Баланс: <b>{balance:.4f}</b> COK\n"
        f"💎 Стоимость: <b>{value_str}</b>\n\n"
        f"📈 Куплено: <b>{buys:.4f}</b> COK\n"
        f"📉 Продано: <b>{sells:.4f}</b> COK\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Нажми <b>Перевести</b> и ответь:\n"
        "<code>@username 10</code> — кому и сколько COK"
    )

def birja_keyboard() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🟢 Купить", callback_data="crypto:buy"),
        types.InlineKeyboardButton("🔴 Продать", callback_data="crypto:sell"),
    )
    return markup

def wallet_keyboard() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💸 Перевести", callback_data="crypto:transfer"))
    return markup

def generate_exchange_chart() -> Optional[bytes]:
    history = get_crypto_price_history(limit=50)
    if len(history) < 2:
        now = datetime.now()
        butts_per_cok = get_butts_per_cok()
        history = [
            {"price": butts_per_cok * 1.1, "currency": "butts", "at": now},
            {"price": butts_per_cok, "currency": get_crypto_display_currency(), "at": now},
        ]

    times = [h["at"] for h in history]
    prices = []
    for h in history:
        cok_per_butt = 1.0 / h["price"] if h["price"] > 0 else 0
        curr = h["currency"]
        if curr == "cigarettes":
            prices.append(cok_per_butt * CIGARETTE_BUTT_VALUE)
        elif curr == "rubles":
            prices.append(cok_per_butt * RUBLE_BUTT_VALUE)
        else:
            prices.append(cok_per_butt)
    curr = history[-1]["currency"]
    _, curr_label = CRYPTO_CURRENCY_LABELS[curr]
    unit = "₽" if curr == "rubles" else f"1 {curr_label}"
    ylabel = f"COK за {unit}"

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.fill_between(times, prices, alpha=0.3, color="#FF9800")
    ax.plot(times, prices, color="#FF9800", linewidth=2, marker="o", markersize=3)
    ax.set_title("Курс COK на бирже", fontsize=13, fontweight="bold")
    ax.set_xlabel("Время", fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m %H:%M"))
    fig.autofmt_xdate(rotation=45)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="PNG", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()

def generate_wallet_chart(uid: str) -> Optional[bytes]:
    trades = get_user_crypto_trades(uid, limit=50)
    if not trades:
        balance = get_crypto_balance(uid)
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.axhline(balance, color="#2196F3", linewidth=2, linestyle="--")
        ax.set_title("История сделок COK", fontsize=13, fontweight="bold")
        ax.set_xlabel("Время", fontsize=9)
        ax.set_ylabel("Баланс (COK)", fontsize=9)
        ax.text(0.5, 0.5, "Сделок пока нет", ha="center", va="center",
                transform=ax.transAxes, fontsize=12, color="#888")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="PNG", dpi=150)
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()

    times = [t["at"] for t in trades]
    cumulative = []
    total = 0.0
    for t in trades:
        total += t["amount"] if t["side"] == "buy" else -t["amount"]
        cumulative.append(total)

    fig, ax = plt.subplots(figsize=(10, 5))
    colors = ["#4CAF50" if t["side"] == "buy" else "#F44336" for t in trades]
    ax.bar(times, [t["amount"] if t["side"] == "buy" else -t["amount"] for t in trades],
           color=colors, alpha=0.6, width=0.02)
    ax2 = ax.twinx()
    ax2.plot(times, cumulative, color="#2196F3", linewidth=2, marker="o", markersize=3)
    ax.set_title("История сделок COK", fontsize=13, fontweight="bold")
    ax.set_xlabel("Время", fontsize=9)
    ax.set_ylabel("Сделка (COK)", fontsize=9)
    ax2.set_ylabel("Баланс (COK)", fontsize=9, color="#2196F3")
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m %H:%M"))
    fig.autofmt_xdate(rotation=45)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="PNG", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()

def crypto_buy(uid: str, pay_amount: float, pay_currency: str) -> tuple[bool, str]:
    if pay_amount <= 0:
        return False, "Сумма должна быть больше 0."
    if pay_currency not in CRYPTO_CURRENCY_LABELS:
        return False, "Валюта: <b>o</b> (окурки), <b>c</b> (сигареты), <b>r</b> (рубли)."

    payment = int(math.floor(pay_amount))
    if payment <= 0:
        return False, "Минимум 1 единица валюты (только целые числа)."

    crypto_amount = _crypto_from_payment(payment, pay_currency)
    if crypto_amount <= 0:
        return False, "Слишком мало — получится 0 COK."

    ok, err = _deduct_payment(uid, pay_currency, payment)
    if not ok:
        return False, err

    add_crypto_balance(uid, crypto_amount)
    record_crypto_trade("buy", _payment_to_butts(payment, pay_currency))
    record_user_crypto_trade(uid, "buy", crypto_amount, pay_currency)

    pay_str = _format_currency_payment(pay_currency, float(payment))
    new_spot = get_butts_per_cok()
    return True, (
        f"✅ Потрачено {pay_str} → получено <b>{crypto_amount:.6f}</b> COK\n"
        f"Баланс: <b>{get_crypto_balance(uid):.6f}</b> COK\n"
        f"📈 Курс: <b>{new_spot:.2f}</b> ок./COK | Покупок: <b>{get_crypto_buy_ratio() * 100:.1f}%</b>"
    )

def crypto_sell(uid: str, crypto_amount: float) -> tuple[bool, str]:
    if crypto_amount <= 0:
        return False, "Количество должно быть больше 0."

    balance = get_crypto_balance(uid)
    if balance < crypto_amount:
        return False, f"У тебя только <b>{balance:.4f}</b> COK."

    proceeds, currency, actual_proceeds = _crypto_sell_proceeds(crypto_amount)
    butts_volume = crypto_amount * get_butts_per_cok()
    add_crypto_balance(uid, -crypto_amount)
    _add_payment(uid, currency, proceeds)
    record_crypto_trade("sell", butts_volume)
    record_user_crypto_trade(uid, "sell", crypto_amount, currency)

    pay_str = _format_currency_payment(currency, actual_proceeds)
    new_spot = get_butts_per_cok()
    return True, (
        f"✅ Продано <b>{crypto_amount:.4f}</b> COK за {pay_str}\n"
        f"Баланс: <b>{get_crypto_balance(uid):.4f}</b> COK\n"
        f"📉 Курс: <b>{new_spot:.2f}</b> ок./COK | Покупок: <b>{get_crypto_buy_ratio() * 100:.1f}%</b>"
    )

def crypto_transfer(from_uid: str, to_uid: str, amount: float) -> tuple[bool, str]:
    if amount <= 0:
        return False, "Количество должно быть больше 0."
    if from_uid == to_uid:
        return False, "Нельзя переводить самому себе."

    balance = get_crypto_balance(from_uid)
    if balance < amount:
        return False, f"У тебя только <b>{balance:.4f}</b> COK."

    get_or_create_user(to_uid)
    add_crypto_balance(from_uid, -amount)
    add_crypto_balance(to_uid, amount)
    return True, f"✅ Переведено <b>{amount:.4f}</b> COK"

def parse_crypto_buy_input(text: str) -> tuple[Optional[float], Optional[str], Optional[str]]:
    """Parse '100 o' / '5 c' / '50 r' → (currency amount to spend, currency, error)."""
    parts = text.strip().lower().split()
    if len(parts) < 2:
        return None, None, "Формат: <code>100 o</code> — сколько валюты потратить (o/c/r)"
    try:
        amount = float(parts[0].replace(",", "."))
    except ValueError:
        return None, None, "Сумма должна быть числом."
    curr_map = {"o": "butts", "c": "cigarettes", "r": "rubles",
                "окурки": "butts", "окурок": "butts",
                "сигареты": "cigarettes", "сигарета": "cigarettes",
                "рубли": "rubles", "рубль": "rubles"}
    pay_curr = curr_map.get(parts[1])
    if not pay_curr:
        return None, None, "Валюта: <b>o</b> (окурки), <b>c</b> (сигареты), <b>r</b> (рубли)."
    return amount, pay_curr, None

def parse_crypto_transfer_input(text: str) -> tuple[Optional[str], Optional[float], Optional[str]]:
    """Parse '@user 10' or 'user_id 10' → (target, amount, error)."""
    parts = text.strip().split()
    if len(parts) < 2:
        return None, None, "Формат: <code>@username 10</code> или <code>id 10</code>"
    target_raw = parts[0].lstrip("@")
    try:
        amount = float(parts[1].replace(",", "."))
    except ValueError:
        return None, None, "Количество должно быть числом."

    if target_raw.isdigit():
        return target_raw, amount, None

    found = find_user_by_username(target_raw)
    if found:
        return found["id"], amount, None
    return None, None, f"Пользователь <b>@{target_raw}</b> не найден."

def send_birja_message(chat_id: int, reply_to: Optional[int] = None,
                       thread_id: Optional[int] = None) -> None:
    chart = generate_exchange_chart()
    text = format_birja_board()
    markup = birja_keyboard()
    send_kw: dict = {}
    if reply_to:
        send_kw["reply_to_message_id"] = reply_to
    if thread_id:
        send_kw["message_thread_id"] = thread_id
    if chart:
        bot.send_photo(chat_id, chart, caption=text, reply_markup=markup,
                       parse_mode="HTML", **send_kw)
    else:
        bot.send_message(chat_id, text, reply_markup=markup,
                         parse_mode="HTML", **send_kw)

def send_wallet_message(chat_id: int, uid: str, reply_to: Optional[int] = None,
                        thread_id: Optional[int] = None) -> None:
    chart = generate_wallet_chart(uid)
    text = format_wallet_board(uid)
    markup = wallet_keyboard()
    send_kw: dict = {}
    if reply_to:
        send_kw["reply_to_message_id"] = reply_to
    if thread_id:
        send_kw["message_thread_id"] = thread_id
    if chart:
        bot.send_photo(chat_id, chart, caption=text, reply_markup=markup,
                       parse_mode="HTML", **send_kw)
    else:
        bot.send_message(chat_id, text, reply_markup=markup,
                         parse_mode="HTML", **send_kw)

# ═══════════════════════════════════════════════════════════════════════════════
# Central Bank Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _currency_to_butts(currency: str, amount: int) -> float:
    if currency == "real_cigarettes":
        return amount * CIGARETTE_BUTT_VALUE
    if currency == "rubles":
        return amount * RUBLE_BUTT_VALUE
    return float(amount)

def get_central_bank() -> dict:
    result = db_execute(
        "SELECT butts, real_cigarettes, rubles FROM central_bank WHERE id = 1",
        fetch=True, fetch_one=True
    )
    if result:
        return {
            "butts": int(result[0] or 0),
            "real_cigarettes": int(result[1] or 0),
            "rubles": int(result[2] or 0),
        }
    return {"butts": BANK_INITIAL_BUTTS, "real_cigarettes": BANK_INITIAL_CIGARETTES,
            "rubles": BANK_INITIAL_RUBLES}

def get_bank_total_butts_equiv() -> float:
    cb = get_central_bank()
    return (
        cb["butts"]
        + cb["real_cigarettes"] * CIGARETTE_BUTT_VALUE
        + cb["rubles"] * RUBLE_BUTT_VALUE
    )

def _bank_reserve_ratio() -> float:
    total = get_bank_total_butts_equiv()
    if BANK_TARGET_RESERVE <= 0:
        return 1.0
    return max(0.0, min(1.0, total / BANK_TARGET_RESERVE))

def get_bank_commission_pct() -> float:
    """Transfer fee: high when bank is poor, low when bank is rich (min 1%)."""
    ratio = _bank_reserve_ratio()
    pct = BANK_MAX_COMMISSION - (BANK_MAX_COMMISSION - BANK_MIN_COMMISSION) * ratio
    return max(BANK_MIN_COMMISSION, round(pct, 1))

def get_bank_credit_rate_pct() -> float:
    """Loan interest for 3 days: lower when bank is rich."""
    ratio = _bank_reserve_ratio()
    rate = BANK_MAX_CREDIT_RATE - (BANK_MAX_CREDIT_RATE - BANK_MIN_CREDIT_RATE) * ratio
    return round(rate, 1)

def get_bank_deposit_yield_pct() -> float:
    """Deposit yield for 3 days: higher when bank is poor."""
    ratio = _bank_reserve_ratio()
    yield_pct = BANK_MIN_DEPOSIT_YIELD + (BANK_MAX_DEPOSIT_YIELD - BANK_MIN_DEPOSIT_YIELD) * (1.0 - ratio)
    return round(yield_pct, 1)

def bank_add_currency(currency: str, amount: int) -> None:
    if amount <= 0 or currency not in BANK_CURRENCY_KEYS:
        return
    db_execute(
        f"UPDATE central_bank SET {currency} = {currency} + %s, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
        (amount,)
    )

def bank_take_currency(currency: str, amount: int) -> bool:
    if amount <= 0 or currency not in BANK_CURRENCY_KEYS:
        return False
    cb = get_central_bank()
    if cb.get(currency, 0) < amount:
        return False
    db_execute(
        f"UPDATE central_bank SET {currency} = {currency} - %s, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
        (amount,)
    )
    return True

def _get_user_currency_balance(uid: str, currency: str) -> int:
    if currency == "butts":
        return get_cigarettes(uid)
    if currency == "real_cigarettes":
        return get_real_cigarettes(uid)
    return get_rubles(uid)

def _set_user_currency_balance(uid: str, currency: str, value: int) -> None:
    if currency == "butts":
        update_user(uid, cigarettes=value)
    elif currency == "real_cigarettes":
        update_user(uid, real_cigarettes=value)
    else:
        update_user(uid, rubles=value)

def bank_credit_user(uid: str, currency: str, amount: int) -> None:
    """Credit user directly (loan payout) — bypasses debt redirect."""
    current = _get_user_currency_balance(uid, currency)
    _set_user_currency_balance(uid, currency, current + amount)

def bank_force_debit(uid: str, currency: str, amount: int) -> int:
    """Debit user allowing negative balance; returns amount sent to bank."""
    current = _get_user_currency_balance(uid, currency)
    collected = max(0, min(current, amount))
    _set_user_currency_balance(uid, currency, current - amount)
    if collected > 0:
        bank_add_currency(currency, collected)
    return collected

def transfer_with_bank_commission(from_uid: str, to_uid: str, currency: str,
                                  amount: int) -> tuple[bool, str, int, int]:
    """P2P transfer with central bank commission. Returns ok, error, received, fee."""
    if amount <= 0:
        return False, "Сумма должна быть больше 0.", 0, 0
    commission_pct = get_bank_commission_pct()
    fee = max(1, int(math.ceil(amount * commission_pct / 100.0)))
    if fee >= amount:
        return False, "Слишком маленькая сумма для перевода.", 0, 0
    received = amount - fee
    balance = _get_user_currency_balance(from_uid, currency)
    if balance < amount:
        _, label, _ = BANK_CURRENCY_LABELS[currency]
        unit = "₽" if currency == "rubles" else label
        return False, f"Не хватает средств. Нужно {amount} {unit}, у тебя {balance}.", 0, 0
    _set_user_currency_balance(from_uid, currency, balance - amount)
    if currency == "butts":
        add_cigarettes(to_uid, received)
    elif currency == "real_cigarettes":
        add_real_cigarettes(to_uid, received)
    else:
        add_rubles(to_uid, received)
    bank_add_currency(currency, fee)
    return True, "", received, fee

def get_user_active_loans(uid: str) -> list:
    results = db_execute(
        "SELECT id, currency, principal, interest_rate, total_due, issued_at, due_at "
        "FROM bank_loans WHERE user_id = %s AND collected = false ORDER BY due_at ASC",
        (str(uid),), fetch=True
    )
    if not results:
        return []
    return [
        {"id": r[0], "currency": r[1], "principal": r[2], "interest_rate": float(r[3]),
         "total_due": r[4], "issued_at": r[5], "due_at": r[6]}
        for r in results
    ]

def get_user_total_debt(uid: str) -> dict:
    """Get total debt per currency for a user."""
    results = db_execute(
        "SELECT currency, SUM(total_due) FROM bank_loans "
        "WHERE user_id = %s AND collected = false GROUP BY currency",
        (str(uid),), fetch=True
    )
    debt = {"butts": 0, "real_cigarettes": 0, "rubles": 0}
    if results:
        for r in results:
            debt[r[0]] = r[1]
    return debt

def has_active_loans(uid: str) -> bool:
    """Check if user has any active loans."""
    results = db_execute(
        "SELECT 1 FROM bank_loans WHERE user_id = %s AND collected = false LIMIT 1",
        (str(uid),), fetch=True, fetch_one=True
    )
    return results is not None

def get_user_active_deposits(uid: str) -> list:
    results = db_execute(
        "SELECT id, currency, amount, yield_rate, deposited_at "
        "FROM bank_deposits WHERE user_id = %s AND withdrawn = false ORDER BY deposited_at ASC",
        (str(uid),), fetch=True
    )
    if not results:
        return []
    return [
        {"id": r[0], "currency": r[1], "amount": r[2], "yield_rate": float(r[3]),
         "deposited_at": r[4]}
        for r in results
    ]

def get_due_loans() -> list:
    now = time.time()
    results = db_execute(
        "SELECT id, user_id, currency, total_due FROM bank_loans "
        "WHERE collected = false AND due_at <= %s",
        (now,), fetch=True
    )
    if not results:
        return []
    return [{"id": r[0], "user_id": r[1], "currency": r[2], "total_due": r[3]} for r in results]

def collect_bank_loan(loan_id: int, user_id: str, currency: str, total_due: int) -> None:
    bank_force_debit(user_id, currency, total_due)
    db_execute("UPDATE bank_loans SET collected = true WHERE id = %s", (loan_id,))

def repay_bank_loan(uid: str, loan_id: int) -> tuple[bool, str]:
    """Repay a specific loan early."""
    results = db_execute(
        "SELECT id, currency, total_due FROM bank_loans "
        "WHERE id = %s AND user_id = %s AND collected = false",
        (loan_id, str(uid)), fetch=True, fetch_one=True
    )
    if not results:
        return False, "❌ Кредит не найден или уже погашен."
    
    loan_currency = results[1]
    amount_due = results[2]
    
    # Check if user has enough balance
    balance = _get_user_currency_balance(uid, loan_currency)
    if balance < amount_due:
        _, label, _ = BANK_CURRENCY_LABELS[loan_currency]
        unit = "₽" if loan_currency == "rubles" else label
        return False, f"❌ Недостаточно средств.\nНужно: <b>{amount_due} {unit}</b>\nУ тебя: <b>{balance} {unit}</b>"
    
    # Deduct from user and mark as collected
    _set_user_currency_balance(uid, loan_currency, balance - amount_due)
    bank_add_currency(loan_currency, amount_due)
    db_execute("UPDATE bank_loans SET collected = true WHERE id = %s", (loan_id,))
    
    _, label, _ = BANK_CURRENCY_LABELS[loan_currency]
    unit = "₽" if loan_currency == "rubles" else label
    return True, f"✅ Кредит #{loan_id} погашен!\nСписано: <b>{amount_due} {unit}</b>"

def issue_bank_loan(uid: str, currency: str, amount: int) -> tuple[bool, str]:
    if amount <= 0:
        return False, "Сумма должна быть больше 0."
    if currency not in BANK_CURRENCY_KEYS:
        return False, "Валюта: <b>o</b>, <b>c</b> или <b>r</b>."
    
    # Check if user has active loans
    if has_active_loans(uid):
        return False, "❌ У тебя есть активные кредиты. Погаси их прежде чем брать новые.\nИспользуй /pay для досрочного погашения."
    
    # Check credit limits: 200 окурков, 2 сигареты, 1 рубль
    max_limits = {"butts": 200, "real_cigarettes": 2, "rubles": 1}
    if amount > max_limits.get(currency, 0):
        _, label, _ = BANK_CURRENCY_LABELS[currency]
        max_label = f"{max_limits[currency]} {label}" if currency != "rubles" else f"{max_limits[currency]}₽"
        return False, f"❌ Лимит кредита: <b>{max_label}</b>.\nЗапрос: {amount}."
    
    if not bank_take_currency(currency, amount):
        _, label, _ = BANK_CURRENCY_LABELS[currency]
        return False, f"В банке недостаточно {label} для кредита."
    rate = get_bank_credit_rate_pct()
    total_due = int(math.ceil(amount * (1.0 + rate / 100.0)))
    now = time.time()
    db_execute(
        "INSERT INTO bank_loans (user_id, currency, principal, interest_rate, total_due, "
        "issued_at, due_at, collected) VALUES (%s, %s, %s, %s, %s, %s, %s, false)",
        (str(uid), currency, amount, rate, total_due, now, now + BANK_LOAN_TERM_SECONDS)
    )
    _, label, _ = BANK_CURRENCY_LABELS[currency]
    if currency == "butts":
        add_cigarettes(uid, amount)
    elif currency == "real_cigarettes":
        add_real_cigarettes(uid, amount)
    else:
        add_rubles(uid, amount)
    unit = f"{amount}₽" if currency == "rubles" else f"{amount} {label}"
    due_date = datetime.fromtimestamp(now + BANK_LOAN_TERM_SECONDS).strftime("%d.%m.%Y %H:%M")
    return True, (
        f"✅ Кредит выдан: <b>{unit}</b>\n"
        f"Ставка: <b>{rate}%</b> на 3 дня\n"
        f"К возврату: <b>{total_due}</b> "
        f"{'₽' if currency == 'rubles' else label}\n"
        f"Срок: <b>{due_date}</b>\n"
        f"<i>Если не хватит денег — счёт уйдёт в минус, пополнения погасят долг банку.</i>"
    )

def create_bank_deposit(uid: str, currency: str, amount: int) -> tuple[bool, str]:
    if amount <= 0:
        return False, "Сумма должна быть больше 0."
    if currency not in BANK_CURRENCY_KEYS:
        return False, "Валюта: <b>o</b>, <b>c</b> или <b>r</b>."
    balance = _get_user_currency_balance(uid, currency)
    if balance < amount:
        return False, "Недостаточно средств для вклада."
    yield_rate = get_bank_deposit_yield_pct()
    _set_user_currency_balance(uid, currency, balance - amount)
    bank_add_currency(currency, amount)
    now = time.time()
    db_execute(
        "INSERT INTO bank_deposits (user_id, currency, amount, yield_rate, deposited_at, withdrawn) "
        "VALUES (%s, %s, %s, %s, %s, false)",
        (str(uid), currency, amount, yield_rate, now)
    )
    _, label, _ = BANK_CURRENCY_LABELS[currency]
    unlock = datetime.fromtimestamp(now + BANK_DEPOSIT_TERM_SECONDS).strftime("%d.%m.%Y %H:%M")
    return True, (
        f"✅ Вклад открыт: <b>{amount}</b> "
        f"{'₽' if currency == 'rubles' else label}\n"
        f"Доходность: <b>{yield_rate}%</b> за 3 дня\n"
        f"Вывод доступен с: <b>{unlock}</b>"
    )

def withdraw_bank_deposits(uid: str) -> tuple[bool, str]:
    deposits = get_user_active_deposits(uid)
    if not deposits:
        return False, "У тебя нет активных вкладов."
    now = time.time()
    matured = [d for d in deposits if now >= d["deposited_at"] + BANK_DEPOSIT_TERM_SECONDS]
    if not matured:
        next_unlock = min(d["deposited_at"] + BANK_DEPOSIT_TERM_SECONDS for d in deposits)
        when = datetime.fromtimestamp(next_unlock).strftime("%d.%m.%Y %H:%M")
        return False, f"Вклад ещё не созрел. Ближайший вывод: <b>{when}</b>"

    lines = []
    for dep in matured:
        payout = int(math.floor(dep["amount"] * (1.0 + dep["yield_rate"] / 100.0)))
        bonus = payout - dep["amount"]
        if not bank_take_currency(dep["currency"], payout):
            _, label, _ = BANK_CURRENCY_LABELS[dep["currency"]]
            lines.append(f"⚠️ Не хватило резервов банка для вклада #{dep['id']} ({label})")
            continue
        if dep["currency"] == "butts":
            add_cigarettes(uid, payout)
        elif dep["currency"] == "real_cigarettes":
            add_real_cigarettes(uid, payout)
        else:
            add_rubles(uid, payout)
        db_execute("UPDATE bank_deposits SET withdrawn = true WHERE id = %s", (dep["id"],))
        _, label, _ = BANK_CURRENCY_LABELS[dep["currency"]]
        unit = "₽" if dep["currency"] == "rubles" else label
        lines.append(
            f"💰 #{dep['id']}: <b>{dep['amount']}</b> → <b>{payout}</b> {unit} "
            f"(+{bonus}, {dep['yield_rate']}%)"
        )
    if not lines:
        return False, "Банк временно не может выплатить вклады — мало резервов."
    return True, "✅ <b>Вывод вкладов</b>\n\n" + "\n".join(lines)

def parse_bank_amount_input(text: str) -> tuple[Optional[int], Optional[str], Optional[str]]:
    """Parse '100 o' / '5 c' / '10 r'."""
    parts = text.strip().lower().split()
    if len(parts) < 2:
        return None, None, "Формат: <code>100 o</code> (окурки), <code>5 c</code> (сигареты), <code>10 r</code> (₽)"
    try:
        amount = int(float(parts[0].replace(",", ".")))
    except ValueError:
        return None, None, "Сумма должна быть целым числом."
    curr_map = {
        "o": "butts", "окурки": "butts", "окурок": "butts",
        "c": "real_cigarettes", "сигареты": "real_cigarettes", "сигарета": "real_cigarettes",
        "r": "rubles", "рубли": "rubles", "рубль": "rubles", "₽": "rubles",
    }
    currency = curr_map.get(parts[1])
    if not currency:
        return None, None, "Валюта: <b>o</b>, <b>c</b> или <b>r</b>."
    if amount <= 0:
        return None, None, "Сумма должна быть больше 0."
    return amount, currency, None

def parse_bank_convert_amount(text: str) -> tuple[Optional[int], Optional[str]]:
    """Parse integer amount for currency conversion."""
    raw = text.strip().replace(",", ".")
    try:
        amount = int(float(raw))
    except ValueError:
        return None, "Укажи целое число."
    if amount <= 0:
        return None, "Сумма должна быть больше 0."
    return amount, None

def convert_butts_to_cigarettes(uid: str, butts_amount: int) -> tuple[bool, str]:
    """Exchange butts for cigarettes at central bank rate (100 o = 1 c)."""
    if butts_amount < BANK_CONV_BUTTS_PER_CIG:
        return False, f"Минимум <b>{BANK_CONV_BUTTS_PER_CIG}</b> окурков для обмена."
    balance = get_cigarettes(uid)
    if balance < butts_amount:
        return False, f"Не хватает окурков. Нужно {butts_amount}, у тебя {balance}."
    convertible = butts_amount // BANK_CONV_BUTTS_PER_CIG
    spent = convertible * BANK_CONV_BUTTS_PER_CIG
    add_cigarettes(uid, -spent)
    add_real_cigarettes(uid, convertible)
    return True, (
        f"✅ Обмен: <b>{spent}</b> окурков → <b>{convertible}</b> сигарет\n"
        f"Курс: <b>{BANK_CONV_BUTTS_PER_CIG}</b> о = 1 сиг.\n"
        f"Баланс: <b>{get_cigarettes(uid)}</b> о | <b>{get_real_cigarettes(uid)}</b> с"
    )

def convert_cigarettes_to_rubles(uid: str, cig_amount: int) -> tuple[bool, str]:
    """Exchange cigarettes for rubles at central bank rate (5 c = 1₽)."""
    if cig_amount < BANK_CONV_CIG_PER_RUBLE:
        return False, f"Минимум <b>{BANK_CONV_CIG_PER_RUBLE}</b> сигарет для обмена."
    balance = get_real_cigarettes(uid)
    if balance < cig_amount:
        return False, f"Не хватает сигарет. Нужно {cig_amount}, у тебя {balance}."
    convertible = cig_amount // BANK_CONV_CIG_PER_RUBLE
    spent = convertible * BANK_CONV_CIG_PER_RUBLE
    add_real_cigarettes(uid, -spent)
    add_rubles(uid, convertible)
    return True, (
        f"✅ Обмен: <b>{spent}</b> сигарет → <b>{convertible}</b>₽\n"
        f"Курс: <b>{BANK_CONV_CIG_PER_RUBLE}</b> сиг. = 1₽\n"
        f"Баланс: <b>{get_real_cigarettes(uid)}</b> с | <b>{get_rubles(uid)}</b>₽"
    )

def format_bank_board(uid: str) -> str:
    cb = get_central_bank()
    commission = get_bank_commission_pct()
    credit_rate = get_bank_credit_rate_pct()
    deposit_yield = get_bank_deposit_yield_pct()
    reserve_total = int(get_bank_total_butts_equiv())

    return (
        "🏦 <b>ЦЕНТРОБАНК</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "💱 <b>Курс валют (базовый):</b>\n"
        f"   🚬 1 сигарета = <b>{int(CIGARETTE_BUTT_VALUE)}</b> окурков\n"
        f"   💰 1₽ = <b>{int(RUBLE_BUTT_VALUE)}</b> окурков "
        f"(<b>{BANK_CONV_CIG_PER_RUBLE}</b> сиг.)\n"
        f"   🔄 Обмен в ЦБ: <b>{BANK_CONV_BUTTS_PER_CIG}</b> о → 1 сиг. | "
        f"<b>{BANK_CONV_CIG_PER_RUBLE}</b> сиг. → 1₽\n\n"
        "🏛 <b>Резервы ЦБ:</b>\n"
        f"   🚬 Окурки: <b>{cb['butts']:,}</b>\n"
        f"   🚬 Сигареты: <b>{cb['real_cigarettes']:,}</b>\n"
        f"   💰 Рубли: <b>{cb['rubles']:,}</b>\n"
        f"   📊 Эквивалент: <b>{reserve_total:,}</b> ок.\n\n"
        f"💸 Комиссия переводов: <b>{commission}%</b>\n"
        f"💳 Ставка кредита (3 дн.): <b>{credit_rate}%</b>\n"
        f"📈 Доходность вклада (3 дн.): <b>{deposit_yield}%</b>\n"
        "<i>Мало денег в банке → выше комиссия и кредит, выше доход вклада.\n"
        "Много денег → ниже комиссия и кредит, ниже доход вклада.</i>"
    )


def format_loans_board(uid: str) -> str:
    loans = get_user_active_loans(uid)
    
    if not loans:
        return "✅ <b>У тебя нет активных кредитов</b>\n\n" \
               "Используй /bank для просмотра основной информации."
    
    lines = "📋 <b>Твои активные кредиты:</b>\n\n"
    for ln in loans:
        _, label, _ = BANK_CURRENCY_LABELS[ln["currency"]]
        due = datetime.fromtimestamp(ln["due_at"]).strftime("%d.%m.%Y %H:%M")
        unit = "₽" if ln["currency"] == "rubles" else label
        lines += f"• #{ln['id']}: вернуть <b>{ln['total_due']}</b> {unit} до {due}\n"
    
    lines += "\n<i>Для досрочного погашения используй /pay &lt;номер_кредита&gt;</i>"
    return lines


def format_deposits_board(uid: str) -> str:
    deposits = get_user_active_deposits(uid)
    now = time.time()
    
    if not deposits:
        return "✅ <b>У тебя нет активных вкладов</b>\n\n" \
               "Используй /bank для просмотра основной информации."
    
    lines = "🏦 <b>Твои активные вклады:</b>\n\n"
    for dep in deposits:
        _, label, _ = BANK_CURRENCY_LABELS[dep["currency"]]
        unit = "₽" if dep["currency"] == "rubles" else label
        unlock = dep["deposited_at"] + BANK_DEPOSIT_TERM_SECONDS
        status = "✅ можно вывести" if now >= unlock else f"⏳ до {datetime.fromtimestamp(unlock).strftime('%d.%m.%H:%M')}"
        lines += (
            f"• #{dep['id']}: <b>{dep['amount']}</b> {unit} "
            f"({dep['yield_rate']}%) — {status}\n"
        )
    
    lines += "\n<i>Для вывода используй кнопку 'Вывести вклад' в /bank</i>"
    return lines

def generate_bank_chart() -> Optional[bytes]:
    cb = get_central_bank()
    commission = get_bank_commission_pct()
    credit_rate = get_bank_credit_rate_pct()
    deposit_yield = get_bank_deposit_yield_pct()

    fig, axes = plt.subplots(1, 2, figsize=(10, 5))

    labels = ["Окурки", "Сигареты", "Рубли"]
    reserves = [cb["butts"], cb["real_cigarettes"], cb["rubles"]]
    colors = ["#8D6E63", "#FF9800", "#4CAF50"]
    axes[0].bar(labels, reserves, color=colors, alpha=0.85)
    axes[0].set_title("Резервы Центробанка", fontsize=12, fontweight="bold")
    axes[0].set_ylabel("Количество", fontsize=9)
    axes[0].grid(True, axis="y", alpha=0.3)

    worth_labels = ["1 окурок", "1 сигарета", "1₽"]
    worth_butts = [1, CIGARETTE_BUTT_VALUE, RUBLE_BUTT_VALUE]
    axes[1].bar(worth_labels, worth_butts, color=["#795548", "#FFB74D", "#66BB6A"], alpha=0.85)
    axes[1].set_title("Стоимость валют (в окурках)", fontsize=12, fontweight="bold")
    axes[1].set_ylabel("Окурков", fontsize=9)
    axes[1].grid(True, axis="y", alpha=0.3)

    fig.suptitle(
        f"Комиссия {commission}% | Кредит {credit_rate}% | Вклад {deposit_yield}%",
        fontsize=11, fontweight="bold"
    )
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="PNG", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()

def bank_keyboard() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💳 Кредит", callback_data="bank:loan"),
        types.InlineKeyboardButton("🏦 Вклад", callback_data="bank:deposit"),
    )
    markup.add(
        types.InlineKeyboardButton("📋 Мои кредиты", callback_data="bank:my_loans"),
        types.InlineKeyboardButton("🏦 Мои вклады", callback_data="bank:my_deposits"),
    )
    markup.add(
        types.InlineKeyboardButton("💰 Вывести вклад", callback_data="bank:withdraw"),
        types.InlineKeyboardButton("🔄 Обновить", callback_data="bank:refresh"),
    )
    markup.add(
        types.InlineKeyboardButton(
            f"🔄 {BANK_CONV_BUTTS_PER_CIG}о→1с", callback_data="bank:conv_o"),
        types.InlineKeyboardButton(
            f"🔄 {BANK_CONV_CIG_PER_RUBLE}с→1₽", callback_data="bank:conv_c"),
    )
    return markup

def send_bank_message(chat_id: int, uid: str, reply_to: Optional[int] = None,
                      thread_id: Optional[int] = None,
                      message_id: Optional[int] = None) -> None:
    chart = generate_bank_chart()
    text = format_bank_board(uid)
    markup = bank_keyboard()
    send_kw: dict = {}
    if reply_to:
        send_kw["reply_to_message_id"] = reply_to
    if thread_id:
        send_kw["message_thread_id"] = thread_id
    if message_id:
        try:
            if chart:
                media = types.InputMediaPhoto(chart, caption=text, parse_mode="HTML")
                bot.edit_message_media(media, chat_id, message_id, reply_markup=markup)
            else:
                bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="HTML")
            return
        except Exception:
            pass
    if chart:
        bot.send_photo(chat_id, chart, caption=text, reply_markup=markup,
                       parse_mode="HTML", **send_kw)
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML", **send_kw)

# ═══════════════════════════════════════════════════════════════════════════════
# Punishment Helpers (for admin commands and /enemy_list)
# ═══════════════════════════════════════════════════════════════════════════════

def add_punishment(chat_id: int, target_id: str, target_name: str,
                   admin_id: str, admin_name: str,
                   punishment_type: str, reason: str, duration: str) -> int:
    """Record a punishment and return its id."""
    result = db_execute(
        "INSERT INTO punishments (chat_id, target_id, target_name, admin_id, admin_name, punishment_type, reason, duration) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (chat_id, str(target_id), target_name, str(admin_id), admin_name, punishment_type, reason, duration),
        fetch=True, fetch_one=True
    )
    return result[0] if result else 0

def get_recent_punishments(chat_id: int, limit: int = 6) -> list:
    """Get recent punishments in a chat."""
    results = db_execute(
        "SELECT target_name, admin_name, punishment_type, reason, duration, created_at "
        "FROM punishments WHERE chat_id = %s ORDER BY created_at DESC LIMIT %s",
        (chat_id, limit),
        fetch=True
    )
    if results:
        return [
            {"target_name": r[0], "admin_name": r[1], "type": r[2],
             "reason": r[3], "duration": r[4], "created_at": r[5]}
            for r in results
        ]
    return []

# ═══════════════════════════════════════════════════════════════════════════════
# Whisper Helpers (for /shhh)
# ═══════════════════════════════════════════════════════════════════════════════

def create_whisper(from_id: str, from_name: str, to_id: str, to_name: str, secret_text: str) -> int:
    """Create a whisper record and return its id."""
    result = db_execute(
        "INSERT INTO whispers (from_id, from_name, to_id, to_name, secret_text) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (str(from_id), from_name, str(to_id), to_name, secret_text),
        fetch=True, fetch_one=True
    )
    return result[0] if result else 0

def get_whisper(whisper_id: int) -> Optional[dict]:
    """Get a whisper by id."""
    result = db_execute(
        "SELECT from_id, from_name, to_id, to_name, secret_text FROM whispers WHERE id = %s",
        (whisper_id,),
        fetch=True, fetch_one=True
    )
    if result:
        return {"from_id": result[0], "from_name": result[1], "to_id": result[2],
                "to_name": result[3], "secret_text": result[4]}
    return None

# ═══════════════════════════════════════════════════════════════════════════════
# User Lookup Helper
# ═══════════════════════════════════════════════════════════════════════════════

def find_user_by_username(username: str) -> Optional[dict]:
    """Find a user by username (without @)."""
    if not username:
        return None
    clean = username.lstrip("@").lower().strip()
    if not clean:  # Если после очистки осталась пустая строка — отменяем поиск
        return None
        
    result = db_execute(
        "SELECT id, username FROM users WHERE LOWER(username) = %s LIMIT 1",
        (clean,),
        fetch=True, fetch_one=True
    )
    if result:
        return {"id": result[0], "username": result[1] or ""}
    return None

# ═══════════════════════════════════════════════════════════════════════════════
# Clan Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def create_clan(leader_id: str, name: str) -> Optional[int]:
    """Create a new clan. Returns clan_id or None on failure."""
    try:
        result = db_execute(
            "INSERT INTO clans (name, leader_id, reputation) VALUES (%s, %s, %s) RETURNING id",
            (name, str(leader_id), 0),
            fetch=True,
            fetch_one=True
        )
        clan_id = result[0] if result else None
        if clan_id:
            update_user(str(leader_id), clan_id=clan_id)
        return clan_id
    except Exception as e:
        log_err("CLAN", f"Error creating clan: {e}")
        return None

def delete_clan(clan_id: int) -> bool:
    """Delete a clan and remove all members' clan_id."""
    try:
        db_execute("UPDATE users SET clan_id = NULL WHERE clan_id = %s", (clan_id,))
        db_execute("DELETE FROM clans WHERE id = %s", (clan_id,))
        return True
    except Exception as e:
        log_err("CLAN", f"Error deleting clan: {e}")
        return False

def get_clan(clan_id: int) -> Optional[dict]:
    result = db_execute(
        "SELECT id, name, leader_id, reputation FROM clans WHERE id = %s",
        (clan_id,),
        fetch=True,
        fetch_one=True
    )
    if result:
        return {"id": result[0], "name": result[1], "leader_id": result[2], "reputation": result[3]}
    return None

def get_clan_by_name(name: str) -> Optional[dict]:
    result = db_execute(
        "SELECT id, name, leader_id, reputation FROM clans WHERE name = %s",
        (name,),
        fetch=True,
        fetch_one=True
    )
    if result:
        return {"id": result[0], "name": result[1], "leader_id": result[2], "reputation": result[3]}
    return None

def get_clan_members(clan_id: int) -> list:
    results = db_execute(
        "SELECT id, username FROM users WHERE clan_id = %s ORDER BY username ASC",
        (clan_id,),
        fetch=True
    )
    return [(r[0], r[1] or "") for r in results] if results else []

def add_clan_reputation(clan_id: int, amount: int) -> int:
    clan = get_clan(clan_id)
    if not clan:
        return 0
    new_rep = clan["reputation"] + amount
    db_execute("UPDATE clans SET reputation = %s WHERE id = %s", (new_rep, clan_id))
    return new_rep

def get_user_clan(uid: str) -> Optional[dict]:
    user = get_or_create_user(uid)
    clan_id = user.get("clan_id")
    if clan_id is None:
        return None
    return get_clan(clan_id)

def join_clan(uid: str, clan_id: int) -> bool:
    try:
        update_user(uid, clan_id=clan_id)
        return True
    except Exception as e:
        log_err("CLAN", f"Error joining clan: {e}")
        return False

def leave_clan(uid: str) -> None:
    update_user(uid, clan_id=None)

def get_all_clans() -> list:
    results = db_execute(
        "SELECT id, name, reputation FROM clans ORDER BY reputation DESC",
        fetch=True
    )
    return [(r[0], r[1], r[2]) for r in results] if results else []

# ═══════════════════════════════════════════════════════════════════════════════
# Promo Code Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def create_promo_code(code: str, reward_type: str, reward_amount: int, max_uses: int, created_by: str) -> bool:
    try:
        db_execute(
            "INSERT INTO promo_codes (code, reward_type, reward_amount, max_uses, uses, created_by) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (code, reward_type, reward_amount, max_uses, 0, str(created_by))
        )
        return True
    except Exception as e:
        log_err("PROMO", f"Error creating promo code: {e}")
        return False

def get_promo_code(code: str) -> Optional[dict]:
    result = db_execute(
        "SELECT id, code, reward_type, reward_amount, max_uses, uses FROM promo_codes WHERE code = %s",
        (code,),
        fetch=True,
        fetch_one=True
    )
    if result:
        return {"id": result[0], "code": result[1], "reward_type": result[2],
                "reward_amount": result[3], "max_uses": result[4], "uses": result[5]}
    return None

def has_user_used_promo(promo_id: int, uid: str) -> bool:
    result = db_execute(
        "SELECT 1 FROM promo_activations WHERE promo_id = %s AND user_id = %s",
        (promo_id, str(uid)),
        fetch=True,
        fetch_one=True
    )
    return result is not None

def activate_promo_code(code: str, uid: str) -> Optional[str]:
    """Activate a promo code. Returns reward_type on success, None on failure, 'used' if already used, 'max' if maxed."""
    promo = get_promo_code(code)
    if not promo:
        return None

    if has_user_used_promo(promo["id"], uid):
        return "used"

    if promo["uses"] >= promo["max_uses"]:
        return "max"

    reward_type = promo["reward_type"]
    reward_amount = promo["reward_amount"]

    if reward_type == "rubles":
        add_rubles(uid, reward_amount)
    elif reward_type == "cigarettes":
        add_cigarettes(uid, reward_amount)
    elif reward_type == "real_cigarettes":
        add_real_cigarettes(uid, reward_amount)
    else:
        return None

    db_execute("UPDATE promo_codes SET uses = uses + 1 WHERE id = %s", (promo["id"],))
    db_execute(
        "INSERT INTO promo_activations (promo_id, user_id) VALUES (%s, %s)",
        (promo["id"], str(uid))
    )
    return reward_type

# ═══════════════════════════════════════════════════════════════════════════════
# Chat History Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def get_history(uid: str) -> list:
    """Get user's in-memory AI chat history."""
    return list(ai_chat_history.get(str(uid), []))

def append_history(uid: str, role: str, content: str) -> list:
    """Add message to in-memory history and return last N messages."""
    uid = str(uid)
    history = ai_chat_history.setdefault(uid, [])
    history.append({"role": role, "content": content})
    if len(history) > AI_HISTORY_LIMIT:
        ai_chat_history[uid] = history[-AI_HISTORY_LIMIT:]
    return list(ai_chat_history[uid])

def clear_history(uid: str) -> None:
    """Clear user's in-memory AI chat history."""
    ai_chat_history.pop(str(uid), None)

def get_leaderboard() -> list:
    """Get top 10 users by cigarettes."""
    results = db_execute(
        "SELECT id, cigarettes, username FROM users WHERE cigarettes > 0 ORDER BY cigarettes DESC LIMIT 10",
        fetch=True
    )
    return [(r[0], r[1], r[2] or "") for r in results] if results else []

def get_all_roles(uid: str) -> dict:
    """Get all available roles (system + custom)."""
    roles = get_system_roles().copy()
    results = db_execute("SELECT id, owner_id, name, prompt, description FROM custom_roles", fetch=True)

    if results:
        for r in results:
            roles[r[0]] = {
                "name": r[2],
                "prompt": r[3],
                "description": r[4],
                "owner": r[1]
            }
    return roles

def add_custom_role(uid: str, role_key: str, name: str, prompt: str, description: str) -> bool:
    role_id = f"custom_{uid}_{role_key}"
    try:
        db_execute(
            "INSERT INTO custom_roles (id, owner_id, name, prompt, description) VALUES (%s, %s, %s, %s, %s)",
            (role_id, str(uid), name, prompt, description)
        )
        return True
    except Exception as e:
        log_err("DB", f"Error adding custom role: {e}")
        return False

def delete_custom_role(role_id: str, uid: str) -> bool:
    db_execute(
        "DELETE FROM custom_roles WHERE id = %s AND owner_id = %s",
        (role_id, str(uid))
    )
    return True

def register_chat(chat_id: int) -> None:
    try:
        db_execute("INSERT INTO chats (id) VALUES (%s) ON CONFLICT DO NOTHING", (chat_id,))
    except:
        pass

def get_all_chats() -> list[int]:
    results = db_execute("SELECT id FROM chats", fetch=True)
    return [r[0] for r in results] if results else []

def add_quote(chat_id: int, text: str, author: str, photo_file_id: str = None) -> int:
    results = db_execute("SELECT COUNT(*) FROM quotes WHERE chat_id = %s", (chat_id,), fetch=True)
    count = results[0][0] if results else 0

    db_execute(
        "INSERT INTO quotes (chat_id, text, author, photo_file_id) VALUES (%s, %s, %s, %s)",
        (chat_id, text, author, photo_file_id)
    )
    return count + 1

def get_random_quote(chat_id: int) -> Optional[dict]:
    results = db_execute(
        "SELECT text, author, photo_file_id FROM quotes WHERE chat_id = %s ORDER BY RANDOM() LIMIT 1",
        (chat_id,),
        fetch=True
    )
    if results:
        return {"text": results[0][0], "author": results[0][1], "photo_file_id": results[0][2]}
    return None

def get_quotes_list(chat_id: int, limit: int = 20) -> list:
    results = db_execute(
        "SELECT id, text, author FROM quotes WHERE chat_id = %s ORDER BY id DESC LIMIT %s",
        (chat_id, limit),
        fetch=True
    )
    if results:
        return [{"id": r[0], "text": r[1], "author": r[2]} for r in results]
    return []

def delete_quote_by_id(quote_id: int, chat_id: int) -> bool:
    results = db_execute(
        "DELETE FROM quotes WHERE id = %s AND chat_id = %s RETURNING id",
        (quote_id, chat_id),
        fetch=True
    )
    return bool(results)

def add_reminder(uid: str, chat_id: int, text: str, remind_at: float) -> int:
    result = db_execute(
        "INSERT INTO reminders (user_id, chat_id, text, remind_at, created_at, fired) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
        (str(uid), chat_id, text, remind_at, time.time(), False),
        fetch=True,
        fetch_one=True
    )
    return result[0] if result else 0

def get_user_reminders(uid: str) -> list:
    results = db_execute(
        "SELECT id, user_id, chat_id, text, remind_at, created_at, fired FROM reminders WHERE user_id = %s AND fired = false",
        (str(uid),),
        fetch=True
    )
    if results:
        return [
            {"id": r[0], "user_id": r[1], "chat_id": r[2], "text": r[3], "remind_at": r[4], "created_at": r[5], "fired": r[6]}
            for r in results
        ]
    return []

def delete_reminder(reminder_id: int, uid: str) -> bool:
    db_execute(
        "UPDATE reminders SET fired = true WHERE id = %s AND user_id = %s",
        (reminder_id, str(uid))
    )
    return True

def get_pending_reminders() -> list:
    results = db_execute(
        "SELECT id, user_id, chat_id, text, remind_at, created_at, fired FROM reminders WHERE fired = false AND remind_at <= %s",
        (time.time(),),
        fetch=True
    )
    if results:
        return [
            {"id": r[0], "user_id": r[1], "chat_id": r[2], "text": r[3], "remind_at": r[4], "created_at": r[5], "fired": r[6]}
            for r in results
        ]
    return []

def mark_reminder_fired(reminder_id: int) -> None:
    db_execute("UPDATE reminders SET fired = true WHERE id = %s", (reminder_id,))

# ═══════════════════════════════════════════════════════════════════════════════
# Utility Functions
# ═══════════════════════════════════════════════════════════════════════════════

def uptime_str() -> str:
    delta = datetime.now() - START_TIME
    total_seconds = int(delta.total_seconds())
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days: parts.append(f"{days} д.")
    if hours: parts.append(f"{hours} ч.")
    if minutes: parts.append(f"{minutes} мин.")
    if not parts or seconds: parts.append(f"{seconds} сек.")
    return " ".join(parts)

def get_system_prompt(role_key: str) -> str:
    roles = get_all_roles("system")
    role = roles.get(role_key, roles.get("default", {}))
    return role.get("prompt", "Ты полезный ассистент.")

def ask_ai(uid: str, user_message: str) -> str:
    role_key = get_user_role(uid)
    system_prompt = get_system_prompt(role_key)
    history = append_history(uid, "user", user_message)
    messages = [{"role": "system", "content": system_prompt}] + history
    
    try:
        log_ai(uid, user_message, "...")
        
        # Запрос напрямую к OpenRouter без посредничества g4f
        if openrouter_client is None:
            log_err("AI", f"OpenRouter client not initialized for user={uid}")
            return "AI сервис временно недоступен. Попробуйте позже."
        
        response = openrouter_client.chat.completions.create(
            model="gemma3-1b_heretic",  # Указываем конкретную бесплатную модель
            messages=messages
        )
        
        answer = response.choices[0].message.content
        if answer is None or not str(answer).strip():
            log_err("AI", f"Empty response for user={uid}")
            return "Не получилось сформировать ответ. Попробуй ещё раз."
            
        answer = str(answer).strip()
        append_history(uid, "assistant", answer)
        log_ai(uid, user_message, answer)
        return answer
        
    except Exception as e:
        log_err("AI", f"Error for user={uid}: {e}")
        return "Произошла ошибка при обращении к AI."

def generate_image(uid: str, prompt: str) -> Optional[str]:
    try:
        log_gen(uid, "IMAGE", prompt, False, "generating...")
        response = ai_client.images.generate(
            model="flux-dev",
            prompt=prompt,
            response_format="url",
        )
        url = response.data[0].url
        log_gen(uid, "IMAGE", prompt, True, url)
        return url
    except Exception as e:
        log_err("GEN_IMAGE", f"Error for user={uid}: {e}")
        log_gen(uid, "IMAGE", prompt, False)
        return None

def roles_keyboard(uid: str) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=2)
    roles = get_all_roles(uid)
    buttons = []

    for key, val in roles.items():
        if key.startswith("custom_") and val.get("owner") != uid:
            continue
        buttons.append(types.InlineKeyboardButton(text=val["name"], callback_data=f"setrole:{key}"))

    buttons.append(types.InlineKeyboardButton("➕ Создать персонажа", callback_data="create_role"))
    buttons.append(types.InlineKeyboardButton("🗑 Удалить персонажа", callback_data="delete_role_menu"))
    markup.add(*buttons)
    return markup

def get_uid(message: types.Message) -> str:
    return str(message.from_user.id)

def is_group(message: types.Message) -> bool:
    return message.chat.type in ("group", "supergroup")

def is_admin(message: types.Message) -> bool:
    username = (message.from_user.username or "").lower()
    return username in ADMIN_USERNAMES

def is_group_admin(message: types.Message) -> bool:
    """Check if the user is an admin of the Telegram group (or a bot admin)."""
    if is_admin(message):
        return True
    if not is_group(message):
        return True
    try:
        member = bot.get_chat_member(message.chat.id, message.from_user.id)
        return member.status in ("administrator", "creator")
    except Exception as e:
        log_err("ADMIN_CHECK", f"Error checking group admin: {e}")
        return False

def can_award(message: types.Message) -> bool:
    """Check if the user can award others — must be a group admin or bot admin."""
    return is_group_admin(message)

def get_display_name(user) -> str:
    """Get a display name from a Telegram user object."""
    if user.username:
        return f"@{user.username}"
    name = user.first_name or ""
    if user.last_name:
        name += f" {user.last_name}"
    return name or f"user_{user.id}"

# ═══════════════════════════════════════════════════════════════════════════════
# Pizdec — Pure Algorithmic Text Distortion (no AI)
# ═══════════════════════════════════════════════════════════════════════════════

_RU_LETTERS_LOWER = "абвгдежзийклмнопрстуфхцчшщъыьэюя"
_RU_LETTERS_ALL = _RU_LETTERS_LOWER + _RU_LETTERS_LOWER.upper()

_KEYBOARD_NEIGHBORS = {
    'а': 'фпо', 'б': 'иьв', 'в': 'мбл', 'г': 'шрф', 'д': 'бшл',
    'е': 'пук', 'ж': 'ыоэ', 'з': 'щшг', 'и': 'мкб', 'й': 'цыф',
    'к': 'езу', 'л': 'допр', 'м': 'св', 'н': 'тмс', 'о': 'рлж',
    'п': 'рма', 'р': 'аоп', 'с': 'чвм', 'т': 'сн', 'у': 'цке',
    'ф': 'агш', 'х': 'зжэ', 'ц': 'уйс', 'ч': 'см', 'ш': 'гзд',
    'щ': 'шз', 'ъ': 'эж', 'ы': 'йчц', 'ь': 'би', 'э': 'жхъ',
    'ю': 'ьбх', 'я': 'фч',
}

_MAT_WORDS = [
    "блядь", "пиздец", "хуй", "ебаный", "уебок", "пидор", "сука",
    "ахуенно", "охуеть", "ебать", "гандон", "мудак", "залупа",
    "дрочить", "ебало", "хуйня", "пизда", "ебля", "хуёво", "пиздить",
    "ёбнутый", "херня", "охуеть", "ебанько", "пиздабол", "уёбище",
]

_RAND_PUNCT = ["!", "?", ".", ",", "!?", "?!", "!!!", "...", ",,"]

# Per-level parameters: (typo_chance, random_letters_per_word, ending_distort_pct,
#   beginning_distort_pct, mat_chance, caps_chance, punct_chance, destroy_word_pct)
# destroy_word_pct — chance to replace a whole short word with gibberish
_PIZDEC_PARAMS = {
    1:  (0.04, 0, 0.0,  0.0,  0.0,  0.0,  0.0,  0.0),
    2:  (0.10, 0, 0.0,  0.0,  0.0,  0.02, 0.0,  0.0),
    3:  (0.20, 1, 0.05, 0.0,  0.0,  0.05, 0.03, 0.0),
    4:  (0.30, 1, 0.15, 0.03, 0.0,  0.08, 0.06, 0.0),
    5:  (0.40, 2, 0.30, 0.08, 0.03, 0.12, 0.10, 0.0),
    6:  (0.50, 2, 0.50, 0.15, 0.08, 0.15, 0.15, 0.05),
    7:  (0.60, 3, 0.60, 0.25, 0.15, 0.20, 0.20, 0.12),
    8:  (0.70, 4, 0.70, 0.35, 0.22, 0.25, 0.25, 0.20),
    9:  (0.80, 5, 0.80, 0.45, 0.30, 0.30, 0.30, 0.30),
    10: (0.90, 6, 1.0,  0.55, 0.40, 0.35, 0.35, 0.45),
}


def _is_cyrillic(ch: str) -> bool:
    return ch.lower() in _RU_LETTERS_LOWER


def _rand_ru_char() -> str:
    return random.choice(_RU_LETTERS_LOWER)


def _keyboard_typo(ch: str) -> str:
    lower = ch.lower()
    neighbors = _KEYBOARD_NEIGHBORS.get(lower)
    if not neighbors:
        return ch
    replacement = random.choice(neighbors)
    return replacement.upper() if ch.isupper() else replacement


def _distort_ending(word: str, intensity: int) -> str:
    if len(word) < 3:
        return word
    keep = max(1, len(word) - 1 - intensity)
    if keep >= len(word):
        return word
    core = word[:keep]
    tail_len = len(word) - keep
    garbage = "".join(_rand_ru_char() for _ in range(tail_len + random.randint(0, intensity)))
    preserve_case = word[keep:] if random.random() < 0.3 else garbage
    return core + preserve_case


def _distort_beginning(word: str, intensity: int) -> str:
    if len(word) < 3:
        return word
    keep = max(1, len(word) - 1 - intensity)
    core = word[keep:]
    head_len = keep
    garbage = "".join(_rand_ru_char() for _ in range(head_len + random.randint(0, intensity)))
    return garbage + core


def _insert_random_letters(word: str, count: int) -> str:
    if count <= 0 or len(word) < 2:
        return word
    chars = list(word)
    insertions = min(count, len(word))
    for _ in range(insertions):
        pos = random.randint(0, len(chars))
        chars.insert(pos, _rand_ru_char())
    return "".join(chars)


def _random_caps(word: str, chance: float) -> str:
    if chance <= 0:
        return word
    chars = []
    for ch in word:
        if _is_cyrillic(ch) and random.random() < chance:
            chars.append(ch.upper())
        else:
            chars.append(ch)
    return "".join(chars)


def _maybe_swap_letter(word: str, typo_chance: float) -> str:
    if typo_chance <= 0 or len(word) < 2:
        return word
    chars = list(word)
    for i, ch in enumerate(chars):
        if _is_cyrillic(ch) and random.random() < typo_chance:
            r = random.random()
            if r < 0.4:
                chars[i] = _keyboard_typo(ch)
            elif r < 0.7:
                pos = random.randint(0, len(chars))
                chars.insert(pos, ch)
            elif r < 0.85:
                if len(chars) > 2:
                    j = random.randint(0, len(chars) - 1)
                    chars[i], chars[j] = chars[j], chars[i]
            else:
                chars[i] = _rand_ru_char()
    return "".join(chars)


def _destroy_word(word: str, intensity: int) -> str:
    if len(word) < 4:
        keep_n = 1
    else:
        keep_n = max(1, len(word) // 3)
    keep = word[:keep_n]
    garbage_len = random.randint(2, 4 + intensity)
    garbage = "".join(_rand_ru_char() for _ in range(garbage_len))
    return keep + garbage


def _maybe_insert_mat(words: list[str], mat_chance: float) -> list[str]:
    if mat_chance <= 0 or not words:
        return words
    result = []
    for w in words:
        result.append(w)
        if random.random() < mat_chance:
            mat = random.choice(_MAT_WORDS)
            result.append(mat)
    return result


def _maybe_insert_punct(text: str, punct_chance: float) -> str:
    if punct_chance <= 0:
        return text
    words = text.split()
    result = []
    for i, w in enumerate(words):
        result.append(w)
        if i < len(words) - 1 and random.random() < punct_chance:
            result.append(random.choice(_RAND_PUNCT))
    return " ".join(result)


def distort_text(text: str, level: int) -> str:
    if level < 1:
        level = 1
    if level > 10:
        level = 10

    p = _PIZDEC_PARAMS[level]
    typo_chance, rand_letters, end_pct, beg_pct, mat_chance, caps_chance, punct_chance, destroy_pct = p
    intensity = level // 3

    words = text.split()
    result_words = []

    for word in words:
        prefix = ""
        suffix = ""
        for _ in range(len(word)):
            if word[0] not in _RU_LETTERS_ALL and not word[0].isalnum():
                prefix += word[0]
                word = word[1:]
            else:
                break
        for _ in range(len(word)):
            if word and word[-1] not in _RU_LETTERS_ALL and not word[-1].isalnum():
                suffix = word[-1] + suffix
                word = word[:-1]
            else:
                break

        core = word
        if not core:
            result_words.append(prefix + suffix)
            continue

        if random.random() < destroy_pct:
            core = _destroy_word(core, intensity)
        else:
            core = _maybe_swap_letter(core, typo_chance)
            core = _insert_random_letters(core, rand_letters)
            if random.random() < end_pct:
                core = _distort_ending(core, intensity)
            if random.random() < beg_pct:
                core = _distort_beginning(core, intensity)
            core = _random_caps(core, caps_chance)

        result_words.append(prefix + core + suffix)

    result_words = _maybe_insert_mat(result_words, mat_chance)
    result = " ".join(result_words)
    result = _maybe_insert_punct(result, punct_chance)
    return result

# ═══════════════════════════════════════════════════════════════════════════════
# Command List (command - description)
# ═══════════════════════════════════════════════════════════════════════════════

COMMAND_LIST = [
    "/about - информация о боте",
    "/roles - выбрать роль/персонажа",
    "/createrole - создать персонажа",
    "/deleterole - удалить персонажа",
    "/gen  - сгенерировать картинку",
    "/tts  - озвучить текст",
    "/meme - создать мем",
    "/pizdec - искажить текст (уровень 1-10, в ответ на сообщение)",
    "/trash - получить окурки (раз в 40 мин)",
    "/smoke - выкурить окурок",
    "/leaderboard - топ по окуркам",
    "/roulette - русская рулетка",
    "/revive - воскреснуть",
    "/ping - проверить пинг бота",
    "/clear - очистить память ИИ",
    "/reverse - отзеркалить фото",
    "/blackwhite - ч/б фото",
    "/brown - коричневый фильтр",
    "/jpeg - ухудшить качество",
    "/invert - инвертировать цвета",
    "/sepia - сепия фильтр",
    "/blur - размытие фото",
    "/qr - создать QR-код",
    "/weather - погода",
    "/translate - перевод на английский",
    "/8ball - магический шар",
    "/dice - бросок кубика (d6 по умолчанию)",
    "/choose - случайный выбор",
    "/remind - напоминание",
    "/reminders - список напоминаний",
    "/delremind - удалить напоминание",
    "/stats - статистика (своя или чужая, с графиком)",
    "/top_chat - топ общительных в этом чате",
    "/top_bot - топ общительных с ботом",
    "/say - отправить сообщение без изменений",
    "/delbot - удалить последние сообщения бота (кол-во)",
    "/birja - биржа Крипто-Окурков (график, купить/продать COK)",
    "/wallet - кошелёк COK (график, перевод)",
    "/bank - Центробанк (кредит, вклад, комиссии)",
    "/quote - сохранить цитату",
    "/ship - шипперим двух рандомных людей из чата",
    "/shhh - нашептать секретное сообщение",
    "/mines - игра Мины (ставка на окурки/рубли/сигареты)",
    "/cr - казино-рулетка (ставка на цвет или число)",
    "/bj - блэкджек (ставка на окурки/рубли/сигареты)",
]

VIRUS_COMMANDS = [
    "/create_virus - создать патоген (имя)",
    "/lab - лаборатория: улучшить патоген",
    "/virus - заразить человека (в ответ на сообщение)",
    "/delete_virus - уничтожить патоген (все болеющие выздоровеют)",
]

CLAN_COMMANDS = [
    "/create_clan - создать клан",
    "/delete_clan - удалить свой клан (только лидер)",
    "/clan - информация о твоём клане",
    "/clans - список всех кланов",
    "/join_clan - вступить в клан",
    "/leave_clan - покинуть клан",
    "/trash_to_clan - перевести окурки в репутацию клана",
    "/cigar_to_clan - перевести сигареты в репутацию клана",
]

ECONOMY_COMMANDS = [
    "/beggar - попытаться выпросить рубль (шанс 1 к 20000)",
    "/buy_cigarettes - купить сигареты за рубли (5₽/шт)",
    "/balance - проверить баланс (окурки, рубли, сигареты)",
    "/bank - Центробанк (кредит, вклад, комиссии переводов)",
    "/to_cig - обменять окурки на сигареты (100 о = 1 с)",
    "/to_rub - обменять сигареты на рубли (5 с = 1₽)",
]

PROMO_COMMANDS = [
    "/create_promo - создать промокод (админ)",
    "/promo - активировать промокод",
]

TRANSFER_COMMANDS = [
    "/send_item - передать предмет (в ответ на сообщение)",
]

AWARD_COMMANDS = [
    "/to_award - наградить человека (в ответ на сообщение, админ)",
]

ADMIN_COMMANDS = [
    "/ban - забанить (в ответ на сообщение, админ)",
    "/unban - разбанить (в ответ на сообщение, админ)",
    "/mute - замутить (в ответ, админ)",
    "/unmute - размутить (в ответ, админ)",
    "/warn - выдать предупреждение (в ответ, админ)",
    "/unwarn - снять предупреждение (в ответ, админ)",
    "/enemy_list - список 6 последних наказаний в чате",
]

def _format_sections(sections) -> str:
    text = ""
    for title, cmds in sections:
        text += f"\n<b>{title}:</b>\n"
        for cmd in cmds:
            text += f"  {cmd}\n"
    return text

def format_commands_part1() -> str:
    return _format_sections([
        ("Основное", COMMAND_LIST),
        ("Патогены", VIRUS_COMMANDS),
        ("Кланы", CLAN_COMMANDS),
        ("Экономика", ECONOMY_COMMANDS),
    ])

def format_commands_part2() -> str:
    return _format_sections([
        ("Промокоды", PROMO_COMMANDS),
        ("Передача предметов", TRANSFER_COMMANDS),
        ("Награды", AWARD_COMMANDS),
        ("Админ-команды", ADMIN_COMMANDS),
    ])

# ═══════════════════════════════════════════════════════════════════════════════
# Image Processing
# ═══════════════════════════════════════════════════════════════════════════════

def process_image(image_bytes: bytes, mode: str) -> Optional[bytes]:
    try:
        img = Image.open(io.BytesIO(image_bytes))

        if mode == "reverse":
            img = ImageOps.mirror(img)
        elif mode == "blackwhite":
            img = img.convert("L")
        elif mode == "brown":
            img = img.convert("RGB")
            r, g, b = img.split()
            r = r.point(lambda x: min(255, x * 1.2))
            g = g.point(lambda x: x * 0.9)
            b = b.point(lambda x: x * 0.7)
            img = Image.merge("RGB", (r, g, b))
        elif mode == "jpeg":
            img = img.convert("RGB")
            output = io.BytesIO()
            img.save(output, format="JPEG", quality=10)
            return output.getvalue()
        elif mode == "invert":
            img = ImageOps.invert(img.convert("RGB"))
        elif mode == "grayscale":
            img = img.convert("L")
        elif mode == "sepia":
            img = img.convert("RGB")
            r, g, b = img.split()
            r = r.point(lambda x: min(255, x * 0.393 + x * 0.769 + x * 0.189))
            g = g.point(lambda x: min(255, x * 0.349 + x * 0.686 + x * 0.168))
            b = b.point(lambda x: min(255, x * 0.272 + x * 0.534 + x * 0.131))
            img = Image.merge("RGB", (r, g, b))
        elif mode == "blur":
            img = img.filter(ImageFilter.GaussianBlur(radius=5))
        else:
            return None

        output = io.BytesIO()
        img.save(output, format="PNG")
        return output.getvalue()
    except Exception as e:
        log_err("IMG_PROC", f"Error: {e}")
        return None

def create_meme(image_bytes: bytes, top_text: str = "", bottom_text: str = "") -> Optional[bytes]:
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        draw = ImageDraw.Draw(img)

        font_size = max(20, img.width // 15)
        try:
            font = ImageFont.truetype("impact.ttf", font_size)
        except:
            font = ImageFont.load_default()

        def draw_text_with_outline(text, y_pos, center=True):
            if not text:
                return
            text = text.upper()
            x = img.width // 2
            anchor = "mm"

            for adj_x in [-2, -1, 0, 1, 2]:
                for adj_y in [-2, -1, 0, 1, 2]:
                    draw.text((x + adj_x, y_pos + adj_y), text, font=font, fill="black", anchor=anchor)
            draw.text((x, y_pos), text, font=font, fill="white", anchor=anchor)

        draw_text_with_outline(top_text, font_size + 10)
        draw_text_with_outline(bottom_text, img.height - font_size - 10)

        output = io.BytesIO()
        img.save(output, format="PNG")
        return output.getvalue()
    except Exception as e:
        log_err("MEME", f"Error: {e}")
        return None

def apply_image_effect(message: types.Message, mode: str):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"

    if not message.reply_to_message or not message.reply_to_message.photo:
        bot.reply_to(message, "Ответь на сообщение с изображением командой.")
        return

    log_cmd(uid, username, mode, "image processing")
    wait_msg = bot.reply_to(message, "Обрабатываю изображение...")

    def _process():
        set_reply_context(message)
        try:
            file_info = bot.get_file(message.reply_to_message.photo[-1].file_id)
            downloaded = bot.download_file(file_info.file_path)
            processed = process_image(downloaded, mode)
            bot.delete_message(message.chat.id, wait_msg.message_id)

            if processed:
                log_img_proc(uid, mode, True)
                bot.send_photo(message.chat.id, processed, reply_to_message_id=message.message_id)
            else:
                log_img_proc(uid, mode, False)
                bot.reply_to(message, "Не удалось обработать изображение.")
        except Exception as e:
            log_err("IMG_PROC", f"Error for user={uid}: {e}")
            log_img_proc(uid, mode, False)
            bot.delete_message(message.chat.id, wait_msg.message_id)
            bot.reply_to(message, f"Ошибка: {e}")

    threading.Thread(target=_process, daemon=True).start()

def generate_qr_code(text: str) -> Optional[bytes]:
    try:
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        output = io.BytesIO()
        img.save(output, format="PNG")
        return output.getvalue()
    except Exception as e:
        log_err("QR", f"Error: {e}")
        return None

def is_message_fresh(message: types.Message) -> bool:
    """Ignore backlog messages after bot restart or very old messages."""
    if not message.date:
        return True
    msg_ts = float(message.date)
    now = time.time()
    if now - msg_ts > MESSAGE_MAX_AGE:
        return False
    if msg_ts < BOT_READY_AT - 5:
        return False
    return True

def maybe_send_random_quote(message: types.Message) -> bool:
    if not is_message_fresh(message):
        return False

    chat_id = message.chat.id
    now = time.time()
    last_sent = _last_quote_sent.get(chat_id, 0)
    if now - last_sent < QUOTE_COOLDOWN:
        return False

    if random.random() >= QUOTE_CHANCE:
        return False

    quote = get_random_quote(chat_id)
    if not quote:
        return False
    try:
        if quote.get('photo_file_id'):
            caption = f"💬 <i>{quote['text']}</i>\n\n— {quote['author']}" if quote['text'] and quote['text'] != "📷" else f"💬 — {quote['author']}"
            bot.send_photo(chat_id, quote['photo_file_id'], caption=caption,
                           reply_to_message_id=message.message_id)
        else:
            bot.send_message(chat_id, f"💬 <i>{quote['text']}</i>\n\n— {quote['author']}",
                             reply_to_message_id=message.message_id)
        _last_quote_sent[chat_id] = now
        log_info("QUOTE", f"Sent random quote in chat={chat_id}")
        return True
    except Exception as e:
        log_err("QUOTE", f"Failed: {e}")
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# Weather (using python_weather)
# ═══════════════════════════════════════════════════════════════════════════════

async def get_weather_async(city: str) -> dict:
    """Fetch weather using python_weather library."""
    async with python_weather.Client(unit=python_weather.METRIC) as client:
        weather = await client.get(city)

        current_temp = weather.temperature
        current_desc = weather.kind.name if hasattr(weather, 'kind') else "N/A"
        feels_like = current_temp
        if hasattr(weather, 'feels_like'):
            feels_like = weather.feels_like
        humidity = weather.humidity if hasattr(weather, 'humidity') else "N/A"
        wind_speed = weather.wind_speed if hasattr(weather, 'wind_speed') else "N/A"

        return {
            "temp": current_temp,
            "feels_like": feels_like,
            "humidity": humidity,
            "wind_speed": wind_speed,
            "description": current_desc,
            "location": city
        }

def get_weather(city: str) -> Optional[dict]:
    """Sync wrapper for async weather fetch."""
    try:
        return asyncio.run(get_weather_async(city))
    except Exception as e:
        log_err("WEATHER", f"Error: {e}")
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# 8-Ball Answers
# ═══════════════════════════════════════════════════════════════════════════════

EIGHT_BALL_ANSWERS = [
    "✅ Определённо да.",
    "✅ Да, без сомнений.",
    "✅ Можешь быть уверен в этом.",
    "✅ Да, это точно.",
    "🤔 Скорее всего, да.",
    "🤔 Перспективы хорошие.",
    "🤔 Знаки указывают на да.",
    "🤔 Спроси позже.",
    "❓ Спроси ещё раз.",
    "❓ Лучше не говорить тебе сейчас.",
    "❓ Сейчас не могу предсказать.",
    "❌ Сомневайся в этом.",
    "❌ Мой ответ — нет.",
    "❌ По моим данным — нет.",
    "❌ Очень сомнительно.",
    "❌ Нет.",
]

# ═══════════════════════════════════════════════════════════════════════════════
# Time Parser
# ═══════════════════════════════════════════════════════════════════════════════

def parse_remind_time(time_str: str) -> Optional[int]:
    time_str = time_str.lower().strip()
    match = re.match(r"^(\d+)([smhd])$", time_str)
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2)
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    return value * multipliers[unit]

# ═══════════════════════════════════════════════════════════════════════════════
# Handlers
# ═══════════════════════════════════════════════════════════════════════════════

TERMS_OF_USE_URL = "https://ziris.zorgv.su/terms.txt"  # Замените на ваш URL с Terms of Use

def start_menu_keyboard(page: int = 0) -> types.InlineKeyboardMarkup:
    """Создает клавиатуру для меню /start только с 3 кнопками навигации."""
    markup = types.InlineKeyboardMarkup(row_width=3)
    
    # Все команды бота с описаниями (78 команд)
    all_commands = [
        ("8ball", "Магический шар предсказаний"),
        ("about", "Информация о боте"),
        ("balance", "Проверить баланс"),
        ("ban", "Забанить пользователя"),
        ("bank", "Банк: вклады, кредиты"),
        ("beggar", "Попрошайничать"),
        ("birja", "Крипто-биржа окурков"),
        ("bj", "Блэкджек"),
        ("blackwhite", "Ч/б фильтр"),
        ("blur", "Размыть изображение"),
        ("brown", "Коричневый фильтр"),
        ("buy_cigarettes", "Купить сигареты"),
        ("choose", "Случайный выбор"),
        ("cigar_to_clan", "Передать сигарету клану"),
        ("clan", "Инфо о клане"),
        ("clans", "Список кланов"),
        ("clear", "Очистить историю"),
        ("cr", "Crash игра"),
        ("create_clan", "Создать клан"),
        ("create_promo", "Создать промокод"),
        ("create_role", "Создать роль"),
        ("create_virus", "Создать вирус"),
        ("delbot", "Удалить сообщения бота"),
        ("delete_clan", "Удалить клан"),
        ("delete_role", "Удалить роль"),
        ("delete_virus", "Удалить вирус"),
        ("delremind", "Удалить напоминание"),
        ("deposits", "Мои вклады"),
        ("dice", "Бросить кубик"),
        ("enemy_list", "Список врагов"),
        ("gen", "Генерация изображения"),
        ("invert", "Инвертировать цвета"),
        ("join_clan", "Вступить в клан"),
        ("jpeg", "Ухудшить качество"),
        ("lab", "Лаборатория вируса"),
        ("leaderboard", "Топ игроков"),
        ("leave_clan", "Покинуть клан"),
        ("loans", "Мои кредиты"),
        ("meme", "Создать мем"),
        ("mines", "Мины игра"),
        ("mute", "Замутить пользователя"),
        ("pay", "Досрочное погашение кредита"),
        ("ping", "Проверка задержки"),
        ("pizdec", "Режим хаоса"),
        ("promo", "Активировать промокод"),
        ("qr", "Создать QR-код"),
        ("quote", "Цитата из сообщения"),
        ("remind", "Создать напоминание"),
        ("reminders", "Список напоминаний"),
        ("reverse", "Перевернуть текст"),
        ("revive", "Возродиться"),
        ("roles", "Список ролей"),
        ("roulette", "Русская рулетка"),
        ("say", "Заставить бота сказать"),
        ("send_item", "Передать предмет"),
        ("sepia", "Эффект сепии"),
        ("shhh", "Тихий режим"),
        ("ship", "Совместимость"),
        ("smoke", "Выкурить сигарету"),
        ("start", "Главное меню"),
        ("stats", "Твоя статистика"),
        ("to_award", "Конвертировать в награды"),
        ("to_cig", "Окурки → сигареты"),
        ("to_rub", "Окурки → рубли"),
        ("top_bot", "Топ пользователей бота"),
        ("top_chat", "Топ пользователей чата"),
        ("translate", "Перевести текст"),
        ("trash", "Найти окурок"),
        ("trash_to_clan", "Передать окурки клану"),
        ("tts", "Текст в речь"),
        ("unban", "Разбанить"),
        ("unmute", "Размутить"),
        ("unwarn", "Снять предупреждение"),
        ("virus", "Заразить пользователя"),
        ("vsem", "Рассылка всем"),
        ("wallet", "Кошелёк криптовалюты"),
        ("warn", "Предупредить"),
        ("weather", "Узнать погоду")
    ]
    
    # Разбиваем на страницы по 20 команд
    page_size = 20
    total_pages = math.ceil(len(all_commands) / page_size)
    
    # Навигация: только 3 кнопки - Назад, Далее, Terms of Use
    nav_row = []
    if page > 0:
        nav_row.append(types.InlineKeyboardButton("⬅️", callback_data=f"start_page:{page-1}"))
    if page < total_pages - 1:
        nav_row.append(types.InlineKeyboardButton("➡️", callback_data=f"start_page:{page+1}"))
    
    nav_row.append(types.InlineKeyboardButton("📜 Условия использования", url=TERMS_OF_USE_URL))
    
    markup.add(*nav_row)
    
    return markup


def get_start_text(page: int = 0, name: str = "друг") -> str:
    """Возвращает текст для определенной страницы меню /start со списком команд."""
    # Все команды бота с описаниями
    all_commands = [
        ("8ball", "Магический шар предсказаний"),
        ("about", "Информация о боте"),
        ("balance", "Проверить баланс"),
        ("ban", "Забанить пользователя"),
        ("bank", "Банк: вклады, кредиты"),
        ("beggar", "Попрошайничать"),
        ("birja", "Крипто-биржа окурков"),
        ("bj", "Блэкджек"),
        ("blackwhite", "Ч/б фильтр"),
        ("blur", "Размыть изображение"),
        ("brown", "Коричневый фильтр"),
        ("buy_cigarettes", "Купить сигареты"),
        ("choose", "Случайный выбор"),
        ("cigar_to_clan", "Передать сигарету клану"),
        ("clan", "Инфо о клане"),
        ("clans", "Список кланов"),
        ("clear", "Очистить историю"),
        ("cr", "Crash игра"),
        ("create_clan", "Создать клан"),
        ("create_promo", "Создать промокод"),
        ("create_role", "Создать роль"),
        ("create_virus", "Создать вирус"),
        ("delbot", "Удалить сообщения бота"),
        ("delete_clan", "Удалить клан"),
        ("delete_role", "Удалить роль"),
        ("delete_virus", "Удалить вирус"),
        ("delremind", "Удалить напоминание"),
        ("deposits", "Мои вклады"),
        ("dice", "Бросить кубик"),
        ("enemy_list", "Список врагов"),
        ("gen", "Генерация изображения"),
        ("invert", "Инвертировать цвета"),
        ("join_clan", "Вступить в клан"),
        ("jpeg", "Ухудшить качество"),
        ("lab", "Лаборатория вируса"),
        ("leaderboard", "Топ игроков"),
        ("leave_clan", "Покинуть клан"),
        ("loans", "Мои кредиты"),
        ("meme", "Создать мем"),
        ("mines", "Мины игра"),
        ("mute", "Замутить пользователя"),
        ("pay", "Досрочное погашение кредита"),
        ("ping", "Проверка задержки"),
        ("pizdec", "Режим хаоса"),
        ("promo", "Активировать промокод"),
        ("qr", "Создать QR-код"),
        ("quote", "Цитата из сообщения"),
        ("remind", "Создать напоминание"),
        ("reminders", "Список напоминаний"),
        ("reverse", "Перевернуть текст"),
        ("revive", "Возродиться"),
        ("roles", "Список ролей"),
        ("roulette", "Русская рулетка"),
        ("say", "Заставить бота сказать"),
        ("send_item", "Передать предмет"),
        ("sepia", "Эффект сепии"),
        ("shhh", "Тихий режим"),
        ("ship", "Совместимость"),
        ("smoke", "Выкурить сигарету"),
        ("start", "Главное меню"),
        ("stats", "Твоя статистика"),
        ("to_award", "Конвертировать в награды"),
        ("to_cig", "Окурки → сигареты"),
        ("to_rub", "Окурки → рубли"),
        ("top_bot", "Топ пользователей бота"),
        ("top_chat", "Топ пользователей чата"),
        ("translate", "Перевести текст"),
        ("trash", "Найти окурок"),
        ("trash_to_clan", "Передать окурки клану"),
        ("tts", "Текст в речь"),
        ("unban", "Разбанить"),
        ("unmute", "Размутить"),
        ("unwarn", "Снять предупреждение"),
        ("virus", "Заразить пользователя"),
        ("vsem", "Рассылка всем"),
        ("wallet", "Кошелёк криптовалюты"),
        ("warn", "Предупредить"),
        ("weather", "Узнать погоду")
    ]
    
    total_pages = math.ceil(len(all_commands) / 20)
    
    # Получаем команды для текущей страницы
    page_size = 20
    start_idx = page * page_size
    end_idx = min((page + 1) * page_size, len(all_commands))
    current_commands = all_commands[start_idx:end_idx]
    
    # Формируем список команд текстом
    commands_list = "\n".join([f"/{cmd} — {desc}" for cmd, desc in current_commands])
    
    if page == 0:
        return (
            f"👋 Привет, <b>{name}</b>! Я AI-бот.\n\n"
            "Я умею общаться, генерировать картинки, озвучивать текст,\n"
            "играть в рулетку, создавать мемы, QR-коды и многое другое.\n\n"
            f"<b>📋 Список всех команд ({page+1}/{total_pages})</b>\n"
            f"{'─' * 30}\n\n"
            f"{commands_list}\n\n"
            f"{'─' * 30}\n"
            "Используй кнопки ниже для навигации."
        )
    else:
        return (
            f"<b>📋 Список всех команд ({page+1}/{total_pages})</b>\n"
            f"{'─' * 30}\n\n"
            f"{commands_list}\n\n"
            f"{'─' * 30}\n"
            "Используй кнопки ниже для навигации."
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith("start_page:"))
def callback_start_page(call: types.CallbackQuery):
    """Обработчик переключения страниц меню /start."""
    uid = str(call.from_user.id)
    page = int(call.data.split(":")[1])
    name = call.from_user.first_name or "друг"
    
    bot.answer_callback_query(call.id)
    
    text = get_start_text(page, name)
    markup = start_menu_keyboard(page)
    
    try:
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=markup
        )
    except Exception as e:
        log_err("START_PAGE", str(e))


@bot.callback_query_handler(func=lambda call: call.data.startswith("start_cmd:"))
def callback_start_cmd(call: types.CallbackQuery):
    """Обработчик нажатия на кнопку команды в меню /start."""
    cmd = call.data.split(":")[1]
    bot.answer_callback_query(call.id, f"/{cmd}", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data == "start_divider")
def callback_start_divider(call: types.CallbackQuery):
    """Обработчик нажатия на разделитель в меню /start."""
    bot.answer_callback_query(call.id)


@bot.message_handler(commands=["start"])
def cmd_start(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    name = message.from_user.first_name or "друг"
    log_cmd(uid, username, "start")
    register_chat(message.chat.id)
    if message.from_user.username:
        update_username(uid, message.from_user.username)
    track_chat_member(message.chat.id, message.from_user)
    increment_stat(uid, "commands")
    set_first_message_if_null(uid)

    # Отправляем меню с кнопками
    text = get_start_text(0, name)
    markup = start_menu_keyboard(0)
    
    bot.reply_to(message, text, parse_mode="HTML", reply_markup=markup)


@bot.message_handler(commands=["about"])
def cmd_about(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    register_chat(message.chat.id)
    if message.from_user.username:
        update_username(uid, message.from_user.username)
    track_chat_member(message.chat.id, message.from_user)
    log_cmd(uid, username, "about")
    increment_stat(uid, "commands")
    set_first_message_if_null(uid)

    role_key = get_user_role(uid)
    roles = get_all_roles(uid)
    current_role = roles.get(role_key, {}).get("name", "Обычный ассистент")
    uptime = uptime_str()
    cigs = get_cigarettes(uid)
    rubles = get_rubles(uid)
    real_cigs = get_real_cigarettes(uid)
    is_dead = is_user_dead(uid)
    status = "💀 Мёртв" if is_dead else "✅ Жив"

    bot.reply_to(message,
        "ℹ️ <b>О боте</b>\n\n"
        "Я тг бог работающий на <b>GPT.</b> "
        "Генерация изображений через <b>Flux</b>.\n"
        "TTS через <b>Silero</b>.\n"
        "Данные хранятся в <b>PostgreSQL</b>.\n\n"
        f"<b>Время работы:</b> {uptime}\n"
        f"<b>Твоя текущая роль:</b> {current_role}\n"
        f"<b>Окурки:</b> {cigs} | <b>Рубли:</b> {rubles}₽ | <b>Сигареты:</b> {real_cigs}\n"
        f"<b>Статус:</b> {status}\n\n"
        "<b>Меня создал @weird_maan</b>"
    )


@bot.message_handler(commands=["roles"])
def cmd_roles(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    log_cmd(uid, username, "roles")
    increment_stat(uid, "commands")

    role_key = get_user_role(uid)
    roles = get_all_roles(uid)
    current_name = roles.get(role_key, {}).get("name", "Обычный ассистент")

    text = f"🎭 <b>Роли и персонажи</b>\nТекущая роль: <b>{current_name}</b>\n\nВыбери роль или персонажа:"
    bot.reply_to(message, text, reply_markup=roles_keyboard(uid))


@bot.callback_query_handler(func=lambda call: call.data.startswith("setrole:"))
def callback_set_role(call: types.CallbackQuery):
    uid = str(call.from_user.id)
    role_key = call.data.split(":", 1)[1]
    roles = get_all_roles(uid)

    if role_key not in roles:
        bot.answer_callback_query(call.id, "Неизвестная роль.")
        return

    set_user_role(uid, role_key)
    role_name = roles[role_key]["name"]
    role_desc = roles[role_key]["description"]

    bot.answer_callback_query(call.id, f"Роль установлена: {role_name}")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✅ Роль установлена: <b>{role_name}</b>\n<i>{role_desc}</i>",
        parse_mode="HTML"
    )


@bot.callback_query_handler(func=lambda call: call.data == "create_role")
def callback_create_role(call: types.CallbackQuery):
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="➕ <b>Создание персонажа</b>\n\n"
             "Используй команду:\n"
             "<code>/createrole имя | промт | описание</code>\n\n"
             "Пример:\n"
             "<code>/createrole Глеб | Ты ворчливый старик. | Ворчливый дед</code>",
        parse_mode="HTML"
    )


@bot.callback_query_handler(func=lambda call: call.data == "delete_role_menu")
def callback_delete_role_menu(call: types.CallbackQuery):
    uid = str(call.from_user.id)
    roles = get_all_roles(uid)
    user_roles = {k: v for k, v in roles.items() if k.startswith("custom_") and v.get("owner") == uid}

    if not user_roles:
        bot.answer_callback_query(call.id, "У тебя нет своих персонажей.")
        return

    bot.answer_callback_query(call.id)
    markup = types.InlineKeyboardMarkup(row_width=1)
    for role_id, role_data in user_roles.items():
        markup.add(types.InlineKeyboardButton(f"🗑 {role_data['name']}", callback_data=f"delrole:{role_id}"))

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="🗑 <b>Выбери персонажа для удаления:</b>",
        parse_mode="HTML",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("delrole:"))
def callback_delete_role(call: types.CallbackQuery):
    uid = str(call.from_user.id)
    role_id = call.data.split(":", 1)[1]

    if delete_custom_role(role_id, uid):
        bot.answer_callback_query(call.id, "Персонаж удалён!")
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="✅ Персонаж успешно удалён."
        )
    else:
        bot.answer_callback_query(call.id, "Не удалось удалить персонажа.")


@bot.message_handler(commands=["createrole"])
def cmd_create_role(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    parts = message.text.split("|")

    if len(parts) < 3:
        log_cmd(uid, username, "createrole", "FAILED - not enough args")
        bot.reply_to(message,
            "Использование:\n"
            "<code>/createrole имя | промт | описание</code>\n\n"
            "Пример:\n"
            "<code>/createrole Глеб | Ты ворчливый старик. | Ворчливый дед</code>"
        )
        return

    name = parts[0].replace("/createrole", "").strip()
    prompt = parts[1].strip()
    description = parts[2].strip()

    if not name or not prompt or not description:
        log_cmd(uid, username, "createrole", "FAILED - empty fields")
        bot.reply_to(message, "Все три поля обязательны: имя, промт, описание.")
        return

    role_key = name.lower().replace(" ", "_")
    if add_custom_role(uid, role_key, name, prompt, description):
        log_cmd(uid, username, "createrole", f"name='{name}'")
        bot.reply_to(message,
            f"✅ Персонаж <b>{name}</b> создан!\n"
            f"Промт: <i>{prompt[:50]}...</i>\n"
            f"Описание: {description}\n\n"
            f"Используй /roles чтобы выбрать его."
        )
    else:
        bot.reply_to(message, "Не удалось создать персонажа. Возможно, такое имя уже существует.")


@bot.message_handler(commands=["deleterole"])
def cmd_delete_role(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    log_cmd(uid, username, "deleterole")
    increment_stat(uid, "commands")

    roles = get_all_roles(uid)
    user_roles = {k: v for k, v in roles.items() if k.startswith("custom_") and v.get("owner") == uid}

    if not user_roles:
        bot.reply_to(message, "У тебя нет созданных персонажей.")
        return

    text = "🗑 <b>Твои персонажи:</b>\n\n"
    for role_id, role_data in user_roles.items():
        text += f"• <b>{role_data['name']}</b> - /del_{role_id.split('_')[-1]}\n"
    text += "\nНажми на ссылку для удаления."
    bot.reply_to(message, text)


@bot.message_handler(commands=["gen"])
def cmd_gen(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "Использование: /gen &lt;описание картинки&gt;\nПример: /gen закат над морем")
        return

    prompt = parts[1].strip()
    log_cmd(uid, username, "gen", prompt)
    wait_msg = bot.reply_to(message, f"Генерирую изображение... подожди {AI_DELAY} сек.")

    def _gen():
        set_reply_context(message)
        url = generate_image(uid, prompt)
        bot.delete_message(message.chat.id, wait_msg.message_id)
        if url:
            increment_stat(uid, "images")
            bot.send_photo(message.chat.id, url, caption=f"Держи: <i>{prompt}</i>", reply_to_message_id=message.message_id)
        else:
            bot.reply_to(message, "Не удалось сгенерировать изображение.")

    threading.Thread(target=_gen, daemon=True).start()


@bot.message_handler(commands=["tts"])
def cmd_tts(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, f"Использование: /tts [спикер] &lt;текст&gt;\nСпикеры: {', '.join(SILERO_SPEAKERS)}\nПример: /tts Привет мир!")
        return

    text_part = parts[1].strip()
    speaker = DEFAULT_SPEAKER

    words = text_part.split(maxsplit=1)
    if words[0].lower() in SILERO_SPEAKERS:
        speaker = words[0].lower()
        text_part = words[1] if len(words) > 1 else ""

    if not text_part:
        bot.reply_to(message, "Укажите текст для озвучки.")
        return

    log_cmd(uid, username, "tts", f"speaker={speaker} | text={text_part[:50]}...")
    wait_msg = bot.reply_to(message, "Синтезирую речь (Silero)...")

    def _tts():
        set_reply_context(message)
        try:
            if not init_silero():
                log_tts(uid, text_part, speaker, False)
                bot.delete_message(message.chat.id, wait_msg.message_id)
                bot.reply_to(message, "Модуль TTS не загружен.")
                return

            sample_rate = 48000
            audio_path = silero_model.save_wav(text=text_part, speaker=speaker, sample_rate=sample_rate)

            if not audio_path or not os.path.exists(audio_path):
                log_tts(uid, text_part, speaker, False)
                bot.delete_message(message.chat.id, wait_msg.message_id)
                bot.reply_to(message, "Не удалось создать аудиофайл.")
                return

            with open(audio_path, "rb") as audio_file:
                bot.send_voice(message.chat.id, audio_file, reply_to_message_id=message.message_id, caption=f'<i>{text_part}</i>\nСпикер: {speaker}')

            os.remove(audio_path)
            bot.delete_message(message.chat.id, wait_msg.message_id)
            log_tts(uid, text_part, speaker, True)
        except Exception as e:
            log_err("TTS", f"Error for user={uid}: {e}")
            log_tts(uid, text_part, speaker, False)
            bot.delete_message(message.chat.id, wait_msg.message_id)
            bot.reply_to(message, f"Ошибка TTS: {e}")

    threading.Thread(target=_tts, daemon=True).start()


@bot.message_handler(commands=["meme"])
def cmd_meme(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    parts = message.text.split(maxsplit=1)

    if not message.reply_to_message or not message.reply_to_message.photo:
        bot.reply_to(message, "Ответь на сообщение с изображением командой /meme")
        return

    top_text = ""
    bottom_text = ""

    if len(parts) >= 2:
        text_content = parts[1].strip()
        if "." in text_content:
            text_parts = text_content.split(".", 1)
            top_text = text_parts[0].strip()
            bottom_text = text_parts[1].strip() if len(text_parts) > 1 else ""
        else:
            top_text = text_content

    if not top_text and not bottom_text:
        bot.reply_to(message, "Использование: /meme [текст сверху] . [текст снизу]\nПримеры:\n/meme КОГДА ТЫ . А Я")
        return

    log_cmd(uid, username, "meme", f"top='{top_text}' | bottom='{bottom_text}'")
    wait_msg = bot.reply_to(message, "Создаю мем...")

    def _meme():
        set_reply_context(message)
        try:
            file_info = bot.get_file(message.reply_to_message.photo[-1].file_id)
            downloaded = bot.download_file(file_info.file_path)
            meme_bytes = create_meme(downloaded, top_text, bottom_text)
            bot.delete_message(message.chat.id, wait_msg.message_id)

            if meme_bytes:
                log_meme(uid, top_text, bottom_text, True)
                bot.send_photo(message.chat.id, meme_bytes, reply_to_message_id=message.message_id)
            else:
                log_meme(uid, top_text, bottom_text, False)
                bot.reply_to(message, "Не удалось создать мем.")
        except Exception as e:
            log_err("MEME", f"Error for user={uid}: {e}")
            log_meme(uid, top_text, bottom_text, False)
            bot.delete_message(message.chat.id, wait_msg.message_id)
            bot.reply_to(message, f"Ошибка: {e}")

    threading.Thread(target=_meme, daemon=True).start()


@bot.message_handler(commands=["pizdec"])
def cmd_pizdec(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")

    if not message.reply_to_message:
        bot.reply_to(message,
            "Использование: ответь на сообщение командой <b>/pizdec &lt;уровень&gt;</b>\n"
            "Уровни: <b>1</b> (минимальное искажение) — <b>10</b> (полный пиздец)\n\n"
            "Пример: <code>/pizdec 5</code> (в ответ на сообщение)"
        )
        return

    replied_text = message.reply_to_message.text or message.reply_to_message.caption
    if not replied_text or not replied_text.strip():
        bot.reply_to(message, "Можно исказить только текстовое сообщение.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message,
            "Укажи уровень искажения от <b>1</b> до <b>10</b>.\n\n"
            "Пример: <code>/pizdec 7</code> (в ответ на сообщение)\n\n"
            "<b>1-3</b> — слабое искажение (опечатки)\n"
            "<b>4-5</b> — среднее (искажённые окончания)\n"
            "<b>6-10</b> — жёсткое (нечитаемые слова + мат)"
        )
        return

    try:
        level = int(parts[1].strip())
    except ValueError:
        bot.reply_to(message, "Уровень должен быть числом от 1 до 10.")
        return

    if level < 1 or level > 10:
        bot.reply_to(message, "Уровень должен быть от <b>1</b> до <b>10</b>.")
        return

    source_text = replied_text.strip()
    log_cmd(uid, username, "pizdec", f"level={level} | text={source_text[:50]}...")

    level_emojis = {1: "🟢", 2: "🟢", 3: "🟡", 4: "🟡", 5: "🟠", 6: "🟠", 7: "🔴", 8: "🔴", 9: "🔴", 10: "💥"}
    emoji = level_emojis.get(level, "🟢")

    result = distort_text(source_text, level)
    original_author = get_display_name(message.reply_to_message.from_user)
    bot.reply_to(message,
        f"<b></b>\n{result}"
    )
    log_info("PIZDEC", f"user={uid} level={level} done")


@bot.message_handler(commands=["trash"])
def cmd_trash(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    register_chat(message.chat.id)
    if message.from_user.username:
        update_username(uid, message.from_user.username)
    track_chat_member(message.chat.id, message.from_user)
    log_cmd(uid, username, "trash")
    increment_stat(uid, "commands")
    set_first_message_if_null(uid)

    can_collect, remaining = can_collect_trash(uid)
    if not can_collect:
        minutes = remaining // 60
        seconds = remaining % 60
        log_info("GAME", f"user={uid} trash on cooldown | {remaining}s remaining")
        bot.reply_to(message, f"Подожди ещё <b>{minutes} мин. {seconds} сек.</b> перед тем как искать окурки.")
        return

    rand = random.random()
    if rand < 0.05:
        count = 5
    elif rand < 0.15:
        count = 4
    elif rand < 0.30:
        count = 3
    elif rand < 0.55:
        count = 2
    else:
        count = 1

    set_trash_time(uid)
    new_total = add_cigarettes(uid, count)
    log_info("GAME", f"user={uid} found {count} cigarettes | total={new_total}")

    responses = {
        1: "Находишь один окурок на земле. Фу, какой позор.",
        2: "Роешься в мусорке и находишь 2 окурка. Неплохо!",
        3: "Везёт! Под кустом лежит 3 окурка!",
        4: "Джекпот! 4 окурка в одной пачке!",
        5: "Невероятная удача! 5 окурков! Ты настоящий мусорщик!",
    }

    bot.reply_to(message, f"{responses[count]}\nТеперь у тебя <b>{new_total}</b> окурков.")


@bot.message_handler(commands=["smoke"])
def cmd_smoke(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")

    if not use_cigarette(uid):
        cigs = get_cigarettes(uid)
        log_cmd(uid, username, "smoke", f"FAILED - no cigarettes | total={cigs}")
        bot.reply_to(message, f"У тебя нет окурков! Найди их командой /trash.\nТвои окурки: {cigs}")
        return

    increment_stat(uid, "smokes")
    cigs_left = get_cigarettes(uid)
    log_cmd(uid, username, "smoke", f"SUCCESS | left={cigs_left}")

    if random.random() < 0.5:
        responses = [
            "Ты глубоко затягиваешься... Чувствуешь приятное расслабление.",
            "Окурок оказался неплохим. Тебя накрывает волной спокойствия.",
            "Дым заполняет легкие... Стресс уходит.",
            "Ты выкурил окурок и чувствуешь себя прекрасно.",
        ]
    else:
        responses = [
            "Ты затягиваешься и начинаешь кашлять...",
            "О боже, этот окурок был ужасным!",
            "Срочно выплюнь! Окурок оказался ядовитым!",
            "Ты выкурил окурок и теперь жалеешь об этом.",
        ]

    bot.reply_to(message, f"{random.choice(responses)}\nОсталось окурков: {cigs_left}")


@bot.message_handler(commands=["roulette"])
def cmd_roulette(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")

    if is_user_dead(uid):
        log_cmd(uid, username, "roulette", "FAILED - already dead")
        bot.reply_to(message, "💀 Ты уже мёртв! Воскресни командой /revive")
        return

    log_cmd(uid, username, "roulette", "spinning...")
    bot.reply_to(message, "🎰 Русская рулетка...")

    def _roulette():
        set_reply_context(message)
        time.sleep(2)
        increment_stat(uid, "roulette_plays")

        if random.random() < ROULETTE_DEATH_CHANCE:
            set_user_dead(uid, True)
            increment_stat(uid, "roulette_deaths")
            log_info("GAME", f"user={uid} ROULETTE: DIED")
            bot.reply_to(message, "💥 <b>BANG!</b>\n\nПуля прошила твой череп. Ты мёртв.\nИспользуй /revive чтобы воскреснуть.")
        else:
            log_info("GAME", f"user={uid} ROULETTE: SURVIVED")
            bot.reply_to(message, "🔫 <b>КЛИК!</b>\n\nПусто! Повезло... в этот раз.\nСыграешь ещё?")

    threading.Thread(target=_roulette, daemon=True).start()


@bot.message_handler(commands=["revive"])
def cmd_revive(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")

    if not is_user_dead(uid):
        log_cmd(uid, username, "revive", "FAILED - already alive")
        bot.reply_to(message, "Ты и так жив! Зачем тебе /revive?")
        return

    set_user_dead(uid, False)
    log_cmd(uid, username, "revive", "SUCCESS")
    bot.reply_to(message, "✨ Ты воскрес! Добро пожаловать обратно в мир живых.")


@bot.message_handler(commands=["leaderboard"])
def cmd_leaderboard(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    register_chat(message.chat.id)
    if message.from_user.username:
        update_username(uid, message.from_user.username)
    track_chat_member(message.chat.id, message.from_user)
    log_cmd(uid, username, "leaderboard")
    increment_stat(uid, "commands")

    leaders = get_leaderboard()
    if not leaders:
        bot.reply_to(message, "Лидерборд пуст! Никто ещё не нашёл окурки.")
        return

    text = "🏆 <b>Лидерборд окурков</b>\n\n"
    medals = ["🥇", "🥈", "🥉"]

    for i, (uid, count, uname) in enumerate(leaders):
        medal = medals[i] if i < 3 else f"{i+1}."
        display_name = f"@{uname}" if uname else f"user_{uid}"
        text += f"{medal} {display_name} — {count} окурков\n"

    bot.reply_to(message, text)


@bot.message_handler(commands=["clear"])
def cmd_clear(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    log_cmd(uid, username, "clear")
    increment_stat(uid, "commands")
    clear_history(uid)
    bot.reply_to(message, "🧹 История диалога очищена! ИИ забыл всё, что ты ему писал.")


@bot.message_handler(commands=["reverse"])
def cmd_reverse(message: types.Message):
    increment_stat(get_uid(message), "commands")
    apply_image_effect(message, "reverse")


@bot.message_handler(commands=["blackwhite"])
def cmd_blackwhite(message: types.Message):
    increment_stat(get_uid(message), "commands")
    apply_image_effect(message, "blackwhite")


@bot.message_handler(commands=["brown"])
def cmd_brown(message: types.Message):
    increment_stat(get_uid(message), "commands")
    apply_image_effect(message, "brown")


@bot.message_handler(commands=["jpeg"])
def cmd_jpeg(message: types.Message):
    increment_stat(get_uid(message), "commands")
    apply_image_effect(message, "jpeg")


@bot.message_handler(commands=["invert"])
def cmd_invert(message: types.Message):
    increment_stat(get_uid(message), "commands")
    apply_image_effect(message, "invert")


@bot.message_handler(commands=["sepia"])
def cmd_sepia(message: types.Message):
    increment_stat(get_uid(message), "commands")
    apply_image_effect(message, "sepia")


@bot.message_handler(commands=["blur"])
def cmd_blur(message: types.Message):
    increment_stat(get_uid(message), "commands")
    apply_image_effect(message, "blur")


@bot.message_handler(commands=["ping"])
def cmd_ping(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    log_cmd(uid, username, "ping")
    increment_stat(uid, "commands")

    start_time = time.time()
    msg = bot.reply_to(message, "🏓 Проверяю пинг...")
    end_time = time.time()

    ping = round((end_time - start_time) * 1000, 2)
    bot.edit_message_text(chat_id=message.chat.id, message_id=msg.message_id, text=f"🏓 <b>Понг!</b>\n\nПинг: <b>{ping} мс</b>")


@bot.message_handler(commands=["qr"])
def cmd_qr(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "Использование: /qr &lt;текст или ссылка&gt;\nПример: /qr https://google.com")
        return

    text = parts[1].strip()
    log_cmd(uid, username, "qr", text[:50])

    def _qr():
        set_reply_context(message)
        qr_bytes = generate_qr_code(text)
        if qr_bytes:
            bot.send_photo(message.chat.id, qr_bytes, caption=f"QR-код для: <i>{text[:50]}</i>", reply_to_message_id=message.message_id)
        else:
            bot.reply_to(message, "Не удалось создать QR-код.")

    threading.Thread(target=_qr, daemon=True).start()


@bot.message_handler(commands=["weather"])
def cmd_weather(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "Использование: /weather &lt;город&gt;\nПример: /weather Москва")
        return

    city = parts[1].strip()
    log_cmd(uid, username, "weather", city)
    wait_msg = bot.reply_to(message, "🌤 Получаю погоду...")

    def _weather():
        set_reply_context(message)
        weather_data = get_weather(city)
        bot.delete_message(message.chat.id, wait_msg.message_id)

        if weather_data:
            bot.reply_to(message,
                f"🌤 <b>Погода: {weather_data['location']}</b>\n\n"
                f"🌡 Температура: <b>{weather_data['temp']}°C</b>\n"
                f"🤔 Ощущается как: <b>{weather_data['feels_like']}°C</b>\n"
                f"💧 Влажность: <b>{weather_data['humidity']}%</b>\n"
                f"💨 Ветер: <b>{weather_data['wind_speed']} км/ч</b>\n"
                f"☁️ Состояние: <i>{weather_data['description']}</i>"
            )
        else:
            bot.reply_to(message, f"Не удалось получить погоду для: {city}")

    threading.Thread(target=_weather, daemon=True).start()


@bot.message_handler(commands=["translate"])
def cmd_translate(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "Использование: /translate &lt;текст&gt;\nПеревод с русского на английский.")
        return

    text = parts[1].strip()
    log_cmd(uid, username, "translate", text[:50])
    wait_msg = bot.reply_to(message, "🌐 Перевожу...")

    def _translate():
        set_reply_context(message)
        try:
            prompt = f"Translate the following Russian text to English. Reply ONLY with the translation.\n\n{text}"
            response = ai_client.chat.completions.create(
                model="",
                messages=[{"role": "user", "content": prompt}],
                web_search=False,
            )
            translation = response.choices[0].message.content.strip()
            bot.delete_message(message.chat.id, wait_msg.message_id)
            bot.reply_to(message, f"🌐 <b>Перевод:</b>\n\n<i>Оригинал:</i> {text}\n<i>Перевод:</i> {translation}")
        except Exception as e:
            log_err("TRANSLATE", f"Error for user={uid}: {e}")
            bot.delete_message(message.chat.id, wait_msg.message_id)
            bot.reply_to(message, f"Ошибка перевода: {e}")

    threading.Thread(target=_translate, daemon=True).start()


@bot.message_handler(commands=["8ball"])
def cmd_8ball(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "Использование: /8ball &lt;вопрос&gt;\nПример: /8ball Стоит ли мне сегодня курить?")
        return

    question = parts[1].strip()
    answer = random.choice(EIGHT_BALL_ANSWERS)
    log_cmd(uid, username, "8ball", question[:50])
    bot.reply_to(message, f"🎱 <b>Магический шар</b>\n\n❓ <i>{question}</i>\n👉 {answer}")


@bot.message_handler(commands=["dice"])
def cmd_dice(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    parts = message.text.split(maxsplit=1)

    dice_notation = "d6"
    if len(parts) >= 2 and parts[1].strip():
        dice_notation = parts[1].strip().lower()

    match = re.match(r"^(\d*)d(\d+)$", dice_notation)
    if not match:
        bot.reply_to(message, "Использование: /dice [dN]\nПримеры: /dice, /dice d20, /dice 3d6")
        return

    count = int(match.group(1)) if match.group(1) else 1
    sides = int(match.group(2))

    if count < 1 or count > 100:
        bot.reply_to(message, "Количество кубиков: от 1 до 100.")
        return
    if sides < 2 or sides > 1000:
        bot.reply_to(message, "Граней у кубика: от 2 до 1000.")
        return

    rolls = [random.randint(1, sides) for _ in range(count)]
    total = sum(rolls)
    log_cmd(uid, username, "dice", f"{dice_notation} | rolls={rolls}")

    if count == 1:
        bot.reply_to(message, f"🎲 <b>d{sides}</b>: выпало <b>{rolls[0]}</b>")
    else:
        rolls_str = ", ".join(str(r) for r in rolls)
        bot.reply_to(message, f"🎲 <b>{count}d{sides}</b>\n\nБроски: {rolls_str}\nСумма: <b>{total}</b>")


@bot.message_handler(commands=["choose"])
def cmd_choose(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "Использование: /choose &lt;опция1 | опция2 | ...&gt;\nПример: /choose пицца | суши | бургер")
        return

    options_text = parts[1].strip()
    options = [o.strip() for o in options_text.split("|") if o.strip()]

    if len(options) < 2:
        bot.reply_to(message, "Нужно минимум 2 варианта, разделённых |")
        return

    choice = random.choice(options)
    log_cmd(uid, username, "choose", f"options={len(options)} | choice={choice}")
    bot.reply_to(message, f"🤔 <b>Случайный выбор</b>\n\nВарианты: {', '.join(options)}\n👉 Выбрано: <b>{choice}</b>")


@bot.message_handler(commands=["remind"])
def cmd_remind(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    parts = message.text.split(maxsplit=2)

    if len(parts) < 3:
        bot.reply_to(message, "Использование: /remind &lt;время&gt; &lt;текст&gt;\nВремя: 30s, 10m, 2h, 1d\nПример: /remind 10m покурить")
        return

    time_str = parts[1].strip()
    text = parts[2].strip()

    seconds = parse_remind_time(time_str)
    if seconds is None:
        bot.reply_to(message, "Не понял время. Используй формат: 30s, 10m, 2h, 1d")
        return

    if seconds > 7 * 86400:
        bot.reply_to(message, "Максимум — 7 дней.")
        return

    get_or_create_user(uid)
    remind_at = time.time() + seconds
    reminder_id = add_reminder(uid, message.chat.id, text, remind_at)
    log_cmd(uid, username, "remind", f"id={reminder_id} | time={time_str} | text={text[:50]}")

    if seconds < 60:
        time_display = f"{seconds} сек."
    elif seconds < 3600:
        time_display = f"{seconds // 60} мин."
    elif seconds < 86400:
        time_display = f"{seconds // 3600} ч."
    else:
        time_display = f"{seconds // 86400} д."

    bot.reply_to(message, f"⏰ <b>Напоминание установлено!</b>\n\nЧерез: <b>{time_display}</b>\nТекст: <i>{text}</i>\nID: {reminder_id}")


@bot.message_handler(commands=["reminders"])
def cmd_reminders(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    log_cmd(uid, username, "reminders")

    reminders = get_user_reminders(uid)
    if not reminders:
        bot.reply_to(message, "У тебя нет активных напоминаний.")
        return

    text = "⏰ <b>Твои напоминания:</b>\n\n"
    for r in reminders:
        remaining = r["remind_at"] - time.time()
        if remaining < 60:
            time_display = f"{int(remaining)} сек."
        elif remaining < 3600:
            time_display = f"{int(remaining // 60)} мин."
        elif remaining < 86400:
            time_display = f"{int(remaining // 3600)} ч."
        else:
            time_display = f"{int(remaining // 86400)} д."
        text += f"• <b>#{r['id']}</b> (через {time_display}): {r['text']}\n"
    text += "\nДля удаления: /delremind &lt;ID&gt;"
    bot.reply_to(message, text)


@bot.message_handler(commands=["delremind"])
def cmd_delremind(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "Использование: /delremind &lt;ID&gt;")
        return

    try:
        reminder_id = int(parts[1].strip())
    except ValueError:
        bot.reply_to(message, "ID должен быть числом.")
        return

    if delete_reminder(reminder_id, uid):
        log_cmd(uid, username, "delremind", f"id={reminder_id} SUCCESS")
        bot.reply_to(message, f"✅ Напоминание #{reminder_id} удалено.")
    else:
        log_cmd(uid, username, "delremind", f"id={reminder_id} FAILED")
        bot.reply_to(message, f"Напоминание #{reminder_id} не найдено или не твоё.")


# ═══════════════════════════════════════════════════════════════════════════════
# Enhanced Stats Command (with matplotlib graph) — supports /stats {username}
# ═══════════════════════════════════════════════════════════════════════════════

def _build_stats_text(target_uid: str, owner_label: str) -> str:
    """Build the stats text for a given user id. owner_label is 'Твоя' or display name."""
    stats = get_stats(target_uid)
    cigs = get_cigarettes(target_uid)
    rubles = get_rubles(target_uid)
    real_cigs = get_real_cigarettes(target_uid)
    role_key = get_user_role(target_uid)
    roles = get_all_roles(target_uid)
    current_role = roles.get(role_key, {}).get("name", "Обычный ассистент")
    clan = get_user_clan(target_uid)
    awards = get_awards(target_uid)
    first_msg = get_first_message_date(target_uid)

    survival_rate = "—"
    roulette_plays = stats.get("roulette_plays", 0)
    roulette_deaths = stats.get("roulette_deaths", 0)
    if roulette_plays > 0:
        survival_rate = f"{round((roulette_plays - roulette_deaths) / roulette_plays * 100, 1)}%"

    clan_text = f"🏷 Клан: <b>{clan['name']}</b> (реп. {clan['reputation']})" if clan else "🏷 Клан: <i>не состоит</i>"

    awards_text = ""
    if awards:
        awards_text = "\n\n🏅 <b>Награды:</b>\n"
        for a in awards:
            awards_text += f"  • {a['name']} ({a['date']})\n"

    first_msg_text = f"\n📅 Первое сообщение: <b>{first_msg}</b>" if first_msg else ""

    return (
        f"📊 <b>Статистика — {owner_label}</b>\n\n"
        f"🎭 Роль: <b>{current_role}</b>\n"
        f"{clan_text}\n"
        f"💀 Статус: {'Мёртв' if is_user_dead(target_uid) else 'Жив'}\n\n"
        f"🚬 Окурки: <b>{cigs}</b>\n"
        f"💰 Рубли: <b>{rubles}₽</b>\n"
        f"🚬 Сигареты: <b>{real_cigs}</b>\n\n"
        f"💬 Сообщений (всего): <b>{stats.get('messages', 0)}</b>\n"
        f"🤖 С ботом: <b>{sum(c for _, c in get_daily_activity(target_uid))}</b>\n"
        f"💭 В чате: <b>{sum(c for _, c in get_daily_chat_activity(target_uid))}</b>\n"
        f"⚙️ Команд: <b>{stats.get('commands', 0)}</b>\n"
        f"🖼 Картинок: <b>{stats.get('images', 0)}</b>\n"
        f"🚬 Выкурено: <b>{stats.get('smokes', 0)}</b>\n"
        f"🎰 Рулеток: <b>{roulette_plays}</b> (выжил в {survival_rate})"
        f"{first_msg_text}"
        f"{awards_text}"
    )


@bot.message_handler(commands=["stats"])
def cmd_stats(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    log_cmd(uid, username, "stats")

    parts = message.text.split(maxsplit=1)
    target_uid = uid
    owner_label = "Твоя статистика"

    # Priority 1: reply to a message → show that user's stats
    if message.reply_to_message and not message.reply_to_message.from_user.is_bot:
        target_user = message.reply_to_message.from_user
        target_uid = str(target_user.id)
        owner_label = get_display_name(target_user)
        get_or_create_user(target_uid)
        if target_user.username:
            update_username(target_uid, target_user.username)
        log_cmd(uid, username, "stats", f"target={target_uid}")
    # Priority 2: /stats {username}
        # Priority 2: /stats {username}
    elif len(parts) >= 2 and parts[1].strip():
        username_query = parts[1].strip().lstrip("@").lower()
        
        # Проверяем, что передан именно юзернейм (состоит из допустимых символов и не пустой)
        if not username_query or not re.match(r"^[a-zA-Z0-9_]{3,32}$", username_query):
            bot.reply_to(message, "Пожалуйста, укажите корректный юзернейм пользователя.")
            return
            
        found = find_user_by_username(username_query)
        if found:
            target_uid = found["id"]
            owner_label = f"@{found['username']}" if found["username"] else f"user_{found['id']}"
            log_cmd(uid, username, "stats", f"target={target_uid}")
        else:
            bot.reply_to(message, f"Пользователь @{username_query} не найден в базе бота.")
            return
    stats_text = _build_stats_text(target_uid, owner_label)

    wait_msg = bot.reply_to(message, "📊 Генерирую график общительности...")

    def _send_stats():
        set_reply_context(message)
        graph_bytes = generate_activity_graph(target_uid)
        try:
            bot.delete_message(message.chat.id, wait_msg.message_id)
        except:
            pass

        if graph_bytes:
            bot.send_photo(message.chat.id, graph_bytes, caption=stats_text, reply_to_message_id=message.message_id)
        else:
            stats_text_no_graph = stats_text + "\n\n<i>График появится, как только пользователь начнёт проявлять активность в чате.</i>"
            bot.reply_to(message, stats_text_no_graph)

    threading.Thread(target=_send_stats, daemon=True).start()


@bot.message_handler(commands=["top_chat"])
def cmd_top_chat(message: types.Message):
    uid = get_uid(message)
    increment_stat(uid, "commands")
    log_cmd(uid, message.from_user.username or "unknown", "top_chat")
    top = get_top_talkative("chat", 15, chat_id=message.chat.id)
    if not top:
        bot.reply_to(message, "📭 Пока нет данных об общительности в этом чате.")
        return
    text = "💭 <b>Топ общительных в этом чате</b>\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, (user_id, count, uname) in enumerate(top):
        medal = medals[i] if i < 3 else f"{i + 1}."
        name = f"@{uname}" if uname else f"user_{user_id}"
        text += f"{medal} {name} — <b>{count}</b> сообщ.\n"
    bot.reply_to(message, text)


@bot.message_handler(commands=["top_bot"])
def cmd_top_bot(message: types.Message):
    uid = get_uid(message)
    increment_stat(uid, "commands")
    log_cmd(uid, message.from_user.username or "unknown", "top_bot")
    top = get_top_talkative("bot", 15)
    if not top:
        bot.reply_to(message, "📭 Пока нет данных об общительности с ботом.")
        return
    text = "🤖 <b>Топ общительных с ботом</b>\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, (user_id, count, uname) in enumerate(top):
        medal = medals[i] if i < 3 else f"{i + 1}."
        name = f"@{uname}" if uname else f"user_{user_id}"
        text += f"{medal} {name} — <b>{count}</b> сообщ.\n"
    bot.reply_to(message, text)


@bot.message_handler(commands=["say"])
def cmd_say(message: types.Message):
    uid = get_uid(message)
    increment_stat(uid, "commands")
    log_cmd(uid, message.from_user.username or "unknown", "say")
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "Использование: /say &lt;текст&gt;\nОтправляет сообщение без изменений.")
        return
    bot.send_message(message.chat.id, parts[1], parse_mode=None, reply_to_message_id=message.message_id)


@bot.message_handler(commands=["delbot"])
def cmd_delbot(message: types.Message):
    uid = get_uid(message)
    increment_stat(uid, "commands")
    log_cmd(uid, message.from_user.username or "unknown", "delbot")

    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Использование: /delbot &lt;кол-во&gt;\n"
                               "Удаляет указанное число последних сообщений бота в этом чате.")
        return

    try:
        count = int(parts[1])
    except ValueError:
        bot.reply_to(message, "Количество должно быть числом.")
        return

    if count <= 0 or count > 100:
        bot.reply_to(message, "Укажи число от 1 до 100.")
        return

    deleted, failed = delete_last_bot_messages(message.chat.id, count)
    extra = f" Не удалось удалить: <b>{failed}</b>." if failed else ""
    bot.reply_to(message, f"🗑 Удалено сообщений бота: <b>{deleted}</b>.{extra}")


@bot.message_handler(commands=["birja"])
def cmd_birja(message: types.Message):
    uid = get_uid(message)
    increment_stat(uid, "commands")
    log_cmd(uid, message.from_user.username or "unknown", "birja")
    send_birja_message(
        message.chat.id,
        reply_to=message.message_id,
        thread_id=get_message_thread_id(message),
    )


@bot.message_handler(commands=["wallet"])
def cmd_wallet(message: types.Message):
    uid = get_uid(message)
    increment_stat(uid, "commands")
    log_cmd(uid, message.from_user.username or "unknown", "wallet")
    send_wallet_message(
        message.chat.id, uid,
        reply_to=message.message_id,
        thread_id=get_message_thread_id(message),
    )


@bot.message_handler(commands=["bank"])
def cmd_bank(message: types.Message):
    uid = get_uid(message)
    increment_stat(uid, "commands")
    log_cmd(uid, message.from_user.username or "unknown", "bank")
    send_bank_message(
        message.chat.id, uid,
        reply_to=message.message_id,
        thread_id=get_message_thread_id(message),
    )


@bot.message_handler(commands=["loans"])
def cmd_loans(message: types.Message):
    uid = get_uid(message)
    increment_stat(uid, "commands")
    log_cmd(uid, message.from_user.username or "unknown", "loans")
    text = format_loans_board(uid)
    bot.send_message(
        message.chat.id, text, parse_mode="HTML",
        reply_to_message_id=message.message_id,
        message_thread_id=get_message_thread_id(message),
    )


@bot.message_handler(commands=["deposits"])
def cmd_deposits(message: types.Message):
    uid = get_uid(message)
    increment_stat(uid, "commands")
    log_cmd(uid, message.from_user.username or "unknown", "deposits")
    text = format_deposits_board(uid)
    bot.send_message(
        message.chat.id, text, parse_mode="HTML",
        reply_to_message_id=message.message_id,
        message_thread_id=get_message_thread_id(message),
    )


@bot.message_handler(commands=["pay"])
def cmd_pay(message: types.Message):
    uid = get_uid(message)
    increment_stat(uid, "commands")
    log_cmd(uid, message.from_user.username or "unknown", "pay")
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(
            message,
            "💳 <b>Досрочное погашение кредита</b>\n\n"
            "Использование: <code>/pay &lt;номер_кредита&gt;</code>\n\n"
            "Пример: <code>/pay 5</code> — погасить кредит #5\n\n"
            "Узнай номер кредита через /loans",
            parse_mode="HTML"
        )
        return
    
    try:
        loan_id = int(parts[1].strip())
    except ValueError:
        bot.reply_to(message, "❌ Номер кредита должен быть числом.", parse_mode="HTML")
        return
    
    ok, result = repay_bank_loan(uid, loan_id)
    log_cmd(uid, message.from_user.username or "unknown", "pay", f"#{loan_id} {'OK' if ok else 'FAIL'}")
    bot.reply_to(message, result, parse_mode="HTML")
    if ok:
        send_bank_message(message.chat.id, uid, reply_to=message.message_id,
                          thread_id=get_message_thread_id(message))


@bot.message_handler(commands=["to_cig"])
def cmd_to_cig(message: types.Message):
    uid = get_uid(message)
    increment_stat(uid, "commands")
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(
            message,
            f"Использование: /to_cig &lt;окурки&gt;\n"
            f"Курс ЦБ: <b>{BANK_CONV_BUTTS_PER_CIG}</b> окурков = 1 сигарета\n"
            f"Пример: <code>/to_cig 500</code> → 5 сигарет"
        )
        return
    amount, err = parse_bank_convert_amount(parts[1].strip())
    if err:
        bot.reply_to(message, err, parse_mode="HTML")
        return
    ok, result = convert_butts_to_cigarettes(uid, amount)
    log_cmd(uid, message.from_user.username or "unknown", "to_cig",
            f"{amount} {'OK' if ok else 'FAIL'}")
    bot.reply_to(message, result, parse_mode="HTML")


@bot.message_handler(commands=["to_rub"])
def cmd_to_rub(message: types.Message):
    uid = get_uid(message)
    increment_stat(uid, "commands")
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(
            message,
            f"Использование: /to_rub &lt;сигареты&gt;\n"
            f"Курс ЦБ: <b>{BANK_CONV_CIG_PER_RUBLE}</b> сигарет = 1₽\n"
            f"Пример: <code>/to_rub 10</code> → 2₽"
        )
        return
    amount, err = parse_bank_convert_amount(parts[1].strip())
    if err:
        bot.reply_to(message, err, parse_mode="HTML")
        return
    ok, result = convert_cigarettes_to_rubles(uid, amount)
    log_cmd(uid, message.from_user.username or "unknown", "to_rub",
            f"{amount} {'OK' if ok else 'FAIL'}")
    bot.reply_to(message, result, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("bank:"))
def callback_bank(call: types.CallbackQuery):
    uid = str(call.from_user.id)
    action = call.data.split(":", 1)[1]
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    thread_id = get_message_thread_id(call.message)
    reply_kw = reply_kwargs_for_call(call)

    if action == "refresh":
        send_bank_message(chat_id, uid, thread_id=thread_id, message_id=call.message.message_id)
        return

    if action == "withdraw":
        ok, result = withdraw_bank_deposits(uid)
        bot.send_message(chat_id, result, parse_mode="HTML", **reply_kw)
        if ok:
            send_bank_message(chat_id, uid, thread_id=thread_id)
        return

    if action == "my_loans":
        text = format_loans_board(uid)
        bot.send_message(chat_id, text, parse_mode="HTML", **reply_kw)
        return

    if action == "my_deposits":
        text = format_deposits_board(uid)
        bot.send_message(chat_id, text, parse_mode="HTML", **reply_kw)
        return

    prompts = {
        "loan": (
            "💳 <b>Кредит Центробанка</b>\n\n"
            f"Ставка сейчас: <b>{get_bank_credit_rate_pct()}%</b> на 3 дня.\n"
            "Ответь — сколько взять:\n"
            "<code>100 o</code> — окурки\n"
            "<code>5 c</code> — сигареты\n"
            "<code>10 r</code> — рубли"
        ),
        "deposit": (
            "🏦 <b>Вклад в Центробанк</b>\n\n"
            f"Доходность сейчас: <b>{get_bank_deposit_yield_pct()}%</b> за 3 дня.\n"
            "Ответь — сколько вложить:\n"
            "<code>100 o</code> — окурки\n"
            "<code>5 c</code> — сигареты\n"
            "<code>10 r</code> — рубли"
        ),
        "conv_o": (
            f"🔄 <b>Окурки → сигареты</b>\n\n"
            f"Курс: <b>{BANK_CONV_BUTTS_PER_CIG}</b> окурков = 1 сигарета\n"
            "Ответь — сколько <b>окурков</b> обменять (целое число):\n"
            f"<code>{BANK_CONV_BUTTS_PER_CIG}</code> или <code>500</code>"
        ),
        "conv_c": (
            f"🔄 <b>Сигареты → рубли</b>\n\n"
            f"Курс: <b>{BANK_CONV_CIG_PER_RUBLE}</b> сигарет = 1₽\n"
            "Ответь — сколько <b>сигарет</b> обменять (целое число):\n"
            f"<code>{BANK_CONV_CIG_PER_RUBLE}</code> или <code>10</code>"
        ),
    }
    if action not in prompts:
        return

    prompt = bot.send_message(chat_id, prompts[action], parse_mode="HTML",
                              reply_markup=types.ForceReply(selective=True), **reply_kw)
    BANK_PENDING[uid] = {
        "action": action,
        "prompt_id": prompt.message_id,
        "chat_id": chat_id,
        "thread_id": thread_id,
    }


@bot.message_handler(func=lambda m: (
    m.content_type == "text"
    and str(m.from_user.id) in BANK_PENDING
    and m.reply_to_message is not None
    and m.reply_to_message.message_id == BANK_PENDING[str(m.from_user.id)]["prompt_id"]
), content_types=["text"])
def handle_bank_reply(message: types.Message):
    uid = str(message.from_user.id)
    pending = BANK_PENDING.pop(uid, None)
    if not pending:
        return

    action = pending["action"]
    text = (message.text or "").strip()
    reply_kw = reply_kwargs_for_message(message)

    if action == "conv_o":
        amount, err = parse_bank_convert_amount(text)
        if err:
            bot.send_message(message.chat.id, err, parse_mode="HTML", **reply_kw)
            return
        ok, result = convert_butts_to_cigarettes(uid, amount)
        log_cmd(uid, message.from_user.username or "unknown", "to_cig",
                f"{amount} {'OK' if ok else 'FAIL'}")
        bot.send_message(message.chat.id, result, parse_mode="HTML", **reply_kw)
        if ok:
            send_bank_message(message.chat.id, uid,
                              thread_id=get_message_thread_id(message))
        return

    if action == "conv_c":
        amount, err = parse_bank_convert_amount(text)
        if err:
            bot.send_message(message.chat.id, err, parse_mode="HTML", **reply_kw)
            return
        ok, result = convert_cigarettes_to_rubles(uid, amount)
        log_cmd(uid, message.from_user.username or "unknown", "to_rub",
                f"{amount} {'OK' if ok else 'FAIL'}")
        bot.send_message(message.chat.id, result, parse_mode="HTML", **reply_kw)
        if ok:
            send_bank_message(message.chat.id, uid,
                              thread_id=get_message_thread_id(message))
        return

    amount, currency, err = parse_bank_amount_input(text)
    if err:
        bot.send_message(message.chat.id, err, parse_mode="HTML", **reply_kw)
        return

    if action == "loan":
        ok, result = issue_bank_loan(uid, currency, amount)
        log_cmd(uid, message.from_user.username or "unknown", "bank_loan",
                f"{amount} {currency} {'OK' if ok else 'FAIL'}")
    elif action == "deposit":
        ok, result = create_bank_deposit(uid, currency, amount)
        log_cmd(uid, message.from_user.username or "unknown", "bank_deposit",
                f"{amount} {currency} {'OK' if ok else 'FAIL'}")
    else:
        ok, result = False, "Неизвестная операция."

    bot.send_message(message.chat.id, result, parse_mode="HTML", **reply_kw)
    if ok:
        send_bank_message(message.chat.id, uid,
                          thread_id=get_message_thread_id(message))


@bot.callback_query_handler(func=lambda call: call.data.startswith("crypto:"))
def callback_crypto(call: types.CallbackQuery):
    uid = str(call.from_user.id)
    action = call.data.split(":", 1)[1]
    bot.answer_callback_query(call.id)

    initiator_id = get_initiator_reply_id(call.message) or call.message.message_id
    chat_id = call.message.chat.id
    thread_id = get_message_thread_id(call.message)
    reply_kw = reply_kwargs_for_call(call)

    prompts = {
        "buy": (
            "🟢 <b>Покупка COK</b>\n\n"
            "Ответь на это сообщение — сколько валюты потратить:\n"
            "<code>100 o</code> — потратить 100 окурков\n"
            "<code>5 c</code> — потратить 5 сигарет\n"
            "<code>10 r</code> — потратить 10₽\n\n"
            "<i>COK начисляется дробным числом. Валюта списывается целыми.</i>"
        ),
        "sell": (
            "🔴 <b>Продажа COK</b>\n\n"
            "Ответь на это сообщение — сколько COK продать:\n"
            "<code>10</code>"
        ),
        "transfer": (
            "💸 <b>Перевод COK</b>\n\n"
            "Ответь на это сообщение:\n"
            "<code>@username 10</code> — кому и сколько COK"
        ),
    }

    if action not in prompts:
        return

    prompt = bot.send_message(
        chat_id,
        prompts[action],
        parse_mode="HTML",
        reply_markup=types.ForceReply(selective=True),
        **reply_kw,
    )
    CRYPTO_PENDING[uid] = {
        "action": action,
        "prompt_id": prompt.message_id,
        "chat_id": chat_id,
        "initiator_id": initiator_id,
        "thread_id": thread_id,
    }


@bot.message_handler(func=lambda m: (
    m.content_type == "text"
    and str(m.from_user.id) in CRYPTO_PENDING
    and m.reply_to_message is not None
    and m.reply_to_message.message_id == CRYPTO_PENDING[str(m.from_user.id)]["prompt_id"]
), content_types=["text"])
def handle_crypto_reply(message: types.Message):
    uid = str(message.from_user.id)
    pending = CRYPTO_PENDING.pop(uid, None)
    if not pending:
        return

    text = (message.text or "").strip()
    action = pending["action"]

    def _crypto_reply(result_text: str) -> None:
        bot.send_message(
            message.chat.id,
            result_text,
            **reply_kwargs_for_message(message),
        )

    if action == "buy":
        amount, pay_curr, err = parse_crypto_buy_input(text)
        if err:
            _crypto_reply(err)
            return
        ok, result = crypto_buy(uid, amount, pay_curr)
        log_cmd(uid, message.from_user.username or "unknown", "crypto_buy",
                f"pay {int(math.floor(amount))} {pay_curr} {'OK' if ok else 'FAIL'}")
        _crypto_reply(result)
        return

    if action == "sell":
        try:
            amount = float(text.replace(",", "."))
        except ValueError:
            _crypto_reply("Количество должно быть числом.")
            return
        ok, result = crypto_sell(uid, amount)
        log_cmd(uid, message.from_user.username or "unknown", "crypto_sell", f"{amount} {'OK' if ok else 'FAIL'}")
        _crypto_reply(result)
        return

    if action == "transfer":
        target_uid, amount, err = parse_crypto_transfer_input(text)
        if err:
            _crypto_reply(err)
            return
        ok, result = crypto_transfer(uid, target_uid, amount)
        if ok:
            target_name = target_uid
            found = db_execute(
                "SELECT username FROM users WHERE id = %s", (target_uid,),
                fetch=True, fetch_one=True
            )
            if found and found[0]:
                target_name = f"@{found[0]}"
            result = f"✅ Переведено <b>{amount:.4f}</b> COK пользователю <b>{target_name}</b>"
        log_cmd(uid, message.from_user.username or "unknown", "crypto_transfer", f"{target_uid} {amount} {'OK' if ok else 'FAIL'}")
        _crypto_reply(result)


@bot.message_handler(commands=["quote"])
def cmd_quote(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")

    if not message.reply_to_message:
        bot.reply_to(message, "Ответь на сообщение командой /quote чтобы сохранить его.")
        return

    replied = message.reply_to_message
    text = replied.text or replied.caption
    photo_file_id = None
    if replied.photo:
        photo_file_id = replied.photo[-1].file_id
    if not text or not text.strip():
        if not photo_file_id:
            bot.reply_to(message, "Можно сохранять только текстовые сообщения или фото с подписью.")
            return
        text = "📷"

    author_name = replied.from_user.first_name or ""
    if replied.from_user.username:
        author_name = f"@{replied.from_user.username}"

    total = add_quote(message.chat.id, text.strip(), author_name, photo_file_id)
    log_cmd(uid, username, "quote", f"saved from {author_name} | total={total}")
    bot.reply_to(message, f"💬 Цитата сохранена! Всего цитат в чате: <b>{total}</b>")


# ═══════════════════════════════════════════════════════════════════════════════
# Ship Command
# ═══════════════════════════════════════════════════════════════════════════════

@bot.message_handler(commands=["ship"])
def cmd_ship(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    register_chat(message.chat.id)
    track_chat_member(message.chat.id, message.from_user)
    increment_stat(uid, "commands")
    log_cmd(uid, username, "ship")

    members = get_chat_members(message.chat.id)
    if len(members) < 2:
        bot.reply_to(message, "В чате слишком мало людей для шипперинга. Нужно минимум 2 активных пользователя.")
        return

    pair = random.sample(members, 2)
    user1 = pair[0][1]
    user2 = pair[1][1]

    bot.reply_to(message,
        f"💕 <b>ШИППЕРИМ</b>\n\n"
        f"{user1}, {user2}. Любите друг друга. ❤️"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Shhh (Secret Whisper) Command
# ═══════════════════════════════════════════════════════════════════════════════

@bot.message_handler(commands=["shhh"])
def cmd_shhh(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    register_chat(message.chat.id)
    track_chat_member(message.chat.id, message.from_user)
    increment_stat(uid, "commands")

    parts = message.text.split(maxsplit=2)
    if len(parts) < 3 or not parts[2].strip():
        try:
            bot.send_message(message.from_user.id,
                "Использование: /shhh <кому> <текст>\n"
                "Пример: /shhh @username Я тайно восхищаюсь тобой\n\n"
                "Текст отправляется как секретное сообщение — получатель увидит его только в личном чате с ботом."
            )
        except Exception:
            bot.reply_to(message, "Напиши мне в личку, чтобы узнать как использовать /shhh")
        # Delete the command message so nobody sees the target username
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except Exception:
            pass
        return

    target_query = parts[1].strip()
    secret_text = parts[2].strip()

    # Delete the command message immediately so nobody in the chat sees the target or text
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass

    # Find the target user by username
    found = find_user_by_username(target_query)
    if not found:
        try:
            bot.send_message(message.from_user.id,
                f"Пользователь {target_query} не найден в базе бота. "
                "Возможно, он ещё не писал боту."
            )
        except Exception:
            bot.reply_to(message, "Пользователь не найден. Напиши мне в личку для деталей.")
        return

    target_uid = found["id"]
    target_name = f"@{found['username']}" if found["username"] else f"user_{found['id']}"
    from_name = get_display_name(message.from_user)

    whisper_id = create_whisper(uid, from_name, target_uid, target_name, secret_text)
    if not whisper_id:
        try:
            bot.send_message(message.from_user.id, "Не удалось создать секретное сообщение.")
        except Exception:
            pass
        return

    log_cmd(uid, username, "shhh", f"target={target_uid} | id={whisper_id}")

    # Notify the sender in private chat
    try:
        bot.send_message(message.from_user.id,
            f"🤫 Секрет отправлен пользователю <b>{target_name}</b>.\n"
            f"Сообщение видно только получателю в личном чате с ботом."
        )
    except Exception:
        pass

    # Send the whisper directly to the recipient's private chat
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("👀 Прочитать секрет", callback_data=f"reveal_whisper:{whisper_id}"))

    try:
        bot.send_message(target_uid,
            f"🤫 <b>Тебе нашептали секрет!</b>\n\n"
            f"От кого: <i>секретно</i>\n\n"
            f"Нажми на кнопку ниже, чтобы прочитать.",
            reply_markup=markup
        )
    except Exception as e:
        log_err("WHISPER", f"Failed to send whisper card to target={target_uid}: {e}")
        try:
            bot.send_message(message.from_user.id,
                f"Не удалось отправить секрет пользователю {target_name}. "
                "Возможно, он не начинал диалог с ботом."
            )
        except Exception:
            pass


@bot.callback_query_handler(func=lambda call: call.data.startswith("reveal_whisper:"))
def callback_reveal_whisper(call: types.CallbackQuery):
    caller_id = str(call.from_user.id)
    whisper_id_str = call.data.split(":", 1)[1]

    try:
        whisper_id = int(whisper_id_str)
    except ValueError:
        bot.answer_callback_query(call.id, "Неверный идентификатор.", show_alert=True)
        return

    whisper = get_whisper(whisper_id)
    if not whisper:
        bot.answer_callback_query(call.id, "Секретное сообщение не найдено или удалено.", show_alert=True)
        return

    if caller_id != whisper["to_id"] and caller_id != whisper["from_id"]:
        bot.answer_callback_query(call.id, "🚫 Этот секрет предназначен не для тебя!", show_alert=True)
        return

    sender_label = whisper['from_name'] if caller_id == whisper["to_id"] else "ты сам себе"
    secret_text = (
        f"🤫 Секретное сообщение\n\n"
        f"От: {sender_label}\n"
        f"Текст: {whisper['secret_text']}"
    )
    bot.answer_callback_query(call.id, secret_text, show_alert=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Mines Game
# ═══════════════════════════════════════════════════════════════════════════════

MINES_GRID_SIZE = 5
MINES_COUNT = 4
MINES_MULTIPLIER_STEP = 1.10  # +10% per opened cell

# In-memory game sessions: uid -> {bet, currency, mines: set[int], opened: set[int], msg_id}
mines_sessions: dict = {}

_CURRENCY_MAP = {
    "o": ("cigarettes", "окурков", get_cigarettes, add_cigarettes),
    "c": ("real_cigarettes", "сигарет", get_real_cigarettes, add_real_cigarettes),
    "r": ("rubles", "рублей", get_rubles, add_rubles),
}


def _mines_multiplier(opened_count: int) -> float:
    if opened_count <= 0:
        return 1.0
    return round(MINES_MULTIPLIER_STEP ** opened_count, 2)


def _mines_render_text(uid: str) -> str:
    s = mines_sessions.get(uid)
    if not s:
        return ""
    opened = len(s["opened"])
    mult = _mines_multiplier(opened)
    cur_name = _CURRENCY_MAP[s["currency"]][1]
    potential = int(s["bet"] * mult)
    return (
        f"💣 <b>Мины</b>\n\n"
        f"Ставка: <b>{s['bet']}</b> {cur_name}\n"
        f"Открыто ячеек: <b>{opened}</b>\n"
        f"Множитель: <b>{mult}x</b>\n"
        f"Потенциальный выигрыш: <b>{potential}</b> {cur_name}\n\n"
        f"Открывай ячейки или забери приз!"
    )


def _mines_keyboard(uid: str) -> types.InlineKeyboardMarkup:
    s = mines_sessions.get(uid)
    if not s:
        return types.InlineKeyboardMarkup()

    markup = types.InlineKeyboardMarkup(row_width=MINES_GRID_SIZE)
    buttons = []
    for i in range(MINES_GRID_SIZE * MINES_GRID_SIZE):
        if i in s["opened"]:
            buttons.append(types.InlineKeyboardButton("✅", callback_data="mine_noop"))
        else:
            buttons.append(types.InlineKeyboardButton("⬜", callback_data=f"mine_open:{i}"))

    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton("💰 Забрать приз", callback_data="mine_cashout"))
    return markup


def _mines_currency_balance(uid: str, currency_key: str) -> int:
    getter = _CURRENCY_MAP[currency_key][2]
    return getter(uid)


def _mines_currency_add(uid: str, currency_key: str, amount: int) -> int:
    adder = _CURRENCY_MAP[currency_key][3]
    return adder(uid, amount)


@bot.message_handler(commands=["mines"])
def cmd_mines(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    log_cmd(uid, username, "mines")

    if uid in mines_sessions:
        bot.reply_to(message, "Ты уже играешь! Закончи текущую игру сначала.")
        return

    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        bot.reply_to(message,
            "Использование: /mines &lt;тип валюты&gt; &lt;ставка&gt;\n"
            "Типы: <b>o</b> (окурки), <b>c</b> (сигареты), <b>r</b> (рубли)\n"
            "Пример: /mines o 10"
        )
        return

    currency_input = parts[1].strip().lower()
    if currency_input not in _CURRENCY_MAP:
        bot.reply_to(message, "Неизвестный тип валюты. Доступно: <b>o</b> (окурки), <b>c</b> (сигареты), <b>r</b> (рубли)")
        return

    try:
        bet = int(parts[2].strip())
    except ValueError:
        bot.reply_to(message, "Ставка должна быть числом.")
        return

    if bet <= 0:
        bot.reply_to(message, "Ставка должна быть больше нуля.")
        return

    currency_key = currency_input
    balance = _mines_currency_balance(uid, currency_key)
    if balance < bet:
        cur_name = _CURRENCY_MAP[currency_key][1]
        bot.reply_to(message, f"Недостаточно {cur_name}. У тебя <b>{balance}</b>, нужно <b>{bet}</b>.")
        return

    # Deduct the bet
    _mines_currency_add(uid, currency_key, -bet)

    # Generate mines
    all_cells = list(range(MINES_GRID_SIZE * MINES_GRID_SIZE))
    mines = set(random.sample(all_cells, MINES_COUNT))

    mines_sessions[uid] = {
        "bet": bet,
        "currency": currency_key,
        "mines": mines,
        "opened": set(),
        "msg_id": None,
    }

    log_info("MINES", f"user={uid} started game | bet={bet} {currency_key} | mines={sorted(mines)}")

    text = _mines_render_text(uid)
    markup = _mines_keyboard(uid)
    sent = bot.reply_to(message, text, reply_markup=markup)
    mines_sessions[uid]["msg_id"] = sent.message_id


@bot.callback_query_handler(func=lambda call: call.data == "mine_noop")
def callback_mine_noop(call: types.CallbackQuery):
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("mine_open:"))
def callback_mine_open(call: types.CallbackQuery):
    uid = str(call.from_user.id)

    if uid not in mines_sessions:
        bot.answer_callback_query(call.id, "Игра не найдена.", show_alert=True)
        return

    s = mines_sessions[uid]
    cell = int(call.data.split(":", 1)[1])

    if cell in s["opened"]:
        bot.answer_callback_query(call.id)
        return

    # Hit a mine — game over
    if cell in s["mines"]:
        s["opened"].add(cell)
        cur_name = _CURRENCY_MAP[s["currency"]][1]
        log_info("MINES", f"user={uid} HIT MINE at {cell} | lost {s['bet']} {s['currency']}")

        # Reveal full board
        markup = types.InlineKeyboardMarkup(row_width=MINES_GRID_SIZE)
        buttons = []
        for i in range(MINES_GRID_SIZE * MINES_GRID_SIZE):
            if i in s["mines"]:
                buttons.append(types.InlineKeyboardButton("💣", callback_data="mine_noop"))
            elif i in s["opened"]:
                buttons.append(types.InlineKeyboardButton("✅", callback_data="mine_noop"))
            else:
                buttons.append(types.InlineKeyboardButton("⬜", callback_data="mine_noop"))
        markup.add(*buttons)

        text = (
            f"💥 <b>БАБАХ!</b>\n\n"
            f"Ты попал на мину!\n"
            f"Ставка <b>{s['bet']}</b> {cur_name} сгорела.\n\n"
            f"Открыто ячеек: <b>{len(s['opened']) - 1}</b>"
        )

        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=s["msg_id"],
                text=text,
                reply_markup=markup
            )
        except Exception:
            pass

        bot.answer_callback_query(call.id, "💥 Бабах! Ты проиграл!", show_alert=True)
        del mines_sessions[uid]
        return

    # Safe cell
    s["opened"].add(cell)
    opened_count = len(s["opened"])
    mult = _mines_multiplier(opened_count)
    cur_name = _CURRENCY_MAP[s["currency"]][1]
    potential = int(s["bet"] * mult)

    log_info("MINES", f"user={uid} opened {cell} | opened={opened_count} | mult={mult}x")

    # Check if all safe cells opened (win automatically)
    total_safe = MINES_GRID_SIZE * MINES_GRID_SIZE - MINES_COUNT
    if opened_count >= total_safe:
        winnings = int(s["bet"] * mult)
        _mines_currency_add(uid, s["currency"], winnings)
        log_info("MINES", f"user={uid} CLEARED BOARD | won {winnings} {s['currency']}")

        markup = types.InlineKeyboardMarkup(row_width=MINES_GRID_SIZE)
        buttons = []
        for i in range(MINES_GRID_SIZE * MINES_GRID_SIZE):
            if i in s["mines"]:
                buttons.append(types.InlineKeyboardButton("💣", callback_data="mine_noop"))
            else:
                buttons.append(types.InlineKeyboardButton("✅", callback_data="mine_noop"))
        markup.add(*buttons)

        text = (
            f"🎉 <b>Полная победа!</b>\n\n"
            f"Ты открыл все безопасные ячейки!\n"
            f"Выигрыш: <b>{winnings}</b> {cur_name}\n"
            f"Множитель: <b>{mult}x</b>"
        )

        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=s["msg_id"],
                text=text,
                reply_markup=markup
            )
        except Exception:
            pass

        bot.answer_callback_query(call.id, "🎉 Полная победа!", show_alert=True)
        del mines_sessions[uid]
        return

    # Continue game
    text = (
        f"💣 <b>Мины</b>\n\n"
        f"Ставка: <b>{s['bet']}</b> {cur_name}\n"
        f"Открыто ячеек: <b>{opened_count}</b>\n"
        f"Множитель: <b>{mult}x</b>\n"
        f"Потенциальный выигрыш: <b>{potential}</b> {cur_name}\n\n"
        f"Открывай ячейки или забери приз!"
    )

    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=s["msg_id"],
            text=text,
            reply_markup=_mines_keyboard(uid)
        )
    except Exception:
        pass

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "mine_cashout")
def callback_mine_cashout(call: types.CallbackQuery):
    uid = str(call.from_user.id)

    if uid not in mines_sessions:
        bot.answer_callback_query(call.id, "Игра не найдена.", show_alert=True)
        return

    s = mines_sessions[uid]
    opened_count = len(s["opened"])

    if opened_count == 0:
        bot.answer_callback_query(call.id, "Открой хотя бы одну ячейку сначала!", show_alert=True)
        return

    mult = _mines_multiplier(opened_count)
    winnings = int(s["bet"] * mult)
    cur_name = _CURRENCY_MAP[s["currency"]][1]

    _mines_currency_add(uid, s["currency"], winnings)
    log_info("MINES", f"user={uid} CASHOUT | opened={opened_count} | won {winnings} {s['currency']}")

    # Reveal full board
    markup = types.InlineKeyboardMarkup(row_width=MINES_GRID_SIZE)
    buttons = []
    for i in range(MINES_GRID_SIZE * MINES_GRID_SIZE):
        if i in s["mines"]:
            buttons.append(types.InlineKeyboardButton("💣", callback_data="mine_noop"))
        elif i in s["opened"]:
            buttons.append(types.InlineKeyboardButton("✅", callback_data="mine_noop"))
        else:
            buttons.append(types.InlineKeyboardButton("⬜", callback_data="mine_noop"))
    markup.add(*buttons)

    text = (
        f"💰 <b>Ты забрал приз!</b>\n\n"
        f"Открыто ячеек: <b>{opened_count}</b>\n"
        f"Множитель: <b>{mult}x</b>\n"
        f"Выигрыш: <b>{winnings}</b> {cur_name}"
    )

    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=s["msg_id"],
            text=text,
            reply_markup=markup
        )
    except Exception:
        pass

    bot.answer_callback_query(call.id, f"💰 Ты забрал {winnings} {cur_name}!", show_alert=True)
    del mines_sessions[uid]


# ═══════════════════════════════════════════════════════════════════════════════
# Casino Roulette (/cr)
# ═══════════════════════════════════════════════════════════════════════════════

ROULETTE_RED = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
ROULETTE_BLACK = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
ROULETTE_COLOR_PAYOUT = 2.0    # 1:1 — возвращает 2x ставки (~48.6% шанс)
ROULETTE_NUMBER_PAYOUT = 36.0  # 35:1 — возвращает 36x ставки (~2.7% шанс)

_ROULETTE_RED_ALIASES = {"red", "красное", "красный", "красная", "крас", "r"}
_ROULETTE_BLACK_ALIASES = {"black", "черное", "чёрное", "черный", "чёрный", "чер", "чёр", "b"}


def _casino_balance(uid: str, currency_key: str) -> int:
    return _CURRENCY_MAP[currency_key][2](uid)


def _casino_add(uid: str, currency_key: str, amount: int) -> int:
    return _CURRENCY_MAP[currency_key][3](uid, amount)


def _parse_roulette_target(raw: str) -> tuple[Optional[str], Optional[object]]:
    t = raw.strip().lower()
    if t in _ROULETTE_RED_ALIASES:
        return "color", "red"
    if t in _ROULETTE_BLACK_ALIASES:
        return "color", "black"
    try:
        num = int(t)
        if 0 <= num <= 36:
            return "number", num
    except ValueError:
        pass
    return None, None


def _roulette_color(num: int) -> str:
    if num == 0:
        return "green"
    if num in ROULETTE_RED:
        return "red"
    return "black"


def _roulette_color_emoji(color: str) -> str:
    return {"red": "🔴", "black": "⚫", "green": "🟢"}.get(color, "⚪")


def _roulette_check_win(bet_type: str, bet_value: object, result_num: int) -> bool:
    if bet_type == "color":
        if result_num == 0:
            return False
        return _roulette_color(result_num) == bet_value
    return result_num == bet_value


def _roulette_payout_mult(bet_type: str) -> float:
    return ROULETTE_COLOR_PAYOUT if bet_type == "color" else ROULETTE_NUMBER_PAYOUT


def _format_roulette_bet(bet_type: str, bet_value: object) -> str:
    if bet_type == "color":
        return "🔴 Красное" if bet_value == "red" else "⚫ Чёрное"
    return f"🎯 Число <b>{bet_value}</b>"


def _roulette_result_text(
    currency_key: str, bet: int, bet_type: str, bet_value: object,
    won: bool, winnings: int, result_num: int,
) -> str:
    cur_name = _CURRENCY_MAP[currency_key][1]
    color = _roulette_color(result_num)
    emoji = _roulette_color_emoji(color)
    bet_label = _format_roulette_bet(bet_type, bet_value)
    mult = _roulette_payout_mult(bet_type)

    if won:
        outcome = (
            f"🎉 <b>Выигрыш!</b>\n"
            f"Ты получил <b>{winnings}</b> {cur_name} (x{mult:g})\n"
            f"Чистая прибыль: <b>+{winnings - bet}</b> {cur_name}"
        )
    else:
        outcome = (
            f"😔 <b>Проигрыш</b>\n"
            f"Ставка <b>{bet}</b> {cur_name} сгорела."
        )

    return (
        f"🎰 <b>Рулетка</b>\n\n"
        f"Выпало: {emoji} <b>{result_num}</b>\n"
        f"Твоя ставка: {bet_label} — <b>{bet}</b> {cur_name}\n\n"
        f"{outcome}"
    )


def _roulette_repeat_keyboard(currency_key: str, bet: int, bet_type: str, bet_value: object) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        "🔄 Повторить ставку",
        callback_data=f"cr_repeat:{currency_key}:{bet}:{bet_type}:{bet_value}",
    ))
    return markup


def _play_roulette_spin(
    uid: str, currency_key: str, bet: int, bet_type: str, bet_value: object,
) -> tuple[bool, int, int]:
    _casino_add(uid, currency_key, -bet)
    result_num = random.randint(0, 36)
    won = _roulette_check_win(bet_type, bet_value, result_num)
    winnings = 0
    if won:
        winnings = int(bet * _roulette_payout_mult(bet_type))
        _casino_add(uid, currency_key, winnings)
    log_info("ROULETTE", f"user={uid} spin | bet={bet} {currency_key} | target={bet_type}:{bet_value} | result={result_num} | won={won}")
    return won, winnings, result_num


@bot.message_handler(commands=["cr"])
def cmd_cr(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    log_cmd(uid, username, "cr")

    if uid in mines_sessions:
        bot.reply_to(message, "Сначала закончи игру в мины!")
        return
    if uid in bj_sessions:
        bot.reply_to(message, "Сначала закончи блэкджек!")
        return

    parts = message.text.split(maxsplit=3)
    if len(parts) < 4:
        bot.reply_to(message,
            "Использование: /cr &lt;валюта&gt; &lt;ставка&gt; &lt;на что&gt;\n"
            "Валюта: <b>o</b> (окурки), <b>c</b> (сигареты), <b>r</b> (рубли)\n"
            "На что: <b>red</b>/<b>black</b> (или красное/чёрное) либо число <b>0–36</b>\n\n"
            "Примеры:\n"
            "/cr o 10 red — ставка 10 окурков на красное (x2, ~48%)\n"
            "/cr r 50 black — ставка 50 рублей на чёрное (x2, ~48%)\n"
            "/cr c 5 17 — ставка 5 сигарет на число 17 (x36, ~2.7%)"
        )
        return

    currency_input = parts[1].strip().lower()
    if currency_input not in _CURRENCY_MAP:
        bot.reply_to(message, "Неизвестная валюта. Доступно: <b>o</b>, <b>c</b>, <b>r</b>")
        return

    try:
        bet = int(parts[2].strip())
    except ValueError:
        bot.reply_to(message, "Ставка должна быть числом.")
        return

    if bet <= 0:
        bot.reply_to(message, "Ставка должна быть больше нуля.")
        return

    bet_type, bet_value = _parse_roulette_target(parts[3])
    if bet_type is None:
        bot.reply_to(message, "Неверная ставка. Укажи <b>red</b>, <b>black</b> или число от 0 до 36.")
        return

    currency_key = currency_input
    balance = _casino_balance(uid, currency_key)
    if balance < bet:
        cur_name = _CURRENCY_MAP[currency_key][1]
        bot.reply_to(message, f"Недостаточно {cur_name}. У тебя <b>{balance}</b>, нужно <b>{bet}</b>.")
        return

    wait_msg = bot.reply_to(message, "🎰 Крутим рулетку...")
    chat_id = message.chat.id
    msg_id = wait_msg.message_id

    def _spin():
        set_reply_context(message)
        time.sleep(2)
        won, winnings, result_num = _play_roulette_spin(uid, currency_key, bet, bet_type, bet_value)
        text = _roulette_result_text(currency_key, bet, bet_type, bet_value, won, winnings, result_num)
        markup = _roulette_repeat_keyboard(currency_key, bet, bet_type, bet_value)
        try:
            bot.edit_message_text(text, chat_id, msg_id, reply_markup=markup)
        except Exception:
            bot.send_message(chat_id, text, reply_markup=markup, **reply_kwargs_for_message(message))

    threading.Thread(target=_spin, daemon=True).start()


@bot.callback_query_handler(func=lambda call: call.data.startswith("cr_repeat:"))
def callback_cr_repeat(call: types.CallbackQuery):
    uid = str(call.from_user.id)
    parts = call.data.split(":", 4)
    if len(parts) < 5:
        bot.answer_callback_query(call.id, "Ошибка данных.", show_alert=True)
        return

    currency_key = parts[1]
    try:
        bet = int(parts[2])
    except ValueError:
        bot.answer_callback_query(call.id, "Ошибка ставки.", show_alert=True)
        return

    bet_type = parts[3]
    bet_value_raw = parts[4]
    if bet_type == "number":
        try:
            bet_value = int(bet_value_raw)
        except ValueError:
            bot.answer_callback_query(call.id, "Ошибка данных.", show_alert=True)
            return
    else:
        bet_value = bet_value_raw

    if currency_key not in _CURRENCY_MAP or bet <= 0:
        bot.answer_callback_query(call.id, "Ошибка данных.", show_alert=True)
        return

    if uid in mines_sessions or uid in bj_sessions:
        bot.answer_callback_query(call.id, "Сначала закончи другую игру!", show_alert=True)
        return

    balance = _casino_balance(uid, currency_key)
    if balance < bet:
        cur_name = _CURRENCY_MAP[currency_key][1]
        bot.answer_callback_query(call.id, f"Недостаточно {cur_name}!", show_alert=True)
        return

    bot.answer_callback_query(call.id, "🎰 Крутим...")
    chat_id = call.message.chat.id
    msg_id = call.message.message_id

    def _spin():
        set_reply_context_from_call(call)
        time.sleep(2)
        won, winnings, result_num = _play_roulette_spin(uid, currency_key, bet, bet_type, bet_value)
        text = _roulette_result_text(currency_key, bet, bet_type, bet_value, won, winnings, result_num)
        markup = _roulette_repeat_keyboard(currency_key, bet, bet_type, bet_value)
        try:
            bot.edit_message_text(text, chat_id, msg_id, reply_markup=markup)
        except Exception:
            pass

    threading.Thread(target=_spin, daemon=True).start()


# ═══════════════════════════════════════════════════════════════════════════════
# Blackjack (/bj)
# ═══════════════════════════════════════════════════════════════════════════════

BJ_SUITS = ["♠", "♥", "♦", "♣"]
BJ_RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
BJ_BLACKJACK_PAYOUT = 2.5
BJ_WIN_PAYOUT = 2.0

bj_sessions: dict = {}


def _bj_new_deck() -> list[tuple[str, str]]:
    deck = [(rank, suit) for suit in BJ_SUITS for rank in BJ_RANKS]
    random.shuffle(deck)
    return deck


def _bj_card_str(card: tuple[str, str]) -> str:
    return f"{card[0]}{card[1]}"


def _bj_hand_str(hand: list[tuple[str, str]], hide_first: bool = False) -> str:
    if hide_first and hand:
        parts = [_bj_card_str(hand[0])] + ["🂠"] * (len(hand) - 1)
        return " ".join(parts)
    return " ".join(_bj_card_str(c) for c in hand)


def _bj_card_value(rank: str) -> int:
    if rank in ("J", "Q", "K"):
        return 10
    if rank == "A":
        return 11
    return int(rank)


def _bj_hand_value(hand: list[tuple[str, str]]) -> int:
    total = sum(_bj_card_value(rank) for rank, _ in hand)
    aces = sum(1 for rank, _ in hand if rank == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def _bj_is_blackjack(hand: list[tuple[str, str]]) -> bool:
    return len(hand) == 2 and _bj_hand_value(hand) == 21


def _bj_dealer_peek_upcard(rank: str) -> bool:
    return rank in ("A", "10", "J", "Q", "K")


def _bj_keyboard(can_double: bool = True) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🃏 Ещё", callback_data="bj_hit"),
        types.InlineKeyboardButton("✋ Хватит", callback_data="bj_stand"),
    )
    if can_double:
        markup.add(types.InlineKeyboardButton("💰 Удвоить", callback_data="bj_double"))
    return markup


def _bj_render(uid: str) -> str:
    s = bj_sessions[uid]
    cur_name = _CURRENCY_MAP[s["currency"]][1]
    player_val = _bj_hand_value(s["player"])
    dealer_str = _bj_hand_str(s["dealer"], hide_first=not s.get("dealer_revealed"))
    text = (
        f"🃏 <b>Блэкджек</b>\n\n"
        f"Ставка: <b>{s['bet']}</b> {cur_name}\n\n"
        f"Твои карты: {_bj_hand_str(s['player'])} (<b>{player_val}</b>)\n"
        f"Дилер: {dealer_str}"
    )
    if s.get("dealer_revealed"):
        text += f" (<b>{_bj_hand_value(s['dealer'])}</b>)"
    return text


def _bj_finish(uid: str, chat_id: int, msg_id: int, result_text: str):
    try:
        bot.edit_message_text(result_text, chat_id, msg_id)
    except Exception:
        pass
    if uid in bj_sessions:
        del bj_sessions[uid]


def _bj_resolve(uid: str, chat_id: int, msg_id: int):
    s = bj_sessions[uid]
    s["dealer_revealed"] = True
    cur_name = _CURRENCY_MAP[s["currency"]][1]
    bet = s["bet"]

    while _bj_hand_value(s["dealer"]) < 17:
        s["dealer"].append(s["deck"].pop())

    player_val = _bj_hand_value(s["player"])
    dealer_val = _bj_hand_value(s["dealer"])

    if dealer_val > 21:
        winnings = int(bet * BJ_WIN_PAYOUT)
        _casino_add(uid, s["currency"], winnings)
        result = (
            f"🎉 <b>Дилер перебрал!</b>\n\n"
            f"{_bj_render(uid)}\n\n"
            f"Выигрыш: <b>{winnings}</b> {cur_name} (+{winnings - bet})"
        )
    elif player_val > dealer_val:
        winnings = int(bet * BJ_WIN_PAYOUT)
        _casino_add(uid, s["currency"], winnings)
        result = (
            f"🎉 <b>Ты победил!</b>\n\n"
            f"{_bj_render(uid)}\n\n"
            f"Выигрыш: <b>{winnings}</b> {cur_name} (+{winnings - bet})"
        )
    elif player_val == dealer_val:
        _casino_add(uid, s["currency"], bet)
        result = (
            f"🤝 <b>Ничья!</b>\n\n"
            f"{_bj_render(uid)}\n\n"
            f"Ставка <b>{bet}</b> {cur_name} возвращена."
        )
    else:
        result = (
            f"😔 <b>Дилер победил</b>\n\n"
            f"{_bj_render(uid)}\n\n"
            f"Ставка <b>{bet}</b> {cur_name} сгорела."
        )

    log_info("BLACKJACK", f"user={uid} finished | player={player_val} dealer={dealer_val} | bet={bet}")
    _bj_finish(uid, chat_id, msg_id, result)


@bot.message_handler(commands=["bj", "blackjack"])
def cmd_bj(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    log_cmd(uid, username, "bj")

    if uid in bj_sessions:
        bot.reply_to(message, "Ты уже играешь в блэкджек! Закончи текущую партию.")
        return
    if uid in mines_sessions:
        bot.reply_to(message, "Сначала закончи игру в мины!")
        return

    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        bot.reply_to(message,
            "Использование: /bj &lt;валюта&gt; &lt;ставка&gt;\n"
            "Валюта: <b>o</b> (окурки), <b>c</b> (сигареты), <b>r</b> (рубли)\n"
            "Пример: /bj o 10\n\n"
            "Цель — набрать 21 или ближе к 21, чем дилер.\n"
            "Блэкджек (21 с двух карт) — выплата x2.5"
        )
        return

    currency_input = parts[1].strip().lower()
    if currency_input not in _CURRENCY_MAP:
        bot.reply_to(message, "Неизвестная валюта. Доступно: <b>o</b>, <b>c</b>, <b>r</b>")
        return

    try:
        bet = int(parts[2].strip())
    except ValueError:
        bot.reply_to(message, "Ставка должна быть числом.")
        return

    if bet <= 0:
        bot.reply_to(message, "Ставка должна быть больше нуля.")
        return

    currency_key = currency_input
    balance = _casino_balance(uid, currency_key)
    if balance < bet:
        cur_name = _CURRENCY_MAP[currency_key][1]
        bot.reply_to(message, f"Недостаточно {cur_name}. У тебя <b>{balance}</b>, нужно <b>{bet}</b>.")
        return

    _casino_add(uid, currency_key, -bet)
    deck = _bj_new_deck()
    player = [deck.pop(), deck.pop()]
    dealer = [deck.pop(), deck.pop()]

    bj_sessions[uid] = {
        "bet": bet,
        "currency": currency_key,
        "deck": deck,
        "player": player,
        "dealer": dealer,
        "dealer_revealed": False,
        "doubled": False,
        "msg_id": None,
    }

    cur_name = _CURRENCY_MAP[currency_key][1]
    chat_id = message.chat.id

    # Player blackjack
    if _bj_is_blackjack(player):
        bj_sessions[uid]["dealer_revealed"] = True
        if _bj_is_blackjack(dealer):
            _casino_add(uid, currency_key, bet)
            text = (
                f"🃏 <b>Блэкджек</b>\n\n"
                f"Твои карты: {_bj_hand_str(player)} (21)\n"
                f"Дилер: {_bj_hand_str(dealer)} (21)\n\n"
                f"🤝 <b>Обе стороны — блэкджек!</b> Ставка возвращена."
            )
            sent = bot.reply_to(message, text)
            del bj_sessions[uid]
            return

        winnings = int(bet * BJ_BLACKJACK_PAYOUT)
        _casino_add(uid, currency_key, winnings)
        text = (
            f"🃏 <b>Блэкджек!</b>\n\n"
            f"Твои карты: {_bj_hand_str(player)} (21)\n"
            f"Дилер: {_bj_hand_str(dealer)} ({_bj_hand_value(dealer)})\n\n"
            f"🎉 Выигрыш: <b>{winnings}</b> {cur_name} (+{winnings - bet})"
        )
        sent = bot.reply_to(message, text)
        del bj_sessions[uid]
        return

    # Dealer blackjack (peek)
    if _bj_dealer_peek_upcard(dealer[0][0]) and _bj_is_blackjack(dealer):
        bj_sessions[uid]["dealer_revealed"] = True
        text = (
            f"🃏 <b>Блэкджек</b>\n\n"
            f"Твои карты: {_bj_hand_str(player)} ({_bj_hand_value(player)})\n"
            f"Дилер: {_bj_hand_str(dealer)} (21)\n\n"
            f"😔 У дилера блэкджек! Ставка <b>{bet}</b> {cur_name} сгорела."
        )
        sent = bot.reply_to(message, text)
        del bj_sessions[uid]
        return

    text = _bj_render(uid)
    sent = bot.reply_to(message, text, reply_markup=_bj_keyboard(can_double=True))
    bj_sessions[uid]["msg_id"] = sent.message_id
    log_info("BLACKJACK", f"user={uid} started | bet={bet} {currency_key}")


@bot.callback_query_handler(func=lambda call: call.data == "bj_hit")
def callback_bj_hit(call: types.CallbackQuery):
    uid = str(call.from_user.id)
    if uid not in bj_sessions:
        bot.answer_callback_query(call.id, "Игра не найдена.", show_alert=True)
        return

    s = bj_sessions[uid]
    s["player"].append(s["deck"].pop())
    player_val = _bj_hand_value(s["player"])
    cur_name = _CURRENCY_MAP[s["currency"]][1]
    chat_id = call.message.chat.id
    msg_id = s["msg_id"]

    if player_val > 21:
        s["dealer_revealed"] = True
        text = (
            f"💥 <b>Перебор!</b>\n\n"
            f"{_bj_render(uid)}\n\n"
            f"Ставка <b>{s['bet']}</b> {cur_name} сгорела."
        )
        bot.answer_callback_query(call.id, "💥 Перебор!", show_alert=True)
        _bj_finish(uid, chat_id, msg_id, text)
        return

    if player_val == 21:
        bot.answer_callback_query(call.id)
        _bj_resolve(uid, chat_id, msg_id)
        return

    try:
        bot.edit_message_text(_bj_render(uid), chat_id, msg_id, reply_markup=_bj_keyboard(can_double=False))
    except Exception:
        pass
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "bj_stand")
def callback_bj_stand(call: types.CallbackQuery):
    uid = str(call.from_user.id)
    if uid not in bj_sessions:
        bot.answer_callback_query(call.id, "Игра не найдена.", show_alert=True)
        return

    s = bj_sessions[uid]
    bot.answer_callback_query(call.id)
    _bj_resolve(uid, call.message.chat.id, s["msg_id"])


@bot.callback_query_handler(func=lambda call: call.data == "bj_double")
def callback_bj_double(call: types.CallbackQuery):
    uid = str(call.from_user.id)
    if uid not in bj_sessions:
        bot.answer_callback_query(call.id, "Игра не найдена.", show_alert=True)
        return

    s = bj_sessions[uid]
    if s.get("doubled") or len(s["player"]) != 2:
        bot.answer_callback_query(call.id, "Удвоить можно только на первом ходу!", show_alert=True)
        return

    extra = s["bet"]
    balance = _casino_balance(uid, s["currency"])
    if balance < extra:
        cur_name = _CURRENCY_MAP[s["currency"]][1]
        bot.answer_callback_query(call.id, f"Недостаточно {cur_name} для удвоения!", show_alert=True)
        return

    _casino_add(uid, s["currency"], -extra)
    s["bet"] += extra
    s["doubled"] = True
    s["player"].append(s["deck"].pop())
    player_val = _bj_hand_value(s["player"])
    cur_name = _CURRENCY_MAP[s["currency"]][1]
    chat_id = call.message.chat.id
    msg_id = s["msg_id"]

    if player_val > 21:
        s["dealer_revealed"] = True
        text = (
            f"💥 <b>Перебор после удвоения!</b>\n\n"
            f"{_bj_render(uid)}\n\n"
            f"Ставка <b>{s['bet']}</b> {cur_name} сгорела."
        )
        bot.answer_callback_query(call.id, "💥 Перебор!", show_alert=True)
        _bj_finish(uid, chat_id, msg_id, text)
        return

    bot.answer_callback_query(call.id, "💰 Ставка удвоена!")
    _bj_resolve(uid, chat_id, msg_id)


# ═══════════════════════════════════════════════════════════════════════════════
# Admin Punishment Commands
# ═══════════════════════════════════════════════════════════════════════════════

def _get_target_from_reply(message: types.Message):
    """Get the target user from a replied message. Returns (user_obj, uid, display_name) or None."""
    if not message.reply_to_message:
        bot.reply_to(message, "Ответь на сообщение пользователя, которого хочешь наказать.")
        return None
    target = message.reply_to_message.from_user
    if target.is_bot:
        bot.reply_to(message, "Нельзя наказать бота.")
        return None
    target_uid = str(target.id)
    get_or_create_user(target_uid)
    if target.username:
        update_username(target_uid, target.username)
    return target, target_uid, get_display_name(target)


def _parse_punishment_args(text: str, command: str) -> tuple[str, str]:
    """Extract duration and reason from command args. Returns (duration, reason)."""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return "", ""
    rest = parts[1].strip()
    # Try to parse duration (e.g. "10m", "2h", "1d") as the first token
    tokens = rest.split(maxsplit=1)
    duration = parse_remind_time(tokens[0]) if tokens else None
    if duration is not None:
        duration_display = tokens[0]
        reason = tokens[1].strip() if len(tokens) > 1 else ""
        return duration_display, reason
    else:
        return "", rest


@bot.message_handler(commands=["ban"])
def cmd_ban(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    register_chat(message.chat.id)
    track_chat_member(message.chat.id, message.from_user)

    if not is_group_admin(message):
        log_cmd(uid, username, "ban", "DENIED - not admin")
        bot.reply_to(message, "У тебя нет прав для этой команды.")
        return

    target_info = _get_target_from_reply(message)
    if not target_info:
        return
    target, target_uid, target_name = target_info

    parts = message.text.split(maxsplit=1)
    reason = parts[1].strip() if len(parts) >= 2 else "не указана"

    add_punishment(message.chat.id, target_uid, target_name, uid, get_display_name(message.from_user), "ban", reason, "∞")
    log_cmd(uid, username, "ban", f"target={target_uid} | reason={reason}")

    try:
        bot.ban_chat_member(message.chat.id, target.id)
        bot.reply_to(message, f"🔨 <b>{target_name}</b> забанен.\nПричина: {reason}")
    except Exception as e:
        log_err("BAN", f"Failed to ban user={target_uid}: {e}")
        bot.reply_to(message, f"Не удалось забанить {target_name}. Проверь, что бот — админ чата.\nОшибка: {e}")


@bot.message_handler(commands=["unban"])
def cmd_unban(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    register_chat(message.chat.id)
    track_chat_member(message.chat.id, message.from_user)

    if not is_group_admin(message):
        log_cmd(uid, username, "unban", "DENIED - not admin")
        bot.reply_to(message, "У тебя нет прав для этой команды.")
        return

    target_info = _get_target_from_reply(message)
    if not target_info:
        return
    target, target_uid, target_name = target_info

    add_punishment(message.chat.id, target_uid, target_name, uid, get_display_name(message.from_user), "unban", "снятие бана", "—")
    log_cmd(uid, username, "unban", f"target={target_uid}")

    try:
        bot.unban_chat_member(message.chat.id, target.id)
        bot.reply_to(message, f"✅ <b>{target_name}</b> разбанен.")
    except Exception as e:
        log_err("UNBAN", f"Failed to unban user={target_uid}: {e}")
        bot.reply_to(message, f"Не удалось разбанить {target_name}.\nОшибка: {e}")


@bot.message_handler(commands=["mute"])
def cmd_mute(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    register_chat(message.chat.id)
    track_chat_member(message.chat.id, message.from_user)

    if not is_group_admin(message):
        log_cmd(uid, username, "mute", "DENIED - not admin")
        bot.reply_to(message, "У тебя нет прав для этой команды.")
        return

    target_info = _get_target_from_reply(message)
    if not target_info:
        return
    target, target_uid, target_name = target_info

    duration_str, reason = _parse_punishment_args(message.text, "mute")
    if not reason:
        reason = "не указана"
    if not duration_str:
        duration_str = "∞"

    add_punishment(message.chat.id, target_uid, target_name, uid, get_display_name(message.from_user), "mute", reason, duration_str)
    log_cmd(uid, username, "mute", f"target={target_uid} | duration={duration_str} | reason={reason}")

    until_val = None
    if duration_str and duration_str != "∞":
        seconds = parse_remind_time(duration_str)
        if seconds:
            until_val = time.time() + seconds

    try:
        bot.restrict_chat_member(
            message.chat.id, target.id,
            can_send_messages=False,
            can_send_media_messages=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
            until_date=until_val
        )
        bot.reply_to(message, f"🔇 <b>{target_name}</b> замьючен.\nДлительность: {duration_str}\nПричина: {reason}")
    except Exception as e:
        log_err("MUTE", f"Failed to mute user={target_uid}: {e}")
        bot.reply_to(message, f"Не удалось замьютить {target_name}.\nОшибка: {e}")


@bot.message_handler(commands=["unmute"])
def cmd_unmute(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    register_chat(message.chat.id)
    track_chat_member(message.chat.id, message.from_user)

    if not is_group_admin(message):
        log_cmd(uid, username, "unmute", "DENIED - not admin")
        bot.reply_to(message, "У тебя нет прав для этой команды.")
        return

    target_info = _get_target_from_reply(message)
    if not target_info:
        return
    target, target_uid, target_name = target_info

    add_punishment(message.chat.id, target_uid, target_name, uid, get_display_name(message.from_user), "unmute", "снятие мьюта", "—")
    log_cmd(uid, username, "unmute", f"target={target_uid}")

    try:
        bot.restrict_chat_member(
            message.chat.id, target.id,
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )
        bot.reply_to(message, f"🔊 <b>{target_name}</b> размьючен.")
    except Exception as e:
        log_err("UNMUTE", f"Failed to unmute user={target_uid}: {e}")
        bot.reply_to(message, f"Не удалось размьютить {target_name}.\nОшибка: {e}")


@bot.message_handler(commands=["warn"])
def cmd_warn(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    register_chat(message.chat.id)
    track_chat_member(message.chat.id, message.from_user)

    if not is_group_admin(message):
        log_cmd(uid, username, "warn", "DENIED - not admin")
        bot.reply_to(message, "У тебя нет прав для этой команды.")
        return

    target_info = _get_target_from_reply(message)
    if not target_info:
        return
    target, target_uid, target_name = target_info

    parts = message.text.split(maxsplit=1)
    reason = parts[1].strip() if len(parts) >= 2 else "не указана"

    add_punishment(message.chat.id, target_uid, target_name, uid, get_display_name(message.from_user), "warn", reason, "—")
    log_cmd(uid, username, "warn", f"target={target_uid} | reason={reason}")

    bot.reply_to(message, f"⚠️ <b>{target_name}</b> получил предупреждение.\nПричина: {reason}")


@bot.message_handler(commands=["unwarn"])
def cmd_unwarn(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    register_chat(message.chat.id)
    track_chat_member(message.chat.id, message.from_user)

    if not is_group_admin(message):
        log_cmd(uid, username, "unwarn", "DENIED - not admin")
        bot.reply_to(message, "У тебя нет прав для этой команды.")
        return

    target_info = _get_target_from_reply(message)
    if not target_info:
        return
    target, target_uid, target_name = target_info

    add_punishment(message.chat.id, target_uid, target_name, uid, get_display_name(message.from_user), "unwarn", "снятие предупреждения", "—")
    log_cmd(uid, username, "unwarn", f"target={target_uid}")

    bot.reply_to(message, f"✅ <b>{target_name}</b> — предупреждение снято.")


@bot.message_handler(commands=["enemy_list"])
def cmd_enemy_list(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    register_chat(message.chat.id)
    track_chat_member(message.chat.id, message.from_user)
    log_cmd(uid, username, "enemy_list")

    punishments = get_recent_punishments(message.chat.id, limit=6)
    if not punishments:
        bot.reply_to(message, "📋 В этом чате пока нет наказаний.")
        return

    type_emojis = {
        "ban": "🔨", "unban": "✅", "mute": "🔇", "unmute": "🔊",
        "warn": "⚠️", "unwarn": "✅"
    }

    text = "📋 <b>Список последних наказаний</b>\n\n"
    for p in punishments:
        emoji = type_emojis.get(p["type"], "📌")
        time_str = p["created_at"].strftime("%d.%m.%Y %H:%M") if hasattr(p["created_at"], "strftime") else str(p["created_at"])
        text += (
            f"{emoji} <b>{p['type'].upper()}</b> — {p['target_name']}\n"
            f"   Когда: {time_str}\n"
            f"   Кто наказал: {p['admin_name']}\n"
            f"   Причина: {p['reason']}\n"
            f"   Длительность: {p['duration']}\n\n"
        )

    bot.reply_to(message, text)


@bot.message_handler(commands=["vsem"])
def cmd_vsem(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")

    if not is_admin(message):
        log_cmd(uid, username, "vsem", "DENIED - not admin")
        bot.reply_to(message, "У тебя нет прав для этой команды.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "Использование: /vsem &lt;текст объявления&gt;")
        return

    text = parts[1].strip()
    log_cmd(uid, username, "vsem", text[:80])

    chats = get_all_chats()
    if not chats:
        bot.reply_to(message, "Нет известных чатов для рассылки.")
        return

    announcement = f"📢 <b>Объявление от администрации:</b>\n\n{text}"

    def _broadcast():
        set_reply_context(message)
        sent = 0
        failed = 0
        for chat_id in chats:
            try:
                bot.send_message(chat_id, announcement, _skip_reply=True)
                sent += 1
            except Exception as e:
                log_err("BROADCAST", f"Failed to send to chat_id={chat_id}: {e}")
                failed += 1

        log_info("BROADCAST", f"Done | sent={sent} | failed={failed} | total={len(chats)}")
        bot.reply_to(message, f"Рассылка завершена.\nОтправлено: <b>{sent}</b>\nОшибок: <b>{failed}</b>")

    threading.Thread(target=_broadcast, daemon=True).start()
    bot.reply_to(message, f"Начинаю рассылку в <b>{len(chats)}</b> чат(ов)...")


# ═══════════════════════════════════════════════════════════════════════════════
# Clan Commands
# ═══════════════════════════════════════════════════════════════════════════════

@bot.message_handler(commands=["create_clan"])
def cmd_create_clan(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    log_cmd(uid, username, "create_clan")

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "Использование: /create_clan &lt;название&gt;\nПример: /create_clan Дымные Короли")
        return

    clan_name = parts[1].strip()

    if get_user_clan(uid):
        bot.reply_to(message, "Ты уже состоишь в клане. Сначала покинь его командой /leave_clan.")
        return

    if get_clan_by_name(clan_name):
        bot.reply_to(message, f"Клан с названием «{clan_name}» уже существует. Выбери другое имя.")
        return

    clan_id = create_clan(uid, clan_name)
    if clan_id:
        log_info("CLAN", f"Created clan '{clan_name}' (id={clan_id}) by user={uid}")
        bot.reply_to(message, f"✅ Клан <b>{clan_name}</b> создан!\nТы — лидер клана. Приглашай друзей командой /join_clan.")
    else:
        bot.reply_to(message, "Не удалось создать клан. Возможно, такое название уже занято.")


@bot.message_handler(commands=["delete_clan"])
def cmd_delete_clan(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    log_cmd(uid, username, "delete_clan")

    clan = get_user_clan(uid)
    if not clan:
        bot.reply_to(message, "Ты не состоишь в клане.")
        return

    if clan["leader_id"] != uid:
        bot.reply_to(message, "Только лидер клана может его удалить.")
        return

    clan_name = clan["name"]
    if delete_clan(clan["id"]):
        log_info("CLAN", f"Deleted clan '{clan_name}' (id={clan['id']}) by user={uid}")
        bot.reply_to(message, f"🗑 Клан <b>{clan_name}</b> удалён. Все участники исключены.")
    else:
        bot.reply_to(message, "Не удалось удалить клан.")


@bot.message_handler(commands=["clan"])
def cmd_clan(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    log_cmd(uid, username, "clan")

    clan = get_user_clan(uid)
    if not clan:
        bot.reply_to(message, "Ты не состоишь в клане. Создай свой командой /create_clan или вступи в существующий /join_clan.")
        return

    members = get_clan_members(clan["id"])
    leader_name = "Ты"
    members_text = ""
    for m_id, m_uname in members:
        display = f"@{m_uname}" if m_uname else f"user_{m_id}"
        if m_id == clan["leader_id"]:
            leader_name = display
            members_text += f"  👑 {display} (лидер)\n"
        else:
            members_text += f"  • {display}\n"

    bot.reply_to(message,
        f"🏷 <b>Клан: {clan['name']}</b>\n\n"
        f"👑 Лидер: {leader_name}\n"
        f"⭐ Репутация: <b>{clan['reputation']}</b>\n"
        f"👥 Участники ({len(members)}):\n{members_text}"
    )


@bot.message_handler(commands=["clans"])
def cmd_clans(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    log_cmd(uid, username, "clans")

    clans = get_all_clans()
    if not clans:
        bot.reply_to(message, "Пока нет ни одного клана. Будь первым — создай клан командой /create_clan.")
        return

    text = "🏷 <b>Все кланы</b> (по репутации):\n\n"
    for i, (clan_id, clan_name, clan_rep) in enumerate(clans):
        medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
        text += f"{medal} <b>{clan_name}</b> — репутация: {clan_rep}\n"

    bot.reply_to(message, text)


@bot.message_handler(commands=["join_clan"])
def cmd_join_clan(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    log_cmd(uid, username, "join_clan")

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "Использование: /join_clan &lt;название&gt;\nПример: /join_clan Дымные Короли")
        return

    clan_name = parts[1].strip()

    if get_user_clan(uid):
        bot.reply_to(message, "Ты уже состоишь в клане. Сначала покинь его командой /leave_clan.")
        return

    clan = get_clan_by_name(clan_name)
    if not clan:
        bot.reply_to(message, f"Клан «{clan_name}» не найден. Проверь название.")
        return

    if join_clan(uid, clan["id"]):
        bot.reply_to(message, f"✅ Ты вступил в клан <b>{clan['name']}</b>!")
    else:
        bot.reply_to(message, "Не удалось вступить в клан.")


@bot.message_handler(commands=["leave_clan"])
def cmd_leave_clan(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    log_cmd(uid, username, "leave_clan")

    clan = get_user_clan(uid)
    if not clan:
        bot.reply_to(message, "Ты не состоишь в клане.")
        return

    if clan["leader_id"] == uid:
        bot.reply_to(message, "Ты лидер клана. Используй /delete_clan чтобы удалить клан, или сначала передай лидерство (если планируешь уйти).")
        return

    leave_clan(uid)
    bot.reply_to(message, f"👋 Ты покинул клан <b>{clan['name']}</b>.")


@bot.message_handler(commands=["trash_to_clan"])
def cmd_trash_to_clan(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    log_cmd(uid, username, "trash_to_clan")

    clan = get_user_clan(uid)
    if not clan:
        bot.reply_to(message, "Ты не состоишь в клане. Вступи в клан или создай свой.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "Использование: /trash_to_clan &lt;кол-во окурков&gt;\nПример: /trash_to_clan 10\n1 окурок = 1 репутация.")
        return

    try:
        amount = int(parts[1].strip())
    except ValueError:
        bot.reply_to(message, "Количество должно быть числом.")
        return

    if amount <= 0:
        bot.reply_to(message, "Количество должно быть больше нуля.")
        return

    current_cigs = get_cigarettes(uid)
    if current_cigs < amount:
        bot.reply_to(message, f"У тебя только {current_cigs} окурков. Не хватает {amount - current_cigs}.")
        return

    add_cigarettes(uid, -amount)
    new_rep = add_clan_reputation(clan["id"], amount * TRASH_TO_REP_RATE)
    log_info("CLAN", f"user={uid} converted {amount} butts to rep for clan={clan['id']} | new_rep={new_rep}")

    bot.reply_to(message,
        f"♻️ Ты перевёл <b>{amount}</b> окурков в репутацию клана <b>{clan['name']}</b>.\n"
        f"Получено: <b>+{amount * TRASH_TO_REP_RATE}</b> репутации.\n"
        f"Текущая репутация клана: <b>{new_rep}</b>"
    )


@bot.message_handler(commands=["cigar_to_clan"])
def cmd_cigar_to_clan(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    log_cmd(uid, username, "cigar_to_clan")

    clan = get_user_clan(uid)
    if not clan:
        bot.reply_to(message, "Ты не состоишь в клане. Вступи в клан или создай свой.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "Использование: /cigar_to_clan &lt;кол-во сигарет&gt;\nПример: /cigar_to_clan 3\n1 сигарета = 100 репутации.")
        return

    try:
        amount = int(parts[1].strip())
    except ValueError:
        bot.reply_to(message, "Количество должно быть числом.")
        return

    if amount <= 0:
        bot.reply_to(message, "Количество должно быть больше нуля.")
        return

    current_real_cigs = get_real_cigarettes(uid)
    if current_real_cigs < amount:
        bot.reply_to(message, f"У тебя только {current_real_cigs} сигарет. Не хватает {amount - current_real_cigs}.")
        return

    add_real_cigarettes(uid, -amount)
    rep_gained = amount * CIGAR_TO_REP
    new_rep = add_clan_reputation(clan["id"], rep_gained)
    log_info("CLAN", f"user={uid} converted {amount} cigarettes to rep for clan={clan['id']} | +{rep_gained} | new_rep={new_rep}")

    bot.reply_to(message,
        f"♻️ Ты перевёл <b>{amount}</b> сигарет в репутацию клана <b>{clan['name']}</b>.\n"
        f"Получено: <b>+{rep_gained}</b> репутации.\n"
        f"Текущая репутация клана: <b>{new_rep}</b>"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Economy Commands
# ═══════════════════════════════════════════════════════════════════════════════

@bot.message_handler(commands=["beggar"])
def cmd_beggar(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    log_cmd(uid, username, "beggar")

    if random.random() < BEGGAR_CHANCE:
        new_total = add_rubles(uid, 1)
        log_info("ECONOMY", f"user={uid} BEGGAR: WON 1 ruble | total={new_total}")
        bot.reply_to(message,
            f"🤑 <b>Невероятная удача!</b>\n\n"
            f"Ты выпросил <b>1 рубль</b>!\n"
            f"Теперь у тебя <b>{new_total}₽</b>"
        )
    else:
        bot.reply_to(message,
            "🥺 Ты протягиваешь руку, но тебе никто не дал ничего...\n"
            "Шанс выпросить рубль — 1 к 20000. Попробуй ещё!"
        )


@bot.message_handler(commands=["buy_cigarettes"])
def cmd_buy_cigarettes(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    log_cmd(uid, username, "buy_cigarettes")

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, f"Использование: /buy_cigarettes &lt;кол-во&gt;\nЦена: {CIGARETTE_PRICE}₽ за сигарету\nПример: /buy_cigarettes 3")
        return

    try:
        amount = int(parts[1].strip())
    except ValueError:
        bot.reply_to(message, "Количество должно быть числом.")
        return

    if amount <= 0:
        bot.reply_to(message, "Количество должно быть больше нуля.")
        return

    cost = amount * CIGARETTE_PRICE
    current_rubles = get_rubles(uid)

    if current_rubles < cost:
        bot.reply_to(message,
            f"Не хватает денег. Нужно <b>{cost}₽</b>, у тебя <b>{current_rubles}₽</b>.\n"
            f"Не хватает: <b>{cost - current_rubles}₽</b>"
        )
        return

    add_rubles(uid, -cost)
    new_cig_total = add_real_cigarettes(uid, amount)
    log_info("ECONOMY", f"user={uid} bought {amount} cigarettes for {cost} rubles | total_cigs={new_cig_total}")

    bot.reply_to(message,
        f"🛒 Ты купил <b>{amount}</b> сигарет за <b>{cost}₽</b>.\n"
        f"Осталось рублей: <b>{current_rubles - cost}₽</b>\n"
        f"Теперь у тебя <b>{new_cig_total}</b> сигарет.\n\n"
        f"Перегони их в репутацию клана: /cigar_to_clan {amount}"
    )


@bot.message_handler(commands=["balance"])
def cmd_balance(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    log_cmd(uid, username, "balance")

    cigs = get_cigarettes(uid)
    rubles = get_rubles(uid)
    real_cigs = get_real_cigarettes(uid)
    clan = get_user_clan(uid)
    clan_text = f"\n🏷 Клан: <b>{clan['name']}</b> (реп. {clan['reputation']})" if clan else ""

    bot.reply_to(message,
        f"💰 <b>Твой баланс</b>\n\n"
        f"🚬 Окурки: <b>{cigs}</b>\n"
        f"💵 Рубли: <b>{rubles}₽</b>\n"
        f"🚬 Сигареты: <b>{real_cigs}</b>"
        f"{clan_text}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Promo Code Commands
# ═══════════════════════════════════════════════════════════════════════════════

@bot.message_handler(commands=["create_promo"])
def cmd_create_promo(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")

    if not is_admin(message):
        log_cmd(uid, username, "create_promo", "DENIED - not admin")
        bot.reply_to(message, "У тебя нет прав для этой команды. Только админ бота может создавать промокоды.")
        return

    parts = message.text.split()
    if len(parts) < 5:
        bot.reply_to(message,
            "Использование: /create_promo &lt;тип&gt; &lt;код&gt; &lt;кол-во&gt; &lt;активаций&gt;\n"
            "Типы: <b>rubles</b> (рубли), <b>cigarettes</b> (окурки), <b>real_cigarettes</b> (сигареты)\n"
            "Пример: /create_promo rubles NEWYEAR 10 100"
        )
        return

    reward_type = parts[1].strip().lower()
    code = parts[2].strip()
    try:
        reward_amount = int(parts[3].strip())
        max_uses = int(parts[4].strip())
    except ValueError:
        bot.reply_to(message, "Кол-во и активаций должны быть числами.")
        return

    valid_types = {"rubles", "cigarettes", "real_cigarettes"}
    if reward_type not in valid_types:
        bot.reply_to(message, f"Неизвестный тип. Доступные типы: {', '.join(valid_types)}")
        return

    if reward_amount <= 0 or max_uses <= 0:
        bot.reply_to(message, "Кол-во и активаций должны быть больше нуля.")
        return

    if create_promo_code(code, reward_type, reward_amount, max_uses, uid):
        type_names = {"rubles": "рублей", "cigarettes": "окурков", "real_cigarettes": "сигарет"}
        log_cmd(uid, username, "create_promo", f"code={code} | type={reward_type} | amount={reward_amount} | max={max_uses}")
        bot.reply_to(message,
            f"✅ Промокод создан!\n\n"
            f"Код: <b>{code}</b>\n"
            f"Награда: <b>{reward_amount} {type_names[reward_type]}</b>\n"
            f"Активаций: <b>{max_uses}</b>\n\n"
            f"Игроки могут активировать командой: /promo {code}"
        )
    else:
        bot.reply_to(message, "Не удалось создать промокод. Возможно, такой код уже существует.")


@bot.message_handler(commands=["promo"])
def cmd_promo(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "Использование: /promo &lt;код&gt;\nПример: /promo NEWYEAR")
        return

    code = parts[1].strip()
    log_cmd(uid, username, "promo", code)

    result = activate_promo_code(code, uid)

    type_names = {"rubles": "рублей", "cigarettes": "окурков", "real_cigarettes": "сигарет"}

    if result is None:
        bot.reply_to(message, f"Промокод «{code}» не найден.")
    elif result == "used":
        bot.reply_to(message, "Ты уже активировал этот промокод.")
    elif result == "max":
        bot.reply_to(message, "У этого промокода закончились активации.")
    else:
        promo = get_promo_code(code)
        reward_amount = promo["reward_amount"] if promo else 0
        bot.reply_to(message,
            f"🎉 <b>Промокод активирован!</b>\n\n"
            f"Код: <b>{code}</b>\n"
            f"Получено: <b>{reward_amount} {type_names.get(result, result)}</b>"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Pathogen / Virus Commands
# ═══════════════════════════════════════════════════════════════════════════════

@bot.message_handler(commands=["create_virus"])
def cmd_create_virus(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message,
            "Использование: /create_virus &lt;имя&gt;\n"
            "Пример: /create_virus Коронавирус"
        )
        return

    name = parts[1].strip()
    if len(name) > 50:
        bot.reply_to(message, "Имя патогена не должно превышать 50 символов.")
        return

    log_cmd(uid, username, "create_virus", name)

    if get_pathogen(uid):
        bot.reply_to(message, "У тебя уже есть патоген. Используй /delete_virus чтобы уничтожить его.")
        return

    if create_pathogen(uid, name):
        bot.reply_to(message,
            f"🦠 <b>Патоген создан!</b>\n\n"
            f"Имя: <b>{name}</b>\n\n"
            f"Улучшай его в /lab и заражай людей командой /virus (в ответ на сообщение)."
        )
    else:
        bot.reply_to(message, "Не удалось создать патоген. Попробуй позже.")


@bot.message_handler(commands=["delete_virus"])
def cmd_delete_virus(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    log_cmd(uid, username, "delete_virus")

    pathogen = get_pathogen(uid)
    if not pathogen:
        bot.reply_to(message, "У тебя нет патогена.")
        return

    name = pathogen["name"]
    if delete_pathogen(uid):
        bot.reply_to(message,
            f"☠️ <b>Патоген «{name}» уничтожен!</b>\n\n"
            f"Все заражённые этим патогеном моментально выздоровели."
        )
    else:
        bot.reply_to(message, "Не удалось уничтожить патоген.")


@bot.message_handler(commands=["lab"])
def cmd_lab(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    log_cmd(uid, username, "lab")

    pathogen = get_pathogen(uid)
    if not pathogen:
        bot.reply_to(message,
            "У тебя нет патогена.\n"
            "Создай его командой: /create_virus &lt;имя&gt;"
        )
        return

    bot.reply_to(message, format_lab_text(pathogen), reply_markup=lab_keyboard())


@bot.callback_query_handler(func=lambda call: call.data.startswith("lab_up:"))
def callback_lab_upgrade(call: types.CallbackQuery):
    uid = str(call.from_user.id)
    parts = call.data.split(":")
    if len(parts) != 3:
        bot.answer_callback_query(call.id, "Ошибка данных.")
        return

    stat_key, pay_type = parts[1], parts[2]
    stat = _STAT_MAP.get(stat_key)
    if not stat:
        bot.answer_callback_query(call.id, "Неизвестная характеристика.")
        return

    pathogen = get_pathogen(uid)
    if not pathogen:
        bot.answer_callback_query(call.id, "У тебя нет патогена.")
        return

    if pay_type == "b":
        if get_cigarettes(uid) < VIRUS_BUTT_COST:
            bot.answer_callback_query(
                call.id,
                f"Нужно {VIRUS_BUTT_COST} окурок(а)! Ищи их через /trash.",
                show_alert=True
            )
            return
        add_cigarettes(uid, -VIRUS_BUTT_COST)
        levels = 1
        pay_text = f"{VIRUS_BUTT_COST} окурок"
    elif pay_type == "c":
        if get_real_cigarettes(uid) < 1:
            bot.answer_callback_query(
                call.id,
                "Нужна 1 сигарета! Купи через /buy_cigarettes.",
                show_alert=True
            )
            return
        add_real_cigarettes(uid, -1)
        levels = VIRUS_CIGARETTE_BOOST
        pay_text = "1 сигарета"
    else:
        bot.answer_callback_query(call.id, "Неизвестный способ оплаты.")
        return

    upgraded = upgrade_pathogen_stat(uid, stat, levels)
    if not upgraded:
        bot.answer_callback_query(call.id, "Ошибка улучшения.")
        return

    stat_name = _STAT_NAMES[stat]
    bot.answer_callback_query(call.id, f"{stat_name} +{levels}!")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=format_lab_text(upgraded) + f"\n\n✅ <b>{stat_name}</b> улучшена на <b>{levels}</b> ({pay_text})",
        parse_mode="HTML",
        reply_markup=lab_keyboard()
    )


@bot.message_handler(commands=["virus"])
def cmd_virus(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")

    if is_user_dead(uid):
        bot.reply_to(message, "Мёртвые не могут заражать. Используй /revive.")
        return

    pathogen = get_pathogen(uid)
    if not pathogen:
        bot.reply_to(message,
            "У тебя нет патогена.\n"
            "Создай его: /create_virus &lt;имя&gt;"
        )
        return

    if not message.reply_to_message:
        bot.reply_to(message, "Ответь на сообщение человека, которого хочешь заразить.")
        return

    target = message.reply_to_message.from_user
    if target.is_bot:
        bot.reply_to(message, "Ботов заразить нельзя.")
        return
    if target.id == message.from_user.id:
        bot.reply_to(message, "Нельзя заразить самого себя.")
        return

    can, reason, wait_sec = can_use_virus(uid)
    if not can:
        if reason == "daily_limit":
            bot.reply_to(message,
                f"📅 Дневной лимит исчерпан ({VIRUS_DAILY_LIMIT} заражений в день).\n"
                f"Попробуй завтра."
            )
        elif reason == "cooldown":
            bot.reply_to(message,
                f"⏳ Подожди ещё <b>{format_wait_time(wait_sec)}</b> перед следующим заражением.\n"
                f"(20 мин. + время болезни, если ты заражён)"
            )
        return

    target_uid = str(target.id)
    get_or_create_user(target_uid)
    log_cmd(uid, username, "virus", f"target={target_uid}")

    chance = calc_infect_chance(pathogen, target_uid)
    roll = random.random()
    target_display = get_display_name(target)

    if roll >= chance:
        set_last_infect_time(uid)
        bot.reply_to(message,
            f"🦠 <b>{pathogen['name']}</b> не смог заразить <b>{target_display}</b>.\n"
            f"Шанс был: <b>{chance * 100:.1f}%</b>"
        )
        return

    duration = calc_infected_duration(pathogen)
    apply_infection(target_uid, pathogen["id"], duration)
    set_last_infect_time(uid)
    daily_count = increment_daily_infect_count(uid)

    target_pathogen = get_pathogen(target_uid)
    immunity_note = ""
    if target_pathogen and target_pathogen["immunity"] > 0:
        immunity_note = f"\n🛡 Иммунитет цели: -{target_pathogen['immunity'] * VIRUS_IMMUNITY_REDUCTION * 100:.0f}%"

    bot.reply_to(message,
        f"☣️ <b>Заражение успешно!</b>\n\n"
        f"Патоген: <b>{pathogen['name']}</b>\n"
        f"Жертва: <b>{target_display}</b>\n"
        f"Шанс: <b>{chance * 100:.1f}%</b>{immunity_note}\n"
        f"⏱ Не сможет заражать других: <b>{format_wait_time(duration)}</b>\n"
        f"📅 Заражений сегодня: <b>{daily_count}/{VIRUS_DAILY_LIMIT}</b>"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Send Item Command
# ═══════════════════════════════════════════════════════════════════════════════

@bot.message_handler(commands=["send_item"])
def cmd_send_item(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")
    log_cmd(uid, username, "send_item")

    if not message.reply_to_message:
        bot.reply_to(message, "Ответь на сообщение человека, которому хочешь передать предмет.")
        return

    target = message.reply_to_message.from_user
    if target.id == message.from_user.id:
        bot.reply_to(message, "Нельзя передавать предметы самому себе.")
        return

    if target.is_bot:
        bot.reply_to(message, "Нельзя передавать предметы боту.")
        return

    parts = message.text.split()
    if len(parts) < 3:
        bot.reply_to(message,
            "Использование: /send_item &lt;предмет&gt; &lt;кол-во&gt; (в ответ на сообщение)\n"
            "Предметы: <b>окурки</b>, <b>рубли</b>, <b>сигареты</b>\n"
            "Пример: /send_item окурки 5"
        )
        return

    item_name = parts[1].strip().lower()
    try:
        amount = int(parts[2].strip())
    except ValueError:
        bot.reply_to(message, "Количество должно быть числом.")
        return

    if amount <= 0:
        bot.reply_to(message, "Количество должно быть больше нуля.")
        return

    item_map = {
        "окурки": "cigarettes",
        "окурок": "cigarettes",
        "рубли": "rubles",
        "рубль": "rubles",
        "сигареты": "real_cigarettes",
        "сигарета": "real_cigarettes",
    }

    item_key = item_map.get(item_name)
    if not item_key:
        bot.reply_to(message, f"Неизвестный предмет. Доступно: {', '.join(item_map.keys())}")
        return

    target_uid = str(target.id)
    get_or_create_user(target_uid)

    currency_map = {
        "cigarettes": "butts",
        "rubles": "rubles",
        "real_cigarettes": "real_cigarettes",
    }
    currency = currency_map[item_key]
    ok, err, received, fee = transfer_with_bank_commission(uid, target_uid, currency, amount)
    if not ok:
        bot.reply_to(message, err, parse_mode="HTML")
        return

    target_display = get_display_name(target)
    item_display = {"cigarettes": "окурков", "rubles": "рублей", "real_cigarettes": "сигарет"}[item_key]
    commission_pct = get_bank_commission_pct()

    log_info("TRANSFER", f"user={uid} sent {amount} {item_key} to user={target_uid}, fee={fee}")

    bot.reply_to(message,
        f"🎁 Передано <b>{received}</b> {item_display} пользователю <b>{target_display}</b>.\n"
        f"🏦 Комиссия ЦБ: <b>{fee}</b> ({commission_pct}%)"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Award Command
# ═══════════════════════════════════════════════════════════════════════════════

@bot.message_handler(commands=["to_award"])
def cmd_to_award(message: types.Message):
    uid = get_uid(message)
    username = message.from_user.username or message.from_user.first_name or "unknown"
    increment_stat(uid, "commands")

    if not can_award(message):
        log_cmd(uid, username, "to_award", "DENIED - not admin")
        bot.reply_to(message, "У тебя нет прав для награждения. Только админ группы или создатель бота могут награждать.")
        return

    if not message.reply_to_message:
        bot.reply_to(message, "Ответь на сообщение человека, которого хочешь наградить.")
        return

    target = message.reply_to_message.from_user
    if target.is_bot:
        bot.reply_to(message, "Нельзя наградить бота.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "Использование: /to_award &lt;название награды&gt; (в ответ на сообщение)\nПример: /to_award Лучший курильщик")
        return

    award_name = parts[1].strip()
    target_uid = str(target.id)
    get_or_create_user(target_uid)

    add_award(target_uid, award_name)
    target_display = get_display_name(target)

    log_cmd(uid, username, "to_award", f"target={target_uid} | award='{award_name}'")

    bot.reply_to(message,
        f"🏅 <b>Награда вручена!</b>\n\n"
        f"Пользователь <b>{target_display}</b> получил награду: <b>{award_name}</b>\n\n"
        f"Награда отображается в /stats."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Reminder Checker Thread
# ═══════════════════════════════════════════════════════════════════════════════

def reminder_checker():
    while True:
        try:
            pending = get_pending_reminders()
            for r in pending:
                try:
                    bot.send_message(r["chat_id"], f"⏰ <b>Напоминание!</b>\n\n{r['text']}", _skip_reply=True)
                    mark_reminder_fired(r["id"])
                    log_info("REMINDER", f"Fired reminder id={r['id']} for user={r['user_id']}")
                except Exception as e:
                    log_err("REMINDER", f"Failed to fire reminder id={r['id']}: {e}")
        except Exception as e:
            log_err("REMINDER", f"Checker error: {e}")
        time.sleep(10)


def bank_loan_checker():
    while True:
        try:
            due_loans = get_due_loans()
            for loan in due_loans:
                try:
                    collect_bank_loan(loan["id"], loan["user_id"], loan["currency"], loan["total_due"])
                    log_info("BANK", f"Collected loan id={loan['id']} user={loan['user_id']} "
                             f"due={loan['total_due']} {loan['currency']}")
                except Exception as e:
                    log_err("BANK", f"Failed to collect loan id={loan['id']}: {e}")
        except Exception as e:
            log_err("BANK", f"Loan checker error: {e}")
        time.sleep(30)


# ═══════════════════════════════════════════════════════════════════════════════
# RP Actions (trigger words without /, reply required)
# ═══════════════════════════════════════════════════════════════════════════════

RP_ACTIONS: dict[str, tuple[str, str]] = {
    "поцеловать": ("💋", "поцеловал(а)"),
    "обнять": ("🤗", "обнял(а)"),
    "ударить": ("👊", "ударил(а)"),
    "пнуть": ("🦶", "пнул(а)"),
    "толкнуть": ("👉", "толкнул(а)"),
    "укусить": ("🦷", "укусил(а)"),
    "облизать": ("👅", "облизал(а)"),
    "погладить": ("✋", "погладил(а)"),
    "пощекотать": ("🤭", "пощекотал(а)"),
    "ткнуть": ("👆", "ткнул(а)"),
    "шлёпнуть": ("🖐", "шлёпнул(а)"),
    "пощипать": ("🤏", "щипнул(а)"),
    "обнять крепко": ("🫂", "крепко обнял(а)"),
    "прижать": ("🤗", "прижал(а)"),
    "оттолкнуть": ("🚫", "оттолкнул(а)"),
    "обнять сзади": ("🫂", "обнял(а) сзади"),
    "поцеловать в щёку": ("😘", "поцеловал(а) в щёку"),
    "поцеловать в лоб": ("💋", "поцеловал(а) в лоб"),
    "поцеловать в нос": ("👃", "поцеловал(а) в нос"),
    "поцеловать в руку": ("🤝", "поцеловал(а) руку"),
    "обнять за плечи": ("🫂", "обнял(а) за плечи"),
    "подмигнуть": ("😉", "подмигнул(а)"),
    "помахать": ("👋", "помахал(а)"),
    "кивнуть": ("🙂", "кивнул(а)"),
    "поклониться": ("🙇", "поклонился(ась)"),
    "приветствовать": ("👋", "поприветствовал(а)"),
    "попрощаться": ("👋", "попрощался(ась) с"),
    "обидеться": ("😤", "обиделся(ась) на"),
    "простить": ("💚", "простил(а)"),
    "извиниться": ("🙏", "извинился(ась) перед"),
    "поблагодарить": ("🙏", "поблагодарил(а)"),
    "похвалить": ("⭐", "похвалил(а)"),
    "оскорбить": ("😠", "оскорбил(а)"),
    "унизить": ("😈", "унизил(а)"),
    "запугать": ("👻", "запугал(а)"),
    "испугать": ("😱", "испугал(а)"),
    "успокоить": ("☮️", "успокоил(а)"),
    "утешить": ("🫂", "утешил(а)"),
    "подбодрить": ("💪", "подбодрил(а)"),
    "поддержать": ("🤝", "поддержал(а)"),
    "обнять и не отпускать": ("🫂", "обнял(а) и не отпускает"),
    "потанцевать": ("💃", "потанцевал(а) с"),
    "пригласить потанцевать": ("💃", "пригласил(а) потанцевать"),
    "спеть": ("🎤", "спел(а) для"),
    "сыграть": ("🎸", "сыграл(а) для"),
    "нарисовать": ("🎨", "нарисовал(а) для"),
    "подарить цветы": ("💐", "подарил(а) цветы"),
    "подарить подарок": ("🎁", "подарил(а) подарок"),
    "украсть": ("🦹", "украл(а) у"),
    "обокрасть": ("💰", "обокрал(а)"),
    "обмануть": ("🃏", "обманул(а)"),
    "защитить": ("🛡", "защитил(а)"),
    "спасти": ("🦸", "спас(ла)"),
    "убить": ("💀", "убил(а)"),
    "оживить": ("✨", "оживил(а)"),
    "исцелить": ("💊", "исцелил(а)"),
    "отравить": ("☠️", "отравил(а)"),
    "заколдовать": ("🔮", "заколдовал(а)"),
    "проклясть": ("😈", "проклял(а)"),
    "благословить": ("🙏", "благословил(а)"),
    "пожелать удачи": ("🍀", "пожелал(а) удачи"),
    "пожелать спокойной ночи": ("🌙", "пожелал(а) спокойной ночи"),
    "разбудить": ("⏰", "разбудил(а)"),
    "усыпить": ("😴", "усыпил(а)"),
    "накормить": ("🍽", "накормил(а)"),
    "напоить": ("🥤", "напоил(а)"),
    "угостить": ("🍰", "угостил(а)"),
    "облить": ("💦", "облил(а)"),
    "обсыпать": ("🌾", "обсыпал(а)"),
    "обнять и поцеловать": ("💋", "обнял(а) и поцеловал(а)"),
    "прижать к себе": ("🫂", "прижал(а) к себе"),
    "отвернуться": ("🙄", "отвернулся(ась) от"),
    "игнорировать": ("😐", "игнорирует"),
    "заглянуть в глаза": ("👀", "заглянул(а) в глаза"),
    "посмотреть": ("👁", "посмотрел(а) на"),
    "уставиться": ("👀", "уставился(ась) на"),
    "подставить": ("😏", "подставил(а)"),
    "спрятать": ("🙈", "спрятал(а)"),
    "найти": ("🔍", "нашёл(нашла)"),
    "погоняться": ("🏃", "погнался(ась) за"),
    "догнать": ("🏃", "догнал(а)"),
    "схватить": ("🤜", "схватил(а)"),
    "отпустить": ("🕊", "отпустил(а)"),
    "привязать": ("⛓", "привязал(а)"),
    "освободить": ("🔓", "освободил(а)"),
    "запереть": ("🔒", "запер(ла)"),
    "вытащить": ("🚪", "вытащил(а)"),
    "затащить": ("🚪", "затащил(а)"),
    "посадить": ("🪑", "посадил(а)"),
    "поднять": ("⬆️", "поднял(а)"),
    "опустить": ("⬇️", "опустил(а)"),
    "бросить": ("🎯", "бросил(а)"),
    "поймать": ("🤲", "поймал(а)"),
    "уклониться": ("💨", "уклонился(ась) от"),
    "заблокировать": ("🚫", "заблокировал(а)"),
    "разблокировать": ("✅", "разблокировал(а)"),
    "замутить": ("🔇", "замутил(а)"),
    "размутить": ("🔊", "размутил(а)"),
    "забанить": ("🔨", "забанил(а)"),
    "разбанить": ("🔓", "разбанил(а)"),
    "выдать предупреждение": ("⚠️", "выдал(а) предупреждение"),
    "снять предупреждение": ("✅", "снял(а) предупреждение"),
    "пожать руку": ("🤝", "пожал(а) руку"),
    "хлопнуть по плечу": ("🖐", "хлопнул(а) по плечу"),
    "похлопать": ("👏", "похлопал(а)"),
    "аплодировать": ("👏", "аплодировал(а)"),
    "смеяться": ("😂", "смеётся над"),
    "заплакать": ("😢", "заплакал(а) из-за"),
    "засмеяться": ("😆", "засмеялся(ась) над"),
    "загрустить": ("😔", "загрустил(а) из-за"),
    "разозлиться": ("😡", "разозлился(ась) на"),
    "улыбнуться": ("😊", "улыбнулся(ась)"),
    "расстроиться": ("😞", "расстроился(ась) из-за"),
    "обрадоваться": ("🎉", "обрадовался(ась) из-за"),
    "удивиться": ("😲", "удивился(ась) из-за"),
    "испугаться": ("😨", "испугался(ась) из-за"),
    "влюбиться": ("❤️", "влюбился(ась) в"),
    "разлюбить": ("💔", "разлюбил(а)"),
    "флиртовать": ("😏", "флиртует с"),
    "сделать комплимент": ("💝", "сделал(а) комплимент"),
    "подмигнуть игриво": ("😉", "игриво подмигнул(а)"),
    "обнять нежно": ("🥰", "нежно обнял(а)"),
    "погладить по голове": ("✋", "погладил(а) по голове"),
    "погладить по спине": ("✋", "погладил(а) по спине"),
    "погладить по щеке": ("✋", "погладил(а) по щеке"),
    "погладить по руке": ("✋", "погладил(а) по руке"),
    "обнять и погладить": ("🥰", "обнял(а) и погладил(а)"),
    "поцеловать страстно": ("💋", "страстно поцеловал(а)"),
    "поцеловать нежно": ("💕", "нежно поцеловал(а)"),
    "обнять и прижать": ("🫂", "обнял(а) и прижал(а)"),
    "обнять и пощекотать": ("🤭", "обнял(а) и пощекотал(а)"),
    "обнять и укусить": ("🦷", "обнял(а) и укусил(а)"),
    "обнять и ударить": ("👊", "обнял(а) и ударил(а)"),
    "поцеловать в шею": ("💋", "поцеловал(а) в шею"),
    "поцеловать в ухо": ("👂", "поцеловал(а) в ухо"),
    "поцеловать в губы": ("💋", "поцеловал(а) в губы"),
    "поцеловать в плечо": ("💋", "поцеловал(а) в плечо"),
    "погладить по голове": ("✋", "погладил(а) по голове"),
    "погладить по животу": ("✋", "погладил(а) по животу"),
    "погладить по лицу": ("✋", "погладил(а) по лицу"),
    "погладить по шее": ("✋", "погладил(а) по шее"),
    "погладить по ноге": ("✋", "погладил(а) по ноге"),
    "погладить по бедру": ("✋", "погладил(а) по бедру"),
    "погладить по стопе": ("✋", "погладил(а) по стопе"),
    "погладить по ладони": ("✋", "погладил(а) по ладони"),
    "погладить по волосам": ("✋", "погладил(а) по волосам"),
    "погладить по спине": ("✋", "погладил(а) по спине"),
    "погладить по щеке": ("✋", "погладил(а) по щеке"),
    "погладить по плечу": ("✋", "погладил(а) по плечу"),
    "погладить по колену": ("✋", "погладил(а) по колену"),
    "погладить по локтю": ("✋", "погладил(а) по локтю"),
    "погладить по запястью": ("✋", "погладил(а) по запястью"),
    "погладить по пальцу": ("✋", "погладил(а) по пальцу"),
    "погладить по лбу": ("✋", "погладил(а) по лбу"),
    "погладить по носу": ("👃", "погладил(а) по носу"),
    "погладить по уху": ("👂", "погладил(а) по уху"),
    "погладить по подбородку": ("✋", "погладил(а) по подборodку"),
    "погладить по губе": ("✋", "погладил(а) по губе"),
    "погладить по брови": ("✋", "погладил(а) по брови"),
    "погладить по реснице": ("✋", "погладил(а) по реснице"),
    "погладить по виску": ("✋", "погладил(а) по виску"),
    "погладить по затылку": ("✋", "погладил(а) по затылку"),
    "погладить по ключице": ("✋", "погладил(а) по ключице"),
    "погладить по икре": ("✋", "погладил(а) по икре"),
    "погладить по лодыжке": ("✋", "погладил(а) по лодыжке"),
    "погладить по бицепсу": ("✋", "погладил(а) по бицепсу"),
    "погладить по трицепсу": ("✋", "погладил(а) по трицепсу"),
    "погладить по предплечью": ("✋", "погладил(а) по предплечью"),
    "погладить по костяшкам": ("✋", "погладил(а) по костяшкам"),
    "погладить по ногтям": ("✋", "погладил(а) по ногтям"),
    "погладить по чёлке": ("✋", "погладил(а) по чёлке"),
    "погладить по косе": ("✋", "погладил(а) по косе"),
    "погладить по хвосту": ("✋", "погладил(а) по хвосту"),
    "погладить по пряди": ("✋", "погладил(а) по пряди волос"),
    "погладить по макушке": ("✋", "погладил(а) по макушке"),
    "погладить по груди": ("✋", "погладил(а) по груди"),
    "погладить по спине": ("✋", "погладил(а) по спине"),
    "погладить по талии": ("✋", "погладил(а) по талии"),
    "погладить по бёдрам": ("✋", "погладил(а) по бёдрам"),
    "погладить по ягодицам": ("✋", "погладил(а) по ягодицам"),
    "погладить по пятке": ("✋", "погладил(а) по пятке"),
    "погладить по большому пальцу": ("✋", "погладил(а) по большому пальцу"),
    "погладить по мизинцу": ("✋", "погладил(а) по мизинцу"),
    "погладить по указательному пальцу": ("✋", "погладил(а) по указательному пальцу"),
    "погладить по среднему пальцу": ("✋", "погладил(а) по среднему пальцу"),
    "погладить по безымянному пальцу": ("✋", "погладил(а) по безымянному пальцу"),
    "погладить по тыльной стороне ладони": ("✋", "погладил(а) по тыльной стороне ладони"),
    "погладить по ладони": ("✋", "погладил(а) по ладони"),
    "погладить по ступне": ("✋", "погладил(а) по ступне"),
    "погладить по голени": ("✋", "погладил(а) по голени"),
    "погладить по бедру": ("✋", "погладил(а) по бедру"),
    "погладить по плечу": ("✋", "погладил(а) по плечу"),
    "погладить по шее": ("✋", "погладил(а) по шее"),
    "погладить по спине": ("✋", "погладил(а) по спине"),
    "погладить по груди": ("✋", "погладил(а) по груди"),
    "погладить по животу": ("✋", "погладил(а) по животу"),
    "погладить по спине": ("✋", "погладил(а) по спине"),
}

_RP_SORTED_KEYS = sorted(RP_ACTIONS.keys(), key=len, reverse=True)


def _rp_normalize(text: str) -> str:
    """Normalize RP trigger text for reliable matching."""
    t = (text or "").strip().lower().replace("ё", "е")
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"^[!.,;:\s]+|[!.,;:?…«»\"'()]+$", "", t)
    return t


def _match_rp_action(text: str) -> Optional[str]:
    normalized = _rp_normalize(text)
    if not normalized:
        return None
    for key in _RP_SORTED_KEYS:
        nk = _rp_normalize(key)
        if normalized == nk:
            return key
        if normalized.startswith(nk + " ") or normalized.startswith(nk + ","):
            return key
    return None


def _rp_text_from_message(message: types.Message) -> str:
    """Message text for RP matching, without bot mention."""
    text = message.text or ""
    bot_info = bot.get_me()
    if bot_info and bot_info.username:
        text = re.sub(rf"@?{re.escape(bot_info.username)}", "", text, flags=re.IGNORECASE)
    return text.strip()


def try_rp_action(message: types.Message) -> bool:
    """Handle RP trigger words (reply required). Returns True if handled."""
    if not message.reply_to_message:
        return False
    target_user = message.reply_to_message.from_user
    if not target_user or target_user.is_bot:
        return False
    action_key = _match_rp_action(_rp_text_from_message(message))
    if not action_key:
        return False
    emoji, action = RP_ACTIONS[action_key]
    actor = get_display_name(message.from_user)
    target = get_display_name(target_user)
    try:
        set_reply_context(message)
        bot.reply_to(message, f"{emoji} <b>{actor}</b> {action} <b>{target}</b>", parse_mode="HTML")
    except Exception as e:
        log_err("RP", f"Failed to send RP reply: {e}")
        return False
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# Text Handler
# ═══════════════════════════════════════════════════════════════════════════════

def should_respond(message: types.Message) -> bool:
    if not is_group(message):
        return True

    text_lower = (message.text or "").lower().strip()
    words = set(text_lower.split())
    if words & TRIGGER_WORDS:
        return True

    if message.reply_to_message:
        reply_user = message.reply_to_message.from_user
        if reply_user and reply_user.id == bot.get_me().id:
            return True

    bot_info = bot.get_me()
    if bot_info.username and f"@{bot_info.username.lower()}" in text_lower:
        return True

    return False


def extract_clean_text(message: types.Message) -> str:
    text = message.text or ""
    bot_info = bot.get_me()
    if bot_info.username:
        text = text.replace(f"@{bot_info.username}", "").strip()
    return text


@bot.message_handler(func=lambda m: m.content_type == "text" and not (m.text or "").startswith("/"), content_types=["text"])
def handle_text(message: types.Message):
    register_chat(message.chat.id)
    uid = get_uid(message)
    track_chat_member(message.chat.id, message.from_user)
    increment_stat(uid, "messages")
    set_first_message_if_null(uid)

    if message.from_user.username:
        update_username(uid, message.from_user.username)

    # RP first — must not depend on should_respond or random quote
    if try_rp_action(message):
        return

    if should_respond(message):
        track_daily_activity(uid)
    else:
        track_daily_chat_activity(uid, message.chat.id)

    maybe_send_random_quote(message)

    if str(uid) in CRYPTO_PENDING:
        return

    if str(uid) in BANK_PENDING:
        return

    if random.random() < REACTION_CHANCE:
        try:
            reactions = ["👍", "👎", "❤️", "🔥", "🥰", "👏", "😁", "🤔", "🤯", "😱", "😂", "🤡"]
            reaction = random.choice(reactions)
            bot.set_message_reaction(chat_id=message.chat.id, message_id=message.message_id, reaction=[types.ReactionTypeEmoji(reaction)])
        except Exception as e:
            log_err("REACTION", f"Failed: {e}")

    if not should_respond(message):
        return

    username = message.from_user.username or message.from_user.first_name or "unknown"

    text_lower = (message.text or "").lower().strip()
    words = set(text_lower.split())

    if words & TRIGGER_WORDS:
        triggered = words & TRIGGER_WORDS
        trigger = list(triggered)[0]
        responses = {
            "зырис": "Зырис-мырис, сам такой!",
            "ziris": "Ziris? Серьёзно?",
            "чмо": "Эй, полегче с выражениями!",
        }
        reply_text = responses.get(trigger, "Интересное словечко.")
        log_cmd(uid, username, f"trigger:{trigger}", message.text[:50] if message.text else "")
        bot.reply_to(message, reply_text)
        return

    user_text = extract_clean_text(message)
    if not user_text:
        return

    log_cmd(uid, username, "chat", user_text[:80])
    wait_msg = bot.reply_to(message, f"Думаю... подожди {AI_DELAY} сек.")
    bot.send_chat_action(message.chat.id, "typing")

    def _reply():
        try:
            set_reply_context(message)
            answer = ask_ai(uid, user_text)
            if not answer or not str(answer).strip():
                answer = "Не получилось сформировать ответ. Попробуй ещё раз."
            try:
                bot.delete_message(message.chat.id, wait_msg.message_id)
            except Exception:
                pass
            bot.reply_to(message, answer)
        except Exception as e:
            log_err("AI", f"Reply thread failed for user={uid}: {e}")
            try:
                bot.delete_message(message.chat.id, wait_msg.message_id)
            except Exception:
                pass
            try:
                set_reply_context(message)
                bot.reply_to(message, "Не удалось отправить ответ. Попробуй позже.")
            except Exception:
                pass

    threading.Thread(target=_reply, daemon=True).start()


# ═══════════════════════════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    log_info("STARTUP", "Bot starting...")
    log_info("CONFIG", f"Proxy: {'configured' if PROXY_URL else 'disabled'}")
    log_info("CONFIG", f"AI_DELAY: {AI_DELAY}s")
    log_info("CONFIG", f"Admins: {list(ADMIN_USERNAMES) if ADMIN_USERNAMES else 'none configured'}")
    log_info("CONFIG", f"Database: {DB_HOST}:{DB_PORT}/{DB_NAME}")

    def preload_tts():
        log_info("TTS", "Preloading Silero TTS model...")
        if init_silero():
            log_info("TTS", "Silero TTS ready.")
        else:
            log_err("TTS", "Failed to load Silero TTS model")

    threading.Thread(target=preload_tts, daemon=True).start()
    threading.Thread(target=reminder_checker, daemon=True).start()
    threading.Thread(target=bank_loan_checker, daemon=True).start()

    log_info("STARTUP", "Starting polling...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
