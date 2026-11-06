import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import re
import time
from datetime import timedelta
from collections import defaultdict

WARNINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "warnings.json")
CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def load_warnings():
    if os.path.exists(WARNINGS_FILE):
        try:
            with open(WARNINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_warnings(data):
    with open(WARNINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


class SecurityCog(commands.Cog, name="Security"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Anti-spam tracking: user_id -> list of timestamps
        self.user_message_times = defaultdict(list)
        self.invite_regex = re.compile(
            r"(https?:\/\/)?(www\.)?(discord\.(gg|io|me|li)|discordapp\.com\/invite|discord\.com\/invite)\/([a-zA-Z0-9\-]+)",
            re.IGNORECASE
        )
        self.url_regex = re.compile(r"https?:\/\/[^\s]+", re.IGNORECASE)

    async def log_action(self, guild: discord.Guild, embed: discord.Embed):
        cfg = load_config()
        channel_id = cfg.get("security", {}).get("log_channel_id")
        if channel_id:
            channel = guild.get_channel(channel_id)
            if channel:
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bot messages and DMs
        if message.author.bot or not message.guild:
            return

        # Exempt server administrators & members with manage_messages
        if isinstance(message.author, discord.Member):
            if message.author.guild_permissions.administrator or message.author.guild_permissions.manage_messages:
                return

        cfg = load_config()
        sec_cfg = cfg.get("security", {})
        now = time.time()
        user_id = message.author.id

        # 1. Anti-Spam Check
        if sec_cfg.get("anti_spam", True):
            threshold = sec_cfg.get("max_messages_threshold", 5)
            interval = sec_cfg.get("spam_interval_seconds", 4)
            timeout_mins = sec_cfg.get("spam_timeout_minutes", 5)

            # Filter old timestamps
            self.user_message_times[user_id] = [
                t for t in self.user_message_times[user_id] if now - t < interval
            ]
            self.user_message_times[user_id].append(now)

            if len(self.user_message_times[user_id]) >= threshold:
                self.user_message_times[user_id].clear()
                try:
                    await message.delete()
                except Exception:
                    pass

                try:
                    until = discord.utils.utcnow() + timedelta(minutes=timeout_mins)
                    await message.author.timeout(until, reason="Auto-Mod: Excessive spamming detected")
                    warn_embed = discord.Embed(
                        title="⚠️ Spam Detected",
                        description=f"{message.author.mention} has been timed out for **{timeout_mins} minutes** due to spamming.",
                        color=discord.Color.red()
                    )
                    await message.channel.send(embed=warn_embed, delete_after=10)

                    log_embed = discord.Embed(
                        title="🛡️ Auto-Mod: Anti-Spam Triggered",
                        description=f"**User:** {message.author} (`{message.author.id}`)\n**Action:** Timed out for {timeout_mins}m\n**Channel:** {message.channel.mention}",
                        color=discord.Color.orange(),
                        timestamp=discord.utils.utcnow()
                    )
                    await self.log_action(message.guild, log_embed)
                    return
                except Exception as e:
                    print(f"Failed to timeout spammer: {e}")

        # 2. Anti-Invite Check
        if sec_cfg.get("anti_invites", True):
            if self.invite_regex.search(message.content):
                try:
                    await message.delete()
                    warn_msg = await message.channel.send(
                        f"🚫 {message.author.mention}, Discord invite links are not allowed here!",
                        delete_after=7
                    )
                except Exception:
                    pass

                log_embed = discord.Embed(
                    title="🛡️ Auto-Mod: Invite Link Blocked",
                    description=f"**User:** {message.author} (`{message.author.id}`)\n**Channel:** {message.channel.mention}\n**Content:** `{message.content[:300]}`",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                await self.log_action(message.guild, log_embed)
                return

        # 3. Bad Words Filter
        bad_words = sec_cfg.get("bad_words", [])
        content_lower = message.content.lower()
        for word in bad_words:
            if word and word.lower() in content_lower:
                try:
                    await message.delete()
                    await message.channel.send(
                        f"⚠️ {message.author.mention}, your message contained prohibited terms and was removed.",
                        delete_after=7
                    )
                except Exception:
                    pass

                log_embed = discord.Embed(
                    title="🛡️ Auto-Mod: Prohibited Word Detected",
                    description=f"**User:** {message.author} (`{message.author.id}`)\n**Channel:** {message.channel.mention}\n**Matched Word:** `{word}`",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                await self.log_action(message.guild, log_embed)
                return

        # 4. Anti-Link (External URLs) if enabled
        if sec_cfg.get("anti_links", False):
            urls = self.url_regex.findall(message.content)
            allowed_domains = sec_cfg.get("allowed_domains", [])
            for url in urls:
                allowed = any(domain in url for domain in allowed_domains)
                if not allowed:
                    try:
                        await message.delete()
                        await message.channel.send(
                            f"🚫 {message.author.mention}, external links are restricted in this channel.",
                            delete_after=7
                        )
                    except Exception:
                        pass
                    return

    # ================= Moderation Slash Commands =================

    @app_commands.command(name="kick", description="Kick a member from the server")
    @app_commands.describe(member="Member to kick", reason="Reason for kicking")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick_command(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("❌ You cannot kick someone with an equal or higher role than yours.", ephemeral=True)
            return

        if member == interaction.guild.owner:
            await interaction.response.send_message("❌ Server owner cannot be kicked.", ephemeral=True)
            return

        try:
            await member.kick(reason=f"By {interaction.user}: {reason}")
            embed = discord.Embed(
                title="👢 Member Kicked",
                description=f"**Member:** {member.mention} (`{member.id}`)\n**Moderator:** {interaction.user.mention}\n**Reason:** {reason}",
                color=discord.Color.orange(),
                timestamp=discord.utils.utcnow()
            )
            await interaction.response.send_message(embed=embed)
            await self.log_action(interaction.guild, embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to kick member: {e}", ephemeral=True)

    @app_commands.command(name="ban", description="Ban a member from the server")
    @app_commands.describe(member="Member to ban", reason="Reason for banning", delete_message_days="Days of messages to delete (0-7)")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban_command(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided", delete_message_days: int = 0):
        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("❌ You cannot ban someone with an equal or higher role than yours.", ephemeral=True)
            return

        if member == interaction.guild.owner:
            await interaction.response.send_message("❌ Server owner cannot be banned.", ephemeral=True)
            return

        try:
            await member.ban(reason=f"By {interaction.user}: {reason}", delete_message_days=min(max(delete_message_days, 0), 7))
            embed = discord.Embed(
                title="🔨 Member Banned",
                description=f"**Member:** {member.mention} (`{member.id}`)\n**Moderator:** {interaction.user.mention}\n**Reason:** {reason}",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            await interaction.response.send_message(embed=embed)
            await self.log_action(interaction.guild, embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to ban member: {e}", ephemeral=True)

    @app_commands.command(name="unban", description="Unban a user by their User ID")
    @app_commands.describe(user_id="Discord ID of user to unban", reason="Reason for unbanning")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban_command(self, interaction: discord.Interaction, user_id: str, reason: str = "No reason provided"):
        try:
            uid = int(user_id)
            user = await self.bot.fetch_user(uid)
            await interaction.guild.unban(user, reason=f"By {interaction.user}: {reason}")
            embed = discord.Embed(
                title="🔓 User Unbanned",
                description=f"**User:** {user.name} (`{user.id}`)\n**Moderator:** {interaction.user.mention}\n**Reason:** {reason}",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            await interaction.response.send_message(embed=embed)
            await self.log_action(interaction.guild, embed)
        except ValueError:
            await interaction.response.send_message("❌ Invalid user ID. Please provide numeric Discord ID.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to unban: {e}", ephemeral=True)

    @app_commands.command(name="timeout", description="Timeout (mute) a member")
    @app_commands.describe(member="Member to timeout", minutes="Timeout duration in minutes", reason="Reason for timeout")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout_command(self, interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "No reason provided"):
        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("❌ You cannot timeout someone with an equal or higher role than yours.", ephemeral=True)
            return

        try:
            duration = timedelta(minutes=minutes)
            until = discord.utils.utcnow() + duration
            await member.timeout(until, reason=f"By {interaction.user}: {reason}")
            embed = discord.Embed(
                title="⏳ Member Timed Out",
                description=f"**Member:** {member.mention}\n**Duration:** {minutes} minutes\n**Moderator:** {interaction.user.mention}\n**Reason:** {reason}",
                color=discord.Color.gold(),
                timestamp=discord.utils.utcnow()
            )
            await interaction.response.send_message(embed=embed)
            await self.log_action(interaction.guild, embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to timeout member: {e}", ephemeral=True)

    @app_commands.command(name="untimeout", description="Remove timeout from a member")
    @app_commands.describe(member="Member to remove timeout from", reason="Reason for untimeout")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def untimeout_command(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Removed by moderator"):
        try:
            await member.timeout(None, reason=f"By {interaction.user}: {reason}")
            embed = discord.Embed(
                title="🔊 Timeout Removed",
                description=f"**Member:** {member.mention}\n**Moderator:** {interaction.user.mention}\n**Reason:** {reason}",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            await interaction.response.send_message(embed=embed)
            await self.log_action(interaction.guild, embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to remove timeout: {e}", ephemeral=True)

    @app_commands.command(name="warn", description="Issue a formal warning to a member")
    @app_commands.describe(member="Member to warn", reason="Reason for the warning")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn_command(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        warns = load_warnings()
        guild_id_str = str(interaction.guild.id)
        user_id_str = str(member.id)

        if guild_id_str not in warns:
            warns[guild_id_str] = {}
        if user_id_str not in warns[guild_id_str]:
            warns[guild_id_str][user_id_str] = []

        warn_entry = {
            "moderator_id": interaction.user.id,
            "moderator_name": str(interaction.user),
            "reason": reason,
            "timestamp": int(time.time())
        }
        warns[guild_id_str][user_id_str].append(warn_entry)
        save_warnings(warns)

        total_warns = len(warns[guild_id_str][user_id_str])

        # DM the warned member
        try:
            dm_embed = discord.Embed(
                title=f"⚠️ Warning Received in {interaction.guild.name}",
                description=f"**Reason:** {reason}\n**Total Warnings:** {total_warns}",
                color=discord.Color.red()
            )
            await member.send(embed=dm_embed)
        except Exception:
            pass

        embed = discord.Embed(
            title="⚠️ Warning Issued",
            description=f"**Member:** {member.mention}\n**Moderator:** {interaction.user.mention}\n**Reason:** {reason}\n**Total Warnings:** {total_warns}",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        await interaction.response.send_message(embed=embed)
        await self.log_action(interaction.guild, embed)

    @app_commands.command(name="warnings", description="Check warnings for a member")
    @app_commands.describe(member="Member to inspect")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warnings_command(self, interaction: discord.Interaction, member: discord.Member):
        warns = load_warnings()
        guild_id_str = str(interaction.guild.id)
        user_id_str = str(member.id)

        user_warns = warns.get(guild_id_str, {}).get(user_id_str, [])
        if not user_warns:
            await interaction.response.send_message(f"✅ {member.mention} has no warnings on record.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📋 Warnings for {member.name} ({len(user_warns)})",
            color=discord.Color.blue()
        )
        for i, w in enumerate(user_warns, 1):
            date_str = f"<t:{w['timestamp']}:f>"
            embed.add_field(
                name=f"Warning #{i}",
                value=f"**Mod:** {w.get('moderator_name', 'Unknown')}\n**Reason:** {w['reason']}\n**Date:** {date_str}",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="clearwarns", description="Clear all warnings for a member")
    @app_commands.describe(member="Member whose warnings to clear")
    @app_commands.checks.has_permissions(administrator=True)
    async def clearwarns_command(self, interaction: discord.Interaction, member: discord.Member):
        warns = load_warnings()
        guild_id_str = str(interaction.guild.id)
        user_id_str = str(member.id)

        if guild_id_str in warns and user_id_str in warns[guild_id_str]:
            del warns[guild_id_str][user_id_str]
            save_warnings(warns)
            await interaction.response.send_message(f"🧹 Cleared all warnings for {member.mention}.")
        else:
            await interaction.response.send_message(f"ℹ️ {member.mention} had no warnings to clear.", ephemeral=True)

    @app_commands.command(name="lock", description="Lock current channel (prevent @everyone from messaging)")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock_command(self, interaction: discord.Interaction):
        channel = interaction.channel
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        embed = discord.Embed(
            title="🔒 Channel Locked",
            description="This channel has been locked by a moderator.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="unlock", description="Unlock current channel (restore @everyone message permissions)")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock_command(self, interaction: discord.Interaction):
        channel = interaction.channel
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = True
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        embed = discord.Embed(
            title="🔓 Channel Unlocked",
            description="This channel has been unlocked. Members can send messages.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="slowmode", description="Set channel message slowmode delay")
    @app_commands.describe(seconds="Slowmode delay in seconds (0 to disable)")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode_command(self, interaction: discord.Interaction, seconds: int):
        if seconds < 0 or seconds > 21600:
            await interaction.response.send_message("❌ Slowmode must be between 0 and 21600 seconds (6 hours).", ephemeral=True)
            return
        await interaction.channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            await interaction.response.send_message("⚡ Slowmode disabled for this channel.")
        else:
            await interaction.response.send_message(f"⏱️ Slowmode set to **{seconds} seconds**.")

    @app_commands.command(name="set-modlog", description="Set security/moderation audit log channel")
    @app_commands.describe(channel="Channel for moderation logs")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_modlog_command(self, interaction: discord.Interaction, channel: discord.TextChannel):
        cfg = load_config()
        if "security" not in cfg:
            cfg["security"] = {}
        cfg["security"]["log_channel_id"] = channel.id
        save_config(cfg)
        await interaction.response.send_message(f"✅ Security log channel set to {channel.mention}.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SecurityCog(bot))
