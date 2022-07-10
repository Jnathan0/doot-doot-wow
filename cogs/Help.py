import discord
from modules.command_help import *
from modules import config
from discord.ext import commands

class Help(commands.Cog):
    def __init__(self: object, bot: object):
        self.bot = bot
        self.global_helpdoc = self.get_helpdoc()

    def get_helpdoc(self):
        pass
        # helpdoc = ""
        # for cog in self.bot.cogs:
        #     print(f"{cog}\n")
        #     for command in self.bot.get_cog(cog).get_commands():
        #         print(f"{command.all_commands.items()}\n")

    @commands.command(aliases=['h'])
    async def help(self, ctx):
        """
        Displays this message.
        """
        cogs_desc = ""
        embed = discord.Embed(title="Commands and subcommands",
                                description=f"To get more detail on a command and its usage, use `{config.prefix}help <command>`\n(ex. `{config.prefix}help quicksounds`)",
                                color=discord.Color.green())
        for cog in self.bot.cogs:
            for command in self.bot.get_cog(cog).get_commands():
                if command.hidden:
                    continue
                cogs_desc += (get_command_help(command))
                if "all_commands" in command.__dict__.keys():
                    subcommands=""
                    for subcommand in command.all_commands.values():
                        subcommands += f"{subcommand.name}\n"
                    embed.add_field(name=f"{command}:", value=subcommands, inline=True)
                else:
                    embed.add_field(name=command, value=command.name, inline=True)
        await ctx.send(embed=embed)
            

def setup(bot):
    bot.add_cog(Help(bot))