import aiohttp
import asyncio
from bs4 import BeautifulSoup
import configparser
from datetime import datetime, timedelta
import json
import os
import re

from discord.ext import commands, tasks

config = configparser.ConfigParser()
config.read('resources/config.ini')

ADMIN_CHANNEL = int(config['discord']['admin_channel'])
ADMIN_ROLE = int(config['discord']['admin_role'])
STAFF_CHANNEL = int(config['discord']['staff_channel'])
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

def is_staff(ctx):
    if ctx.author.id == 173123135321800704: 
        return True
    return ctx.author.has_role("Staff")

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.attendanceTask.start()
        self.modcheckTask.start()
        self.recruitTask.start()
    
    @commands.command(name = "reload", hidden = True)
    @commands.is_owner()
    async def _reload(self, ctx, ext: str):
        try:
            self.bot.reload_extension("cogs." + ext)
            print("\nReloaded {} extension".format(ext))
        except Exception as e:
            print("Failed to reload {} extension\n".format(ext))
            print(e)
            print("\n")

    @commands.command(name = "shutdown", hidden = True)
    @commands.is_owner()
    async def _shutdown(self, ctx):
        exit()

    @commands.command(aliases = ["addrole"])
    @commands.check(is_staff)
    async def addrank(self, ctx, *args):
        '''Create a new role'''

        roleQuery = " ".join(args)
        member = ctx.author
        roles = member.guild.roles

        for role in roles[1:]:
            if role.name.lower() == roleQuery.lower():
                await self.send_message(ctx.channel, "{} Role **{}** already exists".format(member.mention, role.name))
                return

        await member.guild.create_role(name = roleQuery, reason = "Created role through .addrank")
        await self.send_message(ctx.channel, "{} Created role **{}**".format(member.mention, roleQuery))

    @commands.command(aliases = ["removerole"])
    @commands.check(is_staff)
    async def removerank(self, ctx, *args):
        '''Remove an existing role'''

        roleQuery = " ".join(args)
        member = ctx.author
        roles = member.guild.roles

        for role in roles[1:]:
            if role.name.lower() == roleQuery.lower():
                if not (role.colour.value == 0):
                    await self.send_message(ctx.channel, "{} **{}** is a reserved role".format(member.mention, role.name))
                    return

                await role.delete(reason = "Removed role through .removerank")
                await self.send_message(ctx.channel, "{} Removed role **{}**".format(member.mention, role.name))
                return

        await self.send_message(ctx.channel, "{} Role **{}** doesn't exist".format(member.mention, roleQuery))

    @commands.command()
    @commands.check(is_staff)
    async def recruitpost(self, ctx):
        """Return or overwrite the recruitment post
        
        Usage:
            .recruitpost   
            -- Output contents of resources/recruit_post.md
            .recruitpost <<with attached file called recruit_post.md>>
            -- Overwrites resources/recruit_post.md, a backup is saved as resources/recruit_post.bak"""

        attachments = ctx.message.attachments

        if attachments == []:
            recruitPost = open('resources/recruit_post.md', 'r').read()
            introString = "Post recruitment on https://www.reddit.com/r/FindAUnit"
            outString = "{}\n```{}```".format(introString, recruitPost)

            await self.send_message(ctx.channel, outString)
        else:
            newRecruitPost = attachments[0]
            if newRecruitPost.filename == "recruit_post.md":
                try:
                    os.remove("resources/recruit_post.bak")
                except FileNotFoundError as e:
                    print("No recruit_post.bak exists, can't remove")

                try:
                    os.rename("resources/recruit_post.md", "resources/recruit_post.bak")
                except FileNotFoundError as e:
                    print("No recruit_post.md exists, can't backup")

                await newRecruitPost.save("resources/recruit_post.md")
                await self.send_message(ctx.channel, "{} {}".format(ctx.author.mention, "Recruitment post has been updated"))
                return
            else:
                await self.send_message(ctx.channel, "{} {}".format(ctx.author.mention, "File must be called recruit_post.md"))
                return

    #===Utility===#

    async def send_message(self, channel, message: str):
        """Send a message to the text channel"""

        await channel.trigger_typing()
        newMessage = await channel.send(message)

        return newMessage

    async def attendancePost(self):
        channel = self.bot.get_channel(ADMIN_CHANNEL)
        outString = "<@&{}> Collect attendance!".format(ADMIN_ROLE)

        await self.send_message(channel, outString)
            
    async def recruitmentPost(self):
        channel = self.bot.get_channel(STAFF_CHANNEL)
        recruitPost = open('resources/recruit_post.md', 'r').read()
        introString = "Post recruitment on https://www.reddit.com/r/FindAUnit"
        outString = "<@&{}> {}\n```{}```".format(ADMIN_ROLE, introString, recruitPost)

        await self.send_message(channel, outString)
    
    async def updatePost(self, name, version, url):
        channel = self.bot.get_channel(STAFF_CHANNEL)
        outString = "<@&{}> **{}** has released a new version ({})\n{}".format(ADMIN_ROLE, name, version, url)

        await self.send_message(channel, outString)
    
    async def handleGithub(self):
        repoUrl = 'https://api.github.com/repos'
        lastModified = {}

        with open('resources/last_modified.json', 'r') as f:
            lastModified = json.load(f)

        for mod in config['github']:
            print(mod)
            url = "{}/{}/releases/latest".format(repoUrl, config['github'][mod])
            if mod in lastModified['github']:
                headers = {'Authorization': GITHUB_TOKEN,
                           'If-Modified-Since': lastModified['github'][mod]}
            else:
                headers = {'Authorization': GITHUB_TOKEN}

            async with self.session.get(url, headers = headers) as response:
                if response.status == 200: #Repo has been updated
                    lastModified['github'][mod] = response.headers['Last-Modified']
                    response = await response.json()
                    await self.updatePost(mod, response['tag_name'], response['html_url'])
                elif response.status == 304: #Repo hasn't been updated
                    print('304 not changed')
                else:
                    print("{} GET error: {} {} - {}".format(mod, response.status, response.reason, response.text))
                
        with open('resources/last_modified.json', 'w') as f:
            json.dump(lastModified, f)
    
    async def handleCup(self):
        lastModified = {}

        with open('resources/last_modified.json', 'r') as f:
            lastModified = json.load(f)

        async with self.session.get('http://cup-arma3.org/download') as response:
            if response.status == 200:
                soup = BeautifulSoup(await response.text(), features = "lxml")
                for row in soup.find('table', {'class': 'table'}).find_all('tr'):
                    td = row.find('td')
                    if td:
                        version = re.search(' ([0-9.]+)(\S+)?', td.text).group(0)
                        name = re.sub(version, '', td.text)
                        version = version[1:] # Remove whitespace
                        
                        if name in lastModified['cup']:
                            if version != lastModified['cup'][name]:
                                lastModified['cup'][name] = version
                                await self.updatePost(name, version, 'http://cup-arma3.org/download')
                        else:
                            lastModified['cup'][name] = version
            else:
                print("cup GET error: {} {} - {}".format(response.status, response.reason, await response.text()))
        
        with open('resources/last_modified.json', 'w') as f:
            json.dump(lastModified, f)
    
    async def handleSteam(self):
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
                response = await response.json()
                filedetails = response['response']['publishedfiledetails']

                for mod in filedetails:
                    modName = mod['title']
                    timeUpdated = str(mod['time_updated'])

                    if modName in lastModified['steam']:
                        if timeUpdated != lastModified['steam'][modName]:
                            lastModified['steam'][modName] = timeUpdated
                            await self.updatePost(modName, "", 'https://steamcommunity.com/sharedfiles/filedetails/changelog/{}'.format(mod['publishedfileid']))
                    else:
                        lastModified['steam'][modName] = timeUpdated
            else:
                print("steam POST error: {} {} - {}".format(response.status, response.reason, await response.text()))
            
        with open('resources/last_modified.json', 'w') as f:
            json.dump(lastModified, f)
    
    #===Tasks===#

    @tasks.loop(hours = 1)
    async def attendanceTask(self):
        targetTimeslot = [17, 21] #5pm -> 9pm

        now = datetime.utcnow()
        #now = datetime(2020, 4, 25, 17)
        if now.weekday() == 5: #Saturday
            if now.hour >= targetTimeslot[0] and now.hour <= targetTimeslot[1]:
                await self.attendancePost()

    @attendanceTask.before_loop
    async def before_attendanceTask(self):
        """Sync up attendanceTask to on the hour"""

        now = datetime.utcnow()
        now = datetime(now.year, now.month, now.day, 16, 59, 55)
        future = datetime(now.year, now.month, now.day, now.hour + 1)

        await asyncio.sleep((future - now).seconds)
    
    @tasks.loop(hours = 1)
    async def modcheckTask(self):
        try:
            await self.handleGithub()
            await self.handleCup()
            await self.handleSteam()
        except Exception as e:
            print(e)

    @tasks.loop(hours = 24)
    async def recruitTask(self):
        targetDays = [0, 2, 4] #Monday, Wednesday, Friday

        now = datetime.utcnow()
        #now = datetime(2020, 4, 22) #A Wednesday
        if now.weekday() in targetDays:
            await self.recruitmentPost()

    @recruitTask.before_loop
    async def before_recruitTask(self):
        """Sync up recruitTask to targetHour:targetMinute:00"""

        targetHour = 17
        targetMinute = 0
        
        now = datetime.utcnow()
        #now = datetime(now.year, now.month, now.day, 16, 59, 55)
        future = datetime(now.year, now.month, now.day, targetHour, targetMinute)

        if now.hour >= targetHour and now.minute > targetMinute:
            future += timedelta(days = 1)

        await asyncio.sleep((future - now).seconds)
        

def setup(bot):
    bot.add_cog(Admin(bot))