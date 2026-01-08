# plugins/fsub.py

from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
from pyrogram.errors import UserNotParticipant
from database import db

# --- Setup Force Join (In PM) ---
@Client.on_callback_query(filters.regex(r"^fsub_setup_"))
async def fsub_setup_intro(client, callback):
    group_id = int(callback.data.split("_")[2])
    await callback.message.edit_text(
        "To set up Force Join:\n"
        "1. Make me Admin in your Channel.\n"
        "2. Forward a message from that Channel to here (PM).\n"
        "3. I will link it to your group.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data=f"manage_{group_id}")]])
    )
    # Note: Logic to capture forwarded message needs a state or temporary storage. 
    # For simplicity, we can use a command here like /setfsub <channel_id> in PM after clicking button.

# Let's use a simpler approach for FSub setup via command in PM for this example
@Client.on_message(filters.private & filters.forwarded)
async def fsub_channel_handler(client, message):
    if not message.forward_from_chat or message.forward_from_chat.type != enums.ChatType.CHANNEL:
        return

    # Assuming the user just clicked "manage" for a group, we need to know WHICH group.
    # A robust way is asking user to send: /setfsub <groupid> <channelid>
    # Or simply:
    await message.reply(
        f"Channel Detected: `{message.forward_from_chat.title}`\nID: `{message.forward_from_chat.id}`\n\n"
        f"Now send: `/linkfsub <group_id> {message.forward_from_chat.id}`"
    )

@Client.on_message(filters.private & filters.command("linkfsub"))
async def link_fsub(client, message):
    try:
        gid = int(message.command[1])
        cid = int(message.command[2])
        
        # Verify bot is admin in channel
        try:
            member = await client.get_chat_member(cid, "me")
            if member.status != enums.ChatMemberStatus.ADMINISTRATOR:
                return await message.reply("Make me admin in channel first!")
        except:
            return await message.reply("I can't access that channel.")
            
        await db.update_settings(gid, "fsub", cid)
        await message.reply("✅ Force Join Linked Successfully!")
    except:
        await message.reply("Error. Format: `/linkfsub <group_id> <channel_id>`")

# --- Force Join Enforcer in Group ---
@Client.on_message(filters.group, group=1)
async def fsub_check(client, message):
    if not message.from_user: return
    group = await db.get_group(message.chat.id)
    if not group: return
    
    channel_id = group["settings"].get("fsub")
    if not channel_id: return
    
    # Check if user joined
    try:
        await client.get_chat_member(channel_id, message.from_user.id)
    except UserNotParticipant:
        # Generate Link
        try:
            invite = await client.create_chat_invite_link(channel_id)
            url = invite.invite_link
        except:
            return # Bot maybe lost admin in channel
            
        # Mute User
        try:
            await client.restrict_chat_member(
                message.chat.id, 
                message.from_user.id,
                ChatPermissions(can_send_messages=False)
            )
        except:
            pass # Bot not admin in group

        # Delete msg and Warn
        try:
            await message.delete()
        except: pass
        
        btn = [
            [InlineKeyboardButton("Join Channel", url=url)],
            [InlineKeyboardButton("Try Unmute", callback_data=f"unmute_{message.from_user.id}")]
        ]
        
        sent = await message.reply(
            f"Hey {message.from_user.mention}, You must join our channel to speak here!",
            reply_markup=InlineKeyboardMarkup(btn)
        )
        # Auto delete logic can be added here

@Client.on_callback_query(filters.regex(r"^unmute_"))
async def unmute_handler(client, callback):
    user_id = int(callback.data.split("_")[1])
    if callback.from_user.id != user_id:
        return await callback.answer("Not for you!", show_alert=True)
        
    group = await db.get_group(callback.message.chat.id)
    channel_id = group["settings"].get("fsub")
    
    try:
        await client.get_chat_member(channel_id, user_id)
        # If passed, unmute
        await client.restrict_chat_member(
            callback.message.chat.id,
            user_id,
            ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True
            )
        )
        await callback.message.delete()
    except UserNotParticipant:
        await callback.answer("You haven't joined yet!", show_alert=True)
