from datetime import datetime, timedelta
import logging
import os
import re
import subprocess

import aiohttp
from bs4 import BeautifulSoup
import discord
from discord.ext import commands
from pytz import timezone, UnknownTimeZoneError

logger = logging.getLogger('bot')

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

class Public(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.utility = bot.get_cog("Utility")
        self.session = aiohttp.ClientSession()

    #===Commands===#

    @commands.command(aliases = ['daylightsavings'])
    async def dst(self, ctx):
        """Check if daylight savings has started (in London)"""
        logger.debug(".dst called")

        timez = timezone("Europe/London")
        outString = "DST is in effect" if datetime.now(timez).dst() else "DST is ***not*** in effect"

        await self.utility.send_message(ctx.channel, outString)

    @commands.command()
    async def members(self, ctx, *args):
        '''Get a list of members in a role
            
            Usage:
                .members rolename
        '''
        logger.debug(".members called")

        roleQuery = " ".join(args)
        author = ctx.author
        role = self.utility.searchRoles(ctx, roleQuery, reserved = True, censorReserved = False)
        
        if role:
            outString = ""
            members = role.members
            members.sort(key = self.utility.roleListKey)
            for member in members:
                outString += "{}\n".format(member.name)
            await self.utility.send_message(ctx.channel, "```md\n# {}\n{}```".format(role.name, outString))
        else:
            await self.utility.send_message(ctx.channel, "{} Role **{}** does not exist".format(author.mention, roleQuery))
    
    @commands.command()
    async def myroles(self, ctx):
        """Get a list of roles you're in"""
        logger.debug(".myroles called")

        roles = self.utility.getRoles(ctx, reserved = True, sort = True, personal = True)
        outString = ""

        for role in roles:
            outString += "{}\n".format(role.name)

        await self.utility.send_message(ctx.channel, "```\n{}```".format(outString))

    @commands.command()
    async def opday(self, ctx):
        """Time left until opday (Saturday optime)"""
        logger.debug(".opday called")

        dt = self.timeUntil("opday")
        dt = self.formatDt(dt)        
        outString = "There {} until opday!".format(dt)
        
        await self.utility.send_message(ctx.channel, outString)

    @commands.command()
    async def optime(self, ctx, modifier = '0', timez = None):
        """Time left until optime

        Usage:
            optime
            optime +x
            optime timezone
            optime -x timezone
            Timezones can be: CET or Europe/London or US/Pacific etc.
        """
        logger.debug(".optime called")

        try:
            modifier = int(modifier)
        except Exception as e:
            logger.debug(".optime modifier was not an int, assume timezone")
            timez = modifier
            modifier = 0

        dt = self.timeUntil("optime", modifier)
        dt = self.formatDt(dt)
        
        if modifier == 0:
            outString = "There {} until optime!".format(dt)
        elif modifier > 0:
            outString = "There {} until optime +{}!".format(dt, modifier)
        else:
            outString = "There {} until optime {}!".format(dt, modifier)
      
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
        logger.debug(".ping called")

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
        """Join or leave a role, with autocomplete
        Usage:
            .role rolename
            --Join or leave rolename

            .role ro
            --Join or leave rolename
        """
        logger.debug(".role called")

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
        logger.debug(".roles called")

        member = ctx.author
        roles = self.utility.getRoles(ctx, reserved = False, sort = True)
        outString = ""
        longestName = 0
        roleList = []

        for role in roles:
            roleList.append(role)
            if len(role.name) > longestName:
                longestName = len(role.name)

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
        logger.debug(".sqf called")

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
        logger.debug(".zulu called")

        now = datetime.utcnow()
        outString = "It is currently {}:{}:{} Zulu time (UTC)".format(now.hour, now.minute, now.second)

        await self.utility.send_message(ctx.channel, outString)
    
    #===Utility===#

    def formatDt(self, dt):
        # TODO: s not removed on +1/-1 messages as time unit's aren't modified
        logger.debug("formatDt called")
        timeUnits = [[dt.days, "days"], [dt.seconds//3600, "hours"], [(dt.seconds//60) % 60, "minutes"]]

        for unit in timeUnits:
            print(unit)
            if unit[0] == 0:
                timeUnits.remove(unit)
            elif unit[0] == 1: # Remove s from end of word if singular
                unit[1] = unit[1][:-1] 

        dtString = ""
        i = 0
        for unit in timeUnits:
            i += 1
            if i == len(timeUnits):
                if dtString != "":
                    if len(timeUnits) > 2:
                        dtString += (", and {} {}".format(unit[0], unit[1]))
                    else:
                        dtString += (" and {} {}".format(unit[0], unit[1]))
                else:
                    dtString += ("{} {}".format(unit[0], unit[1]))
            elif i == len(timeUnits) - 1:
                dtString += ("{} {}".format(unit[0], unit[1]))
            else:
                dtString += ("{} {}, ".format(unit[0], unit[1]))

        isAre = "is" if timeUnits[0][0] == 1 else "are"

        return "{} {}".format(isAre, dtString)
    
    def timeUntil(self, time = "opday", modifier = 0):
        logger.debug("timeUntil called with time = {}".format(time))

        today = datetime.now(tz = timezone('Europe/London'))
        opday = None

        if time == "opday":
            daysUntilOpday = timedelta((12 - today.weekday()) % 7)
            opday = today + daysUntilOpday
            opday = opday.replace(hour = 18, minute = 0, second = 0)
        elif time == "optime":
            opday = today
            opday = opday.replace(hour = 18 + modifier, minute = 0, second = 0)
            if today.hour >= 18:
                opday = opday.replace(day = today.day + 1)

        return opday - today


def setup(bot):
    bot.add_cog(Public(bot))