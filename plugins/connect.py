#  plugins/connect.py

from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import db

# --- Connect Command in PM ---
@Client.on_message(filters.private & filters.command("connect"))
async def connect_handler(client, message):
    try:
        if len(message.command) < 2:
            return await message.reply("Use: `/connect -100xxxxxx` (Group ID)")
        
        group_id = int(message.command[1])
        
        # Check if bot is admin in that group
        try:
            member = await client.get_chat_member(group_id, "me")
            if member.status != enums.ChatMemberStatus.ADMINISTRATOR:
                return await message.reply("Please make me Admin in that group first!")
        except Exception:
            return await message.reply("I am not in that group or ID is wrong.")

        # Get Group Details
        chat = await client.get_chat(group_id)
        
        # Find Owner ID (Only reliable if bot is admin)
        owner_id = None
        async for m in client.get_chat_members(group_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
            if m.status == enums.ChatMemberStatus.OWNER:
                owner_id = m.user.id
                break
        
        if not owner_id:
            owner_id = message.from_user.id # Fallback to user who connected

        # Add to DB
        success = await db.add_group(group_id, chat.title, owner_id)
        
        if success:
            await message.reply(f"Successfully Connected to **{chat.title}**!", 
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Manage Group", callback_data=f"manage_{group_id}")]
                ])
            )
        else:
            await message.reply("Group already connected!")

    except Exception as e:
        await message.reply(f"Error: {e}")

# --- Disconnect ---
@Client.on_message(filters.private & filters.command("disconnect"))
async def disconnect_command(client, message):
    # Show list of connected groups to disconnect
    # For simplicity, just usage instructions here, proper UI in manage
    await message.reply("Click on 'Manage Group' button of the group you want to disconnect.")

# --- Callback: Manage & Settings ---
@Client.on_callback_query(filters.regex(r"^manage_"))
async def manage_group(client, callback):
    group_id = int(callback.data.split("_")[1])
    group = await db.get_group(group_id)
    
    if not group:
        return await callback.answer("Group not found in DB", show_alert=True)

    settings = group.get("settings", {})
    wel_txt = "✅ On" if settings.get("welcome") else "❌ Off"
    spell_txt = "✅ On" if settings.get("spell_check") else "❌ Off"

    buttons = [
        [InlineKeyboardButton(f"Welcome: {wel_txt}", callback_data=f"set_welcome_{group_id}")],
        [InlineKeyboardButton(f"Spell Check: {spell_txt}", callback_data=f"set_spell_{group_id}")],
        [InlineKeyboardButton("Force Join Setup", callback_data=f"fsub_setup_{group_id}")],
        [InlineKeyboardButton("Disconnect Bot", callback_data=f"disc_{group_id}")]
    ]
    
    await callback.message.edit_text(
        f"Settings for **{group['title']}**\nID: `{group_id}`",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r"^set_"))
async def toggle_settings(client, callback):
    action, key, group_id = callback.data.split("_")
    group_id = int(group_id)
    
    group = await db.get_group(group_id)
    current_val = group["settings"].get(key, True)
    await db.update_settings(group_id, key, not current_val)
    
    # Refresh Menu
    await manage_group(client, callback)

@Client.on_callback_query(filters.regex(r"^disc_"))
async def disconnect_btn(client, callback):
    group_id = int(callback.data.split("_")[1])
    await db.delete_group(group_id)
    await callback.message.edit_text("Disconnected Successfully!")
