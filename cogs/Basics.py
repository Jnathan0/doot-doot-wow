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
        """Restarts the bot, need correct permission to do so."""
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

    # owner only command to shutdown bot
    # @commands.command()
    # @commands.guild_only()
    # @commands.is_owner()
    # async def shutdown(self, ctx):
    #     """Kills the bot."""
    #     await ctx.send("you're such a turnoff")
    #     await self.bot.logout()
    #     await self.bot.close()

    @commands.command()
    async def ping(self, ctx: commands.Context):
        """Shows the Gateway Ping."""
        t1 = time.perf_counter()
        await ctx.trigger_typing()
        t2 = time.perf_counter()
        await ctx.send(f"> **PONG**\n:hourglass: gateway ping: {round((t2 - t1) * 1000)}ms :hourglass:")

    @commands.command()
    async def github(self, ctx):
        """Gives you my source code."""
        embed = discord.Embed(
            title="Github repository for DootDoot", colour=0x7289DA,
            description="Want to report bug?\nsubmit feature request?\nmake new feature?\nbot code is available on github page:\n<https://github.com/ks00908/doot-doot>")
        embed.set_image(
            url="https://cdn.discordapp.com/avatars/593170973193273344/0a143cd8cfa9077570ebef54f097c882.webp")
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:  # failover on 403 while sending embed. not used in invite becasue it would look awfull
            await ctx.send(
                "Want to report bug?\nSubmit feature request?\nMake new feature?\nBot code is available on github page:\n<https://github.com/ks00908/doot-doot>")

    @commands.command()
    async def invite(self, ctx):
        """Invite me to your server!"""
        embed = discord.Embed(
            title="Inviting the bot is easy!",
            colour=0x7289DA,
            description="Invite doot-doot to your server using this handy link: [Discord bot invite Oauth](https://discordapp.com/oauth2/authorize?client_id=593170973193273344&scope=bot&permissions=3165184)\nif you don't see your server make sure you are logged to right account at [Discord web client](https://www.discordapp.com)",
        )
        embed.set_image(
            url="https://cdn.discordapp.com/avatars/593170973193273344/0a143cd8cfa9077570ebef54f097c882.webp")
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(
                "There was an error sending Embed with bot invite. please check if bot has permission to embed links and try again")

    @commands.command()
    @commands.is_owner()
    async def setpresence(self, ctx, *, content):
        """Changing bots presence"""
        if len(content) > 0:
            await self.bot.change_presence(activity=discord.Game(name=content))
            await ctx.send("Presence sucesfully changed to\n ```" + content + "```")
        else:
            await ctx.send("Presence cannot be empty string")

    @commands.command()
    @commands.guild_only()
    @commands.has_role(config.owb_id)#decorator to see if whoever requested the command has the role specified, takes roleid argument in int or string form. 
    async def restart(self, ctx):
        file = discord.File(str(config.gifs_path+"illbeback.gif"))
        await ctx.send(file=file)
        # await ctx.send(format_markdown("Restarting Bot..."))
        restart_bot()
    
    @restart.error#error handaling for the restart function
    async def restart_error(self,ctx,error):
        if isinstance(error, commands.MissingRole):#if @commands.has_role returns with MissingRole error, send message
            await ctx.send(format_markdown("Cannot restart, \'owb\' role required"))

def setup(bot):
    bot.add_cog(Basics(bot))