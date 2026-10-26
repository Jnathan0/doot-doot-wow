import discord
from discord import app_commands
from discord.ext import commands
from modules import config
from modules.helper_functions import format_markdown
from modules.permissions import ADMIN_DEFAULT, bot_owner_only, audit

# imports for admin stats function
from time import time
from platform import python_version
from datetime import datetime, timedelta
from discord import Embed
from discord import __version__ as discord_version
from psutil import Process, virtual_memory

# discord rejects avatars larger than this
AVATAR_SIZE_LIMIT = 8 * 1024 * 1024

class Admin(commands.Cog):
    """
    Cog contains admin functions only useable by the bot owner (see modules/permissions.py)
    """
    def __init__(self, bot):
        self.bot = bot

    group = app_commands.Group(
        name="admin",
        description="Bot owner tools",
        default_permissions=ADMIN_DEFAULT,  # hidden from non-admins in the client, the checks below enforce it
        guild_only=True
    )

    @group.command(name="shutdown")
    @bot_owner_only()
    async def admin_shutdown_command(self, interaction: discord.Interaction) -> None:
        """
        Shuts the bot down and kills the process.
        Requires owner permissions.
        """
        await audit(interaction)
        try:
            file = discord.File(str(config.gifs_path+"peaceout.gif"))
            await interaction.response.send_message(content="> you're such a turnoff", file=file)
        except FileNotFoundError:
            await interaction.response.send_message("> shutting down bot..")
        await self.bot.close()

    @group.command(name="presence")
    @bot_owner_only()
    async def admin_setpresence_command(self, interaction: discord.Interaction, content: app_commands.Range[str, 1, 128]) -> None:
        """
        Set a presence message that shows up in the mini profile for the bot in discord
        """
        await audit(interaction, detail=content)
        if len(content) > 0:
            await self.bot.change_presence(activity=discord.Game(name=content))
            await interaction.response.send_message(f"Presence changed to:\n{format_markdown(content)}", delete_after=10)
        else:
            await interaction.response.send_message(format_markdown("Presence cannot be empty string."), delete_after=10)

    @group.command(name="stats")
    @bot_owner_only()
    async def admin_stats_command(self, interaction: discord.Interaction):
        """
        Displays runtime stats of the application in markdown embed.
        Sourced from: https://github.com/Carberra/updated-discord.py-tutorial/blob/085113e9bff69a699a25ed1cd91db5744b8755ea/lib/cogs/meta.py#L54-L82
        """
        embed = Embed(title="Bot Stats",
                color = discord.Color.blurple(),
                timestamp = datetime.utcnow())

        proc = Process()
        with proc.oneshot():
            uptime = str(timedelta(seconds=time()-proc.create_time())).split('.')[0]
            cpu_time = timedelta(seconds=(cpu := proc.cpu_times()).system + cpu.user)
            mem_total = virtual_memory().total / (1024**2)
            mem_of_total = proc.memory_percent()
            mem_usage = mem_total * (mem_of_total / 100)

        fields = [
            ("Python Version", python_version(), True),
            ("discord.py Version", discord_version, True),
            ("Uptime", uptime, True),
            ("CPU Time", cpu_time, True),
            ("Memory Usage", f"{mem_usage:,.2f} / {mem_total:,.0f} MiB ({mem_usage/mem_total:.2f}%)", True),
        ]

        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)

        # host details, only for the owner
        await interaction.response.send_message(embed=embed, ephemeral=True)


    @group.command(name="avatar")
    @bot_owner_only()
    async def admin_avatar_command(self, interaction: discord.Interaction, attachment: discord.Attachment):
        """
        Looks at the first message attachment and uploads the media as the bots new discord avatar
        """
        if not (attachment.content_type or "").startswith("image/"):
            await interaction.response.send_message(format_markdown("Error: the avatar must be an image."), ephemeral=True)
            return
        if attachment.size > AVATAR_SIZE_LIMIT:
            await interaction.response.send_message(format_markdown(f"Error: the avatar can be at most {AVATAR_SIZE_LIMIT >> 20} MB."), ephemeral=True)
            return
        await audit(interaction, detail=attachment.filename)
        try:
            file_bytes = await attachment.read(use_cached=True)
            await self.bot.user.edit(avatar=file_bytes)
            await interaction.response.send_message(format_markdown(f"Bot avatar image changed to {attachment.filename}"), ephemeral=True)
        except Exception as e:
            print(e)
            await interaction.response.send_message(format_markdown("Error: Something happened during avatar uploading process."), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Admin(bot))