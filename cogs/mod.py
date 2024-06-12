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
        self.categories = {}

    async def cache(self, data):
        for guild in data:
            self.categories[guild["_id"]] = (
                guild.get("settings", {}).get("mod", {}).get("categories", [])
            )

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

    async def mod_to_member_check(self,ctx:commands.Context,member:discord.Member):
        bot_top = ctx.guild.get_member(self.client.user.id)
        bot_top_ob = bot_top.top_role
        if member.top_role >= bot_top_ob:
            raise errors.PreRequisiteError(message = f"That user's top role position `({member.top_role.position})` is higher or equal to my top role `({bot_top_ob.position})`.")
        elif ctx.author.top_role <= member.top_role:
            raise errors.PreRequisiteError(message = f"That user's top role position `({member.top_role.position})` is higher or equal to your top role `({ctx.author.top_role.position})`.")
        return True

    async def category_check(self,ctx:commands.Context,category:str):
        if category and category not in self.categories[ctx.guild.id]:
                raise errors.ParsingError(
                    message=f"The category `{category}` is not setup!"
                )
        return True

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
        return datetime.timedelta(hours=duration) if duration else None

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
        if length:
            expiration = datetime.datetime.now() + length
        else:
            expiration = None

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
        if expiration:
            self.client.db.global_data.update_one(
                {"_id": "mod"},
                {
                    "$set": {
                        f"expirations.{reprimand['id']}": {
                            "time": expiration,
                            "guild": ctx.guild.id,
                            "user": user.id,
                        }
                    }
                },
                upsert=True,
            )
        return reprimand

    async def send_reprimand_dm(
        self,
        user: discord.User,
        guild: discord.Guild,
        reprimand: dict,
        additional: list = None,
    ):
        try:
            dm = user.dm_channel
            if dm == None:
                dm = await user.create_dm()
            unix = (
                int(reprimand["expiration"].timestamp())
                if reprimand["expiration"]
                else None
            )
            embed = discord.Embed(
                color=discord.Color.yellow(),
                title=f"Added {reprimand['action'].capitalize()}: {reprimand['id']}",
                description=(
                    f"Added {reprimand['action']} to {user.mention} {reprimand['amount']} time(s) in effect until <t:{unix}:f> (<t:{unix}:R>)."
                    if reprimand["expiration"]
                    else f"Added {reprimand['action']} to {user.mention} {reprimand['amount']} time(s)"
                ),
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
            active, total = await self.pull_active_total(
                user, guild, reprimand["action"], reprimand["category"]
            )
            embed.add_field(name="Active", value=str(active), inline=True)
            embed.add_field(name="Total", value=str(total), inline=True)
            embed.add_field(
                name="Category", value=reprimand["category"] or "None", inline=True
            )
            if additional and len(additional) > 0:
                embed.add_field(name="Triggers", value="\n".join(additional))
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
                title=f"Pardoned {reprimand['action']}: {reprimand['id']}",
                description=f"Pardoned {reprimand['amount']} {reprimand['action']}(s) for {user.mention}",
                timestamp=discord.utils.utcnow(),
            )
            embed.set_author(
                name=f"{user} ({user.id})",
                icon_url=user.display_avatar.url,
            )
            embed.add_field(
                name="Reason",
                value=reprimand["reason"] or "No reason given",
                inline=False,
            )
            embed.add_field(
                name="Pardoned Reason",
                value=reason or "No reason given",
                inline=False,
            )
            active, total = await self.pull_active_total(
                user, guild, reprimand["action"], category=reprimand["category"]
            )
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

    async def pull_reprimand(self, user: discord.User, guild: discord.Guild, id: str):
        raw = self.client.db.guild_data.aggregate(
            [
                {"$match": {"_id": guild.id}},
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

    async def update_reprimand(
        self, user: discord.User, guild: discord.Guild, id: str, updates: list
    ):
        update_set = {f"mod.reprimands.{user.id}.$.{a}": b for a, b in updates}
        self.client.db.guild_data.update_one(
            {
                "_id": guild.id,
                f"mod.reprimands.{user.id}.id": id,
            },
            {"$set": update_set},
        )

    async def delete_reprimand(self, user: discord.User, guild: discord.Guild, id: str):
        self.client.db.global_data.update_one(
            {"_id": "mod"},
            {"$unset": {f"expirations.{id}": ""}},
        )
        self.client.db.guild_data.update_one(
            {
                "_id": guild.id,
                f"mod.reprimands.{user.id}.id": id,
            },
            {"$pull": {f"mod.reprimands.{user.id}": {"id": id}}},
        )

    async def pardon_reprimand(
        self,
        user: discord.User,
        guild: discord.Guild,
        reprimand: dict,
        preason: str,
        revoke: bool = True,
    ):
        self.client.db.global_data.update_one(
            {"_id": "mod"},
            {"$unset": {f"expirations.{reprimand['id']}": ""}},
        )
        await self.update_reprimand(
            user,
            guild,
            reprimand["id"],
            [
                ("expired", True),
                (
                    "ereason",
                    preason,
                ),
            ],
        )
        if revoke and reprimand["action"] == "mute":
            raw = self.db.guild_data.find_one(
                {"_id": guild.id}, {"settings.mod.roles.mute": 1}
            )
            role = guild.get_role(
                methods.query(data=raw, search=["settings", "mod", "roles", "mute"])
            )
            member = guild.get_member(user.id)
            if member:
                await member.remove_roles(
                    (role),
                    reason=preason,
                )
        elif revoke and reprimand["action"] == "ban":
            try:
                await guild.unban(
                    user,
                    reason=preason,
                )
            except:
                pass
        await self.send_pardon_dm(
            user,
            guild,
            reprimand,
            preason,
        )

    async def pull_active_total(
        self,
        user: discord.User,
        guild: discord.guild,
        action: str,
        category: str = None,
    ):
        raw = await self.pull_reprimands(
            user,
            guild,
            [
                {"key": "action", "value": action},
                {"key": "category", "value": category},
            ],
        )
        if len(raw) > 0:
            total = methods.query(
                data=raw[0], search=["mod", "reprimands", str(user.id)]
            )
        else:
            total = []
        acount, tcount = 0, 0
        for reprimand in total:
            if not reprimand["expired"]:
                acount += reprimand["amount"]
            tcount += reprimand["amount"]
        return acount, tcount

    async def trigger_reprimand(
        self, ctx: commands.Context, user: discord.User, reprimand: dict
    ):
        additional = []
        raw = self.client.db.guild_data.find_one(
            {"_id": ctx.guild.id},
            {
                f"settings.mod.triggers.{reprimand['category'] or 'default'}.{reprimand['action']}": 1
            },
        )
        triggers = (
            methods.query(
                data=raw,
                search=[
                    "settings",
                    "mod",
                    "triggers",
                    reprimand["category"] or "default",
                    reprimand["action"],
                ],
            )
            or []
        )
        active, total = await self.pull_active_total(
            user, ctx.guild, reprimand["action"], category=reprimand["category"]
        )
        for trigger in triggers:
            if trigger["count"] == "active":
                at = active
            else:
                at = total
            if (
                (trigger["type"] == "exact" and at == trigger["threshold"])
                or (trigger["type"] == "retroactive" and at >= trigger["threshold"])
                or (trigger["type"] == "multiple" and at % trigger["threshold"] == 0)
            ):
                if trigger["action"] == "mute":
                    raw = self.db.guild_data.find_one(
                        {"_id": ctx.guild.id}, {"settings.mod.roles.mute": 1}
                    )
                    role = ctx.guild.get_role(
                        methods.query(
                            data=raw, search=["settings", "mod", "roles", "mute"]
                        )
                    )
                    member = ctx.guild.get_member(user.id)
                    if member:
                        await member.add_roles(
                            (role),
                            reason=f"Automatic trigger applied at {at} {reprimand['action']}(s) in {reprimand['category'] or 'default'}.",
                        )
                elif trigger["action"] == "ban":
                    await member.ban(
                        reason=f"Automatic trigger applied at {at} {reprimand['action']}(s) in {reprimand['category'] or 'default'}.",
                        delete_message_days=0,
                    )
                reprimand = await self.push_reprimand(
                    ctx,
                    user,
                    self.client.user,
                    trigger["action"],
                    reason=f"Automatic trigger applied at {at} {reprimand['action']}(s) in {reprimand['category'] or 'default'}",
                    amount=trigger["amount"],
                    category=trigger["category"],
                    timestamp=datetime.datetime.now(),
                    length=(
                        datetime.timedelta(hours=trigger["length"])
                        if trigger["length"]
                        else None
                    ),
                )
                unix = (
                    int(reprimand["expiration"].timestamp())
                    if reprimand["expiration"]
                    else None
                )
                additional.append(
                    f"Automatic trigger applied at threshold {at} {reprimand['action']}(s) in {reprimand['category'] or 'default'} applied an additional {trigger['amount']} {trigger['action']}(s) in {trigger['category'] or 'default'} in effect until <t:{unix}:f> (<t:{unix}:R>)."
                    if reprimand["expiration"]
                    else f"Automatic trigger applied at threshold {at} {reprimand['action']}(s) in {reprimand['category'] or 'default'} applied an additional {trigger['amount']} {trigger['action']}(s) in {trigger['category'] or 'default'}"
                )
        return additional

    async def pull_mod_embed(
        self,
        ctx: commands.Context,
        user: discord.User,
        reprimand: dict,
        additional: list,
    ):
        unix = (
            int(reprimand["expiration"].timestamp())
            if reprimand["expiration"]
            else None
        )
        embed = discord.Embed(
            color=discord.Color.yellow(),
            title=f"Added {reprimand['action'].capitalize()}: {reprimand['id']}",
            description=(
                f"Added {reprimand['action']} to {user.mention} {reprimand['amount']} time(s) in effect until <t:{unix}:f> (<t:{unix}:R>)."
                if reprimand["expiration"]
                else f"Added {reprimand['action']} to {user.mention} {reprimand['amount']} time(s)"
            ),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_author(name=f"{user} ({user.id})", icon_url=user.display_avatar.url)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(
            name="Reason", value=reprimand["reason"] or "No reason given.", inline=False
        )
        active, total = await self.pull_active_total(
            user, ctx.guild, reprimand["action"], category=reprimand["category"]
        )
        embed.add_field(name="Active", value=str(active), inline=True)
        embed.add_field(name="Total", value=str(total), inline=True)
        embed.add_field(
            name="Category", value=reprimand["category"] or "None", inline=True
        )
        if len(additional) > 0:
            embed.add_field(name="Triggers", value="\n".join(additional))
        embed.set_footer(
            text=f"Requested by {ctx.author} ({ctx.author.id})",
            icon_url=ctx.author.display_avatar.url,
        )
        return embed

    @tasks.loop(seconds=30)
    async def poll_expirations(self):
        raw = self.client.db.global_data.find_one({"_id": "mod"}, {f"expirations": 1})
        expirations = methods.query(data=raw, search=["expirations"])
        if expirations:
            for id, data in expirations.items():
                if data["time"] <= datetime.datetime.now():
                    user = await self.client.fetch_user(data["user"])
                    guild = self.client.get_guild(data["guild"])
                    reprimand = await self.pull_reprimand(user, guild, id)
                    await self.pardon_reprimand(
                        user,
                        guild,
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
        amount: commands.Range[int, 0] = None,
        reason: str = None,
    ):
        async with ctx.typing():
            await self.mod_to_member_check(ctx,member)
            await self.category_check(ctx,category)
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
            additional = await self.trigger_reprimand(ctx, member, reprimand)
            embed = await self.pull_mod_embed(ctx, member, reprimand, additional)
            view = ReprimandUpdatePersistentView(ctx, member, reprimand, embed)
            await ctx.reply(embed=embed, view=view)
            await self.send_reprimand_dm(
                member, ctx.guild, reprimand, additional=additional
            )

    @commands.hybrid_command(aliases=["n"], help="Notice a member")
    @mod_role_check()
    @app_commands.describe(
        member="The member or user that should be noticed.",
        category="The category this notice should go in.",
        reason="Why you are noticing this member.",
        amount="The amount of notices that should be applied.",
    )
    async def notice(
        self,
        ctx,
        member: discord.Member,
        *,
        category: str = None,
        amount: commands.Range[int, 0] = None,
        reason: str = None,
    ):
        async with ctx.typing():
            await self.mod_to_member_check(ctx,member)
            await self.category_check(ctx,category)
            amount = amount or 1
            reprimand = await self.push_reprimand(
                ctx,
                member,
                ctx.author,
                "notice",
                reason=reason,
                amount=amount,
                category=category,
            )
            additional = await self.trigger_reprimand(ctx, member, reprimand)
            embed = await self.pull_mod_embed(ctx, member, reprimand, additional)
            view = ReprimandUpdatePersistentView(ctx, member, reprimand, embed)
            await ctx.reply(embed=embed, view=view)
            await self.send_reprimand_dm(
                member, ctx.guild, reprimand, additional=additional
            )
    
    @commands.hybrid_command(aliases=["k"], help="Kick a member")
    @commands.has_permissions(kick_members = True) 
    @app_commands.describe(
        member="The member or user that should be kicked.",
        category="The category this kick should go in.",
        reason="Why you are kicking this member.",
    )
    async def kick(
        self,
        ctx,
        member: discord.Member,
        *,
        category: str = None,
        reason: str = None,
    ):
        async with ctx.typing():
            await self.mod_to_member_check(ctx,member)
            await self.category_check(ctx,category)
            await member.kick(reason=reason)
            reprimand = await self.push_reprimand(
                ctx,
                member,
                ctx.author,
                "kick",
                reason=reason,
                amount=1,
                category=category,
            )
            additional = await self.trigger_reprimand(ctx, member, reprimand)
            embed = await self.pull_mod_embed(ctx, member, reprimand, additional)
            view = ReprimandUpdatePersistentView(ctx, member, reprimand, embed)
            await ctx.reply(embed=embed, view=view)
            await self.send_reprimand_dm(
                member, ctx.guild, reprimand, additional=additional
            )
    
    @commands.hybrid_command(aliases=["b"], help="Ban a member")
    @commands.has_permissions(ban_members = True) 
    @app_commands.describe(
        member="The member or user that should be noticed.",
        category="The category this notice should go in.",
        reason="Why you are banning this member or user.",
        length="How long this member or user should be banned.",
        delete_days="How many days of messages from this user should be deleted."
    )
    async def ban(
        self,
        ctx,
        user: discord.User,
        *,
        category: str = None,
        reason: str = None,
        length: str = None,
        delete_days: commands.Range[int, 0, 7] = None
    ):
        async with ctx.typing():
            member = ctx.guild.get_member(user.id)
            if member:
                await self.mod_to_member_check(ctx,member)
            await self.category_check(ctx,category)
            await ctx.guild.ban(user,reason = reason,delete_message_days=delete_days or 0)
            reprimand = await self.push_reprimand(
                ctx,
                user,
                ctx.author,
                "ban",
                reason=reason,
                amount=1,
                category=category,
                length = length
            )
            additional = await self.trigger_reprimand(ctx, user, reprimand)
            embed = await self.pull_mod_embed(ctx, user, reprimand, additional)
            view = ReprimandUpdatePersistentView(ctx, user, reprimand, embed)
            await ctx.reply(embed=embed, view=view)
            await self.send_reprimand_dm(
                user, ctx.guild, reprimand, additional=additional
            )

    @warn.autocomplete("category")
    @notice.autocomplete("category")
    @kick.autocomplete("category")
    async def category_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        categories = self.categories.get(interaction.guild.id, [])
        return [
            app_commands.Choice(name=category, value=category)
            for category in categories
            if current.lower() in category.lower()
        ][:10]


class ReprimandUpdatePersistentView(discord.ui.View):
    def __init__(
        self,
        ctx: commands.Context,
        user: discord.User,
        reprimand: dict,
        embed: discord.Embed,
    ):
        super().__init__(timeout=None)
        self.user = user
        self.reprimand = reprimand
        self.embed = embed
        self.ctx = ctx

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user == self.ctx.author:
            return True
        await interaction.response.send_message(
            embed=discord.Embed(
                description="This menu is not for you!", color=discord.Color.red()
            ),
            ephemeral=True,
        )
        return False

    @discord.ui.button(
        label="Update", custom_id="reprimand_update_persistent_view:update"
    )
    async def update(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            ReprimandReasonUpdateModal(self.user, self.reprimand, self.embed)
        )

    @discord.ui.button(
        label="Pardon", custom_id="reprimand_update_persistent_view:pardon"
    )
    async def pardon(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            ReprimandPardonModal(self.user, self.reprimand, self.embed)
        )

    @discord.ui.button(
        label="Delete",
        style=discord.ButtonStyle.red,
        custom_id="reprimand_update_persistent_view:delete",
    )
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.client.get_cog("mod").delete_reprimand(
            self.user, interaction.guild, self.reprimand["id"]
        )
        self.embed.color = discord.Color.red()
        offset = 1 if self.embed.title.startswith("Pardoned") else 0
        self.embed.title = (
            f"Deleted {self.reprimand['action'].capitalize()}: {self.reprimand['id']}"
        )
        self.embed.set_field_at(
            index=1 + offset,
            name="Active",
            value=int(self.embed.fields[1 + offset].value) - 1,
            inline=True,
        )
        self.embed.set_field_at(
            index=2 + offset,
            name="Total",
            value=int(self.embed.fields[2 + offset].value) - 1,
            inline=True,
        )
        self.embed.description = self.embed.description.replace(
            self.embed.description[: self.embed.description.index(" ")], "Deleted", 1
        )
        await interaction.response.edit_message(embed=self.embed, view=None)


class ReprimandReasonUpdateModal(discord.ui.Modal):
    def __init__(self, user: discord.User, reprimand: dict, embed: discord.Embed):
        super().__init__(title=f"Update {reprimand['id']}")
        self.reprimand = reprimand
        self.embed = embed
        self.user = user

    reason = discord.ui.TextInput(
        label="New Reason",
        placeholder="New reason for this reprimand.",
        style=discord.TextStyle.paragraph,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.client.get_cog("mod").update_reprimand(
            self.user,
            interaction.guild,
            self.reprimand["id"],
            [("reason", self.reason.value)],
        )
        self.embed.set_field_at(
            index=0, name="Reason", value=self.reason.value, inline=False
        )
        await interaction.response.edit_message(embed=self.embed)


class ReprimandPardonModal(discord.ui.Modal):
    def __init__(self, user: discord.User, reprimand: dict, embed: discord.Embed):
        super().__init__(title=f"Pardon {reprimand['id']}")
        self.reprimand = reprimand
        self.embed = embed
        self.user = user

    reason = discord.ui.TextInput(
        label="Pardon Reason",
        placeholder="Parson reason for this reprimand.",
        style=discord.TextStyle.paragraph,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.client.get_cog("mod").pardon_reprimand(
            self.user, interaction.guild, self.reprimand, self.reason.value
        )
        interaction.client.db.global_data.update_one(
            {"_id": "mod"},
            {"$unset": {f"expirations.{self.reprimand['id']}": ""}},
        )
        self.embed.insert_field_at(
            index=1,
            name="Pardoned Reason",
            value=self.reason.value or "No reason given",
            inline=False,
        )
        self.embed.set_field_at(
            index=2,
            name="Active",
            value=int(self.embed.fields[2].value) - 1,
            inline=True,
        )
        self.embed.color = discord.Color.green()
        self.embed.title = (
            f"Pardoned {self.reprimand['action'].capitalize()}: {self.reprimand['id']}"
        )
        self.embed.description = self.embed.description.replace(
            self.embed.description[: self.embed.description.index(" ")], "Pardoned", 1
        )
        await interaction.response.edit_message(embed=self.embed)


async def setup(client):
    await client.add_cog(Mod(client))
