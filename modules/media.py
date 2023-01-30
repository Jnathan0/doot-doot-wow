import discord
import traceback
from discord import ui
from modules.helper_functions import format_markdown

class ImageAddModal(discord.ui.Modal, title='Add Image To Existing Sound'):
    sound = discord.ui.TextInput(label='Sound Name', placeholder='sound name', style=discord.TextStyle.short, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        self.interaction = interaction
        await self.interaction.response.defer(thinking=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message(format_markdown('Error: an error occoured adding image, please contact an admin if this persists'), ephemeral=True)
        traceback.print_exception(type(error), error, error.__traceback__)


class SoundConfirmationDiag(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.confirmed = None

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.interaction = interaction
        self.confirmed = True
        self.stop()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.interaction = interaction
        self.confirmed = False
        self.stop()