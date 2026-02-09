# bio_protection.py - COMPLETE FILE
#"""
#Bio Link Protection System
#Modified for Movie Helper Bot
#"""

import re
import datetime
from pyrogram import Client, filters
from pyrogram.types import Message, ChatPermissions
from database import get_settings, update_settings, add_warning, get_warnings, reset_warnings

class BioLinkProtector:
    
    @staticmethod
    async def check_bio_links(client: Client, message: Message):
        """Check user bio for links"""
        if not message.from_user:
            return False
            
        chat_id = message.chat.id
        user_id = message.from_user.id
        
        # Check if bio protection is enabled
        settings = await get_settings(chat_id)
        if not settings.get("bio_protection", False):
            return False
        
        try:
            # Get user bio
            user = await client.get_chat(user_id)
            bio = user.bio or ""
            
            # Check for URLs
            url_pattern = re.compile(
                r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
                re.IGNORECASE
            )
            
            if url_pattern.search(bio):
                # Delete message
                try:
                    await message.delete()
                except:
                    pass
                
                # Get warning count
                warn_count = await add_warning(chat_id, user_id)
                limit = 3  # Default warning limit
                
                if warn_count >= limit:
                    # Mute user for 24 hours
                    try:
                        await client.restrict_chat_member(
                            chat_id, user_id,
                            ChatPermissions(can_send_messages=False),
                            until_date=datetime.datetime.now() + datetime.timedelta(hours=24)
                        )
                        
                        warning_msg = f"""
⚠️ **BIO LINK VIOLATION** ⚠️

👤 **User:** {user.mention}
🚫 **Action:** Muted for 24 hours
📝 **Reason:** Link found in bio
🔢 **Warnings:** {warn_count}/{limit}

ℹ️ Remove the link from your bio to avoid further actions.
"""
                        msg = await message.reply_text(warning_msg)
                        await reset_warnings(chat_id, user_id)
                        
                        # Auto delete warning message
                        import asyncio
                        asyncio.create_task(BioLinkProtector.auto_delete_message(client, msg, 10))
                        
                    except Exception as e:
                        print(f"Bio protection mute error: {e}")
                        pass
                else:
                    # Warning message
                    warning_msg = f"""
⚠️ **WARNING** ⚠️

👤 **User:** {user.mention}
📝 **Reason:** Link found in bio
🔢 **Warning:** {warn_count}/{limit}
⏰ **Next Action:** Mute (24 hours)

ℹ️ Please remove any links from your bio immediately.
"""
                    msg = await message.reply_text(warning_msg)
                    
                    # Auto delete warning message
                    import asyncio
                    asyncio.create_task(BioLinkProtector.auto_delete_message(client, msg, 10))
                
                return True
                
        except Exception as e:
            print(f"Bio check error: {e}")
        
        return False
    
    @staticmethod
    async def auto_delete_message(client, message, delay: int = 10):
        """Auto delete message after delay"""
        import asyncio
        await asyncio.sleep(delay)
        try:
            await client.delete_messages(message.chat.id, message.id)
        except:
            pass
