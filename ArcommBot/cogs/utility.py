import configparser
from datetime import datetime, timedelta
import logging
import os
import re
import string
from subprocess import CalledProcessError

from discord import File
from discord.ext import commands
from pytz import timezone, UnknownTimeZoneError


class Utility(commands.Cog):
    '''Contains useful functions that can be used in any cogs'''

    def __init__(self, bot):
        self.bot = bot
        if str(bot) != "MockBot":
            self.logger = logging.getLogger('bot')
            self.config = configparser.ConfigParser()
            self.config.read('resources/config.ini')
            self.channels = {}
            self.roles = {}
            self.cog_setup()    

    def cog_setup(self):
        for channel in self.config['channels']:
            self.channels[channel] = self.bot.get_channel(int(self.config['channels'][channel]))

        for role in self.config['roles']:
            self.roles[role] = int(self.config['roles'][role])

        self.REPO_URL = "http://108.61.34.58/main/"

    async def send_message(self, channel, message: str):
        """Send a message to the text channel"""

        await channel.trigger_typing()
        newMessage = await channel.send(message)
        self.logger.info("Sent message to %s : %s", channel, newMessage.content)

        return newMessage

    async def reply(self, message, response: str):
        """Reply to the given message"""

        await message.channel.trigger_typing()
        newMessage = await message.channel.send(response, reference = message.to_reference())
        self.logger.info("Sent message to %s : %s", message.channel, newMessage.content)

        return newMessage

    def getRoles(self, ctx, reserved = False, sort = False, personal = False):
        self.logger.debug("getRoles called")

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

        return roles

    def searchRoles(self, ctx, roleQuery, autocomplete = False, reserved = False, censorReserved = True):
        self.logger.debug("searchRoles called")

        roles = self.getRoles(ctx, reserved = reserved)
        roleQuery = roleQuery.lower()
        candidate = None

        for role in roles:
            roleName = role.name.lower()
            if roleName == roleQuery:
                candidate = role
                break

            if autocomplete and re.match(re.escape(roleQuery), roleName):
                candidate = role

        if candidate:
            if candidate.colour.value == 0:
                return candidate
            if censorReserved:
                return "RESERVED"
            return candidate

        return None

    @staticmethod
    def roleListKey(elem):
        return elem.name.lower()

    def timeUntil(self, time = "opday", modifier = 0):
        # self.logger.debug("timeUntil called with time = {}".format(time))
        today = datetime.now(tz = timezone('Europe/London'))
        opday = None

        if time == "opday":
            daysUntilOpday = timedelta((12 - today.weekday()) % 7)
            opday = today + daysUntilOpday
            opday = opday.replace(hour = 18, minute = 0, second = 0)
        elif time == "optime":
            opday = today
            opday = opday.replace(hour = 18 + modifier, minute = 0, second = 0)
            if today > opday:
                opday = opday + timedelta(days = 1)

        return opday - today

    async def getResource(self, ctx, resource):
        if resource in os.listdir("resources/"):
            await ctx.channel.send(resource, file = File("resources/{}".format(resource), filename = resource))
        else:
            await self.reply(ctx.message, "{} not in resources".format(resource))

    async def setResource(self, ctx):
        attachments = ctx.message.attachments

        if attachments == []:
            await self.reply(ctx.message, "No attachment found")
        else:
            newResource = attachments[0]
            resourceName = newResource.filename
            if resourceName in os.listdir("resources/"):
                os.remove("resources/backups/{}.bak".format(resourceName))
                os.rename("resources/{}".format(resourceName), "resources/backups/{}.bak".format(resourceName))
                await newResource.save("resources/{}".format(resourceName))

                await self.reply(ctx.message, "{} {} has been updated".format(ctx.author.mention, resourceName))
            else:
                await self.reply(ctx.message, "{} {} not in resources".format(ctx.author.mention, resourceName))

    # ===Listeners=== #

    @commands.Cog.listener()
    async def on_command(self, ctx):
        cogName = ctx.cog.qualified_name if ctx.cog is not None else None
        self.logger.info("[%s] command [%s] called by [%s]", cogName, ctx.message.content, ctx.message.author)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        errorType = type(error)

        if errorType == commands.errors.CommandNotFound:
            if ctx.message.content[1].isdigit():
                return

            puncPattern = ".[{}]+".format(re.escape(string.punctuation))
            if re.match(puncPattern, ctx.message.content):
                return

            await self.reply(ctx.message, "Command **{}** not found, use .help for a list".format(ctx.message.content))

        if not ctx.command:
            return

        command = ctx.command.name
        outString = error

        if errorType == commands.errors.MissingRequiredArgument:
            if command == "logs":
                await ctx.channel.send("Bot log", file = File("logs/bot.log", filename = "bot.log"))
                return

        elif errorType == commands.errors.ExtensionNotLoaded:
            await self.reply(ctx.message, command)
            if command == "reload":
                outString = "Cog not previously loaded"

        elif errorType == CalledProcessError:
            if command == "ping":
                outString = "Ping failed: {}".format(error.returncode)

        elif errorType == UnknownTimeZoneError:
            if command == "optime":
                outString = "Invalid timezone"

        elif errorType == commands.errors.CommandInvokeError:
            if str(error) == "Command raised an exception: ValueError: hour must be in 0..23":
                if command == "optime":
                    outString = "Optime modifier is too large"

            elif re.match("Command raised an exception: ExtensionNotLoaded:", str(error)):
                if command == "reload":
                    outString = "Cog not previously loaded"

        await self.reply(ctx.message, outString)

    @commands.Cog.listener()
    async def on_ready(self):
        print("===Bot connected/reconnected===")
        self.logger.info("===Bot connected/reconnected===")
        self.cog_setup()


def setup(bot):
    bot.add_cog(Utility(bot))
