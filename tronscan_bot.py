import os
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# 🔑 Token desde Render (variable de entorno)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TRONSCAN_API_BASE = "https://apilist.tronscanapi.com/api"

# ---------- Helpers ----------
def fetch_json(url, params=None, timeout=10):
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("Fetch error:", url, e)
        return None

def get_account_info(address):
    url = f"{TRONSCAN_API_BASE}/account"
    return fetch_json(url, params={"address": address}) or {}

def get_recent_transactions(address, limit=5):
    url = f"{TRONSCAN_API_BASE}/transaction"
    data = fetch_json(url, params={"address": address, "limit": limit})
    return data.get("data", []) if data else []

# ---------- Parsers ----------
def format_balance(account_info):
    try:
        trx_sun = int(account_info.get("balance", 0))
    except Exception:
        trx_sun = 0
    trx = trx_sun / 1_000_000

    lines = [f"💰 Saldo TRX: {trx:.6f}"]

    # TRC20 tokens
    trc20 = account_info.get("trc20token_balances") or []
    if trc20:
        lines.append("\n🔹 TRC20 tokens:")
        for t in trc20:
            name = t.get("symbol") or t.get("tokenName") or t.get("name") or "TRC20"
            try:
                bal = int(t.get("balance", 0))
                dec = int(t.get("decimals", 6))
                human = bal / (10**dec)
            except Exception:
                human = t.get("balance")
            lines.append(f" • {name}: {human}")
    else:
        lines.append("\n(No TRC20 tokens)")

    # TRC10 tokens
    trc10 = account_info.get("assetV2") or []
    if trc10:
        lines.append("\n🔸 TRC10 tokens:")
        for a in trc10:
            lines.append(f" • {a.get('name')}: {a.get('value')}")
    return "\n".join(lines)

def parse_tx(tx):
    try:
        txid = tx.get("hash") or tx.get("txID") or "?"
        ts = tx.get("timestamp") or tx.get("blockTimeStamp") or tx.get("block_timestamp")
        dt = datetime.utcfromtimestamp(int(ts)/1000).strftime("%Y-%m-%d %H:%M:%S") if ts else "?"

        from_addr = tx.get("ownerAddress") or tx.get("fromAddress") or tx.get("from") or "?"
        to_addr = tx.get("toAddress") or (tx.get("contractData") or {}).get("to_address") or tx.get("to") or "?"

        cd = tx.get("contractData") or {}
        token_info = tx.get("tokenInfo") or cd.get("tokenInfo") or {}
        symbol = token_info.get("symbol") or token_info.get("name") or "TRX"
        decimals = int(token_info.get("decimals", 6)) if token_info else 6

        raw_amount = cd.get("amount") or tx.get("amount") or tx.get("value") or 0
        try:
            if token_info:
                amount = int(raw_amount) / (10**decimals)
            else:
                amount = int(raw_amount) / 1_000_000
        except Exception:
            amount = raw_amount

        confirmed = tx.get("confirmed")
        status = "✅ Confirmed" if confirmed else "❌ Pending/Failed"

        return (
            f"🕒 {dt}\n"
            f"TxID: {txid[:12]}...\n"
            f"From: {from_addr}\n"
            f"To:   {to_addr}\n"
            f"Amount: {amount} {symbol}\n"
            f"Status: {status}"
        )
    except Exception as e:
        return f"- {tx.get('hash','?')} (error {e})"

# ---------- Bot commands ----------
async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ Uso: /check <direccion_tron>")
        return
    address = context.args[0].strip()
    await update.message.reply_text(f"🔎 Consultando {address}...")

    acc = get_account_info(address)
    bal_text = format_balance(acc)

    txs = get_recent_transactions(address, limit=5)
    if txs:
        tx_lines = [parse_tx(tx) for tx in txs]
        tx_text = "\n\n".join(tx_lines)
    else:
        tx_text = "📜 No hay transacciones recientes."

    reply = f"📡 Wallet: {address}\n\n{bal_text}\n\n📜 Últimas transacciones:\n{tx_text}"
    if len(reply) > 3900:
        reply = reply[:3900] + "\n(...truncated)"
    await update.message.reply_text(reply)

# ---------- Main ----------
def main():
    if not TELEGRAM_BOT_TOKEN:
        print("❌ ERROR: Configura TELEGRAM_BOT_TOKEN en Render.")
        return
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("check", check))
    print("✅ Bot corriendo... usa /check <direccion>")
    app.run_polling()

if __name__ == "__main__":
    main()