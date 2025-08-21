import os
from typing import Dict, Any, Optional
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("TOKEN")

# -------- Mémoire (non persistée) par utilisateur --------
# USERS[user_id] = {
#   "capital": float,  # €
#   "risk": float,     # %
#   "lev": float,      # leverage (ex: 10)
#   "fee_bps": float,  # bps aller-retour par défaut (ex: 10 => 0.10% par côté)
# }
USERS: Dict[int, Dict[str, float]] = {}

# -------- Helpers --------
def _to_float(x: str) -> float:
    # Virgules FR: "3564,58" -> 3564.58
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

def _fees_round_trip(notional: float, fee_bps: Optional[float]) -> float:
    """
    Estimation simple des frais aller-retour:
    fee_bps = 10 => 0.10% par côté (~0.20% AR).
    fees = notional * (fee_bps/10000) * 2
    """
    if notional is None or fee_bps is None:
        return 0.0
    return notional * (fee_bps / 10000.0) * 2.0

# -------- Handlers: base --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bienvenue sur le bot Risk68 💰\n\n"
        "1) Enregistre tes défauts :\n"
        "   /setcapital 1000   /setrisk 1   /setlev 10   /setfee 10\n"
        "2) Exemples :\n"
        "   /calc sl 35.42 entry 3600 tp 3659.54\n"
        "   /calcprice entry 3600 sl 3564,58 tp 3659,54\n\n"
        "Tape /help pour l’aide complète."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📖 *Aide complète*\n\n"
        "• /setcapital 1000  – capital par défaut (€)\n"
        "• /setrisk 1        – risque % par défaut\n"
        "• /setlev 10        – levier par défaut (pour marge)\n"
        "• /setfee 10        – frais défaut en bps (10 = 0,10% par côté)\n"
        "• /profile          – affiche tes valeurs par défaut\n"
        "• /updatecapital 38.8 – remplace ton capital\n"
        "• /pnl -1.20          – applique un PnL et recalcule ton 1%\n\n"
        "• /calc [capital …] sl … [risk …] [entry …] [tp …] [lev …] [fee …]\n"
        "  → Distance SL. Si *entry* fourni, affiche 💵 coût, marge (si lev), frais (si fee),\n"
        "    et *Perte max (SL)* / *Gain max (TP)* si *tp* fourni.\n"
        "  Ex: /calc sl 35.42 entry 3600 tp 3659.54\n\n"
        "• /calcprice [capital …] entry … sl … [risk …] [tp …] [side long|short] [lev …] [fee …]\n"
        "  → À partir des prix. Affiche taille, 💵 coût, marge/frais, et toujours:\n"
        "    ❌ Perte max (SL), ✅ Gain max (TP) si tp fourni (brut & net si fee connu).\n"
        "  Ex: /calcprice entry 3600 sl 3564,58 tp 3659,54 risk 1\n\n"
        "• /rr entry … sl … tp … [side long|short] – distances & R:R, cohérence du sens.\n"
        "  Ex: /rr entry 3600 sl 3564,58 tp 3659,54 side long\n\n"
        "Alias: /size = /calc,  /sizeprice = /calcprice\n"
        "_Formats sans `=` acceptés sur mobile. Virgules FR ok._"
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

async def setlev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            raise ValueError("Manquant")
        lev = _to_float(context.args[0])
        if lev <= 0:
            raise ValueError("lev doit être > 0")
        uid = update.effective_user.id
        USERS.setdefault(uid, {})["lev"] = lev
        await update.message.reply_text(f"✅ Levier par défaut enregistré : x{lev:.2f}")
    except Exception:
        await update.message.reply_text("❌ Utilise : /setlev 10")

async def setfee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            raise ValueError("Manquant")
        fee_bps = _to_float(context.args[0])
        if fee_bps < 0:
            raise ValueError("fee doit être ≥ 0")
        uid = update.effective_user.id
        USERS.setdefault(uid, {})["fee_bps"] = fee_bps
        await update.message.reply_text(f"✅ Frais par défaut enregistrés : {fee_bps:.2f} bps")
    except Exception:
        await update.message.reply_text("❌ Utilise : /setfee 10   (10 bps = 0,10% par côté)")

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    d = _get_user_defaults(uid)
    cap = d.get("capital")
    rsk = d.get("risk")
    lev = d.get("lev")
    fee = d.get("fee_bps")
    onepct = (cap * (rsk/100.0)) if (cap is not None and rsk is not None) else None
    await update.message.reply_text(
        "👤 *Profil par défaut*\n"
        f"• Capital : { _num(cap) + ' €' if cap is not None else 'non défini' }\n"
        f"• Risque  : { _num(rsk) + ' %' if rsk is not None else 'non défini' }\n"
        f"• Levier  : { 'x' + _num(lev) if lev is not None else 'non défini' }\n"
        f"• Frais   : { _num(fee) + ' bps' if fee is not None else 'non défini' }\n"
        + ("" if onepct is None else f"• 1% du capital : {onepct:.2f} €"),
        parse_mode="Markdown"
    )

# -------- Mise à jour du capital / PnL --------
async def updatecapital(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            raise ValueError("Manquant")
        new_cap = _to_float(context.args[0])
        if new_cap < 0:
            raise ValueError("Capital < 0")
        uid = update.effective_user.id
        USERS.setdefault(uid, {})["capital"] = new_cap
        r = USERS[uid].get("risk")
        onepct = (new_cap * (r/100.0)) if r is not None else None
        txt = f"✅ Nouveau capital enregistré : {new_cap:.2f} €"
        if onepct is not None:
            txt += f"\n➡️ 1% du capital = {onepct:.2f} €"
        await update.message.reply_text(txt)
    except Exception:
        await update.message.reply_text("❌ Utilise : /updatecapital 38.8")

async def pnl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /pnl -1.20  -> perte
    /pnl 0.80   -> gain
    """
    try:
        if not context.args:
            raise ValueError("Manquant")
        delta = _to_float(context.args[0])
        uid = update.effective_user.id
        d = USERS.setdefault(uid, {})
        if "capital" not in d:
            raise ValueError("Capital non défini. Fais /setcapital d'abord.")
        d["capital"] = max(0.0, d["capital"] + delta)
        cap = d["capital"]
        r = d.get("risk")
        onepct = (cap * (r/100.0)) if r is not None else None
        sign = "gain" if delta >= 0 else "perte"
        txt = f"✅ PnL appliqué ({sign} {delta:+.2f} €)\n"
        txt += f"• Nouveau capital : {cap:.2f} €"
        if onepct is not None:
            txt += f"\n• 1% du capital : {onepct:.2f} €"
        await update.message.reply_text(txt)
    except Exception:
        await update.message.reply_text(
            "❌ Utilise : /pnl -1.20  (ou /pnl 0.80)\n"
            "Astuce: /profile pour voir capital & 1%."
        )

# -------- Calculs --------
async def calc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Distance SL. Optionnel: entry pour coût/marge/frais, tp pour gain.
    Ex: /calc sl 35.42 entry 3600 tp 3659.54
    """
    try:
        params = _parse_kv(context.args)
        uid = update.effective_user.id
        defaults = _get_user_defaults(uid)

        # Capital & Risk
        capital = _to_float(params["capital"]) if "capital" in params else defaults.get("capital")
        if capital is None:
            raise ValueError("Capital manquant (utilise /setcapital 1000 ou capital …)")
        risk = _to_float(params["risk"]) if "risk" in params else defaults.get("risk")
        if risk is None:
            raise ValueError("Risque manquant (utilise /setrisk 1 ou risk …)")

        # Distance SL
        if "sl" not in params:
            raise ValueError("Paramètre sl manquant (distance du SL)")
        sl_dist = _to_float(params["sl"])
        if sl_dist <= 0:
            raise ValueError("La distance SL doit être > 0")

        # Optionnels
        entry = _to_float(params["entry"]) if "entry" in params else None
        tp_price = _to_float(params["tp"]) if "tp" in params else None

        # Calculs principaux
        risk_amount = capital * (risk / 100.0)               # perte brute au SL (1%)
        position_size = risk_amount / sl_dist                # unités
        notional = position_size * entry if entry is not None else None

        # Levier & Frais
        lev = _to_float(params["lev"]) if "lev" in params else defaults.get("lev")
        fee_bps = _to_float(params["fee"]) if "fee" in params else defaults.get("fee_bps")
        margin = (notional / lev) if (notional is not None and lev and lev > 0) else None
        fees = _fees_round_trip(notional, fee_bps) if (notional is not None and fee_bps is not None) else None

        # PnL explicites
        sl_loss_gross = risk_amount  # par définition de la taille
        sl_loss_net = (sl_loss_gross + fees) if fees is not None else None

        tp_gain_gross = None
        tp_gain_net = None
        if entry is not None and tp_price is not None:
            tp_gain_gross = position_size * (tp_price - entry)
            if fees is not None:
                tp_gain_net = tp_gain_gross - fees

        # Message
        msg = (
            "📊 *Calcul (distance SL)*\n"
            f"• Capital : {capital:.2f} €\n"
            f"• Distance SL : {sl_dist:.4f}\n"
            f"• Risque : {risk:.2f}% ({risk_amount:.2f} €)\n"
            f"🧮 *Taille max position* : {position_size:.4f} unités"
        )
        if entry is not None:
            msg += f"\n💵 Coût position ≈ {notional:.2f} € (entry {entry:.6f})"
        if margin is not None:
            msg += f"\n🪙 Marge requise (x{lev:.2f}) ≈ {margin:.2f} €"
        if fees is not None:
            msg += f"\n💸 Frais estimés (AR, {fee_bps:.2f} bps) ≈ {fees:.2f} €"

        # Lignes SL/TP explicites
        if sl_loss_gross is not None:
            if sl_loss_net is not None:
                msg += f"\n\n❌ *Perte max (SL)* : -{sl_loss_gross:.2f} €  (net frais ≈ -{sl_loss_net:.2f} €)"
            else:
                msg += f"\n\n❌ *Perte max (SL)* : -{sl_loss_gross:.2f} €"
        if tp_gain_gross is not None:
            if tp_gain_net is not None:
                msg += f"\n✅ *Gain max (TP)* : +{tp_gain_gross:.2f} €  (net frais ≈ +{tp_gain_net:.2f} €)"
            else:
                msg += f"\n✅ *Gain max (TP)* : +{tp_gain_gross:.2f} €"

        await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception:
        await update.message.reply_text(
            "❌ Format invalide.\n"
            "Ex: /calc sl 35.42 entry 3600 tp 3659.54\n"
            "Optionnel: capital/risk si non définis, lev 10, fee 10"
        )

async def calcprice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    À partir des PRIX. Affiche toujours Perte max (SL) et (si tp) Gain max (TP),
    bruts et nets si 'fee' connu (défaut via /setfee).
    """
    try:
        params = _parse_kv(context.args)
        uid = update.effective_user.id
        defaults = _get_user_defaults(uid)

        # Capital & Risk
        capital = _to_float(params["capital"]) if "capital" in params else defaults.get("capital")
        if capital is None:
            raise ValueError("Capital manquant (utilise /setcapital 1000 ou capital …)")
        risk_pct = _to_float(params["risk"]) if "risk" in params else defaults.get("risk")
        if risk_pct is None:
            raise ValueError("Risque manquant (utilise /setrisk 1 ou risk …)")

        # Prix
        if not all(k in params for k in ("entry", "sl")):
            raise ValueError("entry et sl sont requis")
        entry = _to_float(params["entry"])
        sl_price = _to_float(params["sl"])
        side = params.get("side", "").lower()  # optionnel: long|short

        sl_dist = abs(entry - sl_price)
        if sl_dist <= 0:
            raise ValueError("La distance SL doit être > 0")

        # Taille, notional, risque 1%
        risk_amount = capital * (risk_pct / 100.0)
        position_size = risk_amount / sl_dist
        notional = position_size * entry

        # TP optionnel
        tp_txt = ""
        tp_gain_gross = None
        if "tp" in params:
            tp_price = _to_float(params["tp"])
            tp_dist = abs(tp_price - entry)
            rr = tp_dist / sl_dist if sl_dist else 0.0
            delta = tp_price - entry
            if side == "short":
                delta = -delta
            tp_gain_gross = position_size * delta
            tp_txt = (
                f"\n🎯 TP : {tp_price:.6f}\n"
                f"📐 R:R ≈ {rr:.2f}"
            )

        # Levier & Frais
        lev = _to_float(params["lev"]) if "lev" in params else defaults.get("lev")
        fee_bps = _to_float(params["fee"]) if "fee" in params else defaults.get("fee_bps")
        margin = (notional / lev) if (notional is not None and lev and lev > 0) else None
        fees = _fees_round_trip(notional, fee_bps) if (fee_bps is not None) else None

        # SL / TP explicites
        sl_loss_gross = risk_amount
        sl_loss_net = (sl_loss_gross + (fees or 0.0)) if fees is not None else None
        tp_gain_net = (tp_gain_gross - (fees or 0.0)) if (tp_gain_gross is not None and fees is not None) else None

        # Message
        msg = (
            "📊 *Calcul à partir des PRIX*\n"
            f"• Capital : {capital:.2f} €\n"
            f"• Entrée : {entry:.6f}\n"
            f"• SL : {sl_price:.6f}  (dist {sl_dist:.6f})\n"
            f"• Risque : {risk_pct:.2f}% ({risk_amount:.2f} €)\n"
            f"🧮 *Taille max position* : {position_size:.4f} unités\n"
            f"💵 Coût position ≈ {notional:.2f} €"
            f"{tp_txt}"
        )
        if margin is not None:
            msg += f"\n🪙 Marge requise (x{lev:.2f}) ≈ {margin:.2f} €"
        if fees is not None:
            msg += f"\n💸 Frais estimés (AR, {fee_bps:.2f} bps) ≈ {fees:.2f} €"

        # Lignes SL/TP explicites
        if sl_loss_net is not None:
            msg += f"\n\n❌ *Perte max (SL)* : -{sl_loss_gross:.2f} €  (net frais ≈ -{sl_loss_net:.2f} €)"
        else:
            msg += f"\n\n❌ *Perte max (SL)* : -{sl_loss_gross:.2f} €"

        if tp_gain_gross is not None:
            if tp_gain_net is not None:
                msg += f"\n✅ *Gain max (TP)* : +{tp_gain_gross:.2f} €  (net frais ≈ +{tp_gain_net:.2f} €)"
            else:
                msg += f"\n✅ *Gain max (TP)* : +{tp_gain_gross:.2f} €"

        await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception:
        await update.message.reply_text(
            "❌ Format invalide.\n"
            "Ex: /calcprice entry 3600 sl 3564,58 tp 3659,54  (capital & risk optionnels si /setcapital & /setrisk)\n"
            "Optionnel: side long|short  lev 10  fee 10"
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
            f"• Entrée : {entry:.6f}\n"
            f"• SL : {sl_price:.6f}  (dist {sl_dist:.6f})\n"
            f"• TP : {tp_price:.6f}  (dist {tp_dist:.6f})\n"
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
    app.add_handler(CommandHandler("setlev", setlev))
    app.add_handler(CommandHandler("setfee", setfee))
    app.add_handler(CommandHandler("updatecapital", updatecapital))
    app.add_handler(CommandHandler("pnl", pnl))

    # Calculs
    app.add_handler(CommandHandler("calc", calc))
    app.add_handler(CommandHandler("size", calc))            # alias
    app.add_handler(CommandHandler("calcprice", calcprice))
    app.add_handler(CommandHandler("sizeprice", calcprice))  # alias
    app.add_handler(CommandHandler("rr", rr))

    app.run_polling()
