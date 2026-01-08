from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

FONT_STYLES = {
    "bold": "**{}**",
    "italic": "__{}__",
    "mono": "`{}`",
    "strike": "~~{}~~",
    "underline": "--{}--",
    "smallcaps": "`{}`".upper(),
}

FANCY_FONTS = {
    "𝔹𝕠𝕝𝕕": "𝗔𝗮𝗕𝗯𝗖𝗰𝗗𝗱𝗘𝗲𝗙𝗳𝗚𝗴𝗛𝗵𝗜𝗶𝗝𝗷𝗞𝗸𝗟𝗹𝗠𝗺𝗡𝗻𝗢𝗼𝗣𝗽𝗤𝗾𝗥𝗿𝗦𝘀𝗧𝘁𝗨𝘂𝗩𝘃𝗪𝘄𝗫𝘅𝗬𝘆𝗭𝘇",
    "Ⓒⓘⓡⓒⓛⓔⓓ": "ⒶⒷⒸⒹⒺⒻⒼⒽⒾⒿⓀⓁⓂⓃⓄⓅⓆⓇⓈⓉⓊⓋⓌⓍⓎⓏⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ",
    "🅂🅀🅄🄰🅁🄴": "🄰🄱🄲🄳🄴🄵🄶🄷🄸🄹🄺🄻🄼🄽🄾🄿🅀🅁🅂🅃🅄🅅🅆🅇🅈🅉🄰🄱🄲🄳🄴🄵🄶🄷🄸🄹🄺🄻🄼🄽🄾🄿🅀🅁🅂🅃🅄🅅🅆🅇🅈🅉",
    "𝓒𝓾𝓻𝓼𝓲𝓿𝓮": "𝒜𝐵𝒞𝒟𝐸𝐹𝒢𝐻𝐼𝒥𝒦𝐿𝑀𝒩𝒪𝒫𝒬𝑅𝒮𝒯𝒰𝒱𝒲𝒳𝒴𝒵𝒶𝒷𝒸𝒹𝑒𝒻𝑔𝒽𝒾𝒿𝓀𝓁𝓂𝓃𝑜𝓅𝓆𝓇𝓈𝓉𝓊𝓋𝓌𝓍𝓎𝓏",
    "🇹‌🇪‌🇽‌🇹": "🇦🇧🇨🇩🇪🇫🇬🇭🇮🇯🇰🇱🇲🇳🇴🇵🇶🇷🇸🇹🇺🇻🇼🇽🇾🇿🇦🇧🇨🇩🇪🇫🇬🇭🇮🇯🇰🇱🇲🇳🇴🇵🇶🇷🇸🇹🇺🇻🇼🇽🇾🇿",
    "🄱🄾🅇🄴🄳": "🅰🅱🅲🅳🅴🅵🅶🅷🅸🅹🅺🅻🅼🅽🅾🅿🆀🆁🆂🆃🆄🆅🆆🆇🆈🆉🅰🅱🅲🅳🅴🅵🅶🅷🅸🅹🅺🅻🅼🅽🅾🅿🆀🆁🆂🆃🆄🆅🆆🆇🆈🆉",
}

def convert_to_fancy(text, font_style):
    """Convert text to fancy font"""
    if font_style in FONT_STYLES:
        return FONT_STYLES[font_style].format(text)
    
    if font_style in FANCY_FONTS:
        font_chars = FANCY_FONTS[font_style]
        result = ""
        for char in text:
            if 'a' <= char <= 'z':
                idx = ord(char) - ord('a') + 26
                if idx < len(font_chars):
                    result += font_chars[idx]
                else:
                    result += char
            elif 'A' <= char <= 'Z':
                idx = ord(char) - ord('A')
                if idx < len(font_chars):
                    result += font_chars[idx]
                else:
                    result += char
            else:
                result += char
        return result
    
    return text

@Client.on_message(filters.command("font"))
async def font_command(client, message):
    """Convert text to fancy fonts"""
    if len(message.command) < 2:
        await message.reply(
            "Usage: `/font <text>`\n\n"
            "Example: `/font Hello World`\n\n"
            "Available styles:\n"
            "• **Bold** - `**text**`\n"
            "• *Italic* - `__text__`\n"
            "• `Monospace` - backticks\n"
            "• ~~Strike~~ - `~~text~~`\n"
            "• Fancy fonts - Click buttons below"
        )
        return
    
    text = " ".join(message.command[1:])
    
    if len(text) > 100:
        await message.reply("Text too long! Maximum 100 characters.")
        return
    
    buttons = [
        [
            InlineKeyboardButton("𝐁𝐨𝐥𝐝", callback_data=f"font_bold_{text[:50]}"),
            InlineKeyboardButton("𝕀𝕥𝕒𝕝𝕚𝕔", callback_data=f"font_italic_{text[:50]}")
        ],
        [
            InlineKeyboardButton("Ｍｏｎｏ", callback_data=f"font_mono_{text[:50]}"),
            InlineKeyboardButton("S̶t̶r̶i̶k̶e̶", callback_data=f"font_strike_{text[:50]}")
        ],
        [
            InlineKeyboardButton("𝔉𝔞𝔫𝔠𝔶", callback_data=f"font_fancy_{text[:50]}"),
            InlineKeyboardButton("Ⓕⓐⓝⓒⓨ②", callback_data=f"font_circle_{text[:50]}")
        ],
        [
            InlineKeyboardButton("🅂🅀🅄🄰🅁🄴", callback_data=f"font_square_{text[:50]}"),
            InlineKeyboardButton("🇫‌🇦‌🇳‌🇨‌🇾‌³", callback_data=f"font_flag_{text[:50]}")
        ],
        [
            InlineKeyboardButton("𝓒𝓾𝓻𝓼𝓲𝓿𝓮", callback_data=f"font_cur_{text[:50]}"),
            InlineKeyboardButton("🄱🄾🅇🄴🄳", callback_data=f"font_box_{text[:50]}")
        ]
    ]
    
    await message.reply(
        f"**Original:** `{text}`\n\n"
        "Select a font style:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r"^font_"))
async def font_callback(client, callback):
    """Handle font selection"""
    data = callback.data
    font_type = data.split("_")[1]
    text = data.split("_", 2)[2].replace("_", " ")
    
    # Map callback to font style
    font_map = {
        "bold": "bold",
        "italic": "italic",
        "mono": "mono",
        "strike": "strike",
        "fancy": "𝔹𝕠𝕝𝕕",
        "circle": "Ⓒⓘⓡⓒⓛⓔⓓ",
        "square": "🅂🅀🅄🄰🅁🄴",
        "flag": "🇹‌🇪‌🇽‌🇹",
        "cur": "𝓒𝓾𝓻𝓼𝓲𝓿𝓮",
        "box": "🄱🄾🅇🄴🄳",
    }
    
    if font_type not in font_map:
        await callback.answer("Invalid font!", show_alert=True)
        return
    
    converted = convert_to_fancy(text, font_map[font_type])
    
    # Create copy button
    buttons = [[
        InlineKeyboardButton("📋 Copy", callback_data=f"copy_{converted}"),
        InlineKeyboardButton("🔄 Try Another", callback_data=f"font_{text}")
    ]]
    
    await callback.message.edit_text(
        f"**Font Style:** {font_type.title()}\n\n"
        f"**Converted:**\n`{converted}`\n\n"
        f"**Original:**\n`{text}`",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    
    await callback.answer()

@Client.on_callback_query(filters.regex(r"^copy_"))
async def copy_text(client, callback):
    """Copy text to clipboard (simulate)"""
    text = callback.data.split("_", 1)[1]
    
    # Show copied message
    await callback.answer(f"Copied to clipboard!\n\n{text[:50]}...", show_alert=True)
