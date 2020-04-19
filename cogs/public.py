from datetime import datetime, timedelta
from pytz import timezone

import discord
from discord.ext import commands

class Public(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = {'prev_message' : None}

    #===Commands===#

    @commands.command()
    async def optime(self, ctx):
        dt = self.timeUntilOpday()
        timeUnits = [[dt.days, "days"], [dt.seconds//3600, "hours"], [(dt.seconds//60) % 60, "minutes"]]

        for unit in timeUnits:
            if unit[0] == 0:
                timeUnits.remove(unit)

        i = 0
        dtString = ""
        for unit in timeUnits:
            i += 1
            if i == len(timeUnits):
                if dtString != "":
                    dtString += ("and {} {}".format(unit[0], unit[1]))
                else:
                    dtString += ("{} {}".format(unit[0], unit[1]))
            elif i == len(timeUnits) - 1:
                dtString += ("{} {} ".format(unit[0], unit[1]))
            else:
                dtString += ("{} {}, ".format(unit[0], unit[1]))
            
        outString = "There are {} until optime!".format(dtString)
        #dtString = "There are {} days, {} hours, and {} minutes until opday".format(dt.days, dt.seconds//3600, (dt.seconds//60) % 60)
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

    def timeUntilOpday(self):
        today = datetime.now(tz = timezone('Europe/London'))
        daysUntilOpday = timedelta((12 - today.weekday()) % 7)

        opday = today + daysUntilOpday
        opday = opday.replace(hour = 18, minute = 0, second = 0)

        return opday - today

    #===Listeners===#

    @commands.Cog.listener()
    async def on_ready(self):
        print('Bot is online')


def setup(bot):
    bot.add_cog(Public(bot))