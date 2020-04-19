from datetime import datetime, timedelta
from pytz import timezone, UnknownTimeZoneError

import discord
from discord.ext import commands

class Public(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = {'prev_message' : None}

    #===Commands===#

    @commands.command()
    async def opday(self, ctx):
        dt = self.timeUntil("opday")
        dt = self.formatDt(dt)        
        outString = "There {} until opday!".format(dt)
        await self.send_message(ctx.channel, outString, immutable = True)

    @commands.command()
    async def optime(self, ctx, modifier = '0', timez = None):
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
                await self.send_message(ctx.channel, "Invalid timezone", immutable = True)
                return

        await self.send_message(ctx.channel, outString, immutable = True)
       
    #===Utility===#

    async def send_message(self, channel, message: str, overwrite: bool = False, immutable: bool = False):
        """Send a message to the text channel"""

        prev_message = self.data['prev_message']
        newMessage = None

        if overwrite and (channel.last_message_id == prev_message.id):
            await prev_message.edit(content = message)         
            newMessage = prev_message
        else:
            await channel.trigger_typing()
            newMessage = await channel.send(message)
        
        if not immutable:
            self.data['prev_message'] = newMessage

        return newMessage

    def formatDt(self, dt):
        timeUnits = [[dt.days, "days"], [dt.seconds//3600, "hours"], [(dt.seconds//60) % 60, "minutes"]]

        for unit in timeUnits:
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