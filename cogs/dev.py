import discord
from discord.ext import commands

class Dev(commands.Cog):
    def __init__(self,client):
        self.hidden = True
        self.client = client
    
    @commands.Cog.listener()
    async def on_ready(self):
        print("Dev Category Loaded")

    @commands.command(id = "00",hidden = True)
    @commands.is_owner()
    async def sync(self,ctx,type:str = None,guild:int = None):
        async with ctx.typing():
            type = type or "global"
            guild = guild or ctx.guild.id

            if type == "global":
                response = await self.client.tree.sync()
            elif type == "guild":
                guild = self.client.get_guild(guild)
                response = await self.client.tree.sync(guild = guild)
            
            await ctx.reply(embed = discord.Embed(description = f"Synced `{len(response)}` Commands to `{type}`!",color = discord.Color.green()))
    
    @commands.command(id = "01",hidden=True)
    @commands.is_owner()
    async def reload(self,ctx,extension):
        await self.client.reload_extension(f'cogs.{extension}')
        cog = self.client.get_cog(extension)
        if hasattr(cog,"cache"):
            data = list(self.client.db.guild_data.find({},{"settings":1}))
            cog.cache(data)
        await ctx.reply(embed = discord.Embed(description = f'Reloaded {extension} sucessfully',color = discord.Color.green()))
    @reload.error
    async def reload_error(self,ctx, error):
        await ctx.reply(embed = discord.Embed(description = f'`{error}`',color = discord.Color.red()))
    
    @commands.command(id = "02",hidden=True)
    @commands.is_owner()
    async def load(self,ctx,extension):
        await self.client.load_extension(f'cogs.{extension}')
        cog = self.client.get_cog(extension)
        if hasattr(cog,"cache"):
            data = list(self.client.db.guild_data.find({},{"settings":1}))
            cog.cache(data)
        await ctx.reply(embed = discord.Embed(description = f'Loaded {extension} sucessfully',color = discord.Color.green()))
    @load.error
    async def load_error(self,ctx, error):
        await ctx.reply(embed = discord.Embed(description = f'`{error}`',color = discord.Color.red()))
    
    @commands.command(id = "03",hidden=True)
    @commands.is_owner()
    async def unload(self,ctx,extension):
        await self.client.unload_extension(f'cogs.{extension}')
        await ctx.reply(embed = discord.Embed(description = f'Unloaded {extension} sucessfully',color = discord.Color.green()))
    @unload.error
    async def unload_error(self,ctx, error):
        await ctx.reply(embed = discord.Embed(description = f'`{error}`',color = discord.Color.red()))


async def setup(client):
    await client.add_cog(Dev(client))