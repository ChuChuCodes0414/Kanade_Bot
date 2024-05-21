import discord
from discord import app_commands
from discord.ext import commands
import datetime
import asyncio
import uuid

from utils import errors, methods


class Mod(commands.Cog):
    """
    Mod commands.
    """

    def __init__(self, client):
        self.client = client
        self.short = "haha mod commands funny"

    def mod_role_check():
        async def predicate(ctx):
            if ctx.author.guild_permissions.administrator:
                return True

            raw = ctx.cog.client.db.guild_data.find_one(
                {"_id": ctx.guild.id}, {"settings.mod.mrole": 1}
            )
            roles = methods.query(data=raw, search=["settings", "mod", "mrole"])
            for role in roles:
                roleob = ctx.guild.get_role(role)
                if roleob not in ctx.author.roles:
                    return True
            raise errors.SetupCheckFailure(
                message="You are not permitted to use this command: missing specified mod role"
            )

        return commands.check(predicate)

    async def push_reprimand(
        self,
        ctx: commands.Context,
        user: discord.Member,
        moderator: discord.Member,
        action: str,
        reason: str = None,
        amount: int = None,
        category: str = None,
        timestamp: datetime.datetime = None,
        id: str = None,
    ):
        reprimand = {
            "moderator": moderator.id,
            "action": action,
            "amount": amount or 1,
            "reason": reason or "No reason given",
            "category": category,
            "timestamp": timestamp or datetime.datetime.now(),
            "id": id or str(uuid.uuid4()),
        }
        result = self.client.db.guild_data.update_one(
            {"_id": ctx.guild.id},
            {"$push": {f"mod.reprimands.{user.id}": reprimand}},
            upsert=True,
        )
        return result, reprimand["id"]

    @commands.Cog.listener()
    async def on_ready(self):
        print("Mod Category Loaded.")

    @commands.hybrid_command(aliases=["w"], help="Warn a member")
    @commands.has_permissions(ban_members=True)
    @app_commands.describe(
        member="The member or user that should be warned.",
        category="The category this warn should go in.",
        reason="Why you are warning this member.",
        amount="The amount of warns that should be applied.",
    )
    async def warn(
        self,
        ctx,
        member: discord.Member,
        *,
        category: str = None,
        amount: int = None,
        reason: str = None,
    ):
        async with ctx.typing():
            result, id = await self.push_reprimand(
                ctx,
                member,
                ctx.author,
                "warn",
                reason=reason,
                amount=amount,
                category=category,
            )
            embed = discord.Embed(
                color=discord.Color.yellow(),
                title=f"Added Warning: {id}",
                description=f"Added warn to {member.mention} {amount} time(s).",
                timestamp=discord.utils.utcnow(),
            )
            embed.set_author(
                name=f"{member} ({member.id})", icon_url=member.display_avatar.url
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="lmao placeholder go brrr", value="lol", inline=True)
            embed.set_footer(
                text=f"Requested by {ctx.author} ({ctx.author.id})",
                icon_url=ctx.author.display_avatar.url,
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await ctx.reply(embed=embed)


async def setup(client):
    await client.add_cog(Mod(client))
