import discord
from discord.ext import commands
from .aliases import sounds
from .errors import *
from .app_config import config
from .helper_functions import checkExists, update_quicksound, format_markdown



class Quicksound(discord.ui.Select):
    def __init__(self, group, filename, argument):
        self.group = group
        self.filename = filename
        self.argument = argument
        options=[
            discord.SelectOption(label="1"),
            discord.SelectOption(label="2"),
            discord.SelectOption(label="3")
            ]
        super().__init__(placeholder="Select an option",max_values=1,min_values=1,options=options)
    
    async def callback(self, interaction: discord.Interaction):
        member = interaction.user.id
        try:
            if not checkExists(self.group, self.filename):
                raise Sound_Not_Exist_Error

            config.worker_queue.enqueue(update_quicksound, member, int(self.values[0]), self.argument)

            await interaction.user.send(format_markdown(f"Quicksound {self.values[0]} updated to \"{self.argument}\"."))

        except No_Argument_Error as e:
            await interaction.user.send(format_markdown(e))
            return

        except Slot_Out_Of_Bounds_Error as e:
            await interaction.user.send(format_markdown(e))
            return

        except Generic_Error as e:
            await interaction.user.send(format_markdown(e))
            return
        
        except Sound_Not_Exist_Error as e:
            await interaction.user.send(format_markdown(e))
            return

        except Error as e:
            await interaction.user.send(format_markdown("Something happened, please notify the bot owner."))
            return

        await interaction.message.delete()
        return
