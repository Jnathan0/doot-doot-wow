import discord
from discord import app_commands
from discord.ext import commands
from modules import config
from modules.helper_functions import format_markdown, restart_bot


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
    @app_commands.checks.has_role(config.owb_id) #decorator to see if whoever requested the command has the role specified, takes roleid argument in int or string form. 
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
    
    @restart.error#error handaling for the restart function
    async def restart_error(self,interaction, error):
        if isinstance(error, discord.app_commands.MissingRole):#if @app_commands.checks.has_role() returns with MissingRole error, send message
            await interaction.response.send_message(format_markdown("Cannot restart, \'owb\' role required"))

async def setup(bot):
   await bot.add_cog(Basics(bot))