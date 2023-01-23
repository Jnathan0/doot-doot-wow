import discord
from typing import Optional
from discord import app_commands
from discord.ext import commands
from modules.command_help import *

class Help(commands.Cog):
    def __init__(self: object, bot: object):
        self.bot = bot
        self.global_commands = self.get_global_commands()
        self.global_helpdoc = self.get_helpdoc()
        
    def get_global_commands(self):
        commands_dict = {}
        for cog in self.bot.cogs:
            for command in self.bot.get_cog(cog).get_commands():
                commands_dict[command.name] = command
        return commands_dict
        

    def get_helpdoc(self):
        embed = discord.Embed(title="Help: Commands and subcommands",
                                description=f"To get more detail on a command and its usage, use `/help <command>`\n(ex. `/help quicksounds`)",
                                color=discord.Color.green())
        for command in self.global_commands.values():
            if command.hidden:
                continue
            if "all_commands" in command.__dict__.keys():
                subcommands=""
                for subcommand in command.all_commands.values():
                    subcommands += f"{subcommand.name}\n"
                embed.add_field(name=f"{command}:", value=subcommands, inline=True)
            else:
                embed.add_field(name=command, value=command.name, inline=True)
        return embed


    @app_commands.command(name="help")
    @app_commands.describe(command='The command to get help with')
    async def help(self, interaction: discord.Interaction, command: Optional[str] = None):
        """
        Displays this message.
        Use a specific command in addition to help to view help for that command.
        e.x `help stats`
        """
        if not command:
            await interaction.response.send_message(embed=self.global_helpdoc)
            return
        if command in self.global_commands.keys():
            command = self.global_commands[command]
            await interaction.response.send_message(embed=get_command_help(command))
            return

async def setup(bot):
    await bot.add_cog(Help(bot))