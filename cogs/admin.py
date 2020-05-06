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

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
            await self.send_message(ctx.channel, "Reloaded {} extension".format(ext))
        except Exception as e:
            logger.critical("Failed to reload {} extension".format(ext))
            logger.critical(e)
            await self.send_message(ctx.channel, e)

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
                await self.send_message(ctx.channel, "{} successfully updated".format(newCog.filename))
            else:
                logger.debug("Filename not in cogs")
        else:
            logger.debug("Found no attachment")
    
    @commands.command(aliases = ["addrank", "newrank", "newrole", "createrank", "createrole"])
    @commands.has_role("Staff")
    async def addrole(self, ctx, *args):
        '''Create a new role'''
        logger.debug(".addrank called")

        roleQuery = " ".join(args)
        member = ctx.author
        roles = member.guild.roles

        for role in roles[1:]:
            if role.name.lower() == roleQuery.lower():
                logger.info("Role '{}' already exists".format(role.name))
                await self.send_message(ctx.channel, "{} Role **{}** already exists".format(member.mention, role.name))
                return

        await member.guild.create_role(name = roleQuery, reason = "Created role through .addrank", mentionable = True)
        logger.info("Created '{}' role".format(roleQuery))
        await self.send_message(ctx.channel, "{} Created role **{}**".format(member.mention, roleQuery))

    @commands.command(aliases = ["removerank", "delrank", "delrole", "deleterank", "deleterole"])
    @commands.has_role("Staff")
    async def removerole(self, ctx, *args):
        '''Remove an existing role'''
        logger.debug('.removerank called')

        roleQuery = " ".join(args)
        member = ctx.author
        roles = member.guild.roles

        for role in roles[1:]:
            if role.name.lower() == roleQuery.lower():
                logger.debug("Role '{}' found".format(roleQuery))
                if not (role.colour.value == 0):
                    logger.info("Role '{}' is a reserve role".format(role.name))
                    await self.send_message(ctx.channel, "{} **{}** is a reserved role".format(member.mention, role.name))
                    return

                await role.delete(reason = "Removed role through .removerank")
                logger.info("Removed '{}' role".format(role.name))
                await self.send_message(ctx.channel, "{} Removed role **{}**".format(member.mention, role.name))
                return

        logger.info("Role '{}' doesn't exist".format(role.name))
        await self.send_message(ctx.channel, "{} Role **{}** doesn't exist".format(member.mention, roleQuery))

    @commands.command(aliases = ["renamerank", "rename"])
    @commands.has_role("Staff")
    async def renamerole(self, ctx, oldName, newName):
        '''Rename an existing role
            
           Usage: 
                rename "old name" "new name"
        '''
        member = ctx.author
        roles = member.guild.roles
        role = self.searchRoles(oldName, roles)

        if role != None:
            if role.color.value == 0:
                oldRoleName = str(role.name)
                await role.edit(name = newName)
                await self.send_message(ctx.channel, "{} Renamed **{}** to **{}**".format(member.mention, oldRoleName, role.name))
            else:
                await self.send_message(ctx.channel, "{} **{}** is a reserved role".format(member.mention, role.name))
        else:
            await self.send_message(ctx.channel, "{} Role **{}** does not exist".format(member.mention, roleQuery))
    
    @commands.command()
    @commands.has_role("Staff")
    async def recruitpost(self, ctx):
        """Return or overwrite the recruitment post
        
        Usage:
            .recruitpost   
            -- Output contents of resources/recruit_post.md
            .recruitpost <<with attached file called recruit_post.md>>
            -- Overwrites resources/recruit_post.md, a backup is saved as resources/recruit_post.bak"""
        logger.debug('.recruitpost called')

        attachments = ctx.message.attachments

        if attachments == []:
            await self.recruitmentPost(ctx.channel)
        else:
            logger.debug("Found attachment")
            newRecruitPost = attachments[0]
            if newRecruitPost.filename == "recruit_post.md":
                logger.debug("Attachment '{}' has correct name".format(newRecruitPost.filename))
                try:
                    os.remove("resources/recruit_post.bak")
                    logger.debug("Removed recruit_post.bak")
                except FileNotFoundError as e:
                    logger.debug("No recruit_post.bak exists, can't remove")

                try:
                    os.rename("resources/recruit_post.md", "resources/recruit_post.bak")
                    logger.info("Saved recruit_post.md to recruit_post.bak")
                except FileNotFoundError as e:
                    logger.debug("No recruit_post.md exists, can't backup")

                await newRecruitPost.save("resources/recruit_post.md")
                logger.info("Saved new recruit_post.md")
                await self.send_message(ctx.channel, "{} {}".format(ctx.author.mention, "Recruitment post has been updated"))
                return
            else:
                logger.debug("Attachment '{}' has incorrect name".format(newRecruitPost.filename))
                await self.send_message(ctx.channel, "{} {}".format(ctx.author.mention, "File must be called recruit_post.md"))
                return

    #===Utility===#

    async def send_message(self, channel, message: str):
        """Send a message to the text channel"""

        await channel.trigger_typing()
        newMessage = await channel.send(message)

        logger.info("Sent message to {} : {}".format(channel, newMessage.content))

        return newMessage
        
    async def recruitmentPost(self, channel, pingAdmins = False):
        logger.debug("recruitmentPost called")
        if pingAdmins:
            introString = "<@&{}> Post recruitment on <https://www.reddit.com/r/FindAUnit>".format(ADMIN_ROLE)
        else:
            introString = "Post recruitment on <https://www.reddit.com/r/FindAUnit>"
        
        await channel.send(introString, file = File("resources/recruit_post.md", filename = "recruit_post.md"))
    
    def searchRoles(self, roleQuery, roles):
        logger.debug("searchRoles called")
        roleQuery = roleQuery.lower()

        for role in roles:
            roleName = role.name.lower()
            if roleName == roleQuery:
                return role
        return None
    
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
                await self.send_message(ctx.channel, "Command **{}** not found, use .help for a list".format(ctx.message.content))
                return
        
        if not command: return
        command = ctx.command.name

        if command == "optime" and errorType == commands.errors.CommandInvokeError:
            logger.debug("Optime modifier is too large")
            await self.send_message(ctx.channel, "Optime modifier is too large")
        else:
            logger.warning(error)
            await self.send_message(ctx.channel, error)

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
    bot.add_cog(Admin(bot))