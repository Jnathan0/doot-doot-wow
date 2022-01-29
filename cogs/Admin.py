import discord
from discord.ext import commands
from modules import config
from modules.helper_functions import format_markdown

# imports for admin stats function
import psutil
from time import time
from platform import python_version
from datetime import datetime, timedelta
from discord import Embed
from discord import __version__ as discord_version
from psutil import Process, virtual_memory

# imports for updating bot profile pic
import tempfile
import requests

class Admin(commands.Cog):
    """
    Cog contains admin functions only useable by the discord owner or users with the owner permission
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.group()
    @commands.guild_only()
    @commands.is_owner()
    async def admin(self, ctx):
        """
        Top level command to invoke subcommands
        """
        if ctx.invoked_subcommand is None:
            await ctx.send(format_markdown("Invalid Admin command invoked"))

    @commands.guild_only()
    @commands.is_owner()
    @admin.group()
    async def shutdown(self, ctx):
        """
        Shuts the bot down and kills the process.
        Requires owner permissions.
        """
        file = discord.File(str(config.gifs_path+"peaceout.gif"))
        await ctx.send(content="> you're such a turnoff", file=file)
        await self.bot.logout()
        await self.bot.close()

    @commands.guild_only()
    @commands.is_owner()
    @admin.group()
    async def setpresence(self, ctx, *, content):
        """
        Set a presence message that shows up in the mini profile for the bot in discord
        """
        if len(content) > 0:
            await self.bot.change_presence(activity=discord.Game(name=content))
            await ctx.send(f"Presence changed to:\n{format_markdown(content)}", delete_after=10)
        else:
            await ctx.send(format_markdown("Presence cannot be empty string."), delete_after=10)

    @commands.guild_only()
    @commands.is_owner()
    @admin.group()
    async def stats(self, ctx):
        """
        Displays runtime stats of the application in markdown embed.
        Sourced from: https://github.com/Carberra/updated-discord.py-tutorial/blob/085113e9bff69a699a25ed1cd91db5744b8755ea/lib/cogs/meta.py#L54-L82
        """
        embed = Embed(title="Bot Stats",
                color = ctx.author.color,
                thumbnail = self.bot.user.avatar_url,
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

        await ctx.send(embed=embed)


    # @commands.guild_only()
    # @commands.is_owner()
    # @admin.group()
    # async def avatar(self, ctx):
    #     """
    #     Looks at message attachment and uploads the media as the bots new discord avatar
    #     """
    #     media = ctx.message.attachments[0]
    #     # download = requests.get(media.url)
    #     # temp_img = tempfile.NamedTemporaryFile(dir="/var/tmp")
    #     # open(f"{temp_img.name}", 'wb').write(download.content)
        
    #     # avatar = open(f"{temp_img.name}", 'rb')
    #     await self.bot.user.edit(avatar=bytes(media.url))



def setup(bot):
    bot.add_cog(Admin(bot))