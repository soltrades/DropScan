import os
import asyncio
import logging
import httpx
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, JobQueue
from telegram.constants import ParseMode
from web3 import Web3

from crawler.db import get_db

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Constants
API_BASE = "https://dropscan-api-production.up.railway.app"
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

def shorten_address(address: str) -> str:
    return f"{address[:6]}...{address[-4:]}"

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 *Welcome to DropScan!*\n\n"
        "I am your automated EVM airdrop checker. I monitor 50+ contracts across "
        "Ethereum, Base, Arbitrum, Optimism, and Polygon to find unclaimed tokens for you.\n\n"
        "*Commands:*\n"
        "/scan <address> - Check a wallet for airdrops\n"
        "/watch <address> - Get notified when new drops match this wallet\n"
        "/unwatch <address> - Stop monitoring a wallet\n"
        "/watched - Show your active monitors\n"
        "/new - Show the 5 most recent discoveries\n"
        "/expiring - Show drops ending within 7 days\n"
        "/help - Show this message"
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Please provide a wallet address: `/scan 0x...`", parse_mode=ParseMode.MARKDOWN)
        return

    address = context.args[0]
    if not Web3.is_address(address):
        await update.message.reply_text("❌ Invalid EVM address format.")
        return

    address = Web3.to_checksum_address(address)
    await update.message.reply_text(f"🔍 Scanning `{shorten_address(address)}` for airdrops...", parse_mode=ParseMode.MARKDOWN)

    async with httpx.AsyncClient() as client:
        try:
            res = await client.post(f"{API_BASE}/scan", json={"addresses": [address]}, timeout=30.0)
            data = res.json()
            
            results = data.get("data", {}).get(address, [])
            eligible = [r for r in results if r.get("is_eligible")]

            if not eligible:
                await update.message.reply_text("📉 No unclaimed airdrops found for this wallet.")
                return

            msg = f"🎉 *Found {len(eligible)} Airdrops for {shorten_address(address)}:*\n\n"
            for item in eligible:
                msg += (
                    f"🔹 *{item['project_name']}*\n"
                    f"   Token: {item['token_symbol']}\n"
                    f"   Value: ${item.get('usd_value', 0)}\n"
                    f"   [👉 Claim Here]({item['claim_url']})\n\n"
                )
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
            
        except Exception as e:
            logger.error(f"Scan error: {e}")
            await update.message.reply_text("❌ Error connecting to scan server. Please try again later.")

async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: `/watch 0x...`", parse_mode=ParseMode.MARKDOWN)
        return

    address = context.args[0]
    if not Web3.is_address(address):
        await update.message.reply_text("❌ Invalid EVM address format.")
        return

    address = Web3.to_checksum_address(address)
    chat_id = update.effective_chat.id

    try:
        db = get_db()
        # Upsert wallet and get its id
        wallet_res = db.table("wallets").upsert(
            {"address": address}, on_conflict="address"
        ).execute()
        
        # Fetch the wallet id
        wallet_row = db.table("wallets").select("id").eq("address", address).execute()
        wallet_id = wallet_row.data[0]["id"]
        
        # Upsert subscription using wallet_id
        db.table("alert_subscriptions").upsert({
            "wallet_id": wallet_id,
            "telegram_chat_id": str(chat_id)
        }, on_conflict="wallet_id,telegram_chat_id").execute()

        await update.message.reply_text(f"✅ *Watching* `{shorten_address(address)}`\n\nYou will be notified immediately when new airdrops are discovered for this wallet.", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Watch error: {e}")
        await update.message.reply_text("❌ Failed to register watch. Ensure the DB is initialized.")

async def unwatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: `/unwatch 0x...`", parse_mode=ParseMode.MARKDOWN)
        return

    address = context.args[0]
    chat_id = update.effective_chat.id

    try:
        db = get_db()
        # First get wallet id
        wallet_row = db.table("wallets").select("id").eq(
            "address", address
        ).execute()
        if not wallet_row.data:
            await update.message.reply_text("❌ Wallet not found.")
            return
        wallet_id = wallet_row.data[0]["id"]
        db.table("alert_subscriptions").delete().eq(
            "wallet_id", wallet_id
        ).eq("telegram_chat_id", str(chat_id)).execute()
        await update.message.reply_text(f"🛑 Stopped watching `{shorten_address(address)}`.", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Unwatch error: {e}")
        await update.message.reply_text("❌ Error removing watch.")

async def watched(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        db = get_db()
        res = db.table("alert_subscriptions").select(
            "wallet_id, wallets(address)"
        ).eq("telegram_chat_id", str(chat_id)).execute()
        
        if not res.data:
            await update.message.reply_text("You have no wallets registered. Use `/watch <address>`", parse_mode=ParseMode.MARKDOWN)
            return

        msg = "👀 *Your Monitored Wallets:*\n\n"
        for item in res.data:
            addr = item.get("wallets", {}).get("address", "unknown")
            msg += f"• `{addr}`\n"
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Watched error: {e}")
        await update.message.reply_text("❌ Error fetching watched wallets.")

async def new_drops(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(f"{API_BASE}/feed")
            data = res.json().get("data", [])[:5]
            
            if not data:
                await update.message.reply_text("No recent airdrops found.")
                return

            msg = "🆕 *Latest Discoveries:*\n\n"
            for item in data:
                msg += f"🔥 *{item['project_name']}* ({item['token_symbol']})\n   Network ID: {item['chain_id']}\n\n"
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"New drops error: {e}")
            await update.message.reply_text("❌ Error fetching feed.")

async def expiring(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        db = get_db()
        # Query active contracts with deadline within 7 days
        seven_days_later = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        res = db.table("contracts").select("*").eq("status", "active").lte("deadline", seven_days_later).gte("deadline", datetime.now(timezone.utc).isoformat()).execute()
        
        if not res.data:
            await update.message.reply_text("⏰ No active airdrops expiring within 7 days.")
            return

        msg = "⚠️ *Expiring Soon (7 Days):*\n\n"
        for item in res.data:
            deadline = item.get('deadline', 'N/A')
            msg += f"⏳ *{item['project_name']}* ({item['token_symbol']})\n   Ends: {deadline}\n\n"
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Expiring error: {e}")
        await update.message.reply_text("❌ Error fetching expiring drops.")

# Alert Loop Job
async def alert_loop(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Running Alert loop check...")
    try:
        db = get_db()
        # 1. Get contracts added in last 10 mins
        ten_mins_ago = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        new_contracts = db.table("contracts").select("*").gte("created_at", ten_mins_ago).execute()
        
        if not new_contracts.data:
            return

        # 2. Get all distinct chat_ids that have subscriptions
        subs_res = db.table("alert_subscriptions").select("*").execute()
        if not subs_res.data:
            return

        # Group subscriptions by wallet for efficiency but loop chat_ids for notification
        # For simplicity, we loop every sub and check eligibility against the new contracts
        async with httpx.AsyncClient() as client:
            for sub in subs_res.data:
                wallet_row = db.table("wallets").select("address").eq(
                    "id", sub["wallet_id"]
                ).execute()
                if not wallet_row.data:
                    continue
                wallet = wallet_row.data[0]["address"]
                chat_id = sub["telegram_chat_id"]
                
                # Check eligibility via API
                res = await client.post(f"{API_BASE}/scan", json={"addresses": [wallet]}, timeout=30.0)
                scan_data = res.json().get("data", {}).get(wallet, [])
                
                for contract in new_contracts.data:
                    # Check if this specific new contract matches any eligible item in scan results
                    match = next((item for item in scan_data if item["contract_id"] == contract["id"] and item["is_eligible"]), None)
                    
                    if match:
                        alert_msg = (
                            f"🔔 *New Airdrop Found for your Wallet*\n"
                            f"`{shorten_address(wallet)}`\n\n"
                            f"Project: *{match['project_name']}*\n"
                            f"Token: {match['token_symbol']}\n"
                            f"Network ID: {match['chain_id']}\n"
                            f"Est. Value: ${match.get('usd_value', 0)}\n\n"
                            f"👉 [Claim Now]({match['claim_url']})"
                        )
                        await context.bot.send_message(chat_id=chat_id, text=alert_msg, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Alert loop error: {e}")

# Runner
if __name__ == "__main__":
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment.")
    else:
        app = ApplicationBuilder().token(BOT_TOKEN).build()

        # Commands
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", start))
        app.add_handler(CommandHandler("scan", scan))
        app.add_handler(CommandHandler("watch", watch))
        app.add_handler(CommandHandler("unwatch", unwatch))
        app.add_handler(CommandHandler("watched", watched))
        app.add_handler(CommandHandler("new", new_drops))
        app.add_handler(CommandHandler("expiring", expiring))

        # Background Job
        if app.job_queue:
            app.job_queue.run_repeating(alert_loop, interval=600, first=10) # 10 minutes

        logger.info("Bot starting...")
        app.run_polling()
