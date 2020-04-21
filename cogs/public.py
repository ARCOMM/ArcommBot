from datetime import datetime, timedelta
from pytz import timezone, UnknownTimeZoneError
import os

import discord
from discord.ext import commands

#RESERVED_ROLES = os.getenv('RESERVED_ROLES')

class Public(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    #===Commands===#

    @commands.command()
    async def opday(self, ctx):
        """Time left until opday (Saturday optime)"""

        dt = self.timeUntil("opday")
        dt = self.formatDt(dt)        
        outString = "There {} until opday!".format(dt)
        await self.send_message(ctx.channel, outString)

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
        
        try:
            modifier = int(modifier)
        except Exception as e:
            print(".optime modifier was not an int, assume timezone")
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
                timez = timezone(timez)
                localTime = datetime.now().replace(hour = 18 + modifier)
                localTime = localTime.astimezone(timez)
                outString += "\n({}:00:00 {})".format(localTime.hour, timez.zone)
            except UnknownTimeZoneError as e:
                await self.send_message(ctx.channel, "Invalid timezone")
                return

        await self.send_message(ctx.channel, outString)
       
    @commands.command(aliases = ['daylightsavings'])
    async def dst(self, ctx):
        """Check if DST has started"""

        timez = timezone("Europe/London")
        outString = "DST is in effect" if datetime.now(timez).dst() else "DST is ***not*** in effect"

        await self.send_message(ctx.channel, outString)
    
    @commands.command(aliases = ['utc'])
    async def zulu(self, ctx):
        '''Return Zulu (UTC) time'''

        now = datetime.utcnow()
        outString = "It is currently {}:{}:{} Zulu time (UTC)".format(now.hour, now.minute, now.second)

        await self.send_message(ctx.channel, outString)
    
    @commands.command(aliases = ['role'])
    async def rank(self, ctx, *args):
        """Join or leave a non-reserved role"""

        roleQuery = " ".join(args)
        member = ctx.author
        roles = member.guild.roles

        for role in roles:
            if role.name.lower() == roleQuery.lower():
                if role.colour.value == 0:
                #if not (role.name in RESERVED_ROLES):
                    if role in member.roles:
                        await member.remove_roles(role, reason = "Removed role through .rank command")
                        await self.send_message(ctx.channel, "{} You've left **{}**".format(member.mention, role.name))
                        return
                    else:
                        await ctx.author.add_roles(role, reason = "Added role through .rank command")
                        await self.send_message(ctx.channel, "{} You've joined **{}**".format(member.mention, role.name))
                        return
                else:
                    await self.send_message(ctx.channel, "{} **{}** is a reserved role".format(member.mention, role.name))
                return   

        await self.send_message(ctx.channel, "{} Role **{}** does not exist".format(member.mention, roleQuery))

    @commands.command(aliases = ['roles'])
    async def ranks(self, ctx):
        """Return a list of joinable ranks"""

        member = ctx.author
        roles = member.guild.roles
        outString = ""
        longestName = 0

        for role in roles[1:]:
            if role.colour.value == 0:
                if len(role.name) > longestName:
                    longestName = len(role.name)

        for role in roles[1:]:
            if role.colour.value == 0:
                spaces = " " * (longestName + 1 - len(role.name))
                outString += "{}{}- {} members\n".format(role.name, spaces, len(role.members))

        await self.send_message(ctx.channel, "```{}```".format(outString))
    
    #===Utility===#

    async def send_message(self, channel, message: str):
        """Send a message to the text channel"""

        await channel.trigger_typing()
        newMessage = await channel.send(message)

        return newMessage

    def formatDt(self, dt):
        # TODO: s not removed on +1/-1 messages as time unit's aren't modified
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

    #===Listeners===#

    @commands.Cog.listener()
    async def on_ready(self):
        print('Bot is online')


def setup(bot):
    bot.add_cog(Public(bot))