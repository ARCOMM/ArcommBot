import configparser
from datetime import datetime, timedelta
import logging
import os
import re
import subprocess
import sqlite3

import aiohttp
from bs4 import BeautifulSoup
import discord
from discord.ext import commands
from pytz import timezone, UnknownTimeZoneError
from twitchAPI import Twitch

logger = logging.getLogger('bot')

config = configparser.ConfigParser()
config.read('resources/config.ini')

TWITCH_ID = os.getenv('TWITCH_ID')
TWITCH_SECRET = os.getenv('TWITCH_SECRET')

twitch = Twitch(TWITCH_ID, TWITCH_SECRET)
twitch.authenticate_app([])

EXTRA_TIMEZONES = {
    "PT" : "America/Los_Angeles",
    "PST": "ETC/GMT+8",
    "PDT": "ETC/GMT+7",
    "MT" : "America/Denver",
    "MST": "ETC/GMT+7",
    "MDT": "ETC/GMT+6",
    "CT" : "America/Chicago",
    "CST": "ETC/GMT+6",
    "CDT": "ETC/GMT+5",
    "ET" : "America/New_York",
    "EST": "ETC/GMT+5",
    "EDT": "ETC/GMT+4"
}

class ClipsDB():
    def __init__(self):
        self.conn = sqlite3.connect('resources/clips.db')
        #self.remake()

    def remake(self):
        c = self.conn.cursor()
        try:
            #c.execute("DROP TABLE clips")
            c.execute("CREATE TABLE clips (link STRING PRIMARY KEY, broadcaster STRING NOT NULL, title STRING NOT NULL, video_id INTEGER, date TEXT NOT NULL, time TEXT NOT NULL, type STRING)")
        except Exception as e:
            print(e)

    def storeClip(self, link, broadcaster, title, video_id, date, time, _type):
        c = self.conn.cursor()

        try:
            c.execute("INSERT OR IGNORE INTO clips (link, broadcaster, title, video_id, date, time, type) VALUES(?, ?, ?, ?, ?, ?, ?)", (link, broadcaster, title, video_id, date, time, _type))
        except Exception as e:
            None

        self.conn.commit()

    def searchClips(self, searchQuery):
        c = self.conn.cursor()
        try:
            c.execute("SELECT * FROM clips {}".format(searchQuery))
            results = c.fetchall()
        except Exception as e:
            return e

        return results


class Public(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.clips = ClipsDB()
        self.utility = self.bot.get_cog("Utility")
        self.session = aiohttp.ClientSession()

    #===Commands===#

    @commands.command()
    async def clips(self, ctx, *args):
        searchQuery = " ".join(args)
        results = self.clips.searchClips(searchQuery)
        resultString = ""
        for result in results:
            resultString += (str(result) + "\n")
        results = "```{}```".format(results)

        await self.utility.send_message(ctx.channel, str(results))

    @commands.command(aliases = ['daylightsavings'])
    async def dst(self, ctx):
        """Check if daylight savings has started (in London)"""

        outString = "DST is in effect" if datetime.now(timezone("Europe/London")).dst() else "DST is ***not*** in effect"
        await self.utility.send_message(ctx.channel, outString)

    @commands.command()
    async def members(self, ctx, *args):
        '''Get a list of members in a role
            
            Usage:
                .members rolename
        '''

        roleQuery = " ".join(args)
        role = self.utility.searchRoles(ctx, roleQuery, reserved = True, censorReserved = False)
        
        if role:
            outString = ""
            members = role.members
            members.sort(key = self.utility.roleListKey)

            for member in members:
                outString += "{} ;{}\n".format(member.nick, member.name) if (member.nick != None) else "{}\n".format(member.name)

            await self.utility.send_message(ctx.channel, "```ini\n[ {} ]\n{}```".format(role.name, outString))
        else:
            await self.utility.send_message(ctx.channel, "{} Role **{}** does not exist".format(ctx.author.mention, roleQuery))
    
    @commands.command(aliases = ['myranks'])
    async def myroles(self, ctx):
        """Get a list of roles you're in"""

        roles = self.utility.getRoles(ctx, reserved = True, sort = True, personal = True)
        outString = ""

        for role in roles:
            outString += "{}\n".format(role.name)

        await self.utility.send_message(ctx.channel, "```\n{}```".format(outString))

    @commands.command(aliases = ['opday'])
    async def opstart(self, ctx):
        """Time left until opday (Saturday optime)"""

        dt = self.utility.timeUntil("opday")
        dt = self.formatDt(dt)        
        outString = "Opday starts in {}!".format(dt)
        
        await self.utility.send_message(ctx.channel, outString)

    @commands.command(aliases = ['op'])
    async def optime(self, ctx, modifier = '0', timez = None):
        """Time left until optime

        Usage:
            optime
            optime +x
            optime timezone
            optime -x timezone
            Timezones can be: CET or Europe/London or US/Pacific etc.
        """

        try:
            modifier = int(modifier)
        except Exception as e:
            logger.debug(".optime modifier was not an int, assume timezone")
            timez = modifier
            modifier = 0

        dt = self.utility.timeUntil("optime", modifier)
        dt = self.formatDt(dt)

        if modifier == 0:
            outString = "Optime starts in {}!".format(dt)
        elif modifier > 0:
            outString = "Optime +{} starts in {}!".format(modifier, dt)
        else:
            outString = "Optime {} starts in {}!".format(modifier, dt)
      
        if timez != None:
            try:
                if timez.upper() in EXTRA_TIMEZONES:
                    timez = timezone(EXTRA_TIMEZONES[timez.upper()])
                else:
                    timez = timezone(timez)
                localTime = datetime.now(tz = timezone('Europe/London')).replace(hour = 18 + modifier)
                localTime = localTime.astimezone(timez)
                outString += "\n({}:00:00 {})".format(localTime.hour, timez.zone)
            except UnknownTimeZoneError as e:
                logger.debug("Invalid timezone: {}".format(timezone))
                await self.utility.send_message(ctx.channel, "Invalid timezone")
                return

        await self.utility.send_message(ctx.channel, outString)
            
    @commands.command()
    async def ping(self, ctx, host = None):
        """Check bot response, or ping host/ip address

        Usage:
            .ping
            --return Pong!
            .ping host
            --ping host ip/address
        """

        if host == None:
            await self.utility.send_message(ctx.channel, "Pong!")
        else:
            await self.utility.send_message(ctx.channel, "Pinging...")
            try:
                p = subprocess.check_output(['ping', host])
            except subprocess.CalledProcessError as e:
                logger.warning(e)
                await self.utility.send_message(ctx.channel, "Ping failed: {}".format(e.returncode))
                return
            await self.utility.send_message(ctx.channel, "```{}```".format(p.decode("utf-8")))
    
    @commands.command(aliases = ['rank'])
    async def role(self, ctx, *args):
        """Join or leave a role (with autocomplete)
        Usage:
            .role rolename
            --Join or leave rolename

            .role ro
            --Join or leave rolename
        """

        roleQuery = " ".join(args)
        member = ctx.author
        role = self.utility.searchRoles(ctx, roleQuery, autocomplete = True, reserved = True)

        if role:
            if role != "RESERVED":
                if role in member.roles:
                    await member.remove_roles(role, reason = "Remove role through .role command")
                    await self.utility.send_message(ctx.channel, "{} You've left **{}**".format(member.mention, role.name))
                else:
                    await member.add_roles(role, reason = "Added role through .role command")
                    await self.utility.send_message(ctx.channel, "{} You've joined **{}**".format(member.mention, role.name))
            else:
                await self.utility.send_message(ctx.channel, "{} Role **{}** is reserved".format(member.mention, roleQuery))
        else:
            await self.utility.send_message(ctx.channel, "{} Role **{}** does not exist".format(member.mention, roleQuery))

    @commands.command(aliases = ['ranks'])
    async def roles(self, ctx):
        """Get a list of joinable roles"""

        longestName = 0
        roleList = []

        for role in self.utility.getRoles(ctx, reserved = False, sort = True):
            roleList.append(role)
            if len(role.name) > longestName:
                longestName = len(role.name)
        
        outString = ""

        for role in roleList:
            numOfMembers = str(len(role.members))
            nameSpaces = " " * (longestName + 1 - len(role.name))
            numSpaces = " " * (3 - len(numOfMembers))
            outString += "{}{}-{}{} members\n".format(role.name, nameSpaces, numSpaces, numOfMembers)

        await self.utility.send_message(ctx.channel, "```\n{}```".format(outString))

    @commands.command(aliases = ['wiki'])
    async def sqf(self, ctx, *args):
        """Find a bistudio wiki page

        Usage:
            .sqf BIS_fnc_helicopterDamage
            .sqf BIS fnc helicopterDamage
            --https://community.bistudio.com/wiki/BIS_fnc_helicopterDamage
        """

        sqfQuery = "_".join(args)
        wikiUrl = "https://community.bistudio.com/wiki/{}".format(sqfQuery)

        async with self.session.get(wikiUrl) as response:
            if response.status == 200:
                soup = BeautifulSoup(await response.text(), features = "lxml")

                warnings = soup.find_all("div", {"style": "background-color: #EA0; color: #FFF; display: flex; align-items: center; margin: 0.5em 0"})
                for warning in warnings:
                    warning.decompose()

                desc = soup.find('dt', string = 'Description:')
                syntax = soup.find('dt', string = "Syntax:")
                ret = soup.find('dt', string = "Return Value:")

                elems = [desc, syntax, ret]
                outString = ""
                for elem in elems:
                    if elem != None:
                        elemContent = elem.findNext('dd').text
                        outString += "# {}\n{}\n\n".format(elem.text, elemContent.lstrip().rstrip())
                        
                if outString != "":
                    await self.utility.send_message(ctx.channel, "<{}>\n```md\n{}```".format(wikiUrl, outString))
                else:
                    await self.utility.send_message(ctx.channel, "<{}>".format(wikiUrl))
            else:
                await self.utility.send_message(ctx.channel, "{} Error - Couldn't get <{}>".format(response.status, wikiUrl))
                
    @commands.command(aliases = ['utc'])
    async def zulu(self, ctx):
        '''Return Zulu (UTC) time'''

        now = datetime.utcnow()
        outString = "It is currently {}:{}:{} Zulu time (UTC)".format(now.hour, now.minute, now.second)

        await self.utility.send_message(ctx.channel, outString)
    
    #===Utility===#

    def formatDt(self, dt):
        timeUnits = [[dt.days, "days"], [dt.seconds//3600, "hours"], [(dt.seconds//60) % 60, "minutes"]]
        outUnits = []

        for unit in timeUnits:
            if unit[0] != 0:
                if unit[0] == 1: # Remove s from end of word if singular
                    unit[1] = unit[1][:-1]

                outUnits.append(unit)
                    
        dtString = ""
        i = 0
        for unit in outUnits:
            i += 1
            if i == len(outUnits):
                if dtString != "":
                    if len(outUnits) > 2:
                        dtString += (", and {} {}".format(unit[0], unit[1]))
                    else:
                        dtString += (" and {} {}".format(unit[0], unit[1]))
                else:
                    dtString += ("{} {}".format(unit[0], unit[1]))
            elif i == len(outUnits) - 1:
                dtString += ("{} {}".format(unit[0], unit[1]))
            else:
                dtString += ("{} {}, ".format(unit[0], unit[1]))

        return dtString

    def getEmojiCountFromReactionList(self, emoji, reactionList):
        for reaction in reactionList:
            if (emoji == reaction.emoji):
                return reaction.count
        return 0
    
    def getTwitchClipUrlFromMessage(self, message):
        return 
    
    #===Listeners===#
    
    @commands.Cog.listener()
    async def on_ready(self):
        self.utility = self.bot.get_cog("Utility")
        await self.utility.send_message(self.utility.TEST_CHANNEL, "ArcommBot is fully loaded")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if (payload.emoji.name == "📹"): #:video_camera:
            message = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
            
            if (self.getEmojiCountFromReactionList("👍", message.reactions) == 0):
                clipId = re.search("clips.twitch.tv/(\w+)", message.clean_content)
                messageWithMetadata = ""

                if (clipId != None):
                    link = clipId.group(1)
                    clip = twitch.get_clips(clip_id = [link])['data'][0]
                    video = twitch.get_videos(ids=[clip['video_id']])['data'][0]
                    createdDt = video['created_at'][:-1].split('T')
                    createDate, createdTime = createdDt[0], createdDt[1]
                    messageWithMetadata = "```[{}][{}][{}][{}][{}]```{}".format(clip['broadcaster_name'], clip['title'], video['title'], createDate, createdTime, message.clean_content)

                    self.clips.storeClip(link, clip['broadcaster_name'], clip['title'], video['id'], createDate, createdTime, "Clip")
                else:
                    videoId = re.search("twitch.tv/videos/(\w+)", message.clean_content)
                    if (videoId != None):
                        video = twitch.get_videos(ids=[videoId.group(1)])['data'][0]
                        createdDt = video['created_at'][:-1].split('T')
                        createDate, createdTime = createdDt[0], createdDt[1]
                        messageWithMetadata = "```[{}][{}][{}][{}]```{}".format(video['user_name'], video['title'], createDate, createdTime, message.clean_content)

                        self.clips.storeClip(video['id'], video['user_name'], video['title'], video['id'], createDate, createdTime, "Video")
                
                if (messageWithMetadata != ""):
                    await self.utility.send_message(self.utility.TEST_CHANNEL, messageWithMetadata)
                    await message.add_reaction("👍")

        #await self.utility.send_message(self.utility.TEST_CHANNEL, "```{}```".format(payload.emoji.name))

def setup(bot):
    bot.add_cog(Public(bot))