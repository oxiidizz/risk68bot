import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("TOKEN")

# -------- Helpers --------
def _to_float(x: str) -> float:
    # Gère les virgules françaises: "3564,58" -> 3564.58
    return float(x.replace(",", "."))

# -------- Handlers --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bienvenue sur le bot Risk68 💰\n\n"
        "Deux façons d'utiliser le calculateur :\n"
        "1) Distance SL : /calc capital=250 sl=20 risk=1\n"
        "2) Prix directs : /calcprice capital=1000 entry=3600 sl=3564,58 risk=1 tp=3659,54 (tp optionnel)"
    )

async def calc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        params = {kv.split("=", 1)[0].lower(): float(kv.split("=", 1)[1]) for kv in context.args}
        capital = params.get("capital")
        sl = params.get("sl")
        risk = params.get("risk")
        if not all([capital, sl, risk]):
            raise ValueError("Paramètres manquants.")
        risk_amount = capital * (risk / 100.0)
        position_size = risk_amount / sl
        await update.message.reply_text(
            f"📊 Calcul (distance SL)\n"
            f"• Capital : {capital:.2f} €\n"
            f"• Distance SL : {sl:.2f}\n"
            f"• Risque : {risk:.2f}% ({risk_amount:.2f} €)\n"
            f"🧮 Taille max position : {position_size:.4f} unités"
        )
    except Exception:
        await update.message.reply_text(
            "❌ Format invalide.\nExemple : /calc capital=250 sl=20 risk=1"
        )

async def calcprice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /calcprice capital=1000 entry=3600 sl=3564.58 risk=1 tp=3659.54
    """
    try:
        # Parse key=value tolérant
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

        sl_dist = abs(entry - sl_price)
        if sl_dist == 0:
            raise ValueError("La distance SL ne peut pas être 0")

        risk_amount = capital * (risk_pct / 100.0)
        position_size = risk_amount / sl_dist

        tp_txt = ""
        if "tp" in params:
            tp_price = _to_float(params["tp"])
            tp_dist = abs(tp_price - entry)
            rr = tp_dist / sl_dist if sl_dist else 0.0
            gain_pot = position_size * (tp_price - entry)  # positif si LONG & TP>entry
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

# -------- App --------
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("calc", calc))
    app.add_handler(CommandHandler("calcprice", calcprice))
    app.run_polling()
