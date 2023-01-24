import discord
from discord.ui import View
from discord import ui
from typing import Optional, List

class ButtonMenu(View):
    def __init__(self, pages: list, timeout: float, user: Optional[discord.Member]=None) -> None:
        super().__init__(timeout=timeout)
        self.current_page=0
        self.pages = pages
        self.user = user
        self.length = len(self.pages)-1
    
    async def getPage(self, page):
        if isinstance(page, str):
            return page, [], []
        elif isinstance(page, discord.Embed):
            return None, [page], []
        elif isinstance(page, discord.File):
            return None, [], [page]
        elif isinstance(page, List):
            if all(isinstance(x ,discord.Embed) for x in page):
                return None, page, []
            if all(isinstance(x, discord.File) for x in page):
                return None, [], page
            else:
                raise TypeError("Can't have alternative files and embeds")
        else:
            print("buttonmenu error")
            pass

    async def showPage(self, page: int, interaction: discord.Interaction):
        content, embeds, files = await self.getPage(self.pages[page])
        await interaction.response.edit_message(
            content = content,
            view=self
        )

    @ui.button(emoji="◀️", style=discord.ButtonStyle.blurple)
    async def previous_page(self, interaction, button):
        await self.showPage(self.current_page-1, interaction)

    @ui.button(emoji="▶️", style=discord.ButtonStyle.blurple)
    async def next_page(self, interaction, button):
        await self.showPage(self.current_page+1, interaction)

