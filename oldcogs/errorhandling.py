import discord
from discord.ext import commands
import math
import traceback
import sys
import genshin
import uuid
import datetime
import os

class ErrorHandling(commands.Cog):
    def __init__(self,client):
        self.hidden = True
        self.client = client
    
    async def send_error_embed(self,interaction,message):
        embed = discord.Embed(description = message,color = discord.Color.red())
        try:
            await interaction.response.send_message(embed= embed,ephemeral = True)
        except:
            pass

    def cog_load(self):
        tree = self.client.tree
        tree.on_error = self.on_error
    
    @commands.Cog.listener()
    async def on_ready(self):
        print("Error Handler Ready.")

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if hasattr(ctx.command, 'on_error'):
            return

        # get the original exception
        error = getattr(error, 'original', error)

        if isinstance(error, commands.CommandNotFound):
            return
        
        errorid = uuid.uuid4()
        embed = discord.Embed(title = "Uh oh! Seems like you got an uncaught excpetion.",description = "I have no idea how you got here, but it seems your error was not traced! If this occurs frequently, please feel free to join the [support server](https://discord.com/invite/9pmGDc8pqQ) and report the bug!",color = discord.Color.red())
        if ctx.command.cog_name and ctx.command.cog_name.lower() == "hoyoverse":
            embed.add_field(name = "Error Details:",value = "```I am not able to display error details, as this may reveal sensitive information! The bot developer has been notified to this issue.```")
        else:
            if len(''.join(traceback.format_exception_only(type(error), error))) < 4000:
                embed.add_field(name = "Error Details:",value = f"```{''.join(traceback.format_exception_only(type(error), error))}```")
            else:
                embed.add_field(name = "Error Details:",value = f"```Error details are too long to display! Join the support server with your error code for more details.```")
        embed.add_field(name = "Error ID",value = errorid,inline = False)
        try:
            await ctx.reply(embed = embed)
        except:
            try:
                await ctx.send(embed = embed)
            except:
                pass

        channel = self.client.get_channel(1108503902766248056)
        
        embed = discord.Embed(title = f'⚠ There was an error that was not traced!',description = f'On Command: {ctx.command.name}',color = discord.Color.red())
        embed.add_field(name = "Command Invoke Details",value = f'**Guild Info:** {ctx.guild.name} ({ctx.guild.id})\n**User Information:** {ctx.author.name} | {ctx.author.mention} ({ctx.author.id})\n**Jump URL:** {ctx.message.jump_url}\n**Command Used:** {ctx.message.content}\n**Error ID:** {errorid}',inline = False)
        errordetails = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        if len(errordetails) < 1000:
            embed.add_field(name = "Command Error Log",value = f'```{errordetails}```')
            embed.set_footer(text = f'{ctx.guild.name}',icon_url = ctx.guild.icon)
            embed.timestamp = datetime.datetime.now()
            await channel.send(embed = embed)
        else:
            f =  open(f'errorlogging\{errorid}.txt', 'w')
            f.write(errordetails)
            embed.set_footer(text = f'{ctx.guild.name}',icon_url = ctx.guild.icon)
            embed.timestamp = datetime.datetime.now()
            f.close()
            await channel.send(embed = embed,file = discord.File("errorlogging\\" + str(errorid) + ".txt"))
            os.remove(f"errorlogging\{errorid}.txt")
        
        print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
    
    @commands.Cog.listener()
    async def on_error(self, interaction, error):
        error = getattr(error, 'original', error)
        
        if isinstance(error, discord.app_commands.CommandInvokeError):
            error = error.original

        if isinstance(error, discord.app_commands.MissingPermissions):
            missing = [perm.replace('_', ' ').replace('guild', 'server').title() for perm in error.missing_permissions]
            if len(missing) > 2:
                fmt = '{}, and {}'.format("**, **".join(missing[:-1]), missing[-1])
            else:
                fmt = ' and '.join(missing)
            message = 'You need the **{}** permission(s) to use this command.'.format(fmt)
            await self.send_error_embed(interaction,message)
            return
        
        if isinstance(error,discord.app_commands.CheckFailure):
            await self.send_error_embed(interaction,"You cannot use that command here!")
            return

        if isinstance(error, discord.app_commands.CommandOnCooldown):
            await self.send_error_embed(interaction,"This command is on cooldown, please retry in `{}` seconds.".format(math.ceil(error.retry_after)))
            return
        
        if isinstance(error,discord.Forbidden):
            await self.send_error_embed(interaction,"Looks like I am missing permissions to complete your command.")
            return
        
        if isinstance(error, discord.app_commands.BotMissingPermissions):
            missing = [perm.replace('_', ' ').replace('guild', 'server').title() for perm in error.missing_perms]
            if len(missing) > 2:
                fmt = '{}, and {}'.format("**, **".join(missing[:-1]), missing[-1])
            else:
                fmt = ' and '.join(missing)
            _message = 'I need the **{}** permission(s) to run this command.'.format(fmt)
            await self.send_error_embed(interaction,_message)
            return

        errorid = uuid.uuid4()
        embed = discord.Embed(title = "Uh oh! Seems like you got an uncaught excpetion.",description = "I have no idea how you got here, but it seems your error was not traced! If this occurs frequently, please feel free to join the [support server](https://discord.com/invite/9pmGDc8pqQ) and report the bug!",color = discord.Color.red())
        
        if len(''.join(traceback.format_exception_only(type(error), error))) < 4000:
            embed.add_field(name = "Error Details:",value = f"```{''.join(traceback.format_exception_only(type(error), error))}```")
        else:
            embed.add_field(name = "Error Details:",value = f"```Error details are too long to display! Join the support server with your error code for more details.```")
        
        embed.add_field(name = "Error ID",value = errorid,inline = False)
        embed.set_footer(icon_url = self.client.user.avatar.url, text = self.client.user.name)
        
        try:
            await interaction.response.send_message(embed = embed)
        except:
            try:
                await interaction.followup.send(embed = embed)
            except:
                pass

        channel = self.client.get_channel(1108503902766248056)
        
        embed = discord.Embed(title = f'⚠ There was an error that was not traced!',description = f'On Command: {interaction.command.name}',color = discord.Color.red())
        embed.add_field(name = "Command Invoke Details",value = f'**Guild Info:** {interaction.guild.name} ({interaction.guild.id})\n**User Information:** {interaction.user.name} | {interaction.user.mention} ({interaction.user.id})\n**Error ID:** {errorid}',inline = False)
        errordetails = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        if len(errordetails) < 1000:
            embed.add_field(name = "Command Error Log",value = f'```{errordetails}```')
            embed.set_footer(text = f'{interaction.guild.name}',icon_url = interaction.guild.icon)
            embed.timestamp = datetime.datetime.now()
            await channel.send(embed = embed)
        else:
            f =  open(f'errorlogging\{errorid}.txt', 'w')
            f.write(errordetails)
            embed.set_footer(text = f'{interaction.guild.name}',icon_url = interaction.guild.icon)
            embed.timestamp = datetime.datetime.now()
            f.close()
            await channel.send(embed = embed,file = discord.File("errorlogging\\" + str(errorid) + ".txt"))
            os.remove(f"errorlogging\{errorid}.txt")

        print('Ignoring exception in command {}:'.format(interaction.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


async def setup(client):
    await client.add_cog(ErrorHandling(client))
