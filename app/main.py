# Setting up configuration
import os
import discord

from modules import RedisWorker
from modules import config
from modules.database import *
from datetime import datetime as dt
from discord.ext import commands
from utils import Logger


pid = os.getpid()
with open('pid.txt','w') as f:
    f.write(str(pid))

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            description="Shitposting for all! | The Soundboard | 1 in 500 chance to be rickrolled!",
            command_prefix=config.prefix,
            pm_help=True, 
            case_insensitive=True,
            help_command=None,
            intents=intents
        )
        self.initial_extensions = config.extensions

    async def setup_hook(self):
        for ext in self.initial_extensions:
            await self.load_extension("cogs." + ext)
        self.tree.copy_global_to(guild=discord.Object(id=config.guild_id))
        await self.tree.sync(guild=discord.Object(id=config.guild_id))
        
    async def close(self):
        await super().close()

    async def on_ready(self):
        # We setup the logger first
        Logger.setup_logger()

        await Logger.log("Bot startup done!", client, "INFO",
                        f'Logged in as {client.user.name} (ID: {client.user.id}) | Connected to {len(client.guilds)} '
                        f'servers with a total of {len(client.users)} users')
        await client.change_presence(activity=discord.Game(
            name=f'Type \'h for help | Prefix is {config.prefix}')) #rich presence dialog, shows up in discord in the members list when we come online

intents = discord.Intents.all()
client = MyBot()
# client.redisworker = RedisWorker()

@client.event
async def on_guild_join(guild):
    logs_channel = config.log_channel
    guild_id = str(guild.id)
    owner_id = str(guild.owner)
    owner_name = str(guild.owner.name)
    guild_name = str(guild.name)
    channel = client.get_channel(logs_channel)
    embed = discord.Embed(title="Bot was added to new server", colour=discord.Colour(0x1738d4),
                          description="DootDoot was added to new server\n" + guild_id + "\nOwned by " + owner_name +
                                      "(`" + owner_id + "`)\nGuild name: " + guild_name,
                          timestamp=dt.utcnow())
    embed.set_thumbnail(url="https://cdn.onlinewebfonts.com/svg/img_145486.png")

    await channel.send(embed=embed)
    Logger.logDebug("Bot was added to a new server mannn!", "INFO")


@client.event
async def on_guild_remove(guild):
    ch = client.get_channel(config.log_channel)
    embed = discord.Embed(title="Bot left server", colour=discord.Colour(0x1738d4),
                          description="DootDoot was removed from a server\n{} ({})\n"
                                      "Owned by {} ({})".format(guild.name, guild.id, str(guild.owner),
                                                                guild.owner.id),
                          timestamp=dt.utcnow())
    embed.set_thumbnail(url="https://cdn1.iconfinder.com/data/icons/interface-elements-ii-1/512/Logout-512.png")
    await ch.send(embed=embed)
    Logger.logDebug("Bot was removed from a server!", "INFO")


@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.startswith(config.prefix):
        command = message.content.split(config.prefix, maxsplit=1)[-1].split(maxsplit=1)[0]
        if isinstance(message.channel, discord.DMChannel):
            wheremessage = f"in the DM channel with the ID {message.channel.id}"
        elif message.guild is not None:
            wheremessage = f"in the server {message.guild.name} (`{message.guild.id}`) in the channel " \
                           f"#{message.channel.name} (`{message.channel.id}`)"
        await Logger.log(f"{message.author.name} (`{message.author.id}`) just used {command} command, "
                         f"{wheremessage}!", client, "INFO")
        await client.process_commands(message)


# Adding the cogs to the bot
if __name__ == '__main__':
    client.run(config.token)  

"""
TODO: this is for archiving pins to a specific text channel for a server.
@client.event
async def on_message_edit(before, after):
    if not before.pinned:
        archive = client.get_channel(811025342033821697)
        # pin = await ctx.channel.pins()
        msg = discord.message.id
        obj = Pin(msg)
        embedvar = discord.Embed(title=f"Author", description = f"{obj.mention}", color=0x00ff00)
        embedvar.add_field(name="Posted At", value=f"{obj.created_at.strftime('%m/%d/%Y %H:%M:%S')}", inline=True)
        embedvar.add_field(name="Jump To link", value = msg.jump_url, inline=False)
        print(obj.embed_dict)
        if obj.content is not None:
            embedvar.add_field(name="Message", value=f"{obj.content}", inline=False)
        if obj.embed_dict is not None:
            if obj.embed_dict['type'] == 'link':
                embedvar.set_thumbnail(url=obj.embed_dict['thumbnail']['url'])
                embedvar.add_field(name="Title", value=obj.embed_dict['title'], inline=True)
            if obj.embed_dict['type'] == 'video':
                embedvar.set_image(url=obj.embed_dict['thumbnail']['url'])
                embedvar.add_field(name="Title", value=obj.embed_dict['title'], inline=True)
            if obj.embed_dict['type'] == 'image':
                embedvar.set_image(url=obj.embed_dict['url'])
        if obj.attachments is not None:
            embedvar.set_image(url=obj.attachments[0].url)


        await archive.send(embed=embedvar)
"""