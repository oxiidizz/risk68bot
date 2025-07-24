from telegram.ext import Updater, CommandHandler
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")

def calc(update, context):
    try:
        args = context.args
        capital = float([x.split('=')[1] for x in args if x.startswith('capital=')][0])
        sl = float([x.split('=')[1] for x in args if x.startswith('sl=')][0])
        risk = float([x.split('=')[1] for x in args if x.startswith('risk=')][0])

        risk_amount = capital * (risk / 100)
        position_size = risk_amount / sl

        msg = (
            f"📊 *Calcul de position* :\n\n"
            f"💼 Capital : {capital:.2f} €\n"
            f"📉 Stop Loss : {sl:.2f} $\n"
            f"🔥 Risque : {risk:.2f}% ({risk_amount:.2f} €)\n"
            f"🧮 Taille max de position : *{position_size:.4f}* unités"
        )
        update.message.reply_text(msg, parse_mode='Markdown')
    except Exception as e:
        update.message.reply_text("❌ Erreur. Utilise : /calc capital=250 sl=20 risk=1")

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("calc", calc))
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
