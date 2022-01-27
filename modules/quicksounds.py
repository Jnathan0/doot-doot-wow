from .aliases import sounds
from .errors import *


class Quicksound:
    def __init__(self, ctx, message):
        self.message = message.split("quicksounds ")[1]
        self.filtered_message = self.message.split(' ')
        self.member = ctx.message.author.id
        self.sound = self.parse_subcommand()
        self.number = self.filtered_message[1]
        self.error = self.check_exists()

    def parse_subcommand(self):
        if self.filtered_message[0] != "set":
            raise No_Argument_Error
        if int(self.filtered_message[1]) not in range(1,4):
            raise Slot_Out_Of_Bounds_Error
        if len(self.filtered_message) == 4:
            return self.filtered_message[3]
        if len(self.filtered_message) == 5:
            return str(self.filtered_message[3]+' '+self.filtered_message[4])
        else:
            raise Generic_Error

    def check_exists(self):
        if self.sound not in sounds.alias_dict.keys():
            raise Sound_Not_Exist_Error