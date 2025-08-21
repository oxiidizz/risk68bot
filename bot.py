
import os
from typing import Dict, Any
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("TOKEN")

# -------- In-memory defaults (par utilisateur, non persisté) --------
USERS: Dict[int, Dict[str, float]] = {}  # {user_id: {"capital": float, "risk": float}}

# -------- Helpers --------
def _to_float(x: str) -> float:
    # Gère virgules FR: "3564,58" -> 3564.58
    return float(x.replace(",", "."))

def _parse_kv(args) -> Dict[str, str]:
    """
    Accepte deux formats:
      - entry=3600 sl=3564,58 risk=1
      - entry 3600 sl 3564,58 risk 1
    """
    d: Dict[str, str] = {}
    i = 0
    while i < len(args):
        token = args[i]
        if "=" in token:  # format key=value
            k, v = token.split("=", 1)
            d[k.strip().lower()] = v.strip()
            i += 1
        else:
            # format "key value"
            if i + 1 < len(args):
                d[token.strip().lower()] = args[i + 1].strip()
                i += 2
            else:
                i += 1
    return d

def _get_user_defaults(user_id: int) -> Dict[str, float]:
    return USERS.get(user_id, {})

def _num(v: Any, digits=2) -> str:
    try:
        return f"{float(v):.{digits}f}"
    except:
        return str(v)

# -------- Handlers --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bienvenue sur le bot Risk68 💰\n\n"
        "• Enregistre tes valeurs par défaut :\n"
        "  /setcapital 1000   /setrisk 1\n"
        "• Exemples rapides :\n"
        "  /calc sl=35.42     (utilise tes défauts)\n"
        "  /calcprice entry 3600 sl 3564,58 tp 3659,54\n\n"
        "Tape /help pour l’aide complète."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📖 *Aide*\n\n"
        "• /setcapital 1000 – enregistre ton capital par défaut (€)\n"
        "• /setrisk 1 – enregistre ton risque % par défaut\n"
        "• /profile – affiche tes valeurs par défaut\n\n"
        "• /calc capital=… sl=… risk=… – calcule la taille à partir de la *distance* du SL\n"
        "  Ex: /calc capital=1000 sl=35.42 risk=1\n"
        "  (Si /setcapital & /setrisk faits, capital & risk deviennent optionnels)\n\n"
        "• /calcprice capital=… entry=… sl=… risk=… tp=… side=long|short – calcule la taille à partir des *prix*\n"
        "  Ex: /calcprice entry 3600 sl 3564,58 tp 3659,54 risk 1\n"
        "  (tp & side sont optionnels ; side valide le sens)\n\n"
        "• /rr entry=… sl=… tp=… side=long|short – calcule distances & R:R\n"
        "  Ex: /rr entry=3600 sl=3564,58 tp=3659,54 side=long\n\n"
        "Alias: /size = /calc,  /sizeprice = /calcprice\n"
        "_Les virgules françaises sont acceptées, et tu peux écrire sans `=` sur mobile._"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def setcapital(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            raise ValueError("Manquant")
        capital = _to_float(context.args[0])
        uid = update.effective_user.id
        USERS.setdefault(uid, {})["capital"] = capital
        await update.message.reply_text(f"✅ Capital par défaut enregistré : {capital:.2f} €")
    except Exception:
        await update.message.reply_text("❌ Utilise : /setcapital 1000")

async def setrisk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            raise ValueError("Manquant")
        risk = _to_float(context.args[0])
        uid = update.effective_user.id
        USERS.setdefault(uid, {})["risk"] = risk
        await update.message.reply_text(f"✅ Risque par défaut enregistré : {risk:.2f} %")
    except Exception:
        await update.message.reply_text("❌ Utilise : /setrisk 1")

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    d = _get_user_defaults(uid)
    cap = d.get("capital")
    rsk = d.get("risk")
    await update.message.reply_text(
        "👤 *Profil par défaut*\n"
        f"• Capital : { _num(cap) + ' €' if cap is not None else 'non défini' }\n"
        f"• Risque  : { _num(rsk) + ' %' if rsk is not None else 'non défini' }\n"
        "Astuce: /setcapital 1000  /setrisk 1",
        parse_mode="Markdown"
    )

async def calc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        params = _parse_kv(context.args)
        uid = update.effective_user.id
        defaults = _get_user_defaults(uid)

        # Capital
        capital = _to_float(params["capital"]) if "capital" in params else defaults.get("capital")
        if capital is None:
            raise ValueError("Capital manquant (utilise /setcapital 1000 ou capital=… / capital …)")

        # Risk %
        risk = _to_float(params["risk"]) if "risk" in params else defaults.get("risk")
        if risk is None:
            raise ValueError("Risque manquant (utilise /setrisk 1 ou risk=… / risk …)")

        # Distance SL
        if "sl" not in params:
            raise ValueError("Paramètre sl manquant (distance du SL)")
        sl_dist = _to_float(params["sl"])
        if sl_dist <= 0:
            raise ValueError("La distance SL doit être > 0")

        risk_amount = capital * (risk / 100.0)
        position_size = risk_amount / sl_dist

        await update.message.reply_text(
            "📊 *Calcul (distance SL)*\n"
            f"• Capital : {capital:.2f} €\n"
            f"• Distance SL : {sl_dist:.2f}\n"
            f"• Risque : {risk:.2f}% ({risk_amount:.2f} €)\n"
            f"🧮 *Taille max position* : {position_size:.4f} unités",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(
            "❌ Format invalide.\n"
            "Ex: /calc sl 35.42  (ou ajoute capital/risk si non définis)\n"
            "Ex: /calc capital 1000 sl 35.42 risk 1"
        )

async def calcprice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        params = _parse_kv(context.args)
        uid = update.effective_user.id
        defaults = _get_user_defaults(uid)

        # Capital
        capital = _to_float(params["capital"]) if "capital" in params else defaults.get("capital")
        if capital is None:
            raise ValueError("Capital manquant (utilise /setcapital 1000 ou capital=… / capital …)")

        # Risk %
        risk_pct = _to_float(params["risk"]) if "risk" in params else defaults.get("risk")
        if risk_pct is None:
            raise ValueError("Risque manquant (utilise /setrisk 1 ou risk=… / risk …)")

        # Prix
        if not all(k in params for k in ("entry", "sl")):
            raise ValueError("entry et sl sont requis")
        entry = _to_float(params["entry"])
        sl_price = _to_float(params["sl"])

        side = params.get("side", "").lower()  # optionnel: long|short

        sl_dist = abs(entry - sl_price)
        if sl_dist <= 0:
            raise ValueError("La distance SL doit être > 0")

        risk_amount = capital * (risk_pct / 100.0)
        position_size = risk_amount / sl_dist

        tp_txt = ""
        if "tp" in params:
            tp_price = _to_float(params["tp"])
            tp_dist = abs(tp_price - entry)
            rr = tp_dist / sl_dist if sl_dist else 0.0
            # Gain potentiel (signé selon side si fourni, sinon assume long si tp>entry)
            delta = tp_price - entry
            if side == "short":
                delta = -delta
            gain_pot = position_size * delta
            tp_txt = (
                f"\n🎯 TP : {tp_price:.2f}\n"
                f"📐 R:R ≈ {rr:.2f}\n"
                f"💚 Gain potentiel ≈ {gain_pot:.2f} €"
            )

        await update.message.reply_text(
            "📊 *Calcul à partir des PRIX*\n"
            f"• Capital : {capital:.2f} €\n"
            f"• Entrée : {entry:.2f}\n"
            f"• SL : {sl_price:.2f}  (dist {sl_dist:.2f})\n"
            f"• Risque : {risk_pct:.2f}% ({risk_amount:.2f} €)\n"
            f"🧮 *Taille max position* : {position_size:.4f} unités"
            f"{tp_txt}",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(
            "❌ Format invalide.\n"
            "Ex: /calcprice entry 3600 sl 3564,58 tp 3659,54  (capital & risk optionnels si /setcapital & /setrisk)\n"
            "Ajoute side long|short si tu veux valider le sens."
        )

async def rr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        params = _parse_kv(context.args)
        if not all(k in params for k in ("entry", "sl", "tp")):
            raise ValueError("entry, sl, tp requis")
        entry = _to_float(params["entry"])
        sl_price = _to_float(params["sl"])
        tp_price = _to_float(params["tp"])
        side = params.get("side", "").lower()

        sl_dist = abs(entry - sl_price)
        tp_dist = abs(tp_price - entry)
        if sl_dist <= 0:
            raise ValueError("La distance SL doit être > 0")
        rr_val = tp_dist / sl_dist

        ok = True
        if side == "long" and not (tp_price > entry and sl_price < entry):
            ok = False
        if side == "short" and not (tp_price < entry and sl_price > entry):
            ok = False

        await update.message.reply_text(
            "📐 *R:R*\n"
            f"• Entrée : {entry:.2f}\n"
            f"• SL : {sl_price:.2f}  (dist {sl_dist:.2f})\n"
            f"• TP : {tp_price:.2f}  (dist {tp_dist:.2f})\n"
            f"➡️ R:R ≈ {rr_val:.2f}\n"
            + ("" if side == "" else f"• Side déclaré : {side} → " + ("✅ cohérent" if ok else "⚠️ incohérent")),
            parse_mode="Markdown"
        )
    except Exception:
        await update.message.reply_text(
            "❌ Format invalide.\nEx: /rr entry 3600 sl 3564,58 tp 3659,54 side long"
        )

# -------- App --------
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    # Base
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("setcapital", setcapital))
    app.add_handler(CommandHandler("setrisk", setrisk))

    # Calculs
    app.add_handler(CommandHandler("calc", calc))
    app.add_handler(CommandHandler("size", calc))            # alias
    app.add_handler(CommandHandler("calcprice", calcprice))
    app.add_handler(CommandHandler("sizeprice", calcprice))  # alias
    app.add_handler(CommandHandler("rr", rr))

    app.run_polling()
