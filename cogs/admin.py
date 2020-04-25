import aiohttp
import asyncio
from bs4 import BeautifulSoup
import configparser
from datetime import datetime, timedelta
import json
import logging
import os
import re

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
    
    @commands.command(name = "logs", hidden = True)
    @commands.is_owner()
    async def _logs(self, ctx):
        #TODO: Send entirety of logs folder //client.send(files) seems broken
        logger.debug(".logs called")

        discordLog = File("logs/discord.log", filename = "discord.log")
        botLog = File("logs/bot.log", filename = "bot.log")
        await ctx.channel.send("Discord log", file = File("logs/discord.log", filename = "discord.log"))
        await ctx.channel.send("Bot log", file = File("logs/bot.log", filename = "bot.log"))
    
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

    @commands.command(aliases = ["addrole"])
    @commands.has_role("Staff")
    async def addrank(self, ctx, *args):
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

        await member.guild.create_role(name = roleQuery, reason = "Created role through .addrank")
        logger.info("Created '{}' role".format(roleQuery))
        await self.send_message(ctx.channel, "{} Created role **{}**".format(member.mention, roleQuery))

    @commands.command(aliases = ["removerole"])
    @commands.has_role("Staff")
    async def removerank(self, ctx, *args):
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
        #TODO: If message is too long to send (HTTPException), send a file, otherwise send message
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
        logger.info("Sent message to {} : {}".format(channel, newMessage))

        return newMessage

    async def attendancePost(self):
        logger.debug("attendancePost called")

        channel = self.bot.get_channel(ADMIN_CHANNEL)
        outString = "<@&{}> Collect attendance!".format(ADMIN_ROLE)

        await self.send_message(channel, outString)
            
    async def recruitmentPost(self, channel):
        logger.debug("recruitmentPost called")
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
                    lastModified['github'][mod] = response.headers['Last-Modified']
                    response = await response.json()
                    await self.updatePost(mod, response['tag_name'], "<{}>".format(response['html_url']))
                elif response.status == 304: #Repo hasn't been updated
                    logger.info("Response 304 - Not Changed: {}".format(mod))
                else:
                    logged.warning("{} GET error: {} {} - {}".format(mod, response.status, response.reason, await response.text()))
                
        with open('resources/last_modified.json', 'w') as f:
            json.dump(lastModified, f)
    
    async def handleCup(self):
        logger.debug("handleCup called")
        lastModified = {}

        with open('resources/last_modified.json', 'r') as f:
            lastModified = json.load(f)

        async with self.session.get('http://cup-arma3.org/download') as response:
            if response.status == 200:
                logger.info("Response 200 - Success")
                soup = BeautifulSoup(await response.text(), features = "lxml")
                for row in soup.find('table', {'class': 'table'}).find_all('tr'):
                    td = row.find('td')
                    if td:
                        version = re.search(' ([0-9.]+)(\S+)?', td.text).group(0)
                        name = re.sub(version, '', td.text)
                        version = version[1:] # Remove whitespace
                        
                        if name in lastModified['cup']:
                            if version != lastModified['cup'][name]:
                                logger.info("Mod '{}' has been updated".format(name))

                                lastModified['cup'][name] = version
                                await self.updatePost("CUP - {}".format(name), version, '<http://cup-arma3.org/download>')
                            else:
                                logger.info("Mod '{}' has not been updated".format(name))
                        else:
                            logger.debug("Mod '{}' not in lastModified".format(name))
                            lastModified['cup'][name] = version
            else:
                logger.warning("cup GET error: {} {} - {}".format(response.status, response.reason, await response.text()))
        
        with open('resources/last_modified.json', 'w') as f:
            json.dump(lastModified, f)
    
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

                            lastModified['steam'][modName] = timeUpdated
                            await self.updatePost(modName, "", '<https://steamcommunity.com/sharedfiles/filedetails/changelog/{}>'.format(mod['publishedfileid']))
                        else:
                            logger.info("Mod '{}' has not been updated".format(modName))
                    else:
                        lastModified['steam'][modName] = timeUpdated
            else:
                logger.warning("steam POST error: {} {} - {}".format(response.status, response.reason, await response.text()))
            
        with open('resources/last_modified.json', 'w') as f:
            json.dump(lastModified, f)
    
    #===Tasks===#

    @tasks.loop(hours = 1)
    async def attendanceTask(self):
        logger.debug("attendanceTask called")
        targetTimeslot = [17, 21] #5pm -> 9pm

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
        future = datetime(now.year, now.month, now.day, now.hour + 1)
        logger.debug("{} seconds until attendanceTask called".format((future - now).seconds))

        await asyncio.sleep((future - now).seconds)
    
    @tasks.loop(hours = 1)
    async def modcheckTask(self):
        #TODO: Ping once for each website, not for each post
        logger.debug("modcheckTask called")
        try:
            await self.handleGithub()
            await self.handleCup()
            await self.handleSteam()
        except Exception as e:
            logger.error(e)
    
    @tasks.loop(hours = 24)
    async def recruitTask(self):
        logger.debug("recruitTask called")
        targetDays = [0, 2, 4] #Monday, Wednesday, Friday

        now = datetime.utcnow()
        #now = datetime(2020, 4, 22) #A Wednesday
        if now.weekday() in targetDays:
            logger.debug("Called within targetDays")
            channel = self.bot.get_channel(STAFF_CHANNEL)
            await self.recruitmentPost(channel)

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
        

def setup(bot):
    bot.add_cog(Admin(bot))