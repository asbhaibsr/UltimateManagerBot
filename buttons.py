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
    def features_menu(chat_id: int = None, is_admin: bool = False) -> InlineKeyboardMarkup:
        buttons = []
        
        if chat_id and is_admin:
            buttons.extend([
                [
                    InlineKeyboardButton("📢 Force Subscribe", callback_data="feature_fsub"),
                    InlineKeyboardButton("✅ ON/OFF", callback_data="toggle_fsub")
                ],
                [
                    InlineKeyboardButton("👥 Force Join", callback_data="feature_force_join"),
                    InlineKeyboardButton("✅ ON/OFF", callback_data="toggle_force_join")
                ]
            ])
        
        buttons.extend([
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
                InlineKeyboardButton(f"✅ {corrected[:20]}", 
                 callback_data=f"use_corrected_{corrected}"),
                InlineKeyboardButton(f"❌ Keep Original", 
                 callback_data="keep_original")
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
    
    @staticmethod
    def fsub_setup_buttons():
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📢 Add to Channel", 
                 url=f"https://t.me/{Config.BOT_USERNAME}?startchannel=true&admin=post_messages+edit_messages"),
                InlineKeyboardButton("✅ Done", callback_data="fsub_done")
            ],
            [
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_fsub")
            ]
        ])
    
    @staticmethod
    def fsub_channel_button(channel_username: str):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{channel_username}")],
            [InlineKeyboardButton("✅ I Have Joined", callback_data="check_fsub")]
        ])
    
    @staticmethod
    def force_join_buttons(chat_id: int, required_count: int, current_count: int, invite_link: str):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Get Invite Link", url=invite_link)],
            [InlineKeyboardButton(f"✅ Check Invites ({current_count}/{required_count})", 
             callback_data="check_invites")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_force_join")]
        ])
    
    @staticmethod
    def movie_search_buttons(search_id: str, results: list, current_page: int = 0):
        """Create buttons for movie search results"""
        buttons = []
        results_per_page = 5
        start_idx = current_page * results_per_page
        end_idx = start_idx + results_per_page
        
        for i in range(start_idx, min(end_idx, len(results))):
            movie = results[i]
            title = movie.get('title', f"Movie {i+1}")
            
            # Truncate long titles
            if len(title) > 30:
                title = title[:27] + "..."
            
            buttons.append([
                InlineKeyboardButton(f"🎬 {title} ({movie.get('year', 'N/A')})",
                 callback_data=f"select_movie_{search_id}_{i}")
            ])
        
        # Navigation buttons
        nav_buttons = []
        if current_page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Previous", 
                         callback_data=f"movie_page_{search_id}_{current_page-1}"))
        
        if end_idx < len(results):
            nav_buttons.append(InlineKeyboardButton("Next ➡️", 
                         callback_data=f"movie_page_{search_id}_{current_page+1}"))
        
        if nav_buttons:
            buttons.append(nav_buttons)
        
        # Add close button
        buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_search")])
        
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def movie_details_buttons(movie_id: str, title: str):
        """Create buttons for movie details"""
        buttons = [
            [
                InlineKeyboardButton("🎬 Get Movie", url=f"https://t.me/asfilter_bot?start=movie_{movie_id}"),
                InlineKeyboardButton("📢 Share", switch_inline_query=f"{title}")
            ],
            [
                InlineKeyboardButton("⭐ Rate on IMDb", url=f"https://www.imdb.com/title/tt{movie_id}/"),
                InlineKeyboardButton("🔍 Search Again", callback_data="search_again")
            ],
            [InlineKeyboardButton("❌ Close", callback_data="close_details")]
        ]
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def close_button():
        return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Close", callback_data="close")]])

buttons = ButtonManager()
