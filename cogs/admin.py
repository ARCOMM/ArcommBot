import asyncio
import configparser
from datetime import datetime, timedelta
import json
import logging
import os
import re
import string
import sys
import traceback

import aiohttp
from bs4 import BeautifulSoup
from discord import File
from discord.ext import commands, tasks

logger = logging.getLogger('bot')

config = configparser.ConfigParser()
config.read('resources/config.ini')

ADMIN_CHANNEL = int(config['discord']['admin_channel'])
ADMIN_ROLE = int(config['discord']['admin_role'])
STAFF_CHANNEL = int(config['discord']['staff_channel'])
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.attendanceTask.start()
        self.modcheckTask.start()
        self.recruitTask.start()

    #===Commands===#
    
    @commands.command(name = "logs", hidden = True)
    @commands.is_owner()
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
    @commands.is_owner()
    async def _reload(self, ctx, ext: str):
        logger.debug(".reload called")
        try:
            self.bot.reload_extension("cogs." + ext)
            logger.info("=========Reloaded {} extension=========".format(ext))
            await self.send_message(ctx.channel, "Reloaded {} extension".format(ext))
        except Exception as e:
            logger.critical("Failed to reload {} extension".format(ext))
            logger.critical(e)

    @commands.command(name = "shutdown", hidden = True)
    @commands.is_owner()
    async def _shutdown(self, ctx):
        logger.debug(".shutdown called")
        exit()

    @commands.command(name = "update", hidden = True)
    @commands.is_owner()
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

    @commands.command()
    @commands.has_role("Staff")
    async def recruitpost(self, ctx):
        """Return or overwrite the recruitment post
        
        Usage:
            .recruitpost   
            -- Output contents of resources/recruit_post.md
            .recruitpost <<with attached file called recruit_post.md>>
            -- Overwrites resources/recruit_post.md, a backup is saved as resources/recruit_post.bak"""
        #TODO: If message is too long to send (HTTPException), send a file, otherwise send a message
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

    async def attendancePost(self):
        logger.debug("attendancePost called")

        channel = self.bot.get_channel(ADMIN_CHANNEL)
        outString = "<@&{}> Collect attendance!".format(ADMIN_ROLE)

        await self.send_message(channel, outString)
            
    async def recruitmentPost(self, channel, pingAdmins = False):
        logger.debug("recruitmentPost called")
        if pingAdmins:
            introString = "<@&{}> Post recruitment on <https://www.reddit.com/r/FindAUnit>"
        else:
            introString = "Post recruitment on <https://www.reddit.com/r/FindAUnit>"
        
        await channel.send(introString, file = File("resources/recruit_post.md", filename = "recruit_post.md"))
    
    async def updatePost(self, name, version, url):
        logger.debug("updatePost called")

        channel = self.bot.get_channel(STAFF_CHANNEL)
        outString = "<@&{}> **{}** has released a new version ({})\n{}".format(ADMIN_ROLE, name, version, url)

        await self.send_message(channel, outString)
    
    async def handleGithub(self):
        logger.debug("handleGithub called")

        repoUrl = 'https://api.github.com/repos'
        lastModified = {}

        with open('resources/last_modified.json', 'r') as f:
            lastModified = json.load(f)

        updatePost = ""
        repoChanged = False

        for mod in config['github']:
            url = "{}/{}/releases/latest".format(repoUrl, config['github'][mod])
            if mod in lastModified['github']:
                headers = {'Authorization': GITHUB_TOKEN,
                           'If-Modified-Since': lastModified['github'][mod]}
            else:
                headers = {'Authorization': GITHUB_TOKEN}

            async with self.session.get(url, headers = headers) as response:
                if response.status == 200: #Repo has been updated
                    logger.info("Response 200 Success: {}".format(mod))
                    repoChanged = True

                    lastModified['github'][mod] = response.headers['Last-Modified']
                    response = await response.json()

                    updatePost += "**{}** has released a new version ({})\n<{}>\n".format(mod, response['tag_name'], response['html_url'])
                elif response.status == 304: #Repo hasn't been updated
                    logger.info("Response 304 - Not Changed: {}".format(mod))
                else:
                    logged.warning("{} GET error: {} {} - {}".format(mod, response.status, response.reason, await response.text()))
                
        with open('resources/last_modified.json', 'w') as f:
            json.dump(lastModified, f)

        return repoChanged, updatePost
    
    async def handleCup(self):
        logger.debug("handleCup called")

        lastModified = {}

        with open('resources/last_modified.json', 'r') as f:
            lastModified = json.load(f)

        updatePost = ""
        repoChanged = False

        async with self.session.get('http://cup-arma3.org/download') as response:
            if response.status == 200:
                logger.info("Response 200 - Success")
                soup = BeautifulSoup(await response.text(), features = "lxml")
                for row in soup.find('table', {'class': 'table'}).find_all('tr'):
                    td = row.find('td')
                    if td:
                        version = re.search(r' ([0-9.]+)(\\S+)?', td.text).group(0)
                        name = re.sub(version, '', td.text)
                        version = version[1:] # Remove whitespace
                        
                        if name in lastModified['cup']:
                            if version != lastModified['cup'][name]:
                                logger.info("Mod '{}' has been updated".format(name))

                                repoChanged = True
                                lastModified['cup'][name] = version

                                updatePost += "**{}** has released a new version ({})\n{}\n".format("CUP - {}".format(name), version, '<http://cup-arma3.org/download>')
                            else:
                                logger.info("Mod '{}' has not been updated".format(name))
                        else:
                            logger.debug("Mod '{}' not in lastModified".format(name))
                            lastModified['cup'][name] = version
            else:
                logger.warning("cup GET error: {} {} - {}".format(response.status, response.reason, await response.text()))
        
        with open('resources/last_modified.json', 'w') as f:
            json.dump(lastModified, f)

        return repoChanged, updatePost
    
    async def handleSteam(self):
        logger.debug("handleSteam called")
        steamUrl = 'https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/' # https://partner.steamgames.com/doc/webapi/ISteamRemoteStorage
        lastModified = {}

        with open('resources/last_modified.json', 'r') as f:
            lastModified = json.load(f)

        data = {'itemcount': len(config['steam'])}

        i = 0
        for modId in config['steam']:
            data["publishedfileids[{}]".format(str(i))] = config['steam'][modId]
            i += 1    

        updatePost = ""
        repoChanged = False

        async with self.session.post(steamUrl, data = data) as response:
            if response.status == 200:
                logger.info("Response 200 - Success")
                response = await response.json()
                filedetails = response['response']['publishedfiledetails']

                for mod in filedetails:
                    modName = mod['title']
                    timeUpdated = str(mod['time_updated'])

                    if modName in lastModified['steam']:
                        if timeUpdated != lastModified['steam'][modName]:
                            logger.info("Mod '{}' has been updated".format(modName))

                            repoChanged = True
                            lastModified['steam'][modName] = timeUpdated

                            updatePost += "**{}** has released a new version ({})\n{}\n".format(modName, "", '<https://steamcommunity.com/sharedfiles/filedetails/changelog/{}>'.format(mod['publishedfileid']))
                        else:
                            logger.info("Mod '{}' has not been updated".format(modName))
                    else:
                        lastModified['steam'][modName] = timeUpdated
            else:
                logger.warning("steam POST error: {} {} - {}".format(response.status, response.reason, await response.text()))
            
        with open('resources/last_modified.json', 'w') as f:
            json.dump(lastModified, f)

        return repoChanged, updatePost
    
    #===Tasks===#

    @tasks.loop(hours = 1)
    async def attendanceTask(self):
        logger.debug("attendanceTask called")
        targetTimeslot = [17, 20] #5pm -> 8pm

        now = datetime.utcnow()
        #now = datetime(2020, 4, 25, 17)
        if now.weekday() == 5: #Saturday
            if now.hour >= targetTimeslot[0] and now.hour <= targetTimeslot[1]:
                logger.debug("Called within timeslot")
                await self.attendancePost()

    @attendanceTask.before_loop
    async def before_attendanceTask(self):
        """Sync up attendanceTask to on the hour"""
        logger.debug("before_attendanceTask called")

        now = datetime.utcnow()
        #now = datetime(now.year, now.month, now.day, 16, 59, 55)
        future = datetime(now.year, now.month, now.day, now.hour + 1, 1)
        logger.debug("{} seconds until attendanceTask called".format((future - now).seconds))

        await asyncio.sleep((future - now).seconds)
    
    @tasks.loop(hours = 1)
    async def modcheckTask(self):
        logger.debug("modcheckTask called")
        
        try:
            githubChanged, githubPost = await self.handleGithub()
            cupChanged, cupPost = await self.handleCup()
            steamChanged, steamPost = await self.handleSteam()

            if githubChanged or cupChanged or steamChanged:
                channel = self.bot.get_channel(STAFF_CHANNEL)
                await self.send_message(channel, "<@&{}>\n{}{}{}".format(ADMIN_ROLE, githubPost, cupPost, steamPost))
        except Exception as e:
            logger.error(traceback.format_exc())
    
    @tasks.loop(hours = 24)
    async def recruitTask(self):
        logger.debug("recruitTask called")
        targetDays = [0, 2, 4] #Monday, Wednesday, Friday

        now = datetime.utcnow()
        #now = datetime(2020, 4, 22) #A Wednesday
        if now.weekday() in targetDays:
            logger.debug("Called within targetDays")
            channel = self.bot.get_channel(STAFF_CHANNEL)
            await self.recruitmentPost(channel, pingAdmins = True)

    @recruitTask.before_loop
    async def before_recruitTask(self):
        """Sync up recruitTask to targetHour:targetMinute:00"""
        logger.debug("before_recruitTask called")

        targetHour = 17
        targetMinute = 0
        
        now = datetime.utcnow()
        #now = datetime(now.year, now.month, now.day, 16, 59, 55)
        future = datetime(now.year, now.month, now.day, targetHour, targetMinute)

        if now.hour >= targetHour and now.minute > targetMinute:
            logger.debug("Missed timeslot, adding a day")
            future += timedelta(days = 1)

        logger.debug("{} seconds until recruitTask called".format((future - now).seconds))

        await asyncio.sleep((future - now).seconds)
        
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