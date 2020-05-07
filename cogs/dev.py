import logging
import os
import re
import string
import sys

from discord import File
from discord.ext import commands

logger = logging.getLogger('bot')

DEV_IDS = [173123135321800704, 166337116106653696] # Sven, border

def is_dev():
    async def predicate(ctx):
        return ctx.author.id in DEV_IDS
    return commands.check(predicate)

class Dev(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.utility = bot.get_cog("Utility")

    #===Commands===#

    @commands.command(name = "logs", hidden = True)
    @is_dev()
    async def _logs(self, ctx, logName):
        logger.debug(".logs called")

        for fileName in os.listdir("logs/"):
            if re.match(logName, fileName):
                logFile = File("logs/{}".format(fileName), filename = fileName)
                if logFile.filename != "bot.log":
                    await ctx.channel.send(fileName, file = logFile)

        # For some ungodly reason this only works if bot.log is sent at the end
        if logName == "bot":
            await ctx.channel.send("bot.log", file = File("logs/bot.log", filename = "bot.log"))
    
    @commands.command(name = "reload", hidden = True)
    @is_dev()
    async def _reload(self, ctx, ext: str):
        logger.debug(".reload called")
        try:
            self.bot.reload_extension("cogs." + ext)
            logger.info("=========Reloaded {} extension=========".format(ext))
            await self.utility.send_message(ctx.channel, "Reloaded {} extension".format(ext))
        except Exception as e:
            logger.critical("Failed to reload {} extension".format(ext))
            logger.critical(e)
            await self.utility.send_message(ctx.channel, e)

    @commands.command(name = "shutdown", hidden = True)
    @commands.is_owner()
    async def _shutdown(self, ctx):
        logger.debug(".shutdown called")
        exit()

    @commands.command(name = "update", hidden = True)
    @is_dev()
    async def _update(self, ctx):
        logger.debug(".updatecog called")
        attachments = ctx.message.attachments

        if attachments != []:
            logger.debug("Found attachment")
            newCog = attachments[0]
            cogs = os.listdir("cogs/")

            if newCog.filename in cogs:
                logger.debug("Found filename in cogs")
                tempFilename = "cogs/temp_{}".format(newCog.filename)

                logger.debug("Saving temp file")
                await newCog.save(tempFilename)

                logger.debug("Replacing cog file")
                os.replace(tempFilename, "cogs/{}".format(newCog.filename))

                logger.info("{} successfully updated".format(newCog.filename))
                await self.utility.send_message(ctx.channel, "{} successfully updated".format(newCog.filename))
            else:
                logger.debug("Filename not in cogs")
        else:
            logger.debug("Found no attachment")

    #===Listeners===#

    @commands.Cog.listener()
    async def on_command(self, ctx):
        command = ctx.message.content
        author = ctx.message.author
        cogName = ctx.cog.qualified_name if ctx.cog != None else None
        logger.info("[{}] command [{}] called by [{}]".format(cogName, command, author))

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        logger.debug("on_command_error called")
        errorType = type(error)

        if errorType == commands.errors.CommandNotFound:
            puncPattern = ".[{}]+".format(re.escape(string.punctuation))
            if not (re.match(puncPattern, ctx.message.content)):
                logger.debug("Command [{}] not found".format(ctx.message.content))
                await self.utility.send_message(ctx.channel, "Command **{}** not found, use .help for a list".format(ctx.message.content))
                return
        
        if not ctx.command: return
        command = ctx.command.name

        if command == "optime" and errorType == commands.errors.CommandInvokeError:
            logger.debug("Optime modifier is too large")
            await self.utility.send_message(ctx.channel, "Optime modifier is too large")
        else:
            logger.warning(error)
            await self.utility.send_message(ctx.channel, error)

            botLog = File("logs/bot.log", filename = "bot.log")
            await ctx.channel.send("Bot log", file = File("logs/bot.log", filename = "bot.log"))

    @commands.Cog.listener()
    async def on_error(self, event):
        exc = sys.exc_info()
        logger.warning("Type [{}], Value [{}]\nTraceback[{}]".format(exc[0], exc[1], exc[2]))
    
    @commands.Cog.listener()
    async def on_ready(self):
        print("===Bot connected/reconnected===")
        logger.info("===Bot connected/reconnected===")

def setup(bot):
    bot.add_cog(Dev(bot))