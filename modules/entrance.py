from modules.app_config import config
from modules.errors import *

class Entrance:
    def __init__(self, ctx, message):
        self.message = message.split(config.prefix+"entrance ")[1]
        self.filtered_message = self.message.split(" ")
        self.member = ctx.message.author.id
        self.subcommand_list = ['set', 'remove', 'info']
        self.message_subcommand = self.parse_subcommand()
      
    def parse_subcommand(self):
        message_set = set(self.filtered_message)
        subcommand_set = set(self.subcommand_list)
        x = len(message_set.intersection(subcommand_set))
        if x == 0:
            raise No_Argument_Error
        if x > 1:
            raise Multiple_Argument_Error
        return self.message.split(" ")[0]

    def get_entrance_alias(self):
        return self.message.split("set ")[1]