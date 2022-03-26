
class Error(Exception):
    pass

class Arguement_Not_Exist_Error(Error):
    def __init__(self, message="Error: sub command does not exist"):
        self.message = message

    def __str__(self):
        return f"{self.message} \"{self.item}\""

class No_Argument_Error(Error):
    def __init__(self, message="Error: no sub command listed."):
        self.message = message
    
    def __str__(self):
        return f"{self.message}"


class Multiple_Argument_Error(Error):
    def __init__(self, message="Error: Too many subcommands entered."):
        self.message = message

    def __str__(self):
        return f"{self.message}"

class Slot_Out_Of_Bounds_Error(Error):
    def __init__(self, message="Error: Quicksound slot not 1-3"):
        self.message = message

    def __str__(self):
        return f"{self.message}"

class Generic_Error(Error):
    def __init__(self, message="Error: This is a generic error, you probably did something wrong."):
        self.message = message
    
    def __str__(self):
        return f"{self.message}"
class Directory_Not_Found_Error(Error):
    def __init__(self, message="Error: Configuration Directory not found", ):
        self.message = message

    def __str__(self):
        return f"{self.message}"

class File_Not_Found_Error(Error):
    def __init__(self, message="Error: Configuration File not found", ):
        self.message = message

    def __str__(self):
        return f"{self.message}"

class Sound_Not_Exist_Error(Error):
    def __init__(self, message="Error: Sound name does not exist, please try using the name of a sound that does exist"):
        self.message = message

    def __str__(self):
        return f"{self.message}"

class No_Attachment_Error(Error):
    def __init__(self, message = "Error: No attachment was included in the message."):
        self.message = message
    
    def __str__(self):
        return f"{self.message}"

class Config_Key_Not_Exist_Error(Error):
    def __init__(self, config_key, message = "Error: No valid config key found in config.json")
        self.message = message

    def __str__(self):
        return f"{self.message} {config_key}"

class Image_Too_Large_Error(Error):
    """
    Error to handle when an attempted image upload is larger than the max file size
    in bytes defined in conifg.js

    Parameters:
        size_limit: The Upper size limit in Megabytes
    """
    def __init__(self, size_limit, message = f"Error: Image file size too large, try uploading with a size smaller than"):
        self.message = message
        self.size_limit = size_limit

    def __str__(self):
        return f"{self.message} {self.size_limit} MB"