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
    except Exception:
        await update.message.reply_text(
            "❌ Erreur de format.\nUtilise : /calc capital=250 sl=20 risk=1"
        )

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("calc", calc))

    app.run_polling()
def _to_float(x: str) -> float:
    # Gère les virgules françaises : "3,564.58" ou "3564,58"
    return float(x.replace(",", "."))

async def calcprice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /calcprice capital=1000 entry=3600 sl=3564.58 risk=1 tp=3659.54
    - capital : obligatoire
    - entry : prix d'entrée
    - sl : prix du stop-loss
    - risk : % du capital risqué (ex: 1)
    - tp : (optionnel) prix du take-profit
    """
    try:
        # Parse paramètres key=value
        params = {}
        for kv in context.args:
            if "=" in kv:
                k, v = kv.split("=", 1)
                params[k.lower()] = v

        # Champs obligatoires
        if not all(k in params for k in ("capital", "entry", "sl", "risk")):
            raise ValueError("Paramètres manquants")

        capital = _to_float(params["capital"])
        entry = _to_float(params["entry"])
        sl_price = _to_float(params["sl"])
        risk_pct = _to_float(params["risk"])

        # Distance SL (risque par unité)
        sl_dist = abs(entry - sl_price)
        if sl_dist == 0:
            raise ValueError("La distance SL ne peut pas être 0")

        # Montant risqué et taille de position
        risk_amount = capital * (risk_pct / 100.0)
        position_size = risk_amount / sl_dist

        # TP optionnel
        tp_txt = ""
        if "tp" in params:
            tp_price = _to_float(params["tp"])
            tp_dist = abs(tp_price - entry)
            rr = tp_dist / sl_dist
            gain_pot = position_size * (tp_price - entry)
            tp_txt = (
                f"\n🎯 TP : {tp_price:.2f}\n"
                f"📐 R:R ≈ {rr:.2f}\n"
                f"💚 Gain potentiel ≈ {gain_pot:.2f} €"
            )

        msg = (
            "📊 *Calcul à partir des PRIX*\n"
            f"• Capital : {capital:.2f} €\n"
            f"• Entrée : {entry:.2f}\n"
            f"• SL : {sl_price:.2f}\n"
            f"• Distance SL : {sl_dist:.2f}\n"
            f"• Risque : {risk_pct:.2f}% ({risk_amount:.2f} €)\n"
            f"🧮 *Taille max position* : {position_size:.4f} unités"
            f"{tp_txt}"
        )

        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(
            "❌ Format invalide.\n"
            "Exemple : /calcprice capital=1000 entry=3600 sl=3564,58 risk=1 tp=3659,54\n"
            "(Le `tp` est optionnel. Les virgules sont acceptées.)"
        )
