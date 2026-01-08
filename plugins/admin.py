#  plugins/admin.py

import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from database import db
from config import Config
from datetime import datetime, timedelta

@Client.on_message(filters.command("stats") & filters.user(Config.OWNER_ID))
async def stats_command(client, message):
    """Show bot statistics"""
    users, groups, requests, active_groups = await db.get_stats()
    
    # Get premium groups count
    premium_count = 0
    async for group in await db.get_all_groups():
        if await db.is_premium(group['id']):
            premium_count += 1
    
    text = f"""
**🤖 Bot Statistics**

**👥 Users:** {users}
**📢 Groups:** {groups}
**🌟 Premium Groups:** {premium_count}
**📥 Requests:** {requests}
**🎯 Active Groups (7 days):** {active_groups}

**📊 Database Status:** ✅ Connected
**⏰ Uptime:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    
    buttons = [
        [
            InlineKeyboardButton("🗑 Clean Junk", callback_data="clean_junk"),
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")
        ],
        [
            InlineKeyboardButton("📊 Detailed Stats", callback_data="detailed_stats"),
            InlineKeyboardButton("📢 Broadcast", callback_data="broadcast_menu")
        ]
    ]
    
    await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^refresh_stats$") & filters.user(Config.OWNER_ID))
async def refresh_stats_callback(client, callback):
    """Refresh statistics"""
    await stats_command(client, callback.message)
    await callback.answer("Stats refreshed!")

@Client.on_callback_query(filters.regex(r"^detailed_stats$") & filters.user(Config.OWNER_ID))
async def detailed_stats_callback(client, callback):
    """Show detailed statistics"""
    users, groups, requests, active_groups = await db.get_stats()
    
    # Get recent users (last 7 days)
    week_ago = datetime.now() - timedelta(days=7)
    recent_users = 0
    async for user in await db.get_all_users():
        if user.get('joined_date', datetime.now()) >= week_ago:
            recent_users += 1
    
    # Get group sizes
    small_groups = 0
    medium_groups = 0
    large_groups = 0
    
    async for group in await db.get_all_groups():
        msg_count = group.get('stats', {}).get('total_messages', 0)
        if msg_count < 100:
            small_groups += 1
        elif msg_count < 1000:
            medium_groups += 1
        else:
            large_groups += 1
    
    text = f"""
**📈 Detailed Statistics**

**👥 User Analytics:**
• Total Users: {users}
• New Users (7 days): {recent_users}
• Daily Growth: {recent_users/7:.1f}/day

**📢 Group Analytics:**
• Total Groups: {groups}
• Active Groups: {active_groups}
• Inactive Groups: {groups - active_groups}

**📊 Group Size:**
• Small (<100 msgs): {small_groups}
• Medium (100-1000): {medium_groups}
• Large (>1000): {large_groups}

**📥 Requests:** {requests}
    """
    
    buttons = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_stats")]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^back_to_stats$") & filters.user(Config.OWNER_ID))
async def back_to_stats(client, callback):
    """Go back to main stats"""
    await stats_command(client, callback.message)

@Client.on_message(filters.command("broadcast") & filters.user(Config.OWNER_ID) & filters.reply)
async def broadcast_handler(client, message):
    """Broadcast message to all users and groups"""
    if not message.reply_to_message:
        await message.reply("Please reply to a message to broadcast!")
        return
    
    msg = message.reply_to_message
    confirm_text = """
⚠️ **Broadcast Confirmation**

**Message Type:** {type}
**Content:** {content}

**Targets:**
• All Users ({users_count})
• Free Groups ({groups_count})

**Premium groups will NOT receive this broadcast.**

**Proceed with broadcast?
    """.format(
        type=msg.media and msg.media.value or "Text",
        content=msg.text[:100] + "..." if msg.text else "Media",
        users_count=await db.users.count_documents({}),
        groups_count=await db.groups.count_documents({})
    )
    
    buttons = [
        [
            InlineKeyboardButton("✅ Yes, Broadcast", callback_data="confirm_broadcast"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_broadcast")
        ]
    ]
    
    await message.reply(confirm_text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^broadcast_menu$") & filters.user(Config.OWNER_ID))
async def broadcast_menu(client, callback):
    """Broadcast menu"""
    await callback.message.edit_text(
        "📢 **Broadcast Menu**\n\n"
        "To broadcast:\n"
        "1. Reply to any message\n"
        "2. Use /broadcast command\n\n"
        "Options:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Send Test", callback_data="test_broadcast")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_stats")]
        ])
    )

@Client.on_callback_query(filters.regex(r"^confirm_broadcast$") & filters.user(Config.OWNER_ID))
async def confirm_broadcast(client, callback):
    """Confirm and start broadcast"""
    await callback.message.edit_text("🚀 Starting broadcast...")
    
    msg = callback.message.reply_to_message
    total_users = 0
    success_users = 0
    failed_users = 0
    
    total_groups = 0
    success_groups = 0
    failed_groups = 0
    
    # Broadcast to users
    async for user in await db.get_all_users():
        total_users += 1
        try:
            await msg.copy(chat_id=user['id'])
            success_users += 1
        except Exception as e:
            failed_users += 1
            # Remove inactive users
            if "deactivated" in str(e).lower() or "blocked" in str(e).lower():
                await db.delete_user(user['id'])
        
        # Update progress every 10 users
        if total_users % 10 == 0:
            await callback.message.edit_text(
                f"📤 Broadcasting...\n\n"
                f"👥 Users: {success_users}/{total_users}\n"
                f"📢 Groups: {success_groups}/{total_groups}"
            )
    
    # Broadcast to free groups only
    async for group in await db.get_all_groups():
        if await db.is_premium(group['id']):
            continue  # Skip premium groups
        
        total_groups += 1
        try:
            await msg.copy(chat_id=group['id'])
            success_groups += 1
        except Exception:
            failed_groups += 1
    
    # Final report
    report = f"""
✅ **Broadcast Completed!**

**👥 Users:**
• Total: {total_users}
• Success: {success_users}
• Failed: {failed_users}

**📢 Groups:**
• Total: {total_groups}
• Success: {success_groups}
• Failed: {failed_groups}

**💾 Cleanup:**
• Inactive users removed: {failed_users}
• Premium groups skipped: {await db.premium.count_documents({})}
    """
    
    await callback.message.edit_text(report)

@Client.on_callback_query(filters.regex(r"^cancel_broadcast$") & filters.user(Config.OWNER_ID))
async def cancel_broadcast(client, callback):
    """Cancel broadcast"""
    await callback.message.edit_text("❌ Broadcast cancelled!")
    await callback.answer()

@Client.on_callback_query(filters.regex(r"^clean_junk$") & filters.user(Config.OWNER_ID))
async def clean_junk(client, callback):
    """Clean inactive groups and users"""
    await callback.message.edit_text("🧹 Cleaning junk data...")
    
    removed_groups = 0
    removed_users = 0
    
    # Clean groups where bot is not member
    async for group in await db.get_all_groups():
        try:
            await client.get_chat_member(group['id'], "me")
        except Exception:
            # Bot not in group, remove from DB
            await db.delete_group(group['id'])
            removed_groups += 1
    
    # Clean inactive users (no activity for 30 days)
    month_ago = datetime.now() - timedelta(days=30)
    async for user in await db.get_all_users():
        last_active = user.get('last_active', user.get('joined_date', datetime.now()))
        if last_active < month_ago:
            try:
                # Try to send message
                await client.send_message(user['id'], ".")
            except Exception:
                # User inactive, remove
                await db.delete_user(user['id'])
                removed_users += 1
    
    report = f"""
✅ **Cleanup Completed!**

**🗑 Removed:**
• Groups: {removed_groups}
• Users: {removed_users}

**📊 Remaining:**
• Groups: {await db.groups.count_documents({})}
• Users: {await db.users.count_documents({})}
    """
    
    await callback.message.edit_text(report)

@Client.on_message(filters.command("addpremium") & filters.user(Config.OWNER_ID))
async def add_premium_command(client, message):
    """Add premium to group"""
    if len(message.command) < 3:
        await message.reply(
            "Usage: `/addpremium <group_id> <months>`\n\n"
            "Example: `/addpremium -100123456789 3`\n"
            "This will add 3 months premium."
        )
        return
    
    try:
        group_id = int(message.command[1])
        months = int(message.command[2])
        
        # Check if group exists
        group = await db.get_group(group_id)
        if not group:
            await message.reply("❌ Group not found in database!")
            return
        
        # Add premium
        await db.add_premium(group_id, months)
        
        # Calculate expiry
        expiry_date = datetime.now() + timedelta(days=30*months)
        
        await message.reply(
            f"✅ **Premium Added Successfully!**\n\n"
            f"**Group:** {group['title']}\n"
            f"**Group ID:** `{group_id}`\n"
            f"**Duration:** {months} month(s)\n"
            f"**Amount:** ₹{Config.PREMIUM_PRICE_PER_MONTH * months}\n"
            f"**Expiry:** {expiry_date.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"Premium features are now active!"
        )
        
        # Notify group
        try:
            await client.send_message(
                group_id,
                f"🎉 **Congratulations!**\n\n"
                f"Your group has been upgraded to **Premium** for {months} month(s)!\n\n"
                f"🌟 **Premium Benefits:**\n"
                f"• No broadcast messages\n"
                f"• Priority support\n"
                f"• Advanced features\n"
                f"• And much more!\n\n"
                f"Expiry: {expiry_date.strftime('%Y-%m-%d')}"
            )
        except:
            pass
        
    except ValueError:
        await message.reply("❌ Invalid input! Group ID and months must be numbers.")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

@Client.on_message(filters.command("premiumlist") & filters.user(Config.OWNER_ID))
async def premium_list_command(client, message):
    """List all premium groups"""
    premium_groups = []
    async for premium in await db.premium.find({}):
        group = await db.get_group(premium['group_id'])
        if group:
            premium_groups.append({
                'group': group['title'],
                'id': group['id'],
                'expiry': premium['expiry_date'],
                'months': premium['months']
            })
    
    if not premium_groups:
        await message.reply("No premium groups found!")
        return
    
    text = "🌟 **Premium Groups List**\n\n"
    
    for idx, pg in enumerate(premium_groups, 1):
        days_left = (pg['expiry'] - datetime.now()).days
        status = "✅ Active" if days_left > 0 else "❌ Expired"
        
        text += f"{idx}. **{pg['group']}**\n"
        text += f"   ID: `{pg['id']}`\n"
        text += f"   Months: {pg['months']}\n"
        text += f"   Expiry: {pg['expiry'].strftime('%Y-%m-%d')}\n"
        text += f"   Status: {status} ({days_left} days left)\n\n"
    
    await message.reply(text)

@Client.on_message(filters.command("send") & filters.user(Config.OWNER_ID))
async def send_message_command(client, message):
    """Send message to specific user/group"""
    if len(message.command) < 3:
        await message.reply(
            "Usage: `/send <chat_id> <message>`\n\n"
            "Example: `/send -100123456789 Hello!`\n"
            "Or reply to a message: `/send -100123456789`"
        )
        return
    
    try:
        chat_id = int(message.command[1])
        
        if message.reply_to_message:
            msg = message.reply_to_message
            await msg.copy(chat_id=chat_id)
            await message.reply(f"✅ Message sent to `{chat_id}`")
        else:
            text = " ".join(message.command[2:])
            await client.send_message(chat_id, text)
            await message.reply(f"✅ Message sent to `{chat_id}`")
            
    except ValueError:
        await message.reply("❌ Invalid chat ID!")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")
