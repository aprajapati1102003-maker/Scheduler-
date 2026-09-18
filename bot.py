import asyncio, os, sqlite3
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

DB = os.getenv("DATABASE_PATH", "scheduler.db")
TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Kolkata"))
ADMIN_ID = int(os.environ["ADMIN_ID"])
TOKEN = os.environ["BOT_TOKEN"]

conn = sqlite3.connect(DB, check_same_thread=False)
conn.execute("""CREATE TABLE IF NOT EXISTS jobs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 chat_id TEXT NOT NULL, photo_id TEXT, caption TEXT, button_text TEXT,
 button_url TEXT, frequency TEXT NOT NULL, hour INTEGER, minute INTEGER,
 weekday INTEGER, active INTEGER DEFAULT 1
)""")
conn.commit()

def jobs():
    return conn.execute("SELECT * FROM jobs WHERE active=1").fetchall()

async def is_admin(update):
    return update.effective_user and update.effective_user.id == ADMIN_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update): return
    await update.message.reply_text(
        "Earning Wallah Scheduler\n\n"
        "/add — create a recurring post\n"
        "/list — show active schedules\n"
        "/delete ID — delete a schedule\n"
        "/test — send the current draft\n\n"
        "Use /add and follow the prompts."
    )

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update): return
    context.user_data["draft"] = {}
    context.user_data["state"] = "photo"
    await update.message.reply_text("1/7 Send the photo for the recurring post.")

async def receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update): return
    state = context.user_data.get("state")
    if not state: return
    d = context.user_data["draft"]

    if state == "photo" and update.message.photo:
        d["photo_id"] = update.message.photo[-1].file_id
        d["caption"] = ""
        context.user_data["state"] = "caption"
        await update.message.reply_text("2/7 Send the caption. Send /skip for no caption.")
    elif state == "caption" and update.message.text:
        d["caption"] = "" if update.message.text == "/skip" else update.message.text
        context.user_data["state"] = "button_text"
        await update.message.reply_text("3/7 Button text, e.g. 🚀 JOIN DIWAPAY. Send /skip for no button.")
    elif state == "button_text" and update.message.text:
        d["button_text"] = "" if update.message.text == "/skip" else update.message.text
        if d["button_text"]:
            context.user_data["state"] = "button_url"
            await update.message.reply_text("4/7 Send the button URL.")
        else:
            d["button_url"] = ""
            context.user_data["state"] = "chat"
            await update.message.reply_text("4/7 Send the channel username, e.g. @earningwallahh")
    elif state == "button_url" and update.message.text:
        d["button_url"] = update.message.text
        context.user_data["state"] = "chat"
        await update.message.reply_text("5/7 Send the channel username, e.g. @earningwallahh")
    elif state == "chat" and update.message.text:
        d["chat_id"] = update.message.text.strip()
        context.user_data["state"] = "frequency"
        await update.message.reply_text("6/7 Frequency: daily or weekly")
    elif state == "frequency" and update.message.text:
        f = update.message.text.lower().strip()
        if f not in ("daily", "weekly"):
            await update.message.reply_text("Please send exactly: daily or weekly")
            return
        d["frequency"] = f
        context.user_data["state"] = "time"
        await update.message.reply_text(
            "7/7 Send time in IST as HH:MM (24-hour). "
            + ("Then I will ask for weekday (Mon=0...Sun=6)." if f == "weekly" else "")
        )
    elif state == "time" and update.message.text:
        try:
            h, m = map(int, update.message.text.strip().split(":"))
            if not (0 <= h <= 23 and 0 <= m <= 59): raise ValueError
        except:
            await update.message.reply_text("Use HH:MM, e.g. 20:30")
            return
        d["hour"], d["minute"] = h, m
        if d["frequency"] == "weekly":
            context.user_data["state"] = "weekday"
            await update.message.reply_text("Send weekday number: Mon=0, Tue=1 ... Sun=6")
        else:
            d["weekday"] = None
            await save_job(update, context)

    elif state == "weekday" and update.message.text:
        try: wd = int(update.message.text)
        except: wd = -1
        if wd not in range(7):
            await update.message.reply_text("Use 0 to 6: Mon=0 ... Sun=6")
            return
        d["weekday"] = wd
        await save_job(update, context)

async def save_job(update, context):
    d = context.user_data["draft"]
    cur = conn.execute(
        "INSERT INTO jobs(chat_id,photo_id,caption,button_text,button_url,frequency,hour,minute,weekday) VALUES(?,?,?,?,?,?,?,?,?)",
        (d["chat_id"],d["photo_id"],d["caption"],d["button_text"],d["button_url"],d["frequency"],d["hour"],d["minute"],d["weekday"])
    )
    conn.commit()
    jid = cur.lastrowid
    context.user_data.clear()
    await update.message.reply_text(f"✅ Schedule #{jid} saved in Asia/Kolkata (IST).")

async def list_jobs(update, context):
    if not await is_admin(update): return
    rows = jobs()
    if not rows:
        await update.message.reply_text("No active schedules.")
        return
    out=[]
    for r in rows:
        jid, chat, photo, cap, bt, bu, freq, h, mi, wd, active = r
        day = "" if wd is None else f" weekday={wd}"
        out.append(f"#{jid} | {freq} {h:02d}:{mi:02d}{day} | {chat}")
    await update.message.reply_text("\n".join(out))

async def delete(update, context):
    if not await is_admin(update): return
    if not context.args:
        await update.message.reply_text("Usage: /delete ID")
        return
    try: jid=int(context.args[0])
    except:
        await update.message.reply_text("ID must be a number."); return
    conn.execute("UPDATE jobs SET active=0 WHERE id=?", (jid,))
    conn.commit()
    await update.message.reply_text(f"🗑 Schedule #{jid} deleted.")

async def test(update, context):
    if not await is_admin(update): return
    if not context.user_data.get("draft"):
        await update.message.reply_text("Create a draft with /add first.")
        return
    d=context.user_data["draft"]
    await send_post(context, d)

async def send_post(context, d):
    markup = None
    if d.get("button_text") and d.get("button_url"):
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(d["button_text"], url=d["button_url"])]])
    await context.bot.send_photo(chat_id=d["chat_id"], photo=d["photo_id"],
                                 caption=d.get("caption","")[:1024], reply_markup=markup)

def should_run(row, now):
    _,_,_,_,_,_,freq,h,mi,wd,active=row
    if not active or now.hour != h or now.minute != mi: return False
    if freq == "weekly": return now.weekday() == wd
    return freq == "daily"

async def scheduler(app):
    while True:
        now=datetime.now(TZ).replace(second=0, microsecond=0)
        for r in jobs():
            if should_run(r, now):
                _,chat,photo,cap,bt,bu,freq,h,mi,wd,active=r
                await send_post(app, {"chat_id":chat,"photo_id":photo,"caption":cap,"button_text":bt,"button_url":bu})
        await asyncio.sleep(55)

async def post_init(app):
    app.create_task(scheduler(app))

def main():
    app=Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("list", list_jobs))
    app.add_handler(CommandHandler("delete", delete))
    app.add_handler(CommandHandler("test", test))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, receive))
    app.run_polling()

if __name__ == "__main__":
    main()