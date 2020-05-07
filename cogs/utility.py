import configparser
import logging
import re

from discord.ext import commands

logger = logging.getLogger('bot')

config = configparser.ConfigParser()
config.read('resources/config.ini')

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        self.ADMIN_CHANNEL = bot.get_channel(int(config['discord']['admin_channel']))
        self.STAFF_CHANNEL = bot.get_channel(int(config['discord']['staff_channel']))
        self.TEST_CHANNEL = bot.get_channel(int(config['discord']['test_channel']))
        self.ADMIN_ROLE_ID = int(config['discord']['admin_role']) 

    async def send_message(self, channel, message: str):
        """Send a message to the text channel"""

        await channel.trigger_typing()
        newMessage = await channel.send(message)

        logger.info("Sent message to {} : {}".format(channel, newMessage.content))

        return newMessage

    def getRoles(self, ctx, reserved = False, sort = False, personal = False):
        logger.debug("getRoles called")
        
        if not personal:
            roles = ctx.message.author.guild.roles[1:]
        else:
            roles = ctx.message.author.roles[1:]

        if sort:
            roles.sort(key = self.roleListKey)

        if not reserved:
            newRoles = []
            for role in roles:
                if role.colour.value == 0:
                    newRoles.append(role)
            return newRoles
        else:
            return roles
    
    def searchRoles(self, ctx, roleQuery, autocomplete = False, reserved = False, censorReserved = True):
        logger.debug("searchRoles called")

        roles = self.getRoles(ctx, reserved = reserved)
        roleQuery = roleQuery.lower()
        candidate = None

        for role in roles:
            roleName = role.name.lower()
            if roleName == roleQuery:
                candidate = role
                break
            elif autocomplete and re.match(re.escape(roleQuery), roleName):
                candidate = role

        if candidate:
            if candidate.colour.value == 0:
                return candidate
            else:
                if censorReserved:
                    return "RESERVED"
                else:
                    return candidate
        else:
            return None

    def roleListKey(self, elem):
        return elem.name.lower()

def setup(bot):
    bot.add_cog(Utility(bot))