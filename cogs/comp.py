import logging
import os
import re
import string
import sys
import sqlite3

from discord.ext import commands

logger = logging.getLogger('bot')
dal = sqlite3.connect('resources/competition.db')

class Comp(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    #===Commands===#        

    # addtime [type] [time] [optional link]
    # removetime [type] [time] (only owner or admin/staff)
    # addcomp/addchallenge [type] [explanation for comp info] (only admin/staff)
    # removecomp/removechallenge [type] (only admin/staff)
    # comp/challenge/competition [opt. type] [opt. number]
        # if type left blank
            # COF 2 - 1st BorderKeeper (4m31s) [link if posted], 2nd Sven (4m30s) 3rd Tim (15m21s)
            # KoTH - ...
        # if type specified
            # King of The Hill
            # 1st - BorderKeeper (4m31s) [Link if posted] 
            # 2nd - Sven (4m30s)
            # 3rd - Tim  (15m21s)[Link if posted]
            # ... will post more if number specified
    # comptypes/challengetypes
        # will give a list of competitions available and short info about them

    @commands.command()
    async def addtime(self, ctx, *args):
        """Add a time into the running of a specific competition
        Usage:
            .addtime type time video_link
            --Get type name from .comptypes. Specify time as 2:54 as in 2m and 54s. Link is optional.
        """
        arguments = " ".join(args)
        attachments = ctx.message.attachments
        filename = attachments[0].filename

        logger.debug(".addtime called")

        await self.utility.send_message(ctx.channel, ctx.message)

    #===Listeners===#
    
    @commands.Cog.listener()
    async def on_ready(self):
        self.utility = self.bot.get_cog("Utility")

def setup(bot):
    bot.add_cog(Comp(bot))