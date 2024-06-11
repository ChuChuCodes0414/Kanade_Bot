import discord
from discord.ext import commands
import aiohttp
import os
from dotenv import load_dotenv
from utils import pymongo_client


class Client(commands.Bot):
    def __init__(self):
        self.prefixes = {}
        self.rules = {}
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        self.dbclient = pymongo_client.get_client()
        self.db = self.dbclient.kanade_bot

        super().__init__(
            command_prefix="k!",
            help_command=None,
            intents=intents,
            activity=discord.Game("@Kanade Bot"),
        )

    async def setup_hook(self):
        self.session = aiohttp.ClientSession()
        self._BotBase__cogs = commands.core._CaseInsensitiveDict()
        await self.load_extension("jishaku")
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py"):
                await self.load_extension(f"cogs.{filename[:-3]}")
    
    async def load_caches(self):
        data = list(self.db.guild_data.find({},{"settings":1}))
        for cog, instance in self.cogs.items():
            if hasattr(instance,"cache"):
                instance.cache(data)
        print("All cogs cached!")

    async def on_ready(self):
        print("Bot is online, and cogs are loaded.")


client = Client()

load_dotenv()
client.run(os.getenv("BOT_TOKEN"))
