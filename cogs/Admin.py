import discord
from discord.ext import commands
from modules import config
from modules.helper_functions import format_markdown

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
    async def setpresence(self, ctx, *, content):
        if len(content) > 0:
            await self.bot.change_presence(activity=discord.Game(name=content))
            await ctx.send(f"Presence changed to:\n{format_markdown(content)}", delete_after=10)
        else:
            await ctx.send(format_markdown("Presence cannot be empty string."), delete_after=10)



def setup(bot):
    bot.add_cog(Admin(bot))