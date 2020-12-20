import configparser
from datetime import datetime
import logging
import subprocess

import aiohttp
from bs4 import BeautifulSoup
from discord.ext import commands
from pytz import timezone

logger = logging.getLogger('bot')

config = configparser.ConfigParser()
config.read('resources/config.ini')

EXTRA_TIMEZONES = {
    "PT": "America/Los_Angeles",
    "PST": "ETC/GMT+8",
    "PDT": "ETC/GMT+7",
    "MT": "America/Denver",
    "MST": "ETC/GMT+7",
    "MDT": "ETC/GMT+6",
    "CT": "America/Chicago",
    "CST": "ETC/GMT+6",
    "CDT": "ETC/GMT+5",
    "ET": "America/New_York",
    "EST": "ETC/GMT+5",
    "EDT": "ETC/GMT+4"
}

TICKET_SITES = {
    "acre": "https://github.com/IDI-Systems/acre2/issues/new/choose",
    "ace": "https://github.com/acemod/ACE3/issues/new/choose",
    "cup": "https://dev.cup-arma3.org/maniphest/task/edit/form/1/",
    "cba": "https://github.com/CBATeam/CBA_A3/issues/new/choose",
    "arma": "https://feedback.bistudio.com/maniphest/task/edit/form/3/",
    "arc_misc": "https://github.com/ARCOMM/arc_misc/issues/new",
    "archub": "https://github.com/ARCOMM/ARCHUB/issues/new",
    "tmf": "https://github.com/TMF3/TMF/issues/new"
}


class Public(commands.Cog):
    '''Contains commands that can be used by anyone in the Discord channel'''

    def __init__(self, bot):
        self.bot = bot
        self.utility = self.bot.get_cog("Utility")
        self.session = aiohttp.ClientSession()

    # ===Commands=== #

    @commands.command(aliases = ['daylightsavings'])
    async def dst(self, ctx):
        """Check if daylight savings has started (in London)"""

        outString = "DST is in effect" if datetime.now(timezone("Europe/London")).dst() else "DST is ***not*** in effect"
        await self.utility.send_message(ctx.channel, outString)

    @commands.command()
    async def members(self, ctx, *args):
        '''Get a list of members in a role

            Usage:
                .members rolename
        '''

        roleQuery = " ".join(args)
        role = self.utility.searchRoles(ctx, roleQuery, autocomplete = True, reserved = True, censorReserved = False)

        if role:
            outString = ""
            members = role.members
            members.sort(key = self.utility.roleListKey)

            for member in members:
                if (member.nick is not None):
                    outString += "{} ;{}\n".format(member.nick, member.name)
                else:
                    outString += "{}\n".format(member.name)

            await self.utility.send_message(ctx.channel, "```ini\n[ {} ]\n{}```".format(role.name, outString))
        else:
            await self.utility.send_message(ctx.channel, "{} Role **{}** does not exist".format(ctx.author.mention, roleQuery))

    @commands.command(aliases = ['myranks'])
    async def myroles(self, ctx):
        """Get a list of roles you're in"""

        roles = self.utility.getRoles(ctx, reserved = True, sort = True, personal = True)
        outString = ""

        for role in roles:
            outString += "{}\n".format(role.name)

        await self.utility.send_message(ctx.channel, "```\n{}```".format(outString))

    @commands.command(aliases = ['opday'])
    async def opstart(self, ctx):
        """Time left until opday (Saturday optime)"""

        dt = self.utility.timeUntil("opday")
        dt = self.formatDt(dt)
        outString = "Opday starts in {}!".format(dt)

        await self.utility.send_message(ctx.channel, outString)

    @commands.command(aliases = ['op'])
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
        except Exception:
            logger.debug(".optime modifier was not an int, assume timezone")
            timez = modifier
            modifier = 0

        dt = self.utility.timeUntil("optime", modifier)
        dt = self.formatDt(dt)

        if modifier == 0:
            outString = "Optime starts in {}!".format(dt)
        elif modifier > 0:
            outString = "Optime +{} starts in {}!".format(modifier, dt)
        else:
            outString = "Optime {} starts in {}!".format(modifier, dt)

        if timez is not None:
            if timez.upper() in EXTRA_TIMEZONES:
                timez = timezone(EXTRA_TIMEZONES[timez.upper()])
            else:
                timez = timezone(timez)

            localTime = datetime.now(tz = timezone('Europe/London')).replace(hour = 18 + modifier)
            localTime = localTime.astimezone(timez)
            outString += "\n({}:00:00 {})".format(localTime.hour, timez.zone)

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

        if host is None:
            await self.utility.send_message(ctx.channel, "Pong!")
        else:
            await self.utility.send_message(ctx.channel, "Pinging...")
            p = subprocess.check_output(['ping', host])
            await self.utility.send_message(ctx.channel, "```{}```".format(p.decode("utf-8")))

    @commands.command(aliases = ['rank'])
    async def role(self, ctx, *args):
        """Join or leave a role (with autocomplete)
        Usage:
            .role rolename
            --Join or leave rolename

            .role ro
            --Join or leave rolename
        """

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

        longestName = 0
        roleList = []

        for role in self.utility.getRoles(ctx, reserved = False, sort = True):
            roleList.append(role)
            if len(role.name) > longestName:
                longestName = len(role.name)

        outString = ""

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

        sqfQuery = "_".join(args)
        wikiUrl = "https://community.bistudio.com/wiki/{}".format(sqfQuery)

        async with self.session.get(wikiUrl) as response:
            if response.status == 200:
                soup = BeautifulSoup(await response.text(), features = "lxml")

                warnings = soup.find_all("div", {"style": "background-color: #EA0; color: #FFF; display: flex;" + 
                                                 " align-items: center; margin: 0.5em 0"})
                for warning in warnings:
                    warning.decompose()

                desc = soup.find('dt', string = 'Description:')
                syntax = soup.find('dt', string = "Syntax:")
                ret = soup.find('dt', string = "Return Value:")

                elems = [desc, syntax, ret]
                outString = ""
                for elem in elems:
                    if elem is not None:
                        elemContent = elem.findNext('dd').text
                        outString += "# {}\n{}\n\n".format(elem.text, elemContent.lstrip().rstrip())

                if outString != "":
                    await self.utility.send_message(ctx.channel, "<{}>\n```md\n{}```".format(wikiUrl, outString))
                else:
                    await self.utility.send_message(ctx.channel, "<{}>".format(wikiUrl))
            else:
                await self.utility.send_message(ctx.channel, "{} Error - Couldn't get <{}>".format(response.status, wikiUrl))

    @commands.command()
    async def ticket(self, ctx, site):
        """
        Get a link to create a Github ticket
        Options: acre, ace, arma, cba, cup, archub, arc_misc, tmf
        """
        site = site.lower()
        if site in TICKET_SITES:
            await self.utility.send_message(ctx.channel, "Create a ticket here: <{}>".format(TICKET_SITES[site]))
        else:
            await self.utility.send_message(ctx.channel, "Invalid site ({})".format(", ".join(TICKET_SITES)))

    @commands.command(aliases = ['utc'])
    async def zulu(self, ctx):
        '''Return Zulu (UTC) time'''

        now = datetime.utcnow()
        outString = "It is currently {}:{}:{} Zulu time (UTC)".format(now.hour, now.minute, now.second)

        await self.utility.send_message(ctx.channel, outString)

    # ===Utility=== #

    def formatDt(self, dt):
        timeUnits = [[dt.days, "days"], [dt.seconds // 3600, "hours"], [(dt.seconds // 60) % 60, "minutes"]]
        outUnits = []

        for unit in timeUnits:
            if unit[0] != 0:
                if unit[0] == 1:  # Remove s from end of word if singular
                    unit[1] = unit[1][:-1]

                outUnits.append(unit)

        dtString = ""
        i = 0
        for unit in outUnits:
            i += 1
            if i == len(outUnits):
                if dtString != "":
                    if len(outUnits) > 2:
                        dtString += (", and {} {}".format(unit[0], unit[1]))
                    else:
                        dtString += (" and {} {}".format(unit[0], unit[1]))
                else:
                    dtString += ("{} {}".format(unit[0], unit[1]))
            elif i == len(outUnits) - 1:
                dtString += ("{} {}".format(unit[0], unit[1]))
            else:
                dtString += ("{} {}, ".format(unit[0], unit[1]))

        return dtString

    # ===Listeners=== #

    @commands.Cog.listener()
    async def on_ready(self):
        self.utility = self.bot.get_cog("Utility")
        await self.utility.send_message(self.utility.channels['testing'], "ArcommBot is fully loaded")


def setup(bot):
    bot.add_cog(Public(bot))
