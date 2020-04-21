import os

from discord.ext import commands

RESERVED_ROLES = os.getenv('RESERVED_ROLES')

def is_admin(ctx):
    if ctx.author.id == 173123135321800704: 
        return True
    return ctx.author.has_role("Staff")

class Attendance():
    def __init__(self, channel):
        self.channel = channel
        self.messages = {"intro" : None,
                         "pvp" : None,
                         "coop1" : None,
                         "coop2" : None}
    
    async def send_message(self, channel, name, message, reaction = False):
        newMessage = await channel.send(message)
        self.messages[name] = newMessage

        if reaction:
            await newMessage.add_reaction("\N{THUMBS UP SIGN}")

    async def delete_messages(self):
        for message in self.messages.items():
            if message[1] != None:
                await message[1].delete()

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.attend = None
    
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
    @commands.check(is_admin)
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
    @commands.check(is_admin)
    async def removerank(self, ctx, *args):
        '''Remove an existing role'''

        roleQuery = " ".join(args)
        member = ctx.author
        roles = member.guild.roles

        for role in roles[1:]:
            if role.name.lower() == roleQuery.lower():
                if not (role.colour.value == 0):
                #if role.name in RESERVED_ROLES:
                    await self.send_message(ctx.channel, "{} **{}** is a reserved role".format(member.mention, role.name))
                    return

                await role.delete(reason = "Removed role through .removerank")
                await self.send_message(ctx.channel, "{} Removed role **{}**".format(member.mention, role.name))
                return

        await self.send_message(ctx.channel, "{} Role **{}** doesn't exist".format(member.mention, roleQuery))
    
    @commands.command()
    @commands.is_owner()
    #@commands.check(is_admin)
    async def attendance(self, ctx):
        if self.attend != None:
            await self.attend.delete_messages()

        self.attend = Attendance(ctx.channel)
        await self.attend.send_message(ctx.channel, "intro", "@here intro\nReact to show planned attendance")
        await self.attend.send_message(ctx.channel, "pvp", "pvp post", reaction = True)
        await self.attend.send_message(ctx.channel, "coop1", "coop1 post", reaction = True)
        await self.attend.send_message(ctx.channel, "coop2", "coop2 post", reaction = True)

    #===Utility===#

    async def send_message(self, channel, message: str):
        """Send a message to the text channel"""

        await channel.trigger_typing()
        newMessage = await channel.send(message)

        return newMessage


def setup(bot):
    bot.add_cog(Admin(bot))