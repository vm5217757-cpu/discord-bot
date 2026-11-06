import os
import sys
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

# Ensure console prints unicode properly and unbuffered on Windows
try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

# Load opus library for voice
try:
    if not discord.opus.is_loaded():
        discord.opus._load_default()
except Exception as e:
    print(f"[!] Opus load notice: {e}")

# Load environment variables from .env file
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True


class SecurityTicketBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        # Register persistent views to ensure buttons keep working across restarts
        try:
            from cogs.tickets import TicketLauncherView, TicketControlView
            from cogs.verification import VerifyButtonView
            self.add_view(TicketLauncherView())
            self.add_view(TicketControlView())
            self.add_view(VerifyButtonView())
            print("[OK] Persistent UI Views registered successfully.")
        except Exception as e:
            print(f"[!] Warning: Failed to register persistent views: {e}")

        # Load extension cogs
        cogs = ["cogs.security", "cogs.tickets", "cogs.verification", "cogs.general"]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                print(f"[OK] Cog loaded: {cog}")
            except Exception as e:
                print(f"[ERROR] Failed to load {cog}: {e}")

        # Slash Command synchronization
        try:
            if GUILD_ID and GUILD_ID.strip():
                guild_obj = discord.Object(id=int(GUILD_ID.strip()))
                self.tree.copy_global_to(guild=guild_obj)
                synced = await self.tree.sync(guild=guild_obj)
                print(f"[OK] Fast Sync: {len(synced)} slash commands synced to Guild ID {GUILD_ID}!")
            else:
                synced = await self.tree.sync()
                print(f"[OK] Global Sync: {len(synced)} slash commands synced globally.")
        except Exception as e:
            print(f"[!] Warning: Slash commands sync error: {e}")

    async def on_ready(self):
        print("=" * 60)
        print(f" Logged in as : {self.user.name} ({self.user.id})")
        print(f" Serving      : {len(self.guilds)} server(s)")
        print(f" discord.py   : v{discord.__version__}")
        print("=" * 60)

        # Set rich presence activity
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="🛡️ Server Security & Tickets"
        )
        await self.change_presence(status=discord.Status.online, activity=activity)


bot = SecurityTicketBot()


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        perms = ", ".join(error.missing_permissions)
        msg = f"❌ You don't have permission to use this command. Missing: `{perms}`"
    elif isinstance(error, app_commands.BotMissingPermissions):
        perms = ", ".join(error.missing_permissions)
        msg = f"❌ Bot is missing required permissions to execute this: `{perms}`"
    else:
        msg = f"❌ An unexpected error occurred: {error}"

    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass


def main():
    if not TOKEN or TOKEN.strip() == "" or "YOUR_BOT_TOKEN_HERE" in TOKEN:
        print("\n" + "!" * 60)
        print(" ERROR: DISCORD_TOKEN is missing or not configured!")
        print(" Please open the '.env' file and paste your Discord Bot Token.")
        print(" Example:")
        print(" DISCORD_TOKEN=MTEw...XYZ")
        print("!" * 60 + "\n")
        return

    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("\n[ERROR] Invalid Discord Bot Token! Please verify your token in the .env file.")
    except Exception as e:
        print(f"\n[ERROR] Error launching bot: {e}")


if __name__ == "__main__":
    main()
