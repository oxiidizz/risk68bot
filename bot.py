import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bienvenue sur le bot Risk68 💰\n\n"
        "Utilise la commande suivante pour calculer ta taille de position :\n"
        "/calc capital=250 sl=20 risk=1"
    )

async def calc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        params = {kv.split("=")[0]: float(kv.split("=")[1]) for kv in context.args}
        capital = params.get("capital")
        sl = params.get("sl")
        risk = params.get("risk")

        if not all([capital, sl, risk]):
            raise ValueError("Paramètres manquants.")

        montant_risque = capital * (risk / 100)
        taille_position = montant_risque / sl

        await update.message.reply_text(
            f"🧮 Taille de position : {taille_position:.2f} unités\n"
            f"(Risque : {montant_risque:.2f} € pour un SL de {sl} €)"
        )
    except Exception as e:
        await update.message.reply_text(
            "❌ Erreur de format.\nUtilise : /calc capital=250 sl=20 risk=1"
        )

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("calc", calc))

    app.run_polling()
