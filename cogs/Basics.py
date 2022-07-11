import discord
import time
from datetime import datetime
from discord.ext import commands
from modules import config
from modules.helper_functions import format_markdown, restart_bot


# declaring Cog
class Basics(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # Defining owner only command to reload specific cog allowing to update in example airhorn.cog with new sounds
    # without restarting whole bot
    @commands.command(hidden=True)
    @commands.is_owner()
    async def reload(self, ctx, *, cog: str):
        """
        Restarts the bot, need correct permission to do so.
        """
        cogs = config.extensions
        cog = cog.lower()
        for c in ctx.bot.cogs:
            cogs.append(c.replace('Cog', '').lower())

        if cog in cogs:
            self.bot.unload_extension("cogs." + cog)
            self.bot.load_extension("cogs." + cog)
            await ctx.send(f'**{cog}** has been reloaded.')
        else:
            await ctx.send(f"I can't find that cog.")


    @commands.command()
    async def ping(self, ctx: commands.Context):
        """
        Shows the Gateway Ping.
        """
        t1 = time.perf_counter()
        await ctx.trigger_typing()
        t2 = time.perf_counter()
        await ctx.send(f"> **PONG**\n:hourglass: gateway ping: {round((t2 - t1) * 1000)}ms :hourglass:")

    @commands.command()
    async def github(self, ctx):
        """
        Gives you my source code.
        """
        embed = discord.Embed(
            title="Github repository for Owen Wilson Bot", colour=0x7289DA,
            description="Want to report bug?\nsubmit feature request?\nmake new feature?\nSource Code is available on github page:\n<https://github.com/Jnathan0/doot-doot-wow>")
        embed.set_image(
            url="https://cdn.discordapp.com/avatars/593170973193273344/0a143cd8cfa9077570ebef54f097c882.webp")
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:  # failover on 403 while sending embed. not used in invite becasue it would look awfull
            await ctx.send(
                "Want to report bug?\nSubmit feature request?\nMake new feature?\nBot code is available on github page:\n<https://github.com/Jnathan0/doot-doot-wow>")

    @commands.command()
    @commands.guild_only()
    @commands.has_role(config.owb_id)#decorator to see if whoever requested the command has the role specified, takes roleid argument in int or string form. 
    async def restart(self, ctx):
        try:
            file = discord.File(str(config.gifs_path+"illbeback.gif"))
            await ctx.send(file=file)
        except FileNotFoundError:
            await ctx.send(format_markdown("Restarting Bot..."))
        restart_bot()
    
    @restart.error#error handaling for the restart function
    async def restart_error(self,ctx,error):
        if isinstance(error, commands.MissingRole):#if @commands.has_role returns with MissingRole error, send message
            await ctx.send(format_markdown("Cannot restart, \'owb\' role required"))

def setup(bot):
    bot.add_cog(Basics(bot))