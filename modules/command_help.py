import discord

def get_command_help(command):
    """
    function gets description of top level command and any subsequent sub-commands
    returns string
    """
    command_desc = f"{command.name}: \n\t{command.help}\n"
    return command_desc

def get_subcommand_help(subcommand):
    return f"{subcommand.name}:\n\t{subcommand.help}"