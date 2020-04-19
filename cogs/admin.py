from discord.ext import commands

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name = "reload", hidden = True)
    @commands.is_owner()
    async def _reload(self, ctx, ext: str):
        try:
            self.bot.reload_extension("cogs." + ext)
            print("Reloaded {} extension\n".format(ext))
        except Exception as e:
            print("Failed to reload {} extension\n".format(ext))
            print(e)
            print("\n")

    @commands.command(name = "shutdown", hidden = True)
    @commands.is_owner()
    async def _shutdown(self, ctx):
        exit()


def setup(bot):
    bot.add_cog(Admin(bot))