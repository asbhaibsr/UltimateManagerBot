#  plugins/group_watcher.py

from pyrogram import Client, filters, enums
from database import db
from utils import check_movie_spelling, clean_text
from config import Config

@Client.on_message(filters.group & filters.text & ~filters.command(["request", "search"]))
async def group_text_handler(client, message):
    group = await db.get_group(message.chat.id)
    if not group or not group["settings"].get("spell_check"):
        return

    text = message.text
    # Ignore short messages
    if len(text) < 3:
        return

    # Check spelling
    result_name, status = check_movie_spelling(text)
    
    if status == "correct":
        # Do nothing (Silent)
        pass
        
    elif status == "wrong":
        # Delete user message and suggest
        try:
            await message.delete()
        except:
            pass
        
        msg = await message.reply(
            f"❌ **Spelling Mistake Detected!**\n\n"
            f"👤 {message.from_user.mention}\n"
            f"Did you mean: **{result_name}**?\n\n"
            f"Please type the name correctly without extra words (link, dedo, etc)."
        )
        # Auto delete warning after 10 sec
        # await asyncio.sleep(10)
        # await msg.delete()

# --- Request System ---
@Client.on_message(filters.group & (filters.command("request") | filters.regex(r"^#request")))
async def request_handler(client, message):
    query = message.text.replace("/request", "").replace("#request", "").strip()
    if not query:
        return await message.reply("Give movie name!")

    group = await db.get_group(message.chat.id)
    if not group:
        return # Not connected

    owner_id = group.get("owner_id")
    
    text = (
        f"📩 **New Request!**\n\n"
        f"🎬 Movie: `{query}`\n"
        f"👤 User: {message.from_user.mention}\n"
    )
    
    if owner_id:
        try:
            # Tagging the owner in the group message
            owner = await client.get_users(owner_id)
            text += f"👑 Owner: {owner.mention}"
        except:
            text += f"👑 Owner ID: `{owner_id}`"
    
    await message.reply(text)
