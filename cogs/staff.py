import logging
import os

from discord import File
from discord.ext import commands

logger = logging.getLogger('bot')

class Staff(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.utility = bot.get_cog("Utility")

    #===Commands===#
    
    @commands.command(aliases = ["addrank", "newrank", "newrole", "createrank", "createrole"])
    @commands.has_role("Staff")
    async def addrole(self, ctx, *args):
        '''Create a new role'''
        logger.debug(".addrank called")

        roleQuery = " ".join(args)
        member = ctx.author
        role = self.utility.searchRoles(ctx, roleQuery, reserved = True)

        if role:
            await self.utility.send_message(ctx.channel, "{} Role **{}** already exists".format(member.mention, roleQuery))
        else:
            await member.guild.create_role(name = roleQuery, reason = "Created role through .addrole", mentionable = True)
            await self.utility.send_message(ctx.channel, "{} Created role **{}**".format(member.mention, roleQuery))

    @commands.command(aliases = ["removerank", "delrank", "delrole", "deleterank", "deleterole"])
    @commands.has_role("Staff")
    async def removerole(self, ctx, *args):
        '''Remove an existing role'''
        logger.debug('.removerank called')

        roleQuery = " ".join(args)
        member = ctx.author
        role = self.utility.searchRoles(ctx, roleQuery, reserved = True)

        if role:
            if role != "RESERVED":
                await role.delete(reason = "Removed role through .removerole")
                await self.utility.send_message(ctx.channel, "{} Removed role **{}**".format(member.mention, role.name))
                return
            else:
                await self.utility.send_message(ctx.channel, "{} Role **{}** is reserved".format(member.mention, roleQuery))
                return
        else:
            await self.utility.send_message(ctx.channel, "{} Role **{}** does not exist".format(member.mention, roleQuery))

    @commands.command(aliases = ["renamerank", "rename"])
    @commands.has_role("Staff")
    async def renamerole(self, ctx, oldName, newName):
        '''Rename an existing role
            
           Usage: 
                rename "old name" "new name"
        '''
        member = ctx.author
        role = self.utility.searchRoles(ctx, oldName, reserved = True)

        if role:
            if role != "RESERVED":
                oldRoleName = str(role.name)
                await role.edit(name = newName)
                await self.utility.send_message(ctx.channel, "{} Renamed **{}** to **{}**".format(member.mention, oldRoleName, role.name))
            else:
                await self.utility.send_message(ctx.channel, "{} Role **{}** is reserved".format(member.mention, oldName))
        else:
            await self.utility.send_message(ctx.channel, "{} Role **{}** does not exist".format(member.mention, oldName))
    
    @commands.command()
    @commands.has_role("Staff")
    async def recruitpost(self, ctx):
        """Return or overwrite the recruitment post
        
        Usage:
            .recruitpost   
            -- Output contents of resources/recruit_post.md
            .recruitpost <<with attached file called recruit_post.md>>
            -- Overwrites resources/recruit_post.md, a backup is saved as resources/recruit_post.bak"""
        logger.debug('.recruitpost called')

        attachments = ctx.message.attachments

        if attachments == []:
            await self.recruitmentPost(ctx.channel)
        else:
            logger.debug("Found attachment")
            newRecruitPost = attachments[0]
            if newRecruitPost.filename == "recruit_post.md":
                logger.debug("Attachment '{}' has correct name".format(newRecruitPost.filename))
                try:
                    os.remove("resources/recruit_post.bak")
                    logger.debug("Removed recruit_post.bak")
                except FileNotFoundError as e:
                    logger.debug("No recruit_post.bak exists, can't remove")

                try:
                    os.rename("resources/recruit_post.md", "resources/recruit_post.bak")
                    logger.info("Saved recruit_post.md to recruit_post.bak")
                except FileNotFoundError as e:
                    logger.debug("No recruit_post.md exists, can't backup")

                await newRecruitPost.save("resources/recruit_post.md")
                logger.info("Saved new recruit_post.md")
                await self.utility.send_message(ctx.channel, "{} {}".format(ctx.author.mention, "Recruitment post has been updated"))
                return
            else:
                logger.debug("Attachment '{}' has incorrect name".format(newRecruitPost.filename))
                await self.utility.send_message(ctx.channel, "{} {}".format(ctx.author.mention, "File must be called recruit_post.md"))
                return

    #===Utility===#
        
    async def recruitmentPost(self, channel):
        logger.debug("recruitmentPost called")

        introString = "Post recruitment on <https://www.reddit.com/r/FindAUnit>"  
        await channel.send(introString, file = File("resources/recruit_post.md", filename = "recruit_post.md"))
      

def setup(bot):
    bot.add_cog(Staff(bot))