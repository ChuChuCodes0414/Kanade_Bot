import discord
from discord import app_commands
from discord.ext import commands
import datetime
import asyncio

from utils import errors, methods


class Template(commands.Cog):
    """
    Mod commands.
    """

    def __init__(self, client):
        self.client = client
        self.short = ""

    @commands.Cog.listener()
    async def on_ready(self):
        print("Template Category Loaded.")


async def setup(client):
    await client.add_cog(Template(client))
