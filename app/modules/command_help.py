import discord

def get_command_help(command):
    """
    function gets description of top level command and any subsequent sub-commands
    returns discord embed
    """
    embed = discord.Embed(
        title=command.name,
        description=command.help,
        color=discord.Color.green()
    )
    if "all_commands" in command.__dict__.keys():
        for subcommand in command.all_commands.values():
            embed.add_field(
                name=subcommand.name,
                value=subcommand.help,
                inline=False
                )
    return embed

def get_subcommand_help(subcommand):
    """
    function gets description of a subcommand.
    Returns discord embed
    """
    embed = discord.Embed(
        title={subcommand.name},
        descrption={subcommand.help},
        color=discord.Color.green()
        )
    return embed