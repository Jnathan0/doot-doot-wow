import discord
from discord import app_commands
from discord.ext import commands
from modules import config
from modules.helper_functions import format_markdown

# imports for admin stats function
from time import time
from platform import python_version
from datetime import datetime, timedelta
from discord import Embed
from discord import __version__ as discord_version
from psutil import Process, virtual_memory

# imports for updating bot profile pic
import tempfile

class Admin(commands.Cog):
    """
    Cog contains admin functions only useable by the discord owner or users with the owner permission
    """
    def __init__(self, bot):
        self.bot = bot

    group = app_commands.Group(
        name="admin",
        description="Example usage: /admin"
    )

    @group.command(name="shutdown")
    @commands.is_owner()
    async def admin_shutdown_command(self, interaction: discord.Interaction) -> None:
        """
        Shuts the bot down and kills the process.
        Requires owner permissions.
        """
        try:
            file = discord.File(str(config.gifs_path+"peaceout.gif"))
            await interaction.response.send_message(content="> you're such a turnoff", file=file)
        except FileNotFoundError:
            await interaction.response.send_message("> shutting down bot..")
        await self.bot.close()

    @group.command(name="presence")
    @commands.is_owner()
    async def admin_setpresence_command(self, interaction: discord.Interaction, content: str) -> None:
        """
        Set a presence message that shows up in the mini profile for the bot in discord
        """
        if len(content) > 0:
            await self.bot.change_presence(activity=discord.Game(name=content))
            await interaction.response.send_message(f"Presence changed to:\n{format_markdown(content)}", delete_after=10)
        else:
            await interaction.response.send_message(format_markdown("Presence cannot be empty string."), delete_after=10)

    @group.command(name="stats")
    @commands.is_owner()
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

        await interaction.response.send_message(embed=embed)


    @group.command(name="avatar")
    @app_commands.default_permissions(attach_files=True)
    @commands.is_owner()
    async def admin_stats_command(self, interaction: discord.Interaction, attachment: discord.Attachment):
        """
        Looks at the first message attachment and uploads the media as the bots new discord avatar
        """
        try:
            file_bytes = await attachment.read(use_cached=True)
            temp_dir = tempfile.TemporaryDirectory(dir="/var/tmp/")
            open(f"{temp_dir.name+'/'+attachment.filename}", 'wb').write(file_bytes)
            avatar = open(f"{temp_dir.name+'/'+attachment.filename}", 'rb')
            await self.bot.user.edit(avatar=avatar.read())
            temp_dir.cleanup()
            await interaction.response.send_message(format_markdown(f"Bot avatar image changed to {attachment.filename}"), ephemeral=True)
        except Exception as e:
            print(e)
            await interaction.response.send_message(format_markdown("Error: Something happened during avatar uploading process."))


async def setup(bot):
    await bot.add_cog(Admin(bot))