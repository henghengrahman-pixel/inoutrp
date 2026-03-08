from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)
from datetime import datetime, timedelta
import pytz
import json
import os

TOKEN = "8561186796:AAGGxaXrxq3ZCxSH2Dzi-NWzgckzQSOovYw"
ADMIN_IDS = [1781838636, 5397964203, 7466297540, 6571756903, 1909993917, 6029332350, 6220945648,1407148070]
MAKS_IZIN = 5
TIMEZONE = pytz.timezone("Asia/Jakarta")
IZIN_FILE = "izin.json"

DURASI = {
    "makan": 20,
    "merokok": 10,
    "toilet": 5,
    "bab": 15
}

izin_aktif = {}

def simpan_data():
    with open(IZIN_FILE, "w") as f:
        json.dump(izin_aktif, f, indent=2, default=str)

def load_data():
    global izin_aktif
    if os.path.exists(IZIN_FILE):
        with open(IZIN_FILE, "r") as f:
            raw = json.load(f)
            for uid, data in raw.items():
                izin_aktif[uid] = {
                    "nama": data["nama"],
                    "alasan": data["alasan"],
                    "keluar": datetime.fromisoformat(data["keluar"]),
                    "kembali": datetime.fromisoformat(data["kembali"])
                }

async def kirim_ke_admins(context, pesan: str):
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=pesan)
        except:
            pass

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ["group", "supergroup"]:
        return

    keyboard = [
        [InlineKeyboardButton("🍽️ Makan", callback_data="izin_makan"),
         InlineKeyboardButton("🚬 Merokok", callback_data="izin_merokok")],
        [InlineKeyboardButton("🚽 Toilet", callback_data="izin_toilet"),
         InlineKeyboardButton("💩 BAB", callback_data="izin_bab")]
    ]

    await update.message.reply_text(
        "Silakan pilih jenis izin keluar:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_izin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.message.chat.type not in ["group", "supergroup"]:
        return

    user = query.from_user
    alasan = query.data.replace("izin_", "")
    uid = str(user.id)

    if uid in izin_aktif:
        return await query.message.reply_text("⚠️ Kamu masih dalam status izin.")

    if len(izin_aktif) >= MAKS_IZIN:
        return await query.message.reply_text("❌ Maksimal 5 orang boleh izin bersamaan.")

    now = datetime.now(TIMEZONE)
    kembali = now + timedelta(minutes=DURASI[alasan])

    izin_aktif[uid] = {
        "nama": user.first_name,
        "alasan": alasan,
        "keluar": now,
        "kembali": kembali
    }
    simpan_data()

    tombol = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Saya Sudah Kembali", callback_data=f"in_{uid}")]
    ])

    await query.message.reply_text(
        f"✅ {user.first_name} izin {alasan} pukul {now.strftime('%H:%M')} WIB.\n"
        f"⏳ Estimasi kembali: {kembali.strftime('%H:%M')}",
        reply_markup=tombol
    )

    await kirim_ke_admins(context, f"📤 {user.first_name} izin {alasan}.")

async def handle_kembali(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.message.chat.type not in ["group", "supergroup"]:
        return

    uid = query.data.replace("in_", "")
    user = query.from_user

    if str(user.id) != uid:
        return await query.message.reply_text("❌ Tombol ini hanya untuk pemilik izin.")

    now = datetime.now(TIMEZONE)

    if uid not in izin_aktif:
        return await query.message.reply_text("❌ Data izin tidak ditemukan.")

    data = izin_aktif.pop(uid)
    simpan_data()

    keluar = data["keluar"]
    kembali = data["kembali"]
    durasi = now - keluar

    terlambat = now > kembali
    telat = (now - kembali).seconds // 60 if terlambat else 0

    denda = 0
    if 1 <= telat <= 9:
        denda = telat * 50000
    elif telat >= 10:
        denda = 500000

    teks = (
        f"👋 {user.first_name} kembali dari {data['alasan']}.\n"
        f"⏱️ Durasi: {str(durasi).split('.')[0]}"
    )

    if denda:
        teks += f"\n⚠️ Terlambat {telat} menit.\n💸 Denda: Rp{denda:,}"

    await query.message.reply_text(teks)
    await kirim_ke_admins(context, teks)

async def auto_kembali(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TIMEZONE)
    auto_remove = []

    for uid, data in izin_aktif.items():
        if now > data["kembali"] + timedelta(minutes=10):
            keluar = data["keluar"]
            durasi = now - keluar
            nama = data["nama"]
            alasan = data["alasan"]

            teks = (
                f"⚠️ {nama} tidak kembali.\n"
                f"Alasan: {alasan}\n"
                f"Durasi: {str(durasi).split('.')[0]}\n"
                f"Denda otomatis: Rp500.000"
            )

            await kirim_ke_admins(context, teks)
            auto_remove.append(uid)

    for uid in auto_remove:
        izin_aktif.pop(uid, None)

    if auto_remove:
        simpan_data()

async def get_id(update, context):
    await update.message.reply_text(f"ID kamu: `{update.effective_user.id}`", parse_mode="Markdown")

async def status(update, context):
    if update.effective_user.id not in ADMIN_IDS:
        return

    if not izin_aktif:
        return await update.message.reply_text("✔ Semua sudah kembali.")

    teks = "📋 *Status Izin Aktif:*\n\n"
    for uid, d in izin_aktif.items():
        teks += f"👤 {d['nama']} — {d['alasan']}\n⏳ {d['kembali'].strftime('%H:%M')}\n\n"

    await update.message.reply_text(teks, parse_mode="Markdown")

def main():
    load_data()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", show_menu))
    app.add_handler(CommandHandler("id", get_id))
    app.add_handler(CommandHandler("status", status))

    app.add_handler(MessageHandler(filters.Regex("^(izin|menu)$"), show_menu))

    app.add_handler(CallbackQueryHandler(handle_izin, pattern="^izin_"))
    app.add_handler(CallbackQueryHandler(handle_kembali, pattern="^in_"))

    job = app.job_queue
    job.run_repeating(auto_kembali, interval=60, first=10)

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
