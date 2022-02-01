import discord
from discord.ext import commands
from modules import config
from modules.helper_functions import format_markdown

class ModTools(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group()
    @commands.guild_only()
    @commands.has_role(config.owb_id)
    async def mod(self, ctx):
        """
        Top level command to invoke subcommands for moderators
        """
        if ctx.invoked_subcommand is None:
            await ctx.send(format_markdown("You need to use a subcommand with this command"), delete_after=10)
    
    # @commands.guild_only()
    # @commands.has_role(config.owb_id)
    # @mod.group()
    # async def yodel(self, ctx, member: discord.Member):
    #     """
    #     Puts the mentioned user in the yodeling room and queues the music.

    #     Usage example:
    #     > mod yodel @Owen Wilson Bot
    #     """
    #     if not ctx.message.mentions:
    #         await ctx.reply(format_markdown("You need to @ a user."))
    #         return
    #     if len(ctx.message.mentions) > 1:
    #         await ctx.reply(format_markdown("You can only banish one user to the yodeling room. Relax, satan."))
    #         return
    #     await member.move_to(channel=ctx.guild.get_channel(811024159806849064))
    #     await ctx.send("!play https://www.youtube.com/watch?v=YWeqHMLT27o")
    #     return

def setup(bot):
    bot.add_cog(ModTools(bot))