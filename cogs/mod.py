import discord
from discord import app_commands
from discord.ext import commands, tasks
import datetime
import uuid

from utils import errors, methods


class Mod(commands.Cog):
    """
    Mod commands.
    """

    def __init__(self, client):
        self.client = client
        self.short = "haha mod commands funny"
        self.poll_expirations.start()

    def mod_role_check():
        async def predicate(ctx):
            if ctx.author.guild_permissions.administrator:
                return True

            raw = ctx.cog.client.db.guild_data.find_one(
                {"_id": ctx.guild.id}, {"settings.mod.mrole": 1}
            )
            roles = methods.query(data=raw, search=["settings", "mod", "mrole"]) or []
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
        category: str = None,
    ):
        if not category:
            category = "default"

        raw = ctx.cog.client.db.guild_data.find_one(
            {"_id": ctx.guild.id}, {f"settings.mod.expirations.{category}.{action}": 1}
        )
        duration = methods.query(
            data=raw, search=["settings", "mod", "expirations", category, action]
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
            ctx, action, category=category
        )
        expiration = datetime.datetime.now() + length

        reprimand = {
            "moderator": moderator.id,
            "action": action,
            "amount": amount,
            "reason": reason or "No reason given",
            "category": category,
            "timestamp": timestamp or datetime.datetime.now(),
            "id": id or str(uuid.uuid4()),
            "expiration": expiration,
            "expired": False,
        }
        self.client.db.guild_data.update_one(
            {"_id": ctx.guild.id},
            {"$push": {f"mod.reprimands.{user.id}": reprimand}},
            upsert=True,
        )
        self.client.db.global_data.update_one(
            {"_id": "mod"},
            {
                "$set": {
                    f"expirations": {
                        reprimand["id"]: {
                            "time": expiration,
                            "guild": ctx.guild.id,
                            "user": user.id,
                        }
                    }
                }
            },
            upsert=True,
        )
        return reprimand

    async def send_reprimand_dm(self, user: discord.User,guild: discord.Guild, reprimand: dict):
        try:
            dm = user.dm_channel
            if dm == None:
                dm = await user.create_dm()
            embed = discord.Embed(
                color=discord.Color.yellow(),
                title=f"Expired Warning: {reprimand['id']}",
                description=f"Added {reprimand['action']} to {user.mention} {reprimand['amount']} time(s).",
                timestamp=discord.utils.utcnow(),
            )
            embed.set_author(
                name=f"{user} ({user.id})",
                icon_url=user.display_avatar.url,
            )
            embed.add_field(
                name="Reason",
                value=reprimand["reason"] or "No reason given.",
                inline=False,
            )
            active, total = await self.pull_active_total(user, guild, "warn")
            embed.add_field(name="Active", value=str(active), inline=True)
            embed.add_field(name="Total", value=str(total), inline=True)
            embed.add_field(
                name="Category", value=reprimand["category"] or "None", inline=True
            )
            embed.set_thumbnail(url=user.display_avatar.url)
            await dm.send(embed=embed)
        except:
            pass

    async def send_pardon_dm(
        self, user: discord.User, guild: discord.Guild, reprimand: dict, reason: str
    ):
        try:
            dm = user.dm_channel
            if dm == None:
                dm = await user.create_dm()
            embed = discord.Embed(
                color=discord.Color.yellow(),
                title=f"Expired {reprimand['action']}: {reprimand['id']}",
                description=f"Expired {reprimand['amount']} {reprimand['action']}(s) for {user.mention}",
                timestamp=discord.utils.utcnow(),
            )
            embed.set_author(
                name=f"{user} ({user.id})",
                icon_url=user.display_avatar.url,
            )
            embed.add_field(
                name="Reason",
                value=reprimand["reason"] or "No reason given.",
                inline=False,
            )
            embed.add_field(
                name="Pardoned Reason",
                value=reason or "No reason given.",
                inline=False,
            )
            active, total = await self.pull_active_total(user, guild, "warn")
            embed.add_field(name="Active", value=str(active), inline=True)
            embed.add_field(name="Total", value=str(total), inline=True)
            embed.add_field(
                name="Category", value=reprimand["category"] or "None", inline=True
            )
            embed.set_thumbnail(url=user.display_avatar.url)
            await dm.send(embed=embed)
        except:
            pass

    async def pull_reprimands(
        self, user: discord.User, guild: discord.Guild, query: list
    ):
        cond = {
            "$and": [{"$eq": [f"$$filteredUser.{x['key']}", x["value"]]} for x in query]
        }
        raw = self.client.db.guild_data.aggregate(
            [
                {"$match": {"_id": guild.id}},
                {
                    "$project": {
                        f"mod.reprimands.{user.id}": {
                            "$filter": {
                                "input": f"$mod.reprimands.{user.id}",
                                "as": "filteredUser",
                                "cond": cond,
                            }
                        }
                    }
                },
            ]
        )
        return list(raw)

    async def pull_reprimand(self, user: discord.User, id: str):
        raw = self.client.db.guild_data.aggregate(
            [
                {
                    "$project": {
                        f"mod.reprimands.{user.id}": {
                            "$filter": {
                                "input": f"$mod.reprimands.{user.id}",
                                "as": "filteredUser",
                                "cond": {"$eq": [f"$$filteredUser.id", str(id)]},
                            }
                        }
                    }
                },
                {
                    "$project": {
                        str(user.id): {
                            "$arrayElemAt": [
                                f"$mod.reprimands.{user.id}",
                                0,
                            ]
                        }
                    }
                },
            ]
        )
        reprimands = list(raw)
        if len(reprimands) > 0:
            reprimand = methods.query(data=reprimands[0], search=[str(user.id)])
            return reprimand
        else:
            return None

    async def pull_active_total(
        self, user: discord.User, guild: discord.guild, action: str
    ):
        raw = await self.pull_reprimands(
            user,
            guild,
            [
                {"key": "expired", "value": False},
                {"key": "action", "value": "warn"},
            ],
        )
        if len(raw) > 0:
            active = methods.query(
                data=raw[0], search=["mod", "reprimands", str(user.id)]
            )
        else:
            active = []
        raw = await self.pull_reprimands(
            user,
            guild,
            [
                {"key": "action", "value": "warn"},
            ],
        )
        if len(raw) > 0:
            total = methods.query(
                data=raw[0], search=["mod", "reprimands", str(user.id)]
            )
        else:
            total = []
        return len(active), len(total)

    @tasks.loop(seconds=30)
    async def poll_expirations(self):
        raw = self.client.db.global_data.find_one({"_id": "mod"}, {f"expirations": 1})
        expirations = methods.query(data=raw, search=["expirations"])
        if expirations:
            for id, data in expirations.items():
                if data["time"] <= datetime.datetime.now():
                    self.client.db.global_data.update_one(
                        {"_id": "mod"},
                        {"$unset": {f"expirations.{id}": ""}},
                    )
                    self.client.db.guild_data.update_one(
                        {
                            "_id": data["guild"],
                            f"mod.reprimands.{data['user']}.id": id,
                        },
                        {"$set": {f"mod.reprimands.{data['user']}.$.expired": True}},
                    )

                    user = await self.client.fetch_user(data["user"])
                    reprimand = await self.pull_reprimand(user, id)
                    await self.send_pardon_dm(
                        user,
                        self.client.get_guild(data["guild"]),
                        reprimand,
                        f"{reprimand['action'].capitalize()} has expired.",
                    )

    @poll_expirations.before_loop
    async def before_poll_expirations(self):
        await self.client.wait_until_ready()

    async def cog_unload(self):
        self.poll_expirations.cancel()

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
        amount: commands.Range[int,0] = None,
        reason: str = None,
    ):
        async with ctx.typing():
            amount = amount or 1
            reprimand = await self.push_reprimand(
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
                title=f"Added Warning: {reprimand['id']}",
                description=f"Added warn to {member.mention} {amount} time(s).",
                timestamp=discord.utils.utcnow(),
            )
            embed.set_author(
                name=f"{member} ({member.id})", icon_url=member.display_avatar.url
            )
            embed.add_field(
                name="Reason", value=reason or "No reason given.", inline=False
            )
            active, total = await self.pull_active_total(member, ctx.guild, "warn")
            embed.add_field(name="Active", value=str(active), inline=True)
            embed.add_field(name="Total", value=str(total), inline=True)
            embed.add_field(name="Category", value=category or "None", inline=True)
            embed.set_footer(
                text=f"Requested by {ctx.author} ({ctx.author.id})",
                icon_url=ctx.author.display_avatar.url,
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await ctx.reply(embed=embed)
            await self.send_reprimand_dm(member,ctx.guild,reprimand)


async def setup(client):
    await client.add_cog(Mod(client))
