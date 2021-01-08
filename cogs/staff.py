import logging

from discord.ext import commands

logger = logging.getLogger('bot')


class Staff(commands.Cog):
    '''Contains commands usable by any Staff'''

    def __init__(self, bot):
        self.bot = bot
        self.utility = self.bot.get_cog("Utility")

    # ===Commands=== #

    @commands.command(aliases = ["addrank", "createrank", "createrole"])
    @commands.has_role("Staff")
    async def addrole(self, ctx, *args):
        '''Create a new role'''

        roleQuery = " ".join(args)
        member = ctx.author
        role = self.utility.searchRoles(ctx, roleQuery, reserved = True)

        if role:
            await self.utility.reply(ctx.message, "{} Role **{}** already exists".format(member.mention, roleQuery))
        else:
            await member.guild.create_role(name = roleQuery, reason = "Added role through .addrole", mentionable = True)
            await self.utility.reply(ctx.message, "{} Added role **{}**".format(member.mention, roleQuery))

    @commands.command()
    @commands.has_role("Staff")
    async def config(self, ctx):
        """Return or overwrite the config file

        Usage:
            .config
            -- Get current config
            .config <<with attached file called config.ini>>
            -- Overwrites config, a backup is saved"""

        if ctx.message.attachments == []:
            await self.utility.getResource(ctx, "config.ini")
        elif ctx.message.attachments[0].filename == "config.ini":
            await self.utility.setResource(ctx)

    @commands.command()
    @commands.has_role("Staff")
    async def recruitpost(self, ctx):
        """Return or overwrite the recruitment post

        Usage:
            .recruitpost
            -- Get current recruit post
            .recruitpost <<with attached file called recruit_post.md>>
            -- Overwrites recruitpost, a backup is saved"""

        if ctx.message.attachments == []:
            await self.utility.getResource(ctx, "recruit_post.md")
        elif ctx.message.attachments[0].filename == "recruit_post.md":
            await self.utility.setResource(ctx)

    @commands.command(aliases = ["removerank", "deleterank", "deleterole"])
    @commands.has_role("Staff")
    async def removerole(self, ctx, *args):
        '''Remove an existing role'''

        roleQuery = " ".join(args)
        member = ctx.author
        role = self.utility.searchRoles(ctx, roleQuery, reserved = True)
        outString = ""

        if role:
            if role != "RESERVED":
                await role.delete(reason = "Removed role through .removerole")
                outString = "{} Removed role **{}**".format(member.mention, role.name)
            else:
                outString = "{} Role **{}** is reserved".format(member.mention, roleQuery)
        else:
            outString = "{} Role **{}** doesn't exist".format(member.mention, roleQuery)

        await self.utility.reply(ctx.message, outString)

    @commands.command(aliases = ["renamerank", "rename"])
    @commands.has_role("Staff")
    async def renamerole(self, ctx, oldName, newName):
        '''Rename an existing role

           Usage:
                rename "old name" "new name"
        '''
        member = ctx.author
        role = self.utility.searchRoles(ctx, oldName, reserved = True)
        outString = ""

        if role:
            if role != "RESERVED":
                oldRoleName = str(role.name)
                await role.edit(name = newName)
                outString = "{} Renamed **{}** to **{}**".format(member.mention, oldRoleName, role.name)
            else:
                outString = "{} Role **{}** is reserved".format(member.mention, oldName)
        else:
            outString = "{} Role **{}** doesn't exist".format(member.mention, oldName)

        await self.utility.reply(ctx.message, outString)

    # ===Listeners=== #

    @commands.Cog.listener()
    async def on_ready(self):
        self.utility = self.bot.get_cog("Utility")


def setup(bot):
    bot.add_cog(Staff(bot))
