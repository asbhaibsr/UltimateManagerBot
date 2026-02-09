# fun_commands.py - COMPLETE FILE
"""
Fun Commands for Movie Helper Bot
"""

import random
from pyrogram import Client
from pyrogram.types import Message

class FunCommands:
    
    RUN_STRINGS = [
        "Where do you think you're going?",
        "Huh? what? did they get away?",
        "ZZzzZZzz... Huh? what? oh, just them again, nevermind.",
        "Get back here!",
        "Not so fast...",
        "Look out for the wall!",
        "Don't leave me alone with them!!",
        "You run, you die.",
        "Jokes on you, I'm everywhere",
        "You're gonna regret that...",
        "You could also try /kickme, I hear that's fun.",
    ]
    
    SLAP_TEMPLATES = [
        "{hits} {victim} with a {item}.",
        "{hits} {victim} in the face with a {item}.",
        "{hits} {victim} around a bit with a {item}.",
        "{throws} a {item} at {victim}.",
        "grabs a {item} and {throws} it at {victim}'s face.",
    ]
    
    ITEMS = [
        "fish", "trout", "sock", "pillow", "book", "keyboard", 
        "mouse", "chair", "table", "laptop", "phone", "banana",
        "tomato", "egg", "cup", "plate", "spoon", "fork"
    ]
    
    HIT = ["slaps", "hits", "smacks", "whacks", "bashes", "strikes"]
    THROW = ["throws", "flings", "chucks", "hurls", "tosses"]
    
    @staticmethod
    async def slap_command(client: Client, message: Message):
        """Slap command"""
        if message.reply_to_message:
            user1 = message.from_user.first_name
            user2 = message.reply_to_message.from_user.first_name
            item = random.choice(FunCommands.ITEMS)
            hit = random.choice(FunCommands.HIT)
            throw = random.choice(FunCommands.THROW)
            
            # Randomly choose template
            template = random.choice(FunCommands.SLAP_TEMPLATES)
            
            if "{hits}" in template:
                reply = template.format(hits=hit, victim=user2, item=item)
                reply = f"{user1} {reply}"
            else:
                reply = template.format(throws=throw, victim=user2, item=item)
                reply = f"{user1} {reply}"
            
            await message.reply_text(f"{reply} 👋")
        else:
            await message.reply_text("Reply to someone to slap them! 👋")
    
    @staticmethod
    async def runs_command(client: Client, message: Message):
        """Runs command"""
        reply = random.choice(FunCommands.RUN_STRINGS)
        await message.reply_text(reply)
    
    @staticmethod
    async def roll_command(client: Client, message: Message):
        """Roll dice command"""
        roll = random.randint(1, 6)
        await message.reply_text(f"🎲 You rolled: {roll}")
    
    @staticmethod
    async def toss_command(client: Client, message: Message):
        """Toss coin command"""
        toss = random.choice(["Heads", "Tails"])
        await message.reply_text(f"🪙 Coin toss: {toss}")
