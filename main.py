#!/usr/bin/env python3
import os
import sys
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import (
    FloodWait, UserNotParticipant, ChatAdminRequired, 
    ChannelPrivate, UsernameNotOccupied, PeerIdInvalid
)
from pyrogram.handlers import MessageHandler, CallbackQueryHandler

from config import Config
from database import db
from buttons import buttons
from features import feature_manager
from premium_menu import premium_ui

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global bot instance
bot = None

# ========== HELPER FUNCTIONS ==========
async def is_admin(chat_id: int, user_id: int) -> bool:
    """Check if user is admin in chat"""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
    except:
        return False

async def is_owner(user_id: int) -> bool:
    """Check if user is bot owner"""
    return user_id == Config.OWNER_ID

async def delete_message(message: Message, delay: int = 0):
    """Delete message after delay"""
    if delay > 0:
        await asyncio.sleep(delay)
    try:
        await message.delete()
    except:
        pass

async def extract_channel_info(channel_input: str):
    """Extract channel username/id from input"""
    try:
        if channel_input.startswith('@'):
            channel = await bot.get_chat(channel_input)
        elif channel_input.startswith('-100'):
            channel = await bot.get_chat(int(channel_input))
        elif channel_input.isdigit():
            channel = await bot.get_chat(int(f"-100{channel_input}"))
        else:
            channel = await bot.get_chat(f"@{channel_input}")
        
        return {
            "id": channel.id,
            "username": channel.username,
            "title": channel.title,
            "type": channel.type
        }
    except Exception as e:
        logger.error(f"Channel extraction error: {e}")
        return None

# ========== FSUB HANDLER ==========
async def check_fsub(chat_id: int, user_id: int) -> Dict:
    """Check if user is subscribed to required channel"""
    try:
        fsub_data = await db.get_fsub_channel(chat_id)
        
        if not fsub_data or not fsub_data.get("enabled"):
            return {"required": False, "joined": True}
        
        channel_id = fsub_data.get("channel_id")
        
        if not channel_id:
            return {"required": False, "joined": True}
        
        # Check if bot is admin in channel
        try:
            bot_member = await bot.get_chat_member(channel_id, Config.BOT_USERNAME)
            if bot_member.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                return {"required": True, "joined": False, "error": "bot_not_admin"}
        except:
            return {"required": True, "joined": False, "error": "bot_not_admin"}
        
        # Check user subscription
        try:
            user_member = await bot.get_chat_member(channel_id, user_id)
            is_member = user_member.status not in [enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.BANNED]
            
            # Update database
            await db.update_fsub_status(user_id, channel_id, is_member)
            
            return {
                "required": True,
                "joined": is_member,
                "channel": fsub_data.get("channel"),
                "channel_id": channel_id
            }
        except UserNotParticipant:
            await db.update_fsub_status(user_id, channel_id, False)
            return {
                "required": True,
                "joined": False,
                "channel": fsub_data.get("channel"),
                "channel_id": channel_id
            }
        except Exception as e:
            logger.error(f"FSUB check error: {e}")
            return {"required": False, "joined": True}
            
    except Exception as e:
        logger.error(f"FSUB error: {e}")
        return {"required": False, "joined": True}

async def enforce_fsub(message: Message) -> bool:
    """Enforce force subscription"""
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id
        
        # Skip for admins
        if await is_admin(chat_id, user_id):
            return True
        
        fsub_check = await check_fsub(chat_id, user_id)
        
        if fsub_check.get("required") and not fsub_check.get("joined"):
            channel = fsub_check.get("channel")
            
            # Send join message
            join_msg = f"""📢 <b>Force Subscribe Required!</b>

⚠️ You must join our channel to use this bot.

Channel: @{channel}

Click the button below to join, then click "I Have Joined"."""
            
            await message.reply_text(
                join_msg,
                reply_markup=buttons.fsub_channel_button(channel),
                disable_web_page_preview=True
            )
            return False
        
        return True
    except Exception as e:
        logger.error(f"Enforce FSUB error: {e}")
        return True

# ========== FORCE JOIN HANDLER ==========
async def check_force_join(chat_id: int, user_id: int) -> Dict:
    """Check force join requirements"""
    try:
        group = await db.get_group_settings(chat_id)
        
        if not group.get("force_join_enabled"):
            return {"required": False, "completed": True}
        
        required_count = group.get("force_join_count", 0)
        
        if required_count <= 0:
            return {"required": False, "completed": True}
        
        # Check if user is already cleared
        waiting_user = await db.get_waiting_user(chat_id, user_id)
        if not waiting_user:
            # Add user to waiting list
            username = (await bot.get_users(user_id)).username or ""
            await db.add_user_to_waiting(chat_id, user_id, username)
            waiting_user = {"invited_count": 0}
        
        invited_count = waiting_user.get("invited_count", 0)
        
        return {
            "required": True,
            "completed": invited_count >= required_count,
            "required_count": required_count,
            "current_count": invited_count
        }
    except Exception as e:
        logger.error(f"Force join check error: {e}")
        return {"required": False, "completed": True}

async def enforce_force_join(message: Message) -> bool:
    """Enforce force join"""
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id
        
        # Skip for admins
        if await is_admin(chat_id, user_id):
            return True
        
        force_check = await check_force_join(chat_id, user_id)
        
        if force_check.get("required") and not force_check.get("completed"):
            required = force_check.get("required_count", 0)
            current = force_check.get("current_count", 0)
            
            warn_msg = f"""👥 <b>Force Join Required!</b>

⚠️ You must invite {required} members to this group before you can use the bot.

✅ <b>Your Invites:</b> {current}/{required}

Click "Invite Members" to get your invite link, then ask friends to join.
After they join, click "Check Invites"."""
            
            await message.reply_text(
                warn_msg,
                reply_markup=buttons.force_join_buttons(chat_id, required, current)
            )
            return False
        
        return True
    except Exception as e:
        logger.error(f"Enforce force join error: {e}")
        return True

# ========== COMMAND HANDLERS ==========
async def start_command(client: Client, message: Message):
    """Handle /start command"""
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        await db.add_user(user_id, message.from_user.username or "")
        
        if message.chat.type == enums.ChatType.PRIVATE:
            # Private chat
            welcome_text = f"""👋 <b>Welcome to Movie Bot Pro!</b>

I'm an advanced movie information bot with powerful features:

✨ <b>Features:</b>
• 🎬 Movie/Search details
• 🔤 Spelling correction
• 👥 Force Subscribe
• 💎 Premium system
• ⚡ Fast responses

Use me in groups to get movie information instantly!

<b>Commands:</b>
• /start - Start the bot
• /movie <name> - Get movie details
• /settings - Bot settings (admins only)
• /stats - View statistics
• /premium - Premium information

<b>Add me to your group:</b>"""
            
            await message.reply_text(
                welcome_text,
                reply_markup=buttons.start_menu(user_id),
                disable_web_page_preview=True
            )
        else:
            # Group chat
            welcome_text = f"""👋 <b>Movie Bot Pro is active!</b>

I'm ready to provide movie information and more.

<b>Group Commands:</b>
• /movie <name> - Get movie details
• /settings - Bot settings (admins only)
• /stats - Group statistics
• /premium - Premium information

<b>Simply type movie names to get information!</b>"""
            
            await message.reply_text(
                welcome_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 Channel", url=f"https://t.me/{Config.MAIN_CHANNEL}"),
                     InlineKeyboardButton("👨‍💻 Owner", url="https://t.me/asbhai_bsr")]
                ])
            )
    
    except Exception as e:
        logger.error(f"Start command error: {e}")

async def fsub_command(client: Client, message: Message):
    """Handle /fsub command"""
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id
        
        # Check admin
        if not await is_admin(chat_id, user_id):
            await message.reply_text("❌ Only admins can use this command.")
            return
        
        if len(message.command) < 2:
            # Show current FSUB status
            fsub_data = await db.get_fsub_channel(chat_id)
            
            if fsub_data.get("enabled"):
                channel = fsub_data.get("channel", "N/A")
                status_text = f"""📢 <b>Force Subscribe Status</b>

✅ <b>Enabled:</b> Yes
📢 <b>Channel:</b> @{channel}

To disable: /fsub off
To change channel: /fsub @channel_username"""
            else:
                status_text = """📢 <b>Force Subscribe Status</b>

❌ <b>Enabled:</b> No

To enable: /fsub @channel_username
Example: /fsub @MovieProChannel"""
            
            await message.reply_text(status_text)
            return
        
        arg = message.command[1].lower()
        
        if arg == "off":
            await db.disable_fsub(chat_id)
            await message.reply_text("✅ Force Subscribe disabled.")
            return
        
        # Set FSUB channel
        channel_input = message.command[1]
        
        # Validate channel
        channel_info = await extract_channel_info(channel_input)
        if not channel_info:
            await message.reply_text("❌ Invalid channel. Please provide a valid channel username or ID.")
            return
        
        if channel_info.get("type") != enums.ChatType.CHANNEL:
            await message.reply_text("❌ Please provide a channel, not a group or user.")
            return
        
        # Check if bot is admin in channel
        try:
            bot_member = await bot.get_chat_member(channel_info["id"], Config.BOT_USERNAME)
            if bot_member.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                await message.reply_text(
                    f"❌ Please make me admin in @{channel_info.get('username')} first.\n\n"
                    f"1. Add @{Config.BOT_USERNAME} to your channel\n"
                    f"2. Give me 'Post Messages' permission\n"
                    f"3. Try again"
                )
                return
        except Exception as e:
            await message.reply_text(
                f"❌ Cannot access channel. Please:\n"
                f"1. Add @{Config.BOT_USERNAME} to @{channel_info.get('username', 'your_channel')}\n"
                f"2. Make me admin\n"
                f"3. Try again"
            )
            return
        
        # Save FSUB settings
        await db.set_fsub_channel(
            chat_id,
            channel_info.get("username") or str(channel_info["id"]),
            channel_info["id"]
        )
        
        await message.reply_text(
            f"✅ Force Subscribe enabled!\n\n"
            f"📢 <b>Channel:</b> @{channel_info.get('username', channel_info['id'])}\n"
            f"👥 <b>New users must join this channel to use the bot.</b>\n\n"
            f"To disable: /fsub off"
        )
    
    except Exception as e:
        logger.error(f"FSUB command error: {e}")
        await message.reply_text("❌ Error setting up Force Subscribe.")

async def force_join_command(client: Client, message: Message):
    """Handle /forcejoin command"""
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id
        
        # Check admin
        if not await is_admin(chat_id, user_id):
            await message.reply_text("❌ Only admins can use this command.")
            return
        
        if len(message.command) < 2:
            # Show current status
            group = await db.get_group_settings(chat_id)
            
            if group.get("force_join_enabled"):
                count = group.get("force_join_count", 0)
                status_text = f"""👥 <b>Force Join Status</b>

✅ <b>Enabled:</b> Yes
👥 <b>Required Members:</b> {count}

New users must invite {count} members before they can use the bot.

To disable: /forcejoin off
To change count: /forcejoin <number>"""
            else:
                status_text = """👥 <b>Force Join Status</b>

❌ <b>Enabled:</b> No

To enable: /forcejoin <number>
Example: /forcejoin 5 (users must invite 5 members)"""
            
            await message.reply_text(status_text)
            return
        
        arg = message.command[1].lower()
        
        if arg == "off":
            await db.disable_force_join(chat_id)
            await message.reply_text("✅ Force Join disabled.")
            return
        
        # Set force join count
        try:
            count = int(arg)
            if count < 1 or count > 50:
                await message.reply_text("❌ Please provide a number between 1 and 50.")
                return
            
            await db.set_force_join(chat_id, count)
            
            await message.reply_text(
                f"✅ Force Join enabled!\n\n"
                f"👥 <b>Required Members:</b> {count}\n"
                f"🆕 <b>New users must invite {count} members before using the bot.</b>\n\n"
                f"To disable: /forcejoin off"
            )
        except ValueError:
            await message.reply_text("❌ Please provide a valid number.")
    
    except Exception as e:
        logger.error(f"Force join command error: {e}")
        await message.reply_text("❌ Error setting up Force Join.")

async def movie_command(client: Client, message: Message):
    """Handle /movie command"""
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id
        
        # Check FSUB
        fsub_passed = await enforce_fsub(message)
        if not fsub_passed:
            return
        
        # Check Force Join
        force_passed = await enforce_force_join(message)
        if not force_passed:
            return
        
        if len(message.command) < 2:
            await message.reply_text(
                "❌ Please provide a movie name.\n"
                "Example: `/movie Inception 2010` or `/movie Avengers Endgame`",
                parse_mode=enums.ParseMode.MARKDOWN
            )
            return
        
        # Extract movie name
        movie_name = " ".join(message.command[1:])
        
        # Clean movie name
        clean_name = await feature_manager.clean_movie_request(movie_name)
        
        # Send searching message
        search_msg = await message.reply_text(f"🔍 <b>Searching for:</b> <code>{clean_name}</code>")
        
        # Get movie details
        movie_data = await feature_manager.get_movie_details(clean_name)
        
        if not movie_data.get("success"):
            await search_msg.edit_text(
                f"❌ <b>Movie not found!</b>\n\n"
                f"<b>Searched:</b> <code>{clean_name}</code>\n\n"
                f"<i>Try:</i>\n"
                f"• Check spelling\n"
                f"• Add year (e.g., Inception 2010)\n"
                f"• Try different name"
            )
            return
        
        # Send movie details
        await search_msg.edit_text(
            movie_data.get("text"),
            reply_markup=buttons.movie_details_buttons(
                movie_data.get("imdb_id"),
                movie_data.get("title")
            ),
            disable_web_page_preview=False
        )
        
        # Auto-delete if enabled
        group_settings = await db.get_group_settings(chat_id)
        if group_settings.get("features", {}).get("auto_delete", True):
            delay = group_settings.get("auto_delete_time", 60)
            asyncio.create_task(delete_message(message, delay))
            asyncio.create_task(delete_message(search_msg, delay + 2))
    
    except Exception as e:
        logger.error(f"Movie command error: {e}")
        try:
            await message.reply_text("❌ Error fetching movie details. Please try again.")
        except:
            pass

async def handle_movie_request(client: Client, message: Message):
    """Handle movie name in text messages"""
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id
        text = message.text.strip()
        
        # Ignore commands
        if text.startswith('/'):
            return
        
        # Check FSUB
        fsub_passed = await enforce_fsub(message)
        if not fsub_passed:
            return
        
        # Check Force Join
        force_passed = await enforce_force_join(message)
        if not force_passed:
            return
        
        # Check if it looks like a movie request
        movie_keywords = ['movie', 'film', 'series', 'season', 'download', 'de do', 'chahiye']
        text_lower = text.lower()
        
        if not any(keyword in text_lower for keyword in movie_keywords):
            return
        
        # Extract and clean movie name
        clean_name, year = await feature_manager.extract_movie_name(text)
        
        if not clean_name or len(clean_name) < 2:
            return
        
        # Get group settings
        group_settings = await db.get_group_settings(chat_id)
        
        # Spell check
        if group_settings.get("features", {}).get("spell_check", True):
            spell_check = await feature_manager.check_spelling_correction(clean_name)
            if spell_check.get("needs_correction"):
                await message.reply_text(
                    f"🤔 <b>Did you mean:</b> <code>{spell_check.get('suggested')}</code>?\n"
                    f"<i>Original:</i> <code>{spell_check.get('original')}</code>",
                    reply_markup=buttons.spell_check_buttons(
                        spell_check.get('original'),
                        spell_check.get('suggested')
                    )
                )
                return
        
        # Season check
        if group_settings.get("features", {}).get("season_check", True):
            needs_season, suggested = await feature_manager.check_season_requirement(text)
            if needs_season:
                await message.reply_text(
                    f"📺 <b>Season Required!</b>\n\n"
                    f"Your request looks like a series.\n"
                    f"Please specify season number.\n\n"
                    f"<b>Try:</b> <code>{suggested}</code>"
                )
                return
        
        # Search for movie
        search_msg = await message.reply_text(f"🔍 <b>Searching for:</b> <code>{clean_name}</code>")
        
        # Search multiple results
        search_results = await feature_manager.search_movies(clean_name)
        
        if not search_results:
            await search_msg.edit_text(
                f"❌ <b>No movies found!</b>\n\n"
                f"<b>Searched:</b> <code>{clean_name}</code>\n\n"
                f"<i>Suggestions:</i>\n"
                f"• Check spelling\n"
                f"• Add year (e.g., Inception 2010)\n"
                f"• Try different name"
            )
            return
        
        # Save search results
        search_id = await db.save_search_results(clean_name, search_results)
        
        # Show search results with buttons
        result_text = f"🔍 <b>Search Results for:</b> <code>{clean_name}</code>\n\n"
        result_text += f"📄 <b>Found {len(search_results)} results:</b>\n"
        
        for i, movie in enumerate(search_results[:5], 1):
            title = movie.get('title', 'Unknown')
            year = movie.get('year', 'N/A')
            result_text += f"{i}. <b>{title}</b> ({year})\n"
        
        if len(search_results) > 5:
            result_text += f"\n... and {len(search_results) - 5} more"
        
        result_text += "\n\n<b>Click on a movie for details:</b>"
        
        await search_msg.edit_text(
            result_text,
            reply_markup=buttons.movie_search_buttons(search_id, search_results)
        )
        
        # Auto-delete if enabled
        if group_settings.get("features", {}).get("auto_delete", True):
            delay = group_settings.get("auto_delete_time", 60)
            asyncio.create_task(delete_message(message, delay))
            asyncio.create_task(delete_message(search_msg, delay + 2))
    
    except Exception as e:
        logger.error(f"Movie request handler error: {e}")

async def handle_callback(client: Client, callback_query: CallbackQuery):
    """Handle all callback queries"""
    try:
        chat_id = callback_query.message.chat.id
        user_id = callback_query.from_user.id
        data = callback_query.data
        
        # Check if user is authorized for this callback
        if callback_query.message.reply_to_message:
            original_user = callback_query.message.reply_to_message.from_user.id
            if user_id != original_user and not await is_admin(chat_id, user_id):
                await callback_query.answer("This is not for you!", show_alert=True)
                return
        
        # Handle different callbacks
        if data == "back_to_start":
            await callback_query.message.edit_text(
                "👋 <b>Welcome to Movie Bot Pro!</b>\n\nUse buttons below:",
                reply_markup=buttons.start_menu(user_id)
            )
        
        elif data == "show_features":
            is_admin_user = await is_admin(chat_id, user_id) if chat_id != user_id else False
            await callback_query.message.edit_text(
                "⚙️ <b>Bot Features</b>\n\nToggle features ON/OFF:",
                reply_markup=buttons.features_menu(chat_id, is_admin_user)
            )
        
        elif data.startswith("toggle_"):
            feature = data.replace("toggle_", "")
            group_settings = await db.get_group_settings(chat_id)
            current = group_settings.get("features", {}).get(feature, True)
            new_value = not current
            
            await db.toggle_feature(chat_id, feature, new_value)
            
            status = "✅ ON" if new_value else "❌ OFF"
            await callback_query.answer(f"{feature.replace('_', ' ').title()}: {status}")
            
            # Refresh features menu
            is_admin_user = await is_admin(chat_id, user_id) if chat_id != user_id else False
            await callback_query.message.edit_reply_markup(
                buttons.features_menu(chat_id, is_admin_user)
            )
        
        elif data.startswith("feature_"):
            feature = data.replace("feature_", "")
            feature_names = {
                "fsub": "Force Subscribe",
                "force_join": "Force Join",
                "spell_check": "Spelling Check",
                "season_check": "Season Check",
                "auto_delete": "Auto Delete",
                "file_cleaner": "File Cleaner",
                "request_system": "Request System"
            }
            
            feature_name = feature_names.get(feature, feature.replace('_', ' ').title())
            group_settings = await db.get_group_settings(chat_id)
            status = "✅ ON" if group_settings.get("features", {}).get(feature, True) else "❌ OFF"
            
            await callback_query.answer(f"{feature_name}: {status}")
        
        elif data == "set_time_menu":
            await callback_query.message.edit_text(
                "⏰ <b>Set Auto Delete Time</b>\n\nSelect time for auto-deleting messages:",
                reply_markup=buttons.time_selection_menu("auto_delete")
            )
        
        elif data.startswith("set_time_"):
            parts = data.split("_")
            if len(parts) >= 4:
                feature_type = parts[2]
                time_sec = int(parts[3])
                
                await db.update_group_settings(chat_id, {"auto_delete_time": time_sec})
                
                time_text = "Permanent" if time_sec == 0 else f"{time_sec} seconds"
                await callback_query.answer(f"Auto delete time set to {time_text}")
                
                is_admin_user = await is_admin(chat_id, user_id) if chat_id != user_id else False
                await callback_query.message.edit_reply_markup(
                    buttons.features_menu(chat_id, is_admin_user)
                )
        
        elif data.startswith("use_corrected_"):
            corrected = data.replace("use_corrected_", "")
            await callback_query.message.delete()
            
            # Search with corrected name
            search_msg = await callback_query.message.reply_text(
                f"🔍 <b>Searching for:</b> <code>{corrected}</code>"
            )
            
            movie_data = await feature_manager.get_movie_details(corrected)
            
            if movie_data.get("success"):
                await search_msg.edit_text(
                    movie_data.get("text"),
                    reply_markup=buttons.movie_details_buttons(
                        movie_data.get("imdb_id"),
                        movie_data.get("title")
                    ),
                    disable_web_page_preview=False
                )
            else:
                await search_msg.edit_text(
                    f"❌ <b>Movie not found!</b>\n\n"
                    f"<b>Searched:</b> <code>{corrected}</code>"
                )
        
        elif data == "keep_original":
            await callback_query.answer("Using original name")
            await callback_query.message.delete()
        
        elif data.startswith("select_movie_"):
            parts = data.split("_")
            if len(parts) >= 4:
                search_id = parts[2]
                result_idx = int(parts[3])
                
                # Get cached results
                results = await db.get_search_results(search_id)
                
                if results and 0 <= result_idx < len(results):
                    movie = results[result_idx]
                    
                    # Get full details
                    movie_data = await feature_manager.get_movie_details(movie.get('title'))
                    
                    if movie_data.get("success"):
                        await callback_query.message.edit_text(
                            movie_data.get("text"),
                            reply_markup=buttons.movie_details_buttons(
                                movie_data.get("imdb_id"),
                                movie_data.get("title")
                            ),
                            disable_web_page_preview=False
                        )
                    else:
                        await callback_query.answer("Error fetching details", show_alert=True)
                else:
                    await callback_query.answer("Result not found", show_alert=True)
        
        elif data.startswith("movie_page_"):
            parts = data.split("_")
            if len(parts) >= 4:
                search_id = parts[2]
                page = int(parts[3])
                
                results = await db.get_search_results(search_id)
                if results:
                    await callback_query.message.edit_reply_markup(
                        buttons.movie_search_buttons(search_id, results, page)
                    )
        
        elif data == "search_again":
            await callback_query.message.edit_text(
                "🔍 <b>Search Movies</b>\n\nSend me a movie name:"
            )
        
        elif data == "check_fsub":
            fsub_check = await check_fsub(chat_id, user_id)
            
            if fsub_check.get("joined"):
                await callback_query.answer("✅ Verified! You can now use the bot.", show_alert=True)
                await callback_query.message.delete()
                
                # Send welcome message
                await callback_query.message.reply_text(
                    "✅ <b>Welcome!</b>\n\n"
                    "You can now use all bot features.\n\n"
                    "Send a movie name to get information!"
                )
            else:
                await callback_query.answer(
                    "❌ You haven't joined the channel yet!", 
                    show_alert=True
                )
        
        elif data == "check_invites":
            force_check = await check_force_join(chat_id, user_id)
            
            if force_check.get("completed"):
                await callback_query.answer("✅ Verified! You can now use the bot.", show_alert=True)
                await callback_query.message.delete()
                
                # Remove from waiting list
                await db.remove_user_from_waiting(chat_id, user_id)
                
                # Send welcome message
                await callback_query.message.reply_text(
                    "✅ <b>Welcome!</b>\n\n"
                    "You can now use all bot features.\n\n"
                    "Send a movie name to get information!"
                )
            else:
                required = force_check.get("required_count", 0)
                current = force_check.get("current_count", 0)
                
                await callback_query.answer(
                    f"❌ You need {required - current} more invites!", 
                    show_alert=True
                )
        
        elif data == "cancel_force_join":
            await callback_query.answer("Force join cancelled", show_alert=True)
            await callback_query.message.delete()
        
        elif data == "show_premium":
            await callback_query.message.edit_text(
                premium_ui.main_premium_text(),
                reply_markup=premium_ui.premium_buttons(),
                disable_web_page_preview=True
            )
        
        elif data == "close" or data == "close_search" or data == "close_details":
            await callback_query.message.delete()
        
        await callback_query.answer()
    
    except Exception as e:
        logger.error(f"Callback error: {e}")
        try:
            await callback_query.answer("Error processing request", show_alert=True)
        except:
            pass

async def handle_new_member(client: Client, message: Message):
    """Handle new members joining"""
    try:
        chat_id = message.chat.id
        
        for member in message.new_chat_members:
            if member.id == client.me.id:
                # Bot added to group
                await db.update_group_settings(chat_id, {"title": message.chat.title})
                
                welcome_text = f"""✅ <b>Movie Bot Pro added to {message.chat.title}!</b>

Thank you for adding me! Here's what I can do:

🎬 <b>Movie Information:</b> Just type movie names
🔤 <b>Spelling Correction:</b> Auto-corrects movie names
👥 <b>Force Subscribe:</b> Control who can use the bot
💎 <b>Premium Features:</b> Remove ads, faster responses

<b>Admin Commands:</b>
• /settings - Configure bot
• /fsub - Setup force subscribe
• /forcejoin - Setup force join

<b>Enjoy using Movie Bot Pro! 🎥</b>"""
                
                await message.reply_text(welcome_text)
                return
            
            # Check if this user was invited by someone
            if message.from_user and message.from_user.id != member.id:
                # This is an invite
                inviter_id = message.from_user.id
                invited_id = member.id
                
                # Update invited count
                count = await db.update_invited_count(chat_id, inviter_id, invited_id)
                
                # Check force join requirements
                group = await db.get_group_settings(chat_id)
                required = group.get("force_join_count", 0)
                
                if required > 0 and count >= required:
                    # User has completed requirements
                    welcome_msg = f"""✅ <b>Welcome {member.first_name}!</b>

Thanks for joining! Your friend has completed their invitation requirements.

Enjoy using the bot! 🎬"""
                    
                    await message.reply_text(welcome_msg)
    
    except Exception as e:
        logger.error(f"New member handler error: {e}")

async def stats_command(client: Client, message: Message):
    """Show statistics"""
    try:
        chat_id = message.chat.id
        
        if message.chat.type == enums.ChatType.PRIVATE:
            # Bot stats
            stats = await db.get_bot_stats()
            premium_info = await db.get_premium_info(chat_id)
            
            stats_text = f"""📊 <b>Bot Statistics</b>

👥 <b>Total Users:</b> {stats.get('total_users', 0)}
👥 <b>Total Groups:</b> {stats.get('total_groups', 0)}
💎 <b>Premium Groups:</b> {stats.get('premium_groups', 0)}
🎬 <b>Total Requests:</b> {stats.get('total_requests', 0)}
⏳ <b>Pending Requests:</b> {stats.get('pending_requests', 0)}
📅 <b>Today's Requests:</b> {stats.get('today_requests', 0)}

<b>Your Status:</b> {'💎 Premium' if premium_info.get('is_premium') else '🆓 Free'}"""
            
            await message.reply_text(stats_text)
        else:
            # Group stats
            group_stats = await db.get_group_stats(chat_id)
            premium_info = await db.get_premium_info(chat_id)
            
            # Get member count
            try:
                chat = await client.get_chat(chat_id)
                member_count = chat.members_count
            except:
                member_count = "N/A"
            
            stats_text = f"""📊 <b>Group Statistics</b>

👥 <b>Members:</b> {member_count}
🎬 <b>Total Requests:</b> {group_stats.get('total_requests', 0)}
📅 <b>Today's Requests:</b> {group_stats.get('today_requests', 0)}
💎 <b>Premium:</b> {'✅ Active' if premium_info.get('is_premium') else '❌ Not Active'}

<b>Bot added on:</b> {group_stats.get('created').strftime('%Y-%m-%d') if group_stats.get('created') else 'N/A'}"""
            
            await message.reply_text(stats_text)
    
    except Exception as e:
        logger.error(f"Stats command error: {e}")

# ========== MAIN FUNCTION ==========
async def main():
    """Main function"""
    global bot
    
    try:
        # Initialize database
        await db.init_db()
        logger.info("✅ Database initialized")
        
        # Create bot instance
        bot = Client(
            "MovieBotPro",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            workers=20,
            sleep_threshold=60,
            plugins=dict(root="plugins")
        )
        
        # Add handlers
        bot.add_handler(MessageHandler(start_command, filters.command(["start", "help"])))
        bot.add_handler(MessageHandler(fsub_command, filters.command(["fsub"])))
        bot.add_handler(MessageHandler(force_join_command, filters.command(["forcejoin"])))
        bot.add_handler(MessageHandler(movie_command, filters.command(["movie"])))
        bot.add_handler(MessageHandler(stats_command, filters.command(["stats"])))
        bot.add_handler(MessageHandler(handle_movie_request, filters.text & filters.group))
        bot.add_handler(MessageHandler(handle_new_member, filters.new_chat_members))
        bot.add_handler(CallbackQueryHandler(handle_callback))
        
        # Start bot
        logger.info("✅ Starting Movie Bot Pro...")
        await bot.start()
        
        # Get bot info
        bot_info = await bot.get_me()
        logger.info(f"✅ Bot started as @{bot_info.username}")
        
        # Set bot commands
        await bot.set_bot_commands([
            ("start", "Start the bot"),
            ("movie", "Get movie details"),
            ("fsub", "Setup force subscribe (admin)"),
            ("forcejoin", "Setup force join (admin)"),
            ("settings", "Bot settings (admin)"),
            ("stats", "View statistics"),
            ("premium", "Premium information")
        ])
        
        logger.info("✅ Bot commands set")
        logger.info("✅ Bot is running...")
        
        # Keep bot running
        await idle()
        
        logger.info("🛑 Shutting down bot...")
        
    except Exception as e:
        logger.error(f"❌ Main error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            if bot and await bot.is_connected:
                await bot.stop()
                logger.info("✅ Bot stopped successfully")
        except Exception as e:
            logger.error(f"❌ Error stopping bot: {e}")

async def idle():
    """Idle function to keep bot running"""
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        pass

if __name__ == "__main__":
    try:
        # Run the bot
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
