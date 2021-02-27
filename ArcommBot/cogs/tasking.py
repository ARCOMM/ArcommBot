import asyncio
import configparser
from datetime import datetime, timedelta
import json
import logging
import os
import re
import sqlite3
from urllib.parse import urlparse
from httplib2 import ServerNotFoundError

import aiohttp
import aiomysql
from bs4 import BeautifulSoup
from discord import File, Game, Embed
from discord.ext import commands, tasks
from googleapiclient.discovery import build
from google.oauth2 import service_account
from pytz import timezone

from a3s_to_json import repository

logger = logging.getLogger('bot')

config = configparser.ConfigParser()
config.read('resources/config.ini')

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = 'resources/restricted/arcommbot-1c476e6f4869.json'

credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
service = build('calendar', 'v3', credentials = credentials)


class CalendarDB():
    def __init__(self):
        self.conn = sqlite3.connect('resources/calendar.db')
        self.collection = service.events()

    def remake(self):
        c = self.conn.cursor()
        try:
            # c.execute("DROP TABLE calendar")
            c.execute("CREATE TABLE calendar (event_id INTEGER PRIMARY KEY, summary STRING NOT NULL, start STRING NOT NULL, end STRING NOT NULL, UNIQUE(start))")
        except Exception as e:
            print(e)

    def storeCalendar(self, timeFrom = "now"):
        if timeFrom == "now":
            lastDT = datetime.now(tz = timezone("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            lastDT = timeFrom

        request = self.collection.list(calendarId = "arcommdrive@gmail.com", timeMin = lastDT, orderBy = "startTime",
                                       singleEvents = True)
        # request = self.collection.list(calendarId = "bmpdcnk8pab1drvf4qgt4q1580@group.calendar.google.com", timeMin = lastDT, orderBy = "startTime", singleEvents = True)
        response = request.execute()
        c = self.conn.cursor()
        c.execute("DELETE FROM calendar")

        for item in response['items']:
            try:
                c.execute("INSERT OR IGNORE INTO calendar (summary, start, end) VALUES(?, ?, ?)", (item['summary'],
                          item['start']['dateTime'], item['end']['dateTime']))
            except Exception:
                None

        self.conn.commit()

    def pop(self):
        c = self.conn.cursor()

        c.execute("SELECT * FROM calendar ORDER BY event_id ASC LIMIT 1")
        event = c.fetchone()
        c.execute("DELETE FROM calendar WHERE event_id = (SELECT min(event_id) FROM calendar)")

        self.conn.commit()

        return event

class R3DB():
    def __init__(self):
        self.pool = None

    async def getReplays(self, lastId):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                #await cur.execute(f"SELECT id, missionName, map, playerCount, dateStarted, lastEventMissionTime FROM replays WHERE id > {lastId} AND hidden = '0' AND (missionName LIKE 'ARC_COOP%' OR missionName LIKE 'ARC_TVT%')")
                await cur.execute(f"SELECT id, missionName, map, playerCount, dateStarted, lastEventMissionTime FROM replays WHERE id > {lastId} AND hidden = '0'")

                replays = []
                for row in await cur.fetchall():
                    _id, mission, _map, count, start, end = row
                    runtime = end - start if end is not None and start is not None else "N/A"
                    replay = f"https://r3.arcomm.co.uk/{_id}"
                    print(row)
                    if runtime is not "N/A":
                        replays.append((mission, _map, count, start, end, runtime, replay, _id))

        return replays
    
    async def createPool(self):
        self.pool = await aiomysql.create_pool(host='r3.arcomm.co.uk', port=3306,
                                               user='r3_acc', password='38VfJW26hyI8L1q22Mh6',
                                               db='r3_db')

class LastModified():
    resourcesLocked = False

    @classmethod
    def uses_lastModified(cls, func):
        async def wrapper(cog):
            if LastModified.resourcesLocked:
                return False, f"{str(func)} res locked"
            else:
                LastModified.resourcesLocked = True
                try:
                    result = await func(cog)
                    LastModified.resourcesLocked = False
                    return result
                except Exception as e:
                    LastModified.resourcesLocked = False
                    return False, f"Error running {str(func)}:\n{str(e)}"

        return wrapper

class Tasking(commands.Cog):
    '''Contains scheduled tasks'''

    def __init__(self, bot):
        self.bot = bot
        self.utility = self.bot.get_cog("Utility")
        self.calendar = CalendarDB()
        self.r3 = R3DB()
        self.session = aiohttp.ClientSession()

    # ===Commands=== #

    @commands.command()
    @commands.has_role("Staff")
    async def r3(self, ctx):
        success, message = await self.r3Task()

    # ===Tasks=== #

    @tasks.loop(hours = 1)
    async def attendanceTask(self):
        '''Remind admins to take attendance on opday'''

        logger.debug("attendanceTask called")
        targetTimeslot = [17, 20]  # 5pm -> 8pm

        now = datetime.utcnow()
        # now = datetime(2020, 4, 25, 17)
        if now.weekday() == 5:  # Saturday
            if now.hour >= targetTimeslot[0] and now.hour <= targetTimeslot[1]:
                logger.debug("Called within timeslot")
                await self.attendancePost()

    @attendanceTask.before_loop
    async def before_attendanceTask(self):
        """Sync up attendanceTask to on the hour"""
        logger.debug("before_attendanceTask called")
        await self.bot.wait_until_ready()

        now = datetime.utcnow()
        # now = datetime(now.year, now.month, now.day, 16, 59, 55)
        future = datetime(now.year, now.month, now.day, now.hour + 1)
        logger.debug("%d seconds until attendanceTask called", (future - now).seconds)

        await asyncio.sleep((future - now).seconds)

    @tasks.loop(minutes = 1)
    async def calendarTask(self):
        '''Check google calendar for any new events, and post announcements for them'''

        lastDatetime = None
        with open('resources/calendar_datetime.json', 'r') as f:
            lastDatetime = json.load(f)

            if 'datetime' not in lastDatetime:
                lastDatetime['datetime'] = "now"
            else:  # Make sure the lastDatetime isn't in the past, otherwise will be announcing old events
                if lastDatetime['datetime'] != "now":
                    now = datetime.now(tz = timezone("UTC"))
                    lastDT = lastDatetime['datetime'].replace("Z", "+00:00")
                    lastDT = datetime.strptime(lastDT, "%Y-%m-%dT%H:%M:%S%z")

                    if lastDT < now:
                        lastDatetime['datetime'] = "now"

        try:
            self.calendar.storeCalendar(lastDatetime['datetime'])
        except ServerNotFoundError as e:
            self.utility.send_message(self.utility.channels["testing"], e)
            return
        
        newAnnouncement = True

        while newAnnouncement:
            newAnnouncement = False
            event = self.calendar.pop()

            if event:
                now = datetime.now(tz = timezone("UTC"))
                eventStartTime = event[2].replace("Z", "+00:00")
                eventStartTime = datetime.strptime(eventStartTime, "%Y-%m-%dT%H:%M:%S%z")

                timeUntil = eventStartTime - now
                if timedelta(days = 0, hours = 0, minutes = 10) <= timeUntil <= timedelta(days = 0, hours = 1, minutes = 0):
                    newAnnouncement = True
                    lastDatetime['datetime'] = event[3]
                    asyncio.Task(self.announce(timeUntil, event[1], event[2], event[3]))
            else:
                logger.debug('No event popped')
                break

        with open('resources/calendar_datetime.json', 'w') as f:
            json.dump(lastDatetime, f)

    @tasks.loop(hours = 1)
    async def modcheckTask(self):
        logger.debug("modcheckTask called")

        githubChanged, githubPost = await self.handleGithub()
        cupChanged, cupPost = await self.handleCup()
        steamChanged, steamPost = await self.handleSteam()

        if githubChanged or cupChanged or steamChanged:
            outString = "<@&{}>\n{}{}{}".format(self.utility.roles['admin'], githubPost, cupPost, steamPost)
            await self.utility.send_message(self.utility.channels['staff'], outString)

    @tasks.loop(minutes = 10)
    async def a3syncTask(self):
        a3syncChanged, a3syncPost = await self.handleA3Sync()
        if a3syncChanged:
            await self.utility.send_message(self.utility.channels["announcements"], a3syncPost)

    @a3syncTask.before_loop
    async def before_a3syncTask(self):
        """Add a delay before checking a3sync to avoid resource lock"""
        await asyncio.sleep(5)

    @tasks.loop(hours = 24)
    async def recruitTask(self):
        logger.debug("recruitTask called")

        targetDays = [0, 2, 4]  # Monday, Wednesday, Friday
        now = datetime.utcnow()
        # now = datetime(2020, 4, 22) #A Wednesday
        if now.weekday() in targetDays:
            logger.debug("Called within targetDays")
            await self.recruitmentPost(self.utility.channels['staff'], pingAdmins = True)

    @recruitTask.before_loop
    async def before_recruitTask(self):
        """Sync up recruitTask to targetHour:targetMinute:00"""
        logger.debug("before_recruitTask called")
        await self.bot.wait_until_ready()

        targetHour = 17
        targetMinute = 0

        now = datetime.utcnow()
        # now = datetime(now.year, now.month, now.day, 16, 59, 55)
        future = datetime(now.year, now.month, now.day, targetHour, targetMinute, 0, 0)

        if now.hour >= targetHour and now.minute > targetMinute:
            logger.debug("Missed timeslot, adding a day")
            future += timedelta(days = 1)

        logger.debug("%d seconds until recruitTask called", (future - now).seconds)

        await asyncio.sleep((future - now).seconds)

    @tasks.loop(minutes = 1)
    async def presenceTask(self):
        timeLeft = self.utility.timeUntil("optime")
        minutes = (timeLeft.seconds // 60) % 60
        minuteZero = "0" if minutes < 10 else ""
        presenceString = "{}:{}{}:00 until optime".format(timeLeft.seconds // 3600, minuteZero, minutes)

        await self.bot.change_presence(activity = Game(name = presenceString))

    @presenceTask.before_loop
    async def before_presenceTask(self):
        """Sync up presenceTask to on the minute"""
        logger.debug("before_presenceTask called")
        await self.bot.wait_until_ready()

        now = datetime.utcnow()
        # now = datetime(now.year, now.month, now.day, 16, 59, 55)
        future = datetime(now.year, now.month, now.day, now.hour, now.minute + 1)
        logger.debug("%d seconds until presenceTask called", (future - now).seconds)

        await asyncio.sleep((future - now).seconds)

    @LastModified.uses_lastModified
    async def r3Task(self):
        logger.debug("r3Task called")

        lastModified = {}
        with open('resources/last_modified.json', 'r') as f:
            lastModified = json.load(f)

        replays = await self.r3.getReplays(lastModified["r3_lastId"])

        if len(replays) == 0:
            return False, ""

        for r in replays:
            mission, _map, count, start, end, runtime, replay, _id = r
            embed = Embed(timestamp = start, title = mission, url = replay)
            embed.add_field(name = "Map", value = _map).add_field(name = "Players", value = count).add_field(name = "Runtime", value = runtime).add_field(name = "Start", value = start.time()).add_field(name = "End", value = end.time())
            await self.utility.send_embed(self.utility.channels["op_news"], embed)

        lastModified["r3_lastId"] = replays[-1][7]
        with open('resources/last_modified.json', 'w') as f:
            json.dump(lastModified, f)

        return True, ""
    
    # ===Utility=== #

    async def announce(self, timeUntil, summary, startTime, endTime):
        startTime = datetime.strptime(startTime, "%Y-%m-%dT%H:%M:%S%z").astimezone(timezone("UTC"))
        startTimeString = startTime.strftime('%H:%M:%S')

        endTime = datetime.strptime(endTime, "%Y-%m-%dT%H:%M:%S%z").astimezone(timezone("UTC"))
        endTimeString = endTime.strftime('%H:%M:%S')

        timeUntilStr = str(timeUntil).split(".")[0]  # Remove microseconds

        ping = "@here"
        channel = self.utility.channels['op_news']

        for event in config['calendar']:
            if re.search(event, summary.lower()) is not None:
                eventArray = config['calendar'][event][1:-1].split(", ")
                if eventArray[0] != "ignored":
                    ping = "<@&{}>".format(self.utility.roles[eventArray[0]])
                    channel = self.utility.channels[eventArray[1]]
                else:
                    return

        outString = "{}\n```md\n# {}\n\nStarting in {}\n\nStart: {} UTC\nEnd:   {} UTC```".format(ping, summary, timeUntilStr,
                                                                                                  startTimeString, endTimeString)
        await self.utility.send_message(channel, outString)

        await asyncio.sleep((timeUntil - timedelta(minutes = 5)).seconds)

        outString = "{}\n```md\n# {}\n\nStarting in 5 minutes```".format(ping, summary)
        await self.utility.send_message(channel, outString)

    async def attendancePost(self):
        logger.debug("attendancePost called")

        outString = "<@&{}> Collect attendance!".format(self.utility.roles['admin'])
        await self.utility.send_message(self.utility.channels['admin'], outString)

    async def recruitmentPost(self, channel, pingAdmins = False):
        logger.debug("recruitmentPost called")
        if pingAdmins:
            introString = "<@&{}> Post recruitment on <https://www.reddit.com/r/FindAUnit>".format(self.utility.roles['admin'])
        else:
            introString = "Post recruitment on <https://www.reddit.com/r/FindAUnit>"

        await channel.send(introString, file = File("resources/recruit_post.md", filename = "recruit_post.md"))

    @LastModified.uses_lastModified
    async def handleA3Sync(self):
        url = "{}.a3s/".format(self.utility.REPO_URL)
        scheme = urlparse(url).scheme.capitalize

        repo = repository.parse(url, scheme, parseAutoconf=False, parseServerinfo=True, parseEvents=False,
                                parseChangelog=True, parseSync=False)

        lastModified = {}
        with open('resources/last_modified.json', 'r') as f:
            lastModified = json.load(f)

        updatePost = ""
        newRevision = repo["serverinfo"]["SERVER_INFO"]["revision"]
        if not (lastModified['revision'] < newRevision):
            return False, updatePost

        newRepoSize = round((float(repo["serverinfo"]["SERVER_INFO"]["totalFilesSize"]) / 1000000000), 2)
        repoSizeChange = round(newRepoSize - float(lastModified['a3sync_size']), 2)
        repoChangeString = str(repoSizeChange) if (repoSizeChange < 0) else "+{}".format(repoSizeChange)

        newChangelog = None
        for changelog in repo["changelog"]:
            revision = repo["changelog"][changelog]["revision"]
            if revision == newRevision:
                newChangelog = repo["changelog"][changelog]

        updatePost = "```md\n# The ArmA3Sync repo has changed #\n\n[{} GB]({} GB)\n\n< Updated >\n{}\n\n< Added >\n{}\n\n< Removed >\n{}```".format(
            str(newRepoSize),
            repoChangeString,
            "\n".join(newChangelog["updatedAddons"]),
            "\n".join(newChangelog["newAddons"]),
            "\n".join(newChangelog["deletedAddons"])
        )

        lastModified['a3sync_size'] = newRepoSize
        lastModified['revision'] = newRevision

        with open('resources/last_modified.json', 'w') as f:
            json.dump(lastModified, f)
        
        return True, updatePost

    @LastModified.uses_lastModified
    async def handleGithub(self):
        logger.debug("handleGithub called")

        repoUrl = 'https://api.github.com/repos'
        lastModified = {}

        with open('resources/last_modified.json', 'r') as f:
            lastModified = json.load(f)

        updatePost = ""
        repoChanged = False

        for mod in config['github']:
            url = "{}/{}/releases/latest".format(repoUrl, config['github'][mod])
            if mod in lastModified['github']:
                headers = {'Authorization': GITHUB_TOKEN,
                           'If-Modified-Since': lastModified['github'][mod]}
            else:
                headers = {'Authorization': GITHUB_TOKEN}

            async with self.session.get(url, headers = headers) as response:
                if response.status == 200:  # Repo has been updated
                    logger.info("Response 200 Success: %s", mod)
                    repoChanged = True

                    lastModified['github'][mod] = response.headers['Last-Modified']
                    response = await response.json()

                    changelogUrl = "https://github.com/{}/releases/tag/{}".format(config['github'][mod], response['tag_name'])
                    updatePost += "**{}** has released a new version ({})\n<{}>\n".format(mod, response['tag_name'],
                                                                                          changelogUrl)
                else:
                    if response.status != 304:  # 304 = repo not updated
                        logger.warning("%s GET error: %s %s - %s", mod, response.status, response.reason,
                                       await response.text())

        with open('resources/last_modified.json', 'w') as f:
            json.dump(lastModified, f)

        return repoChanged, updatePost

    @LastModified.uses_lastModified
    async def handleCup(self):
        logger.debug("handleCup called")

        lastModified = {}

        with open('resources/last_modified.json', 'r') as f:
            lastModified = json.load(f)

        updatePost = ""
        repoChanged = False

        async with self.session.get('https://www.cup-arma3.org/download') as response:
            if response.status == 200:
                logger.info("Response 200 - Success")
                soup = BeautifulSoup(await response.text(), features = "lxml")

                for header in soup.find_all('h3'):
                    modName = header.text
                    modVersion = header.parent.findNext("p").text
                    modVersion = modVersion.split()[0]

                    if modName in lastModified['cup']:
                        if modVersion != lastModified['cup'][modName]:
                            logger.info("Mod '%s' has been updated", modName)

                            repoChanged = True
                            lastModified['cup'][modName] = modVersion

                            updatePost += "**{}** has released a new version ({})\n".format(modName, modVersion)
                    else:
                        logger.debug("Mod '%s' not in lastModified", modName)
                        lastModified['cup'][modName] = modVersion
            else:
                logger.warning("cup GET error: %s %s - %s", response.status, response.reason, await response.text())

        with open('resources/last_modified.json', 'w') as f:
            json.dump(lastModified, f)

        return repoChanged, updatePost

    @LastModified.uses_lastModified
    async def handleSteam(self):
        logger.debug("handleSteam called")

        # https://partner.steamgames.com/doc/webapi/ISteamRemoteStorage
        steamUrl = 'https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/'
        lastModified = {}

        with open('resources/last_modified.json', 'r') as f:
            lastModified = json.load(f)

        data = {'itemcount': len(config['steam'])}

        i = 0
        for modId in config['steam']:
            data["publishedfileids[{}]".format(str(i))] = config['steam'][modId]
            i += 1

        updatePost = ""
        repoChanged = False

        async with self.session.post(steamUrl, data = data) as response:
            if response.status == 200:
                logger.info("Response 200 - Success")
                response = await response.json()
                filedetails = response['response']['publishedfiledetails']

                for mod in filedetails:
                    modName = mod['title']
                    timeUpdated = str(mod['time_updated'])

                    if modName in lastModified['steam']:
                        if timeUpdated != lastModified['steam'][modName]:
                            logger.info("Mod '%s' has been updated", modName)

                            repoChanged = True
                            lastModified['steam'][modName] = timeUpdated

                            updatePost += "**{}** has released a new version ({})\n{}\n".format(modName, "",
                                            "<https://steamcommunity.com/sharedfiles/filedetails/changelog/{}>".format(mod['publishedfileid']))
                            updatePost += "```\n{}```\n".format(await self.getSteamChangelog(mod['publishedfileid']))
                    else:
                        logger.info("Mod '%s' added to lastModified", modName)
                        lastModified['steam'][modName] = timeUpdated
            else:
                logger.warning("steam POST error: %s %s - %s", response.status, response.reason, await response.text())

        with open('resources/last_modified.json', 'w') as f:
            json.dump(lastModified, f)

        return repoChanged, updatePost

    async def getSteamChangelog(self, modId):
        steamUrl = "https://steamcommunity.com/sharedfiles/filedetails/changelog/{}".format(modId)

        async with self.session.get(steamUrl) as response:
            if response.status == 200:
                soup = BeautifulSoup(await response.text(), features = "lxml")
                headline = soup.find("div", {"class": "changelog headline"})
                return headline.findNext("p").get_text(separator = "\n")
            print("steam GET error: {} {} - {}".format(response.status, response.reason, await response.text()))

        return ""

    # ===Listeners=== #

    def cog_unload(self):
        logger.warning("Cancelling tasks...")
        self.calendarTask.cancel()
        self.attendanceTask.cancel()
        self.modcheckTask.cancel()
        self.recruitTask.cancel()
        self.presenceTask.cancel()
        self.a3syncTask.cancel()
        logger.warning("Tasks cancelled at %s", datetime.now())

    @commands.Cog.listener()
    async def on_ready(self):
        self.utility = self.bot.get_cog("Utility")

        self.calendar.remake()
        self.calendar.storeCalendar()

        await self.r3.createPool()

        self.calendarTask.start()
        self.attendanceTask.start()
        self.modcheckTask.start()
        self.recruitTask.start()
        self.presenceTask.start()
        self.a3syncTask.start()


def setup(bot):
    bot.add_cog(Tasking(bot))
