import discord
from discord.ext import commands
from discord import app_commands
import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


class VerifyButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Verify",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="persistent_verify_btn"
    )
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        cfg = load_config()
        role_id = cfg.get("verification", {}).get("verified_role_id")

        if not role_id:
            await interaction.response.send_message(
                "❌ Verification role is not yet configured. Please notify an administrator.",
                ephemeral=True
            )
            return

        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message(
                "❌ The verification role could not be found. Please contact an admin.",
                ephemeral=True
            )
            return

        if role in interaction.user.roles:
            await interaction.response.send_message(
                "ℹ️ You are already verified!",
                ephemeral=True
            )
            return

        try:
            await interaction.user.add_roles(role, reason="Self-verification passed")
            await interaction.response.send_message(
                f"🎉 Success! You have been verified and granted the **{role.name}** role. Enjoy your stay!",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Bot lacks permission to assign this role. Please ensure the bot's role is higher in server role hierarchy.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error during verification: {e}",
                ephemeral=True
            )


class VerificationCog(commands.Cog, name="Verification"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="verify-setup", description="Deploy the verification gate into a channel")
    @app_commands.describe(
        role="The role granted to users who click verify",
        channel="Channel to post verification embed (defaults to current channel)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def verify_setup(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        channel: discord.TextChannel = None
    ):
        target_channel = channel or interaction.channel
        cfg = load_config()
        if "verification" not in cfg:
            cfg["verification"] = {}

        cfg["verification"]["verified_role_id"] = role.id
        cfg["verification"]["channel_id"] = target_channel.id
        save_config(cfg)

        embed = discord.Embed(
            title="🛡️ Server Verification Gate",
            description=(
                f"Welcome to **{interaction.guild.name}**!\n\n"
                "To access channels and participate in the community, you must verify your account.\n\n"
                "**Rules & Guidelines:**\n"
                "• Be respectful to all members\n"
                "• No hate speech, harassment, or spam\n"
                "• Keep discussions in appropriate channels\n\n"
                "Click the **Verify** button below to accept rules and gain full access."
            ),
            color=discord.Color.green()
        )
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(text="Verification Gate • Click below to get verified")

        view = VerifyButtonView()
        await target_channel.send(embed=embed, view=view)
        await interaction.response.send_message(
            f"✅ Verification panel deployed in {target_channel.mention} with role **{role.name}**!",
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(VerificationCog(bot))
