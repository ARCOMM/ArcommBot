from enum import Enum

from cogs.utility import Utility

class LogSeverity(Enum):
    DEBUG = 0
    INFO = 1

class MockLog():
    def __init__(self, severity, message):
        self.severity = severity
        self.message = message

class MockLogger():
    def __init__(self):
        self.logs = []

    def _log(self, severity, message, args):
        self.logs.append(MockLog(severity, message % args))

    def debug(self, message, *args):
        self._log(LogSeverity.DEBUG, message, args)

    def info(self, message, *args):
        self._log(LogSeverity.INFO, message, args)

    def findLog(self, severity, message):
        for log in self.logs:
            if log.severity == severity and log.message == message:
                return True
        return False

class MockBot():
    def __init__(self, logger):
        self.logger = logger
        self.utility = Utility(self)
        self.utility.logger = logger

    def __str__(self):
        return "MockBot"

    def get_cog(self, cog):
        if cog == "Utility":
            return self.utility

class MockMessage():
    def __init__(self, channel, content, reference, author):
        self.channel = channel
        self.content = content
        self.reference = reference
        self.author = author

    def to_reference(self):
        return self

class MockChannel():
    def __init__(self, name):
        self.name = name
        self.typing = False

    def __str__(self):
        return self.name

    async def trigger_typing(self):
        self.typing = True

    async def send(self, content, reference = None, author = None):
        self.typing = False
        return MockMessage(self, content, reference, author)

class MockContext():
    def __init__(self, message, cog = None):
        self.message = message
        self.cog = cog
        self.author = message.author

class MockUser():
    def __init__(self, guild, name, roles = [], nick = None):
        self.guild = guild
        self.name = name
        self.roles = roles
        self.nick = nick
        self.mention = "<&{}>".format(name)

        self.guild.users.append(self)
        for role in self.roles:
            role.members.append(self)
    
    def __str__(self):
        return self.name

    async def mock_send(self, channel, content, reference = None):
        return await channel.send(content, reference, self)

class MockGuild():
    def __init__(self, name, channels = [], roles = []):
        self.name = name
        self.channel = channels
        self.roles = roles
        self.users = []

class MockRole():
    def __init__(self, name, colour):
        self.name = name
        self.colour = colour
        self.members = []

    def __str__(self):
        return f"{self.name}:{self.colour}"

    def __eq__(self, other): 
        if not isinstance(other, MockRole):
            return NotImplemented
        return self.name == other.name and self.colour == other.colour

class MockColour():
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)
    
    def __eq__(self, other):
        if not isinstance(other, MockColour):
            return NotImplemented
        return self.value == other.value

class MockCog():
    def __init__(self, qualified_name):
        self.qualified_name = qualified_name
