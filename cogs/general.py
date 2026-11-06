import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import time
from typing import Literal

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def get_help_embed(category: str, bot: commands.Bot) -> discord.Embed:
    if category == "security":
        embed = discord.Embed(
            title="🛡️ Security & Moderation Commands",
            description="Protect your server with Auto-Mod and moderation tools.",
            color=discord.Color.red()
        )
        embed.add_field(name="`/kick <member> [reason]`", value="Kick a member from the server.", inline=False)
        embed.add_field(name="`/ban <member> [reason] [days]`", value="Ban a member and optionally delete recent messages.", inline=False)
        embed.add_field(name="`/unban <user_id> [reason]`", value="Unban a user using their numeric Discord ID.", inline=False)
        embed.add_field(name="`/timeout <member> <minutes> [reason]`", value="Mute / timeout a member for specified minutes.", inline=False)
        embed.add_field(name="`/untimeout <member>`", value="Remove active timeout from a member.", inline=False)
        embed.add_field(name="`/warn <member> <reason>`", value="Issue a formal strike/warning to a user.", inline=False)
        embed.add_field(name="`/warnings <member>`", value="View strike history and reasons for a member.", inline=False)
        embed.add_field(name="`/clearwarns <member>`", value="Reset all warnings for a member (Admin only).", inline=False)
        embed.add_field(name="`/lock` & `/unlock`", value="Lock or unlock current channel for @everyone.", inline=False)
        embed.add_field(name="`/slowmode <seconds>`", value="Set message delay slowmode in the channel.", inline=False)
        embed.add_field(name="`/set-modlog <channel>`", value="Configure audit logging channel for mod actions.", inline=False)
        embed.add_field(
            name="🤖 24/7 Auto-Mod Protection",
            value="• **Anti-Spam:** Auto-timeouts rapid message spammers\n• **Anti-Invite:** Deletes unauthorized `discord.gg` links\n• **Bad-Words Filter:** Deletes blacklist terms and warns user",
            inline=False
        )

    elif category == "tickets":
        embed = discord.Embed(
            title="🎫 Support Ticket System",
            description="Manage private customer & community support with button panels.",
            color=discord.Color.blue()
        )
        embed.add_field(name="`/ticket-setup [channel] [category] [support_role]`", value="Deploy the interactive **'Create Ticket'** panel into a channel.", inline=False)
        embed.add_field(name="`/ticket-add <member>`", value="Add a member into the current ticket channel.", inline=False)
        embed.add_field(name="`/ticket-remove <member>`", value="Remove a member from the ticket channel.", inline=False)
        embed.add_field(
            name="🔘 Interactive Ticket Buttons",
            value=(
                "• **📩 Create Ticket Button:** Prompts modal for issue description, creates private ticket channel.\n"
                "• **🔒 Close Ticket Button:** Confirms closure, generates full `.txt` chat transcript, DMs user, and archives.\n"
                "• **🙋 Claim Ticket Button:** Staff members can claim ownership of tickets."
            ),
            inline=False
        )

    elif category == "verification":
        embed = discord.Embed(
            title="✅ Verification System",
            description="Gate server channels behind a 1-click verification rule button.",
            color=discord.Color.green()
        )
        embed.add_field(name="`/verify-setup <role> [channel]`", value="Deploy the **'Verify'** button panel with rule instructions into a channel.", inline=False)
        embed.add_field(
            name="🔘 Verification Button",
            value="Members click **'✅ Verify'** to automatically receive the verified role and access channels.",
            inline=False
        )

    elif category == "general":
        embed = discord.Embed(
            title="⚙️ General & Server Utilities",
            description="Manage welcome messages, auto-roles, and server inspection.",
            color=discord.Color.gold()
        )
        embed.add_field(name="`/welcome-setup <channel> [auto_role] [message]`", value="Configure welcome alerts and automatic member roles upon joining.", inline=False)
        embed.add_field(name="`/purge <amount> [member]`", value="Bulk delete 1 to 100 messages in the channel.", inline=False)
        embed.add_field(name="`/serverinfo`", value="Display server statistics, member counts, channels, and boosts.", inline=False)
        embed.add_field(name="`/userinfo [member]`", value="Inspect a member's roles, join date, and account details.", inline=False)
        embed.add_field(name="`/ping`", value="Check bot latency and Discord API responsiveness.", inline=False)
        embed.add_field(name="`/botinfo`", value="Display system uptime, server count, and library versions.", inline=False)

    else:
        # Default / Overview
        embed = discord.Embed(
            title="🤖 Bot Command Center & Help",
            description=(
                f"Welcome to **{bot.user.name}**!\n\n"
                "Select a category from the dropdown menu below to view detailed command lists and instructions.\n\n"
                "**📌 Modules Available:**\n"
                "• 🛡️ **Security & Moderation** – Kick, Ban, Timeout, Warns, Auto-Mod\n"
                "• 🎫 **Tickets** – Button-based support channels & transcripts\n"
                "• ✅ **Verification** – 1-Click role verification gate\n"
                "• ⚙️ **General & Utilities** – Welcome, Auto-role, Purge, Server info"
            ),
            color=discord.Color.blurple()
        )
        if bot.user.avatar:
            embed.set_thumbnail(url=bot.user.avatar.url)
        embed.set_footer(text="Use / to access all slash commands • Select category below")

    return embed


class HelpSelectView(discord.ui.View):
    def __init__(self, bot: commands.Bot, user: discord.User):
        super().__init__(timeout=120)
        self.bot = bot
        self.user = user

    @discord.ui.select(
        placeholder="📂 Select a category to view commands...",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="Home Overview", value="overview", emoji="🏠", description="Return to main help overview"),
            discord.SelectOption(label="Security & Moderation", value="security", emoji="🛡️", description="Auto-Mod, Ban, Kick, Timeout, Warns"),
            discord.SelectOption(label="Ticket System", value="tickets", emoji="🎫", description="Support panels, buttons & transcripts"),
            discord.SelectOption(label="Verification Gate", value="verification", emoji="✅", description="1-Click rule and role gate"),
            discord.SelectOption(label="General & Utilities", value="general", emoji="⚙️", description="Welcome, Auto-role, Purge, Info"),
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ This menu is for the person who ran the command. Run /help to get your own menu.", ephemeral=True)
            return

        choice = select.values[0]
        new_embed = get_help_embed(choice, self.bot)
        await interaction.response.edit_message(embed=new_embed, view=self)


class GeneralCog(commands.Cog, name="General"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = time.time()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        cfg = load_config()
        welcome_cfg = cfg.get("welcome", {})

        # Auto-role assignment
        auto_role_id = welcome_cfg.get("auto_role_id")
        if auto_role_id:
            role = member.guild.get_role(auto_role_id)
            if role:
                try:
                    await member.add_roles(role, reason="Auto-role on server join")
                except Exception as e:
                    print(f"Failed to assign auto-role: {e}")

        # Welcome message
        if welcome_cfg.get("enabled", True):
            channel_id = welcome_cfg.get("channel_id")
            if channel_id:
                channel = member.guild.get_channel(channel_id)
                if channel:
                    raw_msg = welcome_cfg.get("message", "Welcome {user} to {server}! 🎉")
                    msg_text = raw_msg.replace("{user}", member.mention).replace("{server}", member.guild.name)

                    embed = discord.Embed(
                        title="🎉 Member Joined!",
                        description=msg_text,
                        color=discord.Color.green(),
                        timestamp=discord.utils.utcnow()
                    )
                    if member.avatar:
                        embed.set_thumbnail(url=member.avatar.url)
                    embed.add_field(name="Member Count", value=f"#{member.guild.member_count}", inline=True)
                    embed.add_field(name="Account Created", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
                    try:
                        await channel.send(embed=embed)
                    except Exception as e:
                        print(f"Failed to send welcome message: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        cfg = load_config()
        channel_id = cfg.get("welcome", {}).get("channel_id")
        if channel_id:
            channel = member.guild.get_channel(channel_id)
            if channel:
                embed = discord.Embed(
                    title="👋 Member Left",
                    description=f"**{member.name}** has left the server.",
                    color=discord.Color.light_grey(),
                    timestamp=discord.utils.utcnow()
                )
                if member.avatar:
                    embed.set_thumbnail(url=member.avatar.url)
                embed.add_field(name="Remaining Members", value=f"{member.guild.member_count}", inline=True)
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass

    # ================= Help Command =================

    @app_commands.command(name="help", description="Browse all bot commands and features with interactive menu")
    @app_commands.describe(category="Directly jump to a command category")
    async def help_command(
        self,
        interaction: discord.Interaction,
        category: Literal["overview", "security", "tickets", "verification", "general"] = "overview"
    ):
        embed = get_help_embed(category, self.bot)
        view = HelpSelectView(self.bot, interaction.user)
        await interaction.response.send_message(embed=embed, view=view)

    # ================= General Slash Commands =================

    @app_commands.command(name="purge", description="Bulk delete messages in the channel")
    @app_commands.describe(amount="Number of messages to delete (1-100)", member="Only delete messages from this member")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge_command(self, interaction: discord.Interaction, amount: int, member: discord.Member = None):
        if amount < 1 or amount > 100:
            await interaction.response.send_message("❌ Amount must be between 1 and 100.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        def check(m):
            if member:
                return m.author.id == member.id
            return True

        deleted = await interaction.channel.purge(limit=amount, check=check)
        await interaction.followup.send(
            f"🧹 Successfully cleared **{len(deleted)} messages**." + (f" from {member.mention}" if member else ""),
            ephemeral=True
        )

    @app_commands.command(name="welcome-setup", description="Configure server welcome system and auto-role")
    @app_commands.describe(
        channel="Channel where welcome messages are sent",
        auto_role="Role given automatically to new joiners (optional)",
        message="Custom welcome text (use {user} and {server})"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def welcome_setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        auto_role: discord.Role = None,
        message: str = None
    ):
        cfg = load_config()
        if "welcome" not in cfg:
            cfg["welcome"] = {}

        cfg["welcome"]["enabled"] = True
        cfg["welcome"]["channel_id"] = channel.id
        if auto_role:
            cfg["welcome"]["auto_role_id"] = auto_role.id
        if message:
            cfg["welcome"]["message"] = message

        save_config(cfg)

        reply_text = f"✅ Welcome messages will now be posted in {channel.mention}."
        if auto_role:
            reply_text += f"\nAuto-role set to **{auto_role.name}**."
        await interaction.response.send_message(reply_text, ephemeral=True)

    @app_commands.command(name="ping", description="Check bot latency and API responsiveness")
    async def ping_command(self, interaction: discord.Interaction):
        api_latency = round(self.bot.latency * 1000)
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"**WebSocket Latency:** `{api_latency}ms`",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="Display detailed server information")
    async def serverinfo_command(self, interaction: discord.Interaction):
        guild = interaction.guild
        embed = discord.Embed(
            title=f"📊 Server Info: {guild.name}",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow()
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        owner = guild.owner or await self.bot.fetch_user(guild.owner_id)
        embed.add_field(name="👑 Owner", value=f"{owner.mention} (`{owner.id}`)", inline=True)
        embed.add_field(name="🆔 Server ID", value=f"`{guild.id}`", inline=True)
        embed.add_field(name="📅 Created At", value=f"<t:{int(guild.created_at.timestamp())}:D>", inline=True)

        total_members = guild.member_count
        embed.add_field(name="👥 Members", value=f"{total_members} members", inline=True)
        embed.add_field(name="💬 Channels", value=f"{len(guild.text_channels)} Text | {len(guild.voice_channels)} Voice", inline=True)
        embed.add_field(name="🏷️ Roles", value=f"{len(guild.roles)} roles", inline=True)
        embed.add_field(name="🚀 Boost Level", value=f"Level {guild.premium_tier} ({guild.premium_subscription_count} boosts)", inline=True)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="userinfo", description="Display information about a member")
    @app_commands.describe(member="Member to view info for")
    async def userinfo_command(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        embed = discord.Embed(
            title=f"👤 User Info: {target.name}",
            color=discord.Color.purple(),
            timestamp=discord.utils.utcnow()
        )
        if target.avatar:
            embed.set_thumbnail(url=target.avatar.url)

        embed.add_field(name="Mention", value=target.mention, inline=True)
        embed.add_field(name="ID", value=f"`{target.id}`", inline=True)
        embed.add_field(name="Bot?", value="Yes" if target.bot else "No", inline=True)
        embed.add_field(name="Account Created", value=f"<t:{int(target.created_at.timestamp())}:R>", inline=True)
        if isinstance(target, discord.Member) and target.joined_at:
            embed.add_field(name="Joined Server", value=f"<t:{int(target.joined_at.timestamp())}:R>", inline=True)
            roles = [r.mention for r in target.roles if r.name != "@everyone"]
            roles_str = " ".join(roles) if roles else "None"
            embed.add_field(name="Roles", value=roles_str[:1024], inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="botinfo", description="Display bot system status and stats")
    async def botinfo_command(self, interaction: discord.Interaction):
        uptime_seconds = int(time.time() - self.start_time)
        uptime_str = str(f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m {uptime_seconds % 60}s")

        embed = discord.Embed(
            title="🤖 Bot System Information",
            color=discord.Color.teal(),
            timestamp=discord.utils.utcnow()
        )
        if self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)

        embed.add_field(name="Bot Tag", value=str(self.bot.user), inline=True)
        embed.add_field(name="Servers", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="Uptime", value=uptime_str, inline=True)
        embed.add_field(name="discord.py", value=discord.__version__, inline=True)
        embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.set_footer(text="Discord Bot with Security & Ticket Management")

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(GeneralCog(bot))
