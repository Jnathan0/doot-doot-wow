import discord
from discord import app_commands
from discord.ext import commands
from modules import config
from modules.helper_functions import format_markdown, restart_bot
from modules.permissions import owb_role_required


class Basics(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping")
    async def ping(self, interaction: discord.Interaction) -> None:
        """
        Shows the Gateway Ping.
        """
        await interaction.channel.typing()
        await interaction.response.send_message(f"> **PONG**\n:hourglass: gateway ping: {round(self.bot.latency * 1000)}ms :hourglass:")

    @app_commands.command(name="github")
    async def github(self, interaction: discord.Interaction) -> None:
        """
        Gives you my source code.
        """
        embed = discord.Embed(
            title="Github repository for Owen Wilson Bot", colour=0x7289DA,
            description="Want to report bug?\nsubmit feature request?\nmake new feature?\nSource Code is available on github page:\n<https://github.com/Jnathan0/doot-doot-wow>")
        embed.set_image(
            url="https://cdn.discordapp.com/avatars/593170973193273344/0a143cd8cfa9077570ebef54f097c882.webp")
        try:
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:  # failover on 403 while sending embed. not used in invite becasue it would look awfull
            await interaction.response.send_message(
                "Want to report bug?\nSubmit feature request?\nMake new feature?\nBot code is available on github page:\n<https://github.com/Jnathan0/doot-doot-wow>")

    @app_commands.command(name="restart")
    @app_commands.guild_only()
    @owb_role_required()
    async def restart(self, interaction: discord.Interaction) -> None:
        """
        Restarts the bot.
        """
        try:
            file = discord.File(str(config.gifs_path+"illbeback.gif"))
            await interaction.response.send_message(file=file)
        except FileNotFoundError:
            await interaction.response.send_message(format_markdown("Restarting Bot..."))
        restart_bot()

async def setup(bot):
   await bot.add_cog(Basics(bot))