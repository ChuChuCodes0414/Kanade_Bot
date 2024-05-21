import discord
from discord import app_commands
from discord.ext import commands
from discord.app_commands import locale_str as _T, Choice

from typing import Literal

class Miscellaneous(commands.Cog):
    """
        Miscellaneous Commands
    """
    def __init__(self,client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print("Miscellaneous Category Loaded")

    @app_commands.command(name = "about", description = "Information about the bot, in english only.")
    async def about(self,interaction:discord.Interaction):
        embed = discord.Embed(title = "Ena Bot",description = "A custom bot serving specific servers! If you are a server manager with some simple features you want to be coded, please join the support server and dm the developer!\nCreated and maintained by ChuGames#0001")
        embed.add_field(name = "Servers List",value = "Dank Cafe (`798822518571925575`)")
        embed.add_field(name = "Libraries Used",value = "discord.py (https://github.com/Rapptz/discord.py)",inline = False)
        embed.add_field(name = "Developer Information",value = "This bot is part of the Mafuyu Bot Team, which includes `Mafuyu Bot#0271` and `Oasis Bot#8212`, and is coded by `ChuGames#0001`. Any questions can be directed to the support server at [support server](https://discord.com/invite/9pmGDc8pqQ).")
        embed.set_footer(icon_url = self.client.user.avatar.url, text = self.client.user.name)
        await interaction.response.send_message(embed = embed)
    
    @app_commands.command(name = _T("ping"),description = _T("Check the ping of the bot."))
    async def ping(self,interaction:discord.Interaction):
        apiping = round(self.client.latency*1000)
        embed = discord.Embed(title = "Pong 🏓",description = f"API Ping: `{apiping}ms`",color = discord.Color.random())
        embed.set_footer(text = "Note: This message can be misleading.")
        await interaction.response.send_message(embed = embed)
        message = await interaction.original_response()
        latency = interaction.created_at - message.created_at
        embed = discord.Embed(title = "Pong 🏓",description = f"API Ping: `{apiping}ms`\nMessage Latency: `{latency.microseconds*0.001}ms`",color = discord.Color.random())
        embed.set_footer(text = "Note: This message can be misleading.")
        await interaction.edit_original_response(embed = embed)

async def setup(client):
    await client.add_cog(Miscellaneous(client))