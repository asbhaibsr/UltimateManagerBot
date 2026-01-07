# premium_menu.py

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import Config

class PremiumManager:
    @staticmethod
    def main_premium_text():
        return """💎 <b>MOVIE BOT PRO PREMIUM</b> 💎

<b>Upgrade karein aur payein behtareen features:</b>

✅ <b>AD-FREE Experience:</b> Aapke group mein koi broadcast ads nahi ayenge.
✅ <b>High Speed:</b> Bot fast response karega.
✅ <b>Priority Support:</b> Admin support directly milega.
✅ <b>Unlimited Requests:</b> Koi daily limit nahi.
✅ <b>Custom Branding:</b> Bot mein apna channel name set karein.

<b>💰 PRICING:</b>
• 5 Months: ₹300
• 1 Year (12 Months): ₹500
• 2 Years (24 Months): ₹1000

<b>⚠️ Note:</b> Promotion ke liye bhi contact karein.
"""

    @staticmethod
    def premium_buttons():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Buy Premium / Contact Owner", url="https://t.me/asbhaibsr")],
            [InlineKeyboardButton("🎬 Request Movies", callback_data="request_movie")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_start")]
        ])

    @staticmethod
    def admin_premium_select(group_id: int):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("5 Months (₹300)", callback_data=f"addprem_{group_id}_5")],
            [InlineKeyboardButton("1 Year (₹500)", callback_data=f"addprem_{group_id}_12")],
            [InlineKeyboardButton("2 Years (₹1000)", callback_data=f"addprem_{group_id}_24")],
            [InlineKeyboardButton("❌ Cancel", callback_data="close")]
        ])
    
    @staticmethod
    def premium_status_text(chat_id: int, is_premium: bool, expiry_date=None):
        if not is_premium:
            return """<b>🔴 PREMIUM STATUS: NOT ACTIVE</b>
            
Your group is currently using FREE version.
Some features may be limited and ads may appear.

<b>Upgrade to Premium for:</b>
✅ No Ads
✅ Faster Responses
✅ Priority Support
✅ All Features Unlocked

Click below to upgrade:
"""
        else:
            expiry_str = expiry_date.strftime('%Y-%m-%d %H:%M:%S') if expiry_date else "N/A"
            return f"""<b>🟢 PREMIUM STATUS: ACTIVE</b>
            
✅ Your group has PREMIUM subscription!
✅ No ads will be shown
✅ All features are unlocked

<b>Expiry Date:</b> {expiry_str}

Thank you for choosing Movie Bot Pro!
"""

premium_ui = PremiumManager()
