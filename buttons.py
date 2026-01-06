# buttons.py

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import Config
from premium_menu import premium_ui

class ButtonManager:
    @staticmethod
    def start_menu(user_id: int) -> InlineKeyboardMarkup:
        buttons = [
            [
                InlineKeyboardButton("➕ Add to Group", 
                 url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true"),
                InlineKeyboardButton("📢 Channel", 
                 url=f"https://t.me/{Config.MAIN_CHANNEL}")
            ],
            [
                InlineKeyboardButton("💎 Premium", callback_data="show_premium"),
                InlineKeyboardButton("🎬 Request", callback_data="request_movie")
            ],
            [
                InlineKeyboardButton("⚙️ Features", callback_data="show_features"),
                InlineKeyboardButton("📊 Stats", callback_data="show_stats")
            ],
            [
                InlineKeyboardButton("🆘 Help", callback_data="show_help"),
                InlineKeyboardButton("👨‍💻 Owner", url="https://t.me/asbhai_bsr")
            ]
        ]
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def features_menu(chat_id: int = None) -> InlineKeyboardMarkup:
        buttons = [
            [
                InlineKeyboardButton("🔤 Spelling Check", callback_data="feature_spell_check"),
                InlineKeyboardButton("✅ ON/OFF", callback_data="toggle_spell_check")
            ],
            [
                InlineKeyboardButton("📺 Season Check", callback_data="feature_season_check"),
                InlineKeyboardButton("✅ ON/OFF", callback_data="toggle_season_check")
            ],
            [
                InlineKeyboardButton("🗑️ Auto Delete", callback_data="feature_auto_delete"),
                InlineKeyboardButton("✅ ON/OFF", callback_data="toggle_auto_delete")
            ],
            [
                InlineKeyboardButton("📁 File Cleaner", callback_data="feature_file_cleaner"),
                InlineKeyboardButton("✅ ON/OFF", callback_data="toggle_file_cleaner")
            ],
            [
                InlineKeyboardButton("🎬 Request System", callback_data="feature_request_system"),
                InlineKeyboardButton("✅ ON/OFF", callback_data="toggle_request_system")
            ],
            [
                InlineKeyboardButton("💎 Premium Status", callback_data="check_premium_status"),
                InlineKeyboardButton("⏰ Set Time", callback_data="set_time_menu")
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="back_to_start")
            ]
        ]
        
        if chat_id:
            buttons.insert(0, [
                InlineKeyboardButton("👥 Force Subscribe", callback_data="feature_fsub"),
                InlineKeyboardButton("✅ ON/OFF", callback_data="toggle_fsub")
            ])
            buttons.insert(1, [
                InlineKeyboardButton("👥 Force Join", callback_data="feature_force_join"),
                InlineKeyboardButton("✅ ON/OFF", callback_data="toggle_force_join")
            ])
        
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def time_selection_menu(feature_type: str) -> InlineKeyboardMarkup:
        buttons = []
        time_options = list(Config.TIME_OPTIONS.items())
        
        for i in range(0, len(time_options), 2):
            row = []
            for j in range(2):
                if i + j < len(time_options):
                    time_text, time_sec = time_options[i + j]
                    callback_data = f"set_time_{feature_type}_{time_sec}"
                    row.append(InlineKeyboardButton(time_text, callback_data=callback_data))
            buttons.append(row)
        
        buttons.append([
            InlineKeyboardButton("🔙 Back", callback_data="show_features")
        ])
        
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def spell_check_buttons(original: str, corrected: str) -> InlineKeyboardMarkup:
        buttons = [
            [
                InlineKeyboardButton(f"✅ {corrected}", 
                 callback_data=f"use_corrected_{corrected}"),
                InlineKeyboardButton(f"❌ Keep {original}", 
                 callback_data="keep_original")
            ],
            [
                InlineKeyboardButton("🇮🇳 Hindi", callback_data=f"lang_hi_{corrected}"),
                InlineKeyboardButton("🇬🇧 English", callback_data=f"lang_en_{corrected}")
            ]
        ]
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def premium_status_buttons(is_premium: bool):
        if is_premium:
            return InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Extend Premium", callback_data="extend_premium")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_start")]
            ])
        else:
            return premium_ui.premium_buttons()
    
    @staticmethod
    def admin_buttons():
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📊 Stats", callback_data="admin_stats"),
                InlineKeyboardButton("👥 Groups", callback_data="admin_groups")
            ],
            [
                InlineKeyboardButton("💎 Premium", callback_data="admin_premium"),
                InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="back_to_start")
            ]
        ])

buttons = ButtonManager()
