import discord
from discord import app_commands
from discord.ext import commands, tasks
import datetime
import asyncio
import asyncpg
import uuid

from utils import errors, methods


class Mod(commands.Cog):
    """
    Mod commands.
    """

    def __init__(self, client):
        self.client = client
        self.short = "haha mod commands funny"

        self.poll_expirations.add_exception_type(asyncpg.PostgresConnectionError)
        self.poll_expirations.start()

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

    async def pull_initial_expiration(
        self,
        ctx: commands.Context,
        action: str,
        length: datetime.timedelta,
        category: str = None,
    ):
        if not category:
            category = "default"

        raw = ctx.cog.client.db.guild_data.find_one(
            {"_id": ctx.guild.id}, {f"settings.mod.expirations.{category}": 1}
        )
        duration = methods.query(
            data=raw, search=["settings", "mod", "expirations", category]
        )
        return datetime.timedelta(hours=duration)

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
        length: datetime.timedelta = None,
    ):
        length = length or await self.pull_initial_expiration(
            ctx, action, length, category=category
        )
        expiration = datetime.datetime.now() + length

        reprimand = {
            "moderator": moderator.id,
            "action": action,
            "amount": amount or 1,
            "reason": reason or "No reason given",
            "category": category,
            "timestamp": timestamp or datetime.datetime.now(),
            "id": id or str(uuid.uuid4()),
            "expiration": expiration,
            "expired": False,
        }
        result = self.client.db.guild_data.update_one(
            {"_id": ctx.guild.id},
            {"$push": {f"mod.reprimands.{user.id}": reprimand}},
            upsert=True,
        )
        self.client.db.global_data.update_one(
            {"_id": "mod"},
            {"$set": {f"expirations": {reprimand["id"]: {"time":expiration,"guild":ctx.guild.id,"user":user.id}}}},
            upsert=True,
        )
        self.expirations[reprimand["id"]] = expiration
        return result, reprimand["id"]

    @tasks.loop(minutes=5)
    async def poll_expirations(self):
        async with self.client.pool.acquire() as con:
            raw = self.client.db.global_data.find_one(
                {"_id": "mod"}, {f"expirations": 1}
            )
            expirations = methods.query(data=raw, search=["expirations"])
            for id,data in expirations.items():
                if data["time"] >= datetime.datetime.now():
                    self.client.db.global_data.update_one(
                        {"_id": "mod"},
                        {"$unset": {f"expirations.{id}": ""}},
                    )
                    self.client.db.guild_data.update_one(
                        {"_id": data["guild"],f"mod.reprimands.{data["user"]}.id":data["id"]},
                        {"$set": {f"mod.reprimands.{data["user"]}.$.expired":True}},
                    )

                    # create code to dm the person here

    @poll_expirations.before_loop
    async def before_poll_expirations(self):
        await self.client.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self):
        print("Mod Category Loaded.")

    @commands.hybrid_command(aliases=["w"], help="Warn a member")
    @mod_role_check()
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
