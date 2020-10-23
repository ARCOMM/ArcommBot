import configparser
import logging
import os
import re
import string

from discord import File
from discord.ext import commands
from datetime import datetime, timedelta
from pytz import timezone

logger = logging.getLogger('bot')

config = configparser.ConfigParser()
config.read('resources/config.ini')

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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

    def timeUntil(self, time = "opday", modifier = 0):
        #logger.debug("timeUntil called with time = {}".format(time))
        today = datetime.now(tz = timezone('Europe/London'))
        opday = None

        if time == "opday":
            daysUntilOpday = timedelta((12 - today.weekday()) % 7)
            opday = today + daysUntilOpday
            opday = opday.replace(hour = 18, minute = 0, second = 0)
        elif time == "optime":
            opday = today
            opday = opday.replace(hour = 18 + modifier, minute = 0, second = 0)
            if (today > opday):
                opday = opday.replace(day = opday.day + 1)

        return opday - today
    
    async def getResource(self, ctx, resource):
        if resource in os.listdir("resources/"):
            await ctx.channel.send(resource, file = File("resources/{}".format(resource), filename = resource))
        else:
            await self.send_message(ctx.channel, "{} not in resources".format(resource))

    async def setResource(self, ctx):
        attachments = ctx.message.attachments

        if attachments == []:
            await self.send_message(ctx.channel, "No attachment found")
        else:
            newResource = attachments[0]
            resourceName = newResource.filename
            if resourceName in os.listdir("resources/"):
                try:
                    os.remove("resources/backups/{}.bak".format(resourceName))
                    logger.debug("Removed {}.bak".format(resourceName))
                except FileNotFoundError as e:
                    logger.debug("No {}.bak exists, can't remove".format(resourceName))

                try:
                    os.rename("resources/{}".format(resourceName), "resources/backups/{}.bak".format(resourceName))
                    logger.info("Saved {} to {}.bak".format(resourceName, resourceName))
                except FileNotFoundError as e:
                    logger.debug("No {} exists, can't backup".format(resourceName))

                await newResource.save("resources/{}".format(resourceName))
                await self.send_message(ctx.channel, "{} {} has been updated".format(ctx.author.mention, resourceName))
            else:
                await self.send_message(ctx.channel, "{} {} not in resources".format(ctx.author.mention, resourceName))

    #===Listeners===#

    @commands.Cog.listener()
    async def on_command(self, ctx):
        cogName = ctx.cog.qualified_name if ctx.cog != None else None
        logger.info("[{}] command [{}] called by [{}]".format(cogName, ctx.message.content, ctx.message.author))

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        errorType = type(error)

        if errorType == commands.errors.CommandNotFound:
            puncPattern = ".[{}]+".format(re.escape(string.punctuation))
            if not (re.match(puncPattern, ctx.message.content)):
                logger.debug("Command [{}] not found".format(ctx.message.content))
                await self.send_message(ctx.channel, "Command **{}** not found, use .help for a list".format(ctx.message.content))
            return

        if not ctx.command: return
        command = ctx.command.name

        if errorType == commands.errors.MissingRequiredArgument:
            if command == "logs":
                await ctx.channel.send("Bot log", file = File("logs/bot.log", filename = "bot.log"))
            else:
                await self.send_message(ctx.channel, error)

        elif (command == "optime") and (str(error) == "Command raised an exception: ValueError: hour must be in 0..23"):
            logger.debug("Optime modifier is too large")
            await self.send_message(ctx.channel, "Optime modifier is too large")
        else:
            logger.warning(error)
            await self.send_message(ctx.channel, error)  

    @commands.Cog.listener()
    async def on_ready(self):
        print("===Bot connected/reconnected===")
        logger.info("===Bot connected/reconnected===")

        self.ADMIN_CHANNEL = self.bot.get_channel(int(config['discord']['admin_channel']))
        self.ANNOUNCE_CHANNEL = self.bot.get_channel(int(config['discord']['announce_channel']))
        self.FOOTAGE_CHANNEL = self.bot.get_channel(int(config['discord']['footage_channel']))
        self.OP_NEWS_CHANNEL = self.bot.get_channel(int(config['discord']['op_news_channel']))
        self.STAFF_CHANNEL = self.bot.get_channel(int(config['discord']['staff_channel']))
        self.TEST_CHANNEL = self.bot.get_channel(int(config['discord']['test_channel']))

        self.ADMIN_ROLE_ID = int(config['discord']['admin_role'])
        self.RECRUIT_ROLE_ID = int(config['discord']['recruit_role'])
        self.TDG_ROLE_ID = int(config['discord']['tdg_role'])
        self.TRAINING_ROLE_ID = int(config['discord']['training_role']) 

def setup(bot):
    bot.add_cog(Utility(bot))