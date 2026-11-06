import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import io
import asyncio
from datetime import datetime

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
TRANSCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "transcripts")
os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


class TicketModal(discord.ui.Modal, title="Open Support Ticket"):
    subject = discord.ui.TextInput(
        label="Ticket Subject",
        placeholder="Brief summary of your query or issue...",
        required=True,
        max_length=100
    )
    description = discord.ui.TextInput(
        label="Details",
        style=discord.TextStyle.paragraph,
        placeholder="Please provide full details so staff can assist you...",
        required=True,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        user = interaction.user
        cfg = load_config()
        ticket_cfg = cfg.get("ticket", {})

        # Increment ticket counter
        ticket_counter = ticket_cfg.get("ticket_counter", 0) + 1
        ticket_cfg["ticket_counter"] = ticket_counter
        cfg["ticket"] = ticket_cfg
        save_config(cfg)

        channel_name = f"ticket-{user.name[:10]}-{ticket_counter:04d}"

        # Category
        category = None
        cat_id = ticket_cfg.get("category_id")
        if cat_id:
            category = guild.get_channel(cat_id)

        # Permissions setup
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                attach_files=True,
                embed_links=True,
                read_message_history=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                manage_messages=True,
                read_message_history=True
            )
        }

        support_role = None
        role_id = ticket_cfg.get("support_role_id")
        if role_id:
            support_role = guild.get_role(role_id)
            if support_role:
                overwrites[support_role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True
                )

        try:
            channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"Ticket created by {user} (ID: {user.id}) | Counter #{ticket_counter}"
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to create ticket channel: {e}", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🎫 Support Ticket #{ticket_counter:04d}",
            description=f"Welcome {user.mention}!\nOur support team has been notified and will assist you shortly.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="📌 Subject", value=self.subject.value, inline=False)
        embed.add_field(name="📝 Details", value=self.description.value, inline=False)
        embed.set_footer(text="Click 'Close Ticket' below when your issue is resolved.")

        mention_text = f"{user.mention}"
        if support_role:
            mention_text += f" {support_role.mention}"

        view = TicketControlView()
        await channel.send(content=mention_text, embed=embed, view=view)

        await interaction.followup.send(
            f"✅ Your ticket has been created: {channel.mention}",
            ephemeral=True
        )


class TicketLauncherView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Create Ticket",
        style=discord.ButtonStyle.success,
        emoji="📩",
        custom_id="persistent_create_ticket_btn"
    )
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketModal())


class TicketCloseConfirmView(discord.ui.View):
    def __init__(self, channel: discord.TextChannel):
        super().__init__(timeout=60)
        self.channel = channel

    @discord.ui.button(label="Yes, Close Ticket", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔒 Generating transcript and closing ticket in 5 seconds...")

        # Generate Transcript
        transcript_lines = []
        transcript_lines.append(f"Ticket Transcript: {self.channel.name}")
        transcript_lines.append(f"Closed by: {interaction.user} ({interaction.user.id})")
        transcript_lines.append(f"Closed at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        transcript_lines.append("=" * 60 + "\n")

        async for msg in self.channel.history(limit=500, oldest_first=True):
            time_str = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            attachments = f" [Attachments: {', '.join([a.url for a in msg.attachments])}]" if msg.attachments else ""
            transcript_lines.append(f"[{time_str}] {msg.author} ({msg.author.id}): {msg.content}{attachments}")

        transcript_content = "\n".join(transcript_lines)
        file_data = io.BytesIO(transcript_content.encode("utf-8"))
        filename = f"{self.channel.name}-transcript.txt"

        # Save to local file
        local_path = os.path.join(TRANSCRIPTS_DIR, filename)
        with open(local_path, "w", encoding="utf-8") as f:
            f.write(transcript_content)

        # Send transcript to log channel if set
        cfg = load_config()
        log_id = cfg.get("security", {}).get("log_channel_id")
        if log_id:
            log_ch = interaction.guild.get_channel(log_id)
            if log_ch:
                file_obj = discord.File(io.BytesIO(transcript_content.encode("utf-8")), filename=filename)
                log_embed = discord.Embed(
                    title="📁 Ticket Closed & Transcribed",
                    description=f"**Ticket:** {self.channel.name}\n**Closed By:** {interaction.user.mention}",
                    color=discord.Color.dark_grey(),
                    timestamp=discord.utils.utcnow()
                )
                try:
                    await log_ch.send(embed=log_embed, file=file_obj)
                except Exception:
                    pass

        # Send transcript to user DM
        topic = self.channel.topic or ""
        # Try to find user ID from topic
        if "ID: " in topic:
            try:
                user_id = int(topic.split("ID: ")[1].split(")")[0])
                ticket_user = interaction.guild.get_member(user_id)
                if ticket_user:
                    dm_file = discord.File(io.BytesIO(transcript_content.encode("utf-8")), filename=filename)
                    await ticket_user.send(
                        f"📄 Here is the transcript for your closed ticket (`{self.channel.name}`):",
                        file=dm_file
                    )
            except Exception:
                pass

        await asyncio.sleep(5)
        try:
            await self.channel.delete(reason=f"Ticket closed by {interaction.user}")
        except Exception as e:
            print(f"Error deleting ticket channel: {e}")

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="persistent_close_ticket_btn"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        confirm_view = TicketCloseConfirmView(interaction.channel)
        await interaction.response.send_message(
            "⚠️ Are you sure you want to close this ticket? A transcript will be generated.",
            view=confirm_view,
            ephemeral=False
        )

    @discord.ui.button(
        label="Claim Ticket",
        style=discord.ButtonStyle.primary,
        emoji="🙋",
        custom_id="persistent_claim_ticket_btn"
    )
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            description=f"🙋 This ticket has been claimed by {interaction.user.mention}.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)


class TicketCog(commands.Cog, name="Tickets"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ticket-setup", description="Deploy the ticket creation panel into a channel")
    @app_commands.describe(
        channel="Channel to post the ticket panel",
        category="Category where new ticket channels will be created",
        support_role="Staff role allowed to view and manage tickets"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel = None,
        category: discord.CategoryChannel = None,
        support_role: discord.Role = None
    ):
        target_channel = channel or interaction.channel
        cfg = load_config()
        if "ticket" not in cfg:
            cfg["ticket"] = {}

        if category:
            cfg["ticket"]["category_id"] = category.id
        if support_role:
            cfg["ticket"]["support_role_id"] = support_role.id
        save_config(cfg)

        embed = discord.Embed(
            title="📩 Need Help? Open a Support Ticket",
            description=(
                "Click the button below to open a private support ticket with our team.\n\n"
                "• **Staff Assistance:** Help with questions, issues, or reports\n"
                "• **Private:** Only you and our staff can see the conversation\n"
                "• **Secure:** Auto-transcripts saved upon ticket completion"
            ),
            color=discord.Color.blue()
        )
        embed.set_footer(text="Support System • Click below to get started")

        view = TicketLauncherView()
        await target_channel.send(embed=embed, view=view)
        await interaction.response.send_message(
            f"✅ Ticket panel successfully deployed to {target_channel.mention}!",
            ephemeral=True
        )

    @app_commands.command(name="ticket-add", description="Add a member to the current ticket")
    @app_commands.describe(member="Member to grant access")
    async def ticket_add(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.channel.name.startswith("ticket-"):
            await interaction.response.send_message("❌ This command can only be used inside a ticket channel.", ephemeral=True)
            return

        await interaction.channel.set_permissions(
            member,
            view_channel=True,
            send_messages=True,
            attach_files=True,
            embed_links=True,
            read_message_history=True
        )
        await interaction.response.send_message(f"✅ {member.mention} has been added to this ticket.")

    @app_commands.command(name="ticket-remove", description="Remove a member from the current ticket")
    @app_commands.describe(member="Member to remove access from")
    async def ticket_remove(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.channel.name.startswith("ticket-"):
            await interaction.response.send_message("❌ This command can only be used inside a ticket channel.", ephemeral=True)
            return

        await interaction.channel.set_permissions(member, overwrite=None)
        await interaction.response.send_message(f"👋 {member.mention} has been removed from this ticket.")


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketCog(bot))
