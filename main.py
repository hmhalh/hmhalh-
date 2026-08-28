# -*- coding: utf-8 -*-

import json
import asyncio
from pathlib import Path

from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


# =========================================================
# الإعدادات
# =========================================================

BOT_TOKEN = "8935158045:AAHKN_cuzmRwwgLirCk7i-fUIxoAlAGmMNU"

API_ID = 26928420
API_HASH = "0facea2bb49930df0718fb74cda1790d"

ADMIN_ID = 7199778669


# =========================================================
# الملفات والمجلدات
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
SESSION_DIR = BASE_DIR / "sessions"

DATA_DIR.mkdir(exist_ok=True)
SESSION_DIR.mkdir(exist_ok=True)

DATA_FILE = DATA_DIR / "data.json"


# =========================================================
# البيانات
# =========================================================

def default_data():
    return {
        "account": None,
        "session_file": None,
        "groups": [],
        "messages": {},
        "selected_groups": [],
        "selected_message": None,
        "delay": 60,
        "running": False,
        "limit_mode": "unlimited",
        "max_messages": 0,
        "sent_count": 0
    }


def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("❌ خطأ بحفظ البيانات:", e)


def load_data():
    defaults = default_data()
    if not DATA_FILE.exists():
        save_data(defaults)
        return defaults

    try:
        text = DATA_FILE.read_text(encoding="utf-8").strip()
        if not text:
            save_data(defaults)
            return defaults

        loaded = json.loads(text)
        if not isinstance(loaded, dict):
            save_data(defaults)
            return defaults

        for key, value in defaults.items():
            if key not in loaded:
                loaded[key] = value

        return loaded

    except Exception as e:
        print("⚠️ خطأ في قراءة البيانات:", e)
        save_data(defaults)
        return defaults


data = load_data()


# =========================================================
# المتغيرات
# =========================================================

telegram_client = None
login_state = {}


# =========================================================
# الحماية
# =========================================================

def is_admin(update):
    user = update.effective_user
    return user is not None and user.id == ADMIN_ID


# =========================================================
# الجلسة
# =========================================================

async def get_client():
    global telegram_client
    
    session_name = data.get("session_file") or "main_account"
    session_path = SESSION_DIR / session_name

    if telegram_client is None:
        telegram_client = TelegramClient(
            str(session_path),
            API_ID,
            API_HASH
        )

    if not telegram_client.is_connected():
        await telegram_client.connect()

    return telegram_client


async def disconnect_client():
    global telegram_client
    if telegram_client:
        try:
            await telegram_client.disconnect()
        except Exception:
            pass
        telegram_client = None


async def account_is_ready():
    if not data.get("account"):
        return False

    try:
        client = await get_client()
        return await client.is_user_authorized()
    except Exception:
        return False


# =========================================================
# مهمة النشر التلقائي (مصححة لإرسال الرسائل بدقة)
# =========================================================

async def auto_publisher(app: Application):
    while True:
        try:
            if data.get("running", False):
                selected_groups = data.get("selected_groups", [])
                msg_id = data.get("selected_message")
                msg_text = data.get("messages", {}).format() if isinstance(data.get("messages"), dict) else None
                
                # جلب النص بالطريقة الصحيحة بناءً على مفتاح الرسالة
                if msg_id and str(msg_id) in data.get("messages", {}):
                    msg_text = data["messages"][str(msg_id)]

                limit_mode = data.get("limit_mode", "unlimited")
                max_msgs = data.get("max_messages", 0)
                sent_cnt = data.get("sent_count", 0)

                if limit_mode == "custom" and sent_cnt >= max_msgs:
                    data["running"] = False
                    save_data(data)
                    print("🛑 تم الوصول للعدد المحدد من الرسائل واكتمل النشر.")
                elif selected_groups and msg_text and await account_is_ready():
                    client = await get_client()
                    for group in selected_groups:
                        if not data.get("running", False):
                            break
                        try:
                            # 1. معالجة معرف الكروب أو الـ Username وتجنب أخطاء الانضمام
                            target_entity = group
                            if group.startswith("@") or group.lstrip("-").isdigit():
                                try:
                                    target_entity = await client.get_entity(group)
                                except Exception:
                                    pass

                            # 2. محاولة الانضمام إذا كان معرف نصي عام
                            try:
                                if group.startswith("@"):
                                    await client(JoinChannelRequest(group))
                                    await asyncio.sleep(2)
                            except Exception:
                                pass

                            # 3. إرسال الرسالة مباشرة للكيان الصحيح
                            await client.send_message(target_entity, msg_text)
                            data["sent_count"] = data.get("sent_count", 0) + 1
                            save_data(data)
                            print(f"✅ تم إرسال الرسالة بنجاح إلى: {group}")
                        except Exception as e_send:
                            print(f"❌ خطأ مفصل أثناء الإرسال إلى {group}: {e_send}")

                        if limit_mode == "custom" and data["sent_count"] >= max_msgs:
                            data["running"] = False
                            save_data(data)
                            break
        except Exception as e:
            print("❌ خطأ بمهمة النشر:", e)

        delay = max(data.get("delay", 60), 5)
        await asyncio.sleep(delay)


# =========================================================
# أسماء البيانات
# =========================================================

def account_name():
    if not data.get("account"):
        return "غير مضاف"
    return data["account"].get("name", "الحساب")


def selected_groups_text():
    groups = data.get("selected_groups", [])
    if not groups:
        return "غير محدد"
    return ", ".join(groups)


def selected_message_name():
    message_id = data.get("selected_message")
    if not message_id:
        return "غير محددة"
    return f"رسالة #{message_id}"


def limit_status_text():
    mode = data.get("limit_mode", "unlimited")
    if mode == "unlimited":
        return "♾️ بلا حدود"
    return f"🎯 {data.get('sent_count', 0)} / {data.get('max_messages', 0)} رسالة"


# =========================================================
# لوحة التحكم
# =========================================================

def home_keyboard():
    toggle_text = "⏹️ إيقاف" if data.get("running", False) else "▶️ تشغيل"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👤 الحساب", callback_data="account"),
            InlineKeyboardButton("👥 الكروبات", callback_data="groups")
        ],
        [
            InlineKeyboardButton("💬 الرسائل", callback_data="messages"),
            InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")
        ],
        [
            InlineKeyboardButton("🎯 نظام النشر", callback_data="limit_menu")
        ],
        [
            InlineKeyboardButton("📊 الحالة", callback_data="status")
        ],
        [
            InlineKeyboardButton(toggle_text, callback_data="toggle_run")
        ]
    ])


async def show_home(query):
    user_id = query.from_user.id if hasattr(query, 'from_user') else query.message.chat_id
    login_state.pop(user_id, None)

    status_str = "🟢 شغال" if data.get("running", False) else "🔴 متوقف"

    await query.edit_message_text(
        "🤖 **لوحة التحكم الرئيسية**\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 الحساب: `{account_name()}`\n\n"
        f"👥 الكروبات المحددة: `{selected_groups_text()}`\n\n"
        f"💬 الرسالة: `{selected_message_name()}`\n\n"
        f"🎯 الوضع: `{limit_status_text()}`\n\n"
        f"⏱️ الفاصل: `{data['delay']} ثانية`\n\n"
        f"⚙️ الحالة العامة: {status_str}\n"
        "━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=home_keyboard()
    )


def back_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔙 رجوع", callback_data="home")
        ]
    ])


# =========================================================
# START & CANCEL
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ غير مسموح.")
        return

    login_state.pop(update.effective_user.id, None)

    status_str = "🟢 شغال" if data.get("running", False) else "🔴 متوقف"

    await update.message.reply_text(
        "🤖 **لوحة التحكم الرئيسية**\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 الحساب: `{account_name()}`\n\n"
        f"👥 الكروبات المحددة: `{selected_groups_text()}`\n\n"
        f"💬 الرسالة: `{selected_message_name()}`\n\n"
        f"🎯 الوضع: `{limit_status_text()}`\n\n"
        f"⏱️ الفاصل: `{data['delay']} ثانية`\n\n"
        f"⚙️ الحالة العامة: {status_str}\n"
        "━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=home_keyboard()
    )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    login_state.pop(update.effective_user.id, None)

    await update.message.reply_text(
        "❌ تم الإلغاء والعودة للوحة التحكم.",
        reply_markup=home_keyboard()
    )


# =========================================================
# قائمة الحسابات والتعامل مع ملفات الجلسات الجاهزة
# =========================================================

async def account_menu(query):
    ready = await account_is_ready()
    status = "🟢 متصل" if ready else "🔴 غير متصل"

    buttons = []
    if data.get("account"):
        buttons.append([InlineKeyboardButton("🔌 حالة الحساب", callback_data="account_status")])
        buttons.append([InlineKeyboardButton("🗑️ حذف الحساب", callback_data="delete_account")])

    buttons.append([InlineKeyboardButton("➕ تسجيل جديد (رقم)", callback_data="add_account")])
    buttons.append([InlineKeyboardButton("📁 اختار جلسة من المجلد", callback_data="choose_session_file")])
    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="home")])

    await query.edit_message_text(
        f"👤 **قائمة الحسابات**\n\n"
        f"الحساب الحالي: {account_name()}\n"
        f"الحالة: {status}\n\n"
        "يمكنك تسجيل رقم جديد أو اختيار ملف .session جاهز من مجلد sessions.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def choose_session_file(update, context):
    query = update.callback_query

    session_files = list(SESSION_DIR.glob("*.session"))
    buttons = []

    if not session_files:
        await query.edit_message_text(
            "❌ لا توجد ملفات `.session` داخل مجلد `sessions`!\n\n"
            "ضع ملف الجلسة مثل `9647741904221.session` داخل المجلد وحاول مجدداً.",
            reply_markup=back_keyboard()
        )
        return

    for s_file in session_files:
        file_stem = s_file.stem
        is_active = "✅ " if data.get("session_file") == file_stem else ""
        buttons.append([InlineKeyboardButton(f"{is_active}📄 {file_stem}.session", callback_data=f"set_session:{file_stem}")])

    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="account")])

    await query.edit_message_text(
        "📁 **اختر ملف الجلسة المطلوب:**",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def set_session(update, context):
    query = update.callback_query
    session_stem = query.data.split(":", 1)

    await disconnect_client()

    data["session_file"] = session_stem
    save_data(data)

    client = await get_client()

    try:
        if await client.is_user_authorized():
            me = await client.get_me()
            name = f"@{me.username}" if me.username else me.first_name or "الحساب"
            data["account"] = {"name": name, "id": me.id}
            save_data(data)

            await query.edit_message_text(
                f"✅ تم ربط الجلسة {session_stem}.session بنجاح!\n\n"
                f"👤 الاسم: {name}\n"
                f"🆔 الآيدي: {me.id}",
                reply_markup=back_keyboard()
            )
        else:
            await query.edit_message_text(
                f"❌ ملف الجلسة {session_stem}.session غير مفعل أو منتهي الصلاحية.",
                reply_markup=back_keyboard()
            )
    except Exception as e:
        await query.edit_message_text(
            f"❌ حدث خطأ أثناء تشغيل الجلسة:\n{e}",
            reply_markup=back_keyboard()
        )


async def add_account(update, context):
    query = update.callback_query
    await query.answer()

    login_state[update.effective_user.id] = {"step": "phone"}

    await query.edit_message_text(
        "➕ **إضافة الحساب**\n\n"
        "أرسل رقم الهاتف مع مفتاح الدولة.\n\n"
        "مثال:\n"
        "`+9647xxxxxxxxx`\n\n"
        "للإلغاء اكتب /cancel",
        parse_mode="Markdown",
        reply_markup=back_keyboard()
    )


async def process_phone(update, phone):
    user_id = update.effective_user.id
    
    data["session_file"] = "main_account"
    save_data(data)
    await disconnect_client()
    
    client = await get_client()

    try:
        await client.send_code_request(phone)
        login_state[user_id] = {
            "step": "code",
            "phone": phone
        }
        await update.message.reply_text(
            "🔐 تم إرسال كود Telegram.\n\nأرسل الكود.",
            reply_markup=back_keyboard()
        )

    except Exception as e:
        await update.message.reply_text(f"❌ خطأ:\n{e}", reply_markup=back_keyboard())


async def process_code(update, code):
    user_id = update.effective_user.id
    state = login_state.get(user_id)

    if not state:
        return

    client = await get_client()

    try:
        await client.sign_in(
            phone=state["phone"],
            code=code
        )
        await save_account(update, client)
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ:\n{e}", reply_markup=back_keyboard())


async def process_password(update, password):
    user_id = update.effective_user.id
    client = await get_client()

    try:
        await client.sign_in(password=password)
        await save_account(update, client)
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ:\n{e}", reply_markup=back_keyboard())


async def save_account(update, client):
    me = await client.get_me()
    name = f"@{me.username}" if me.username else me.first_name or "الحساب"

    data["account"] = {
        "name": name,
        "id": me.id
    }

    save_data(data)
    login_state.pop(update.effective_user.id, None)

    await update.message.reply_text(
        f"✅ تمت إضافة الحساب بنجاح!\n\n"
        f"👤 الاسم: {name}\n"
        f"🆔 الآيدي: {me.id}",
        reply_markup=back_keyboard()
    )


async def account_status(update, context):
    query = update.callback_query
    ready = await account_is_ready()
    status = "🟢 متصل ويعمل" if ready else "🔴 غير متصل"

    await query.edit_message_text(
        f"🔌 حالة الحساب\n\n"
        f"👤 الحساب: {account_name()}\n"
        f"📡 الحالة: {status}",
        reply_markup=back_keyboard()
    )


async def delete_account(update, context):
    query = update.callback_query
    data["account"] = None
    data["session_file"] = None
    save_data(data)

    await disconnect_client()

    await query.edit_message_text(
        "✅ تم إلغاء ربط الحساب الحالي.",
        reply_markup=back_keyboard()
    )


# =========================================================
# الكروبات
# =========================================================

async def groups_menu(query):
    await query.edit_message_text(
        "👥 **الكروبات**\n\n"
        f"عدد الكروبات الكلي: `{len(data['groups'])}`\n"
        f"الكروبات المحددة: `{len(data.get('selected_groups', []))}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ إضافة كروب", callback_data="add_group")],
            [InlineKeyboardButton("🎯 تحديد الكروبات للنشر", callback_data="select_group")],
            [InlineKeyboardButton("🗑️ حذف كروب", callback_data="delete_group")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="home")]
        ])
    )


async def add_group(update, context):
    query = update.callback_query
    await query.answer()

    login_state[update.effective_user.id] = {"step": "group"}

    await query.edit_message_text(
        "➕ **إضافة كروب**\n\n"
        "أرسل Username الكروب أو الـ ID.\n\n"
        "مثال:\n"
        "`@mygroup`",
        parse_mode="Markdown",
        reply_markup=back_keyboard()
    )


async def delete_group(update, context):
    query = update.callback_query

    buttons = []
    for group in data["groups"]:
        buttons.append([InlineKeyboardButton(f"🗑️ {group}", callback_data=f"remove_group:{group}")])

    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="home")])

    await query.edit_message_text(
        "🗑️ **حذف كروب**\n\nاختر الكروب لإزالته:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def remove_group(update, context):
    query = update.callback_query
    group = query.data.split(":", 1)

    if group in data["groups"]:
        data["groups"].remove(group)

    if group in data.get("selected_groups", []):
        data["selected_groups"].remove(group)

    save_data(data)

    await query.edit_message_text(
        "✅ تم حذف الكروب.",
        reply_markup=back_keyboard()
    )


async def select_group(update, context):
    query = update.callback_query

    selected_list = data.get("selected_groups", [])
    buttons = []

    for group in data["groups"]:
        is_sel = group in selected_list
        icon = "✅ " if is_sel else "❌ "
        buttons.append([InlineKeyboardButton(f"{icon}{group}", callback_data=f"toggle_group:{group}")])

    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="home")])

    await query.edit_message_text(
        "🎯 **اختيار الكروبات للنشر**\n"
        "اضغط على الكروب لتحديده أو إلغاء تحديده:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def toggle_group(update, context):
    query = update.callback_query
    group = query.data.split(":", 1)

    if "selected_groups" not in data or not isinstance(data["selected_groups"], list):
        data["selected_groups"] = []

    if group in data["selected_groups"]:
        data["selected_groups"].remove(group)
    else:
        data["selected_groups"].append(group)

    save_data(data)
    await select_group(update, context)


# =========================================================
# تحديد أعداد الرسائل
# =========================================================

async def limit_menu(query):
    current_mode = data.get("limit_mode", "unlimited")
    mode_str = "♾️ رسائل بلا حدود" if current_mode == "unlimited" else f"🎯 عدد محدد ({data.get('max_messages', 0)} رسالة)"

    buttons = [
        [InlineKeyboardButton("♾️ رسائل بلا حدود", callback_data="set_unlimited")],
        [InlineKeyboardButton("🔢 تحديد عدد الرسائل", callback_data="set_custom_limit")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="home")]
    ]

    await query.edit_message_text(
        "🎯 **نظام أعداد الرسائل**\n\n"
        f"الوضع الحالي: `{mode_str}`\n"
        f"المرسل حالياً: `{data.get('sent_count', 0)}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def set_unlimited(query):
    data["limit_mode"] = "unlimited"
    data["sent_count"] = 0
    save_data(data)
    await query.answer("✅ تم التعيين على: رسائل بلا حدود")
    await limit_menu(query)


async def set_custom_limit_prompt(update, context):
    query = update.callback_query
    await query.answer()

    login_state[update.effective_user.id] = {"step": "max_messages"}

    await query.edit_message_text(
        "🔢 **تحديد عدد الرسائل**\n\n"
        "أرسل كمية الرسائل المطلوب إرسالها (مثال: `50`):",
        parse_mode="Markdown",
        reply_markup=back_keyboard()
    )


# =========================================================
# الرسائل
# =========================================================

async def messages_menu(query):
    await query.edit_message_text(
        "💬 **الرسائل**\n\n"
        f"عدد الرسائل: `{len(data['messages'])}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ إضافة رسالة", callback_data="add_message")],
            [InlineKeyboardButton("📋 الرسائل", callback_data="message_list")],
            [InlineKeyboardButton("🎯 اختيار رسالة", callback_data="select_message")],
            [InlineKeyboardButton("🗑️ حذف رسالة", callback_data="delete_message")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="home")]
        ])
    )


async def add_message(update, context):
    query = update.callback_query
    await query.answer()

    login_state[update.effective_user.id] = {"step": "message"}

    await query.edit_message_text(
        "➕ **إضافة رسالة**\n\nأرسل نص الرسالة.",
        parse_mode="Markdown",
        reply_markup=back_keyboard()
    )


async def message_list(update, context):
    query = update.callback_query

    text = "📋 **الرسائل**\n\n"
    if not data["messages"]:
        text += "❌ لا توجد رسائل."
    else:
        for message_id, message in data["messages"].items():
            selected = " 🎯" if data["selected_message"] == message_id else ""
            text += f"#{message_id}{selected}\n{message[:100]}\n\n"

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=back_keyboard()
    )


async def select_message(update, context):
    query = update.callback_query

    buttons = []
    for message_id in data["messages"]:
        selected = "✅ " if data["selected_message"] == message_id else ""
        buttons.append([InlineKeyboardButton(f"{selected}رسالة #{message_id}", callback_data=f"choose_message:{message_id}")])

    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="home")])

    await query.edit_message_text(
        "🎯 **اختيار الرسالة**",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def choose_message(update, context):
    query = update.callback_query
    message_id = query.data.split(":", 1)

    data["selected_message"] = message_id
    save_data(data)

    await query.edit_message_text(
        f"✅ تم اختيار الرسالة #{message_id}",
        reply_markup=back_keyboard()
    )


async def delete_message(update, context):
    query = update.callback_query

    buttons = []
    for message_id in data["messages"]:
        buttons.append([InlineKeyboardButton(f"🗑️ رسالة #{message_id}", callback_data=f"remove_message:{message_id}")])

    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="home")])

    await query.edit_message_text(
        "🗑️ **حذف رسالة**\n\nاختر الرسالة:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def remove_message(update, context):
    query = update.callback_query
    message_id = query.data.split(":", 1)

    if message_id in data["messages"]:
        del data["messages"][message_id]

    if data["selected_message"] == message_id:
        data["selected_message"] = None

    save_data(data)

    await query.edit_message_text(
        "✅ تم حذف الرسالة.",
        reply_markup=back_keyboard()
    )


# =========================================================
# الإعدادات والحالة
# =========================================================

async def settings_menu(query):
    await query.edit_message_text(
        f"⚙️ **الإعدادات**\n\n⏱️ الفاصل الحالي: `{data['delay']}` ثانية.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏱️ تغيير الفاصل الزمني", callback_data="change_delay")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="home")]
        ])
    )


async def change_delay(update, context):
    query = update.callback_query
    await query.answer()

    login_state[update.effective_user.id] = {"step": "delay"}

    await query.edit_message_text(
        "⏱️ **تغيير الفاصل الزمني**\n\nأرسل الفاصل الزمني بالثواني (مثال: `60`).",
        parse_mode="Markdown",
        reply_markup=back_keyboard()
    )


async def status_menu(query):
    ready = await account_is_ready()
    status = "🟢 متصل" if ready else "🔴 غير متصل"
    run_status = "🟢 شغال" if data.get("running", False) else "🔴 متوقف"

    await query.edit_message_text(
        f"📊 حالة البوت\n\n"
        f"👤 الحساب: {account_name()} ({status})\n"
        f"👥 الكروبات الكلية: {len(data['groups'])}\n"
        f"👥 الكروبات المحددة: {len(data.get('selected_groups', []))}\n"
        f"💬 الرسائل: {len(data['messages'])}\n"
        f"🎯 الوضع: {limit_status_text()}\n"
        f"⏱️ الفاصل: {data['delay']} ثانية\n"
        f"⚙️ الحالة: {run_status}\n",
        reply_markup=back_keyboard()
    )


async def toggle_run(query):
    current_state = data.get("running", False)
    data["running"] = not current_state
    if data["running"]:
        data["sent_count"] = 0
    save_data(data)
    await show_home(query)


# =========================================================
# معالج النصوص الواردة
# =========================================================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    user_id = update.effective_user.id
    text = update.message.text.strip()
    state = login_state.get(user_id)

    if not state:
        return

    step = state.get("step")

    if step == "phone":
        await process_phone(update, text)
    elif step == "code":
        await process_code(update, text)
    elif step == "password":
        await process_password(update, text)
    elif step == "group":
        if not text.startswith("@") and not text.lstrip("-").isdigit():
            text = f"@{text}"
        if text not in data["groups"]:
            data["groups"].append(text)
            save_data(data)
            await update.message.reply_text(f"✅ تم إضافة الكروب {text}", reply_markup=back_keyboard())
        else:
            await update.message.reply_text("⚠️ الكروب موجود بالفعل.", reply_markup=back_keyboard())
        login_state.pop(user_id, None)
    elif step == "message":
        new_id = str(len(data["messages"]) + 1)
        data["messages"][new_id] = text
        save_data(data)
        await update.message.reply_text(f"✅ تم إضافة الرسالة #{new_id}", reply_markup=back_keyboard())
        login_state.pop(user_id, None)
    elif step == "delay":
        if text.isdigit():
            data["delay"] = int(text)
            save_data(data)
            await update.message.reply_text(f"✅ تم تغيير الفاصل إلى {text} ثانية.", reply_markup=back_keyboard())
            login_state.pop(user_id, None)
        else:
            await update.message.reply_text("❌ يرجى إدخال رقم صحيح.", reply_markup=back_keyboard())
    elif step == "max_messages":
        if text.isdigit() and int(text) > 0:
            data["limit_mode"] = "custom"
            data["max_messages"] = int(text)
            data["sent_count"] = 0
            save_data(data)
            await update.message.reply_text(f"✅ تم تحديد عدد الرسائل بـ {text} رسالة.", reply_markup=back_keyboard())
            login_state.pop(user_id, None)
        else:
            await update.message.reply_text("❌ يرجى إدخال رقم صحيح أكبر من 0.", reply_markup=back_keyboard())


# =========================================================
# معالج الأزرار الشفافة
# =========================================================

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(update):
        return

    cb = query.data

    if cb == "home":
        await show_home(query)
    elif cb == "account":
        await account_menu(query)
    elif cb == "add_account":
        await add_account(update, context)
    elif cb == "choose_session_file":
        await choose_session_file(update, context)
    elif cb.startswith("set_session:"):
        await set_session(update, context)
    elif cb == "account_status":
        await account_status(update, context)
    elif cb == "delete_account":
        await delete_account(update, context)
    elif cb == "groups":
        await groups_menu(query)
    elif cb == "add_group":
        await add_group(update, context)
    elif cb == "delete_group":
        await delete_group(update, context)
    elif cb.startswith("remove_group:"):
        await remove_group(update, context)
    elif cb == "select_group":
        await select_group(update, context)
    elif cb.startswith("toggle_group:"):
        await toggle_group(update, context)
    elif cb == "limit_menu":
        await limit_menu(query)
    elif cb == "set_unlimited":
        await set_unlimited(query)
    elif cb == "set_custom_limit":
        await set_custom_limit_prompt(update, context)
    elif cb == "messages":
        await messages_menu(query)
    elif cb == "add_message":
        await add_message(update, context)
    elif cb == "message_list":
        await message_list(update, context)
    elif cb == "select_message":
        await select_message(update, context)
    elif cb.startswith("choose_message:"):
        await choose_message(update, context)
    elif cb == "delete_message":
        await delete_message(update, context)
    elif cb.startswith("remove_message:"):
        await remove_message(update, context)
    elif cb == "settings":
        await settings_menu(query)
    elif cb == "change_delay":
        await change_date = await change_delay(update, context)
    elif cb == "status":
        await status_menu(query)
    elif cb == "toggle_run":
        await toggle_run(query)


async def post_init(app: Application):
    asyncio.create_task(auto_publisher(app))


# =========================================================
# التشغيل الرئيسي
# =========================================================

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("تم تشغيل البوت بنجاح")
    app.run_polling()


if __name__ == "__main__":
    main()
