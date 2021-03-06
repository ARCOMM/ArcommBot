import logging
import os
import re
import sys
import ArcommBot

from discord import File
from discord.ext import commands

logger = logging.getLogger('bot')

DEV_IDS = [173123135321800704, 166337116106653696]  # Sven, border


def is_dev():
    async def predicate(ctx):
        return ctx.author.id in DEV_IDS
    return commands.check(predicate)


class Dev(commands.Cog):
    '''Contains commands usable by developers'''

    def __init__(self, bot):
        self.bot = bot
        self.utility = self.bot.get_cog("Utility")

    # ===Commands=== #

    @commands.command(name = "logs", hidden = True)
    @is_dev()
    async def _logs(self, ctx, logName):
        for fileName in os.listdir("logs/"):
            if re.match(logName, fileName):
                logFile = File("logs/{}".format(fileName), filename = fileName)
                if logFile.filename != "bot.log":
                    await ctx.channel.send(fileName, file = logFile)

        # For some ungodly reason this only works if bot.log is sent at the end
        if logName == "bot":
            await ctx.channel.send("bot.log", file = File("logs/bot.log", filename = "bot.log"))

    @commands.command(name = "load", hidden = True)
    @is_dev()
    async def _load(self, ctx, ext: str):
        self.bot.load_extension("cogs." + ext)
        logger.info("=========Loaded %s extension=========", ext)
        await self.utility.reply(ctx.message, "Loaded {} extension".format(ext))

    @commands.command(name = "resources", hidden = True)
    @is_dev()
    async def _resources(self, ctx):
        outString = "```\n{}```".format("\n".join(os.listdir("resources/")))
        await self.utility.reply(ctx.message, outString)

    @commands.command(name = "getres", hidden = True)
    @is_dev()
    async def _getres(self, ctx, resource):
        await self.utility.getResource(ctx, resource)

    @commands.command(name = "setres", hidden = True)
    @is_dev()
    async def _setres(self, ctx):
        await self.utility.setResource(ctx)

    @commands.command(name = "reload", hidden = True)
    @is_dev()
    async def _reload(self, ctx, ext: str):
        self.bot.reload_extension("cogs." + ext)
        logger.info("=========Reloaded %s extension=========", ext)
        await self.utility.reply(ctx.message, "Reloaded {} extension".format(ext))

    @commands.command(name = "restart", hidden = True)
    @is_dev()
    async def _restart(self, ctx):
        print("============ RESTARTING ============")
        await self.utility.reply(ctx.message, "Restarting")
        ArcommBot.restart()

    @commands.command(name = "shutdown", hidden = True)
    @is_dev()
    async def _shutdown(self):
        sys.exit()

    @commands.command(name = "update", hidden = True)
    @is_dev()
    async def _update(self, ctx):
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

                logger.info("%s successfully updated", newCog.filename)
                await self.utility.reply(ctx.message, "{} successfully updated".format(newCog.filename))

                return newCog.filename.split(".")[0]

            logger.debug("Filename not in cogs")
        else:
            logger.debug("Found no attachment")

    @commands.command(name = "upload", hidden = True)
    @is_dev()
    async def _upload(self, ctx):
        filename = await self._update(ctx)
        await self._reload(ctx, filename)

    # ===Listeners=== #

    @commands.Cog.listener()
    async def on_ready(self):
        self.utility = self.bot.get_cog("Utility")


def setup(bot):
    bot.add_cog(Dev(bot))
