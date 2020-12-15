import logging

from discord.ext import commands

logger = logging.getLogger('bot')

class CogName(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.utility = self.bot.get_cog("Utility")

    #===Commands===#

    @commands.command()
    async def command_name(self, ctx, *args):
        ''' Command description
        '''

    #===Listeners===#

    @commands.Cog.listener()
    async def on_ready(self):
        self.utility = self.bot.get_cog("Utility")

def setup(bot):
    bot.add_cog(CogName(bot))
