import asyncio
import configparser
from datetime import datetime, timedelta
import json
import logging
import os
import re
import sqlite3
import traceback

import aiohttp
from bs4 import BeautifulSoup
from discord import File
from discord.ext import commands, tasks
from googleapiclient.discovery import build
from google.oauth2 import service_account
from pytz import timezone

logger = logging.getLogger('bot')

config = configparser.ConfigParser()
config.read('resources/config.ini')

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = 'resources/arcommbot-1c476e6f4869.json'

credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
service = build('calendar', 'v3', credentials = credentials)

class CalendarDB():
    def __init__(self):
        self.conn = sqlite3.connect('resources/calendar.db')
        self.collection = service.events()
        #self.remake()
        #self.storeCalendar()

    def remake(self):
        c = self.conn.cursor()
        try:
            #c.execute("DROP TABLE calendar")
            c.execute("CREATE TABLE calendar (event_id INTEGER PRIMARY KEY, summary STRING NOT NULL, start STRING NOT NULL, end STRING NOT NULL, UNIQUE(start))")
        except Exception as e:
            print(e)

    def storeCalendar(self, timeFrom = "now"):
        if timeFrom == "now":
            lastDT = datetime.now(tz = timezone("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            lastDT = timeFrom

        request = self.collection.list(calendarId = "arcommdrive@gmail.com", timeMin = lastDT, orderBy = "startTime", singleEvents = True)
        #request = self.collection.list(calendarId = "bmpdcnk8pab1drvf4qgt4q1580@group.calendar.google.com", timeMin = now, orderBy = "startTime", singleEvents = True)
        response = request.execute()
        c = self.conn.cursor()
        c.execute("DELETE FROM calendar")

        for item in response['items']:
            try:
                c.execute("INSERT OR IGNORE INTO calendar (summary, start, end) VALUES(?, ?, ?)", (item['summary'], item['start']['dateTime'], item['end']['dateTime']))
            except Exception as e:
                None

        self.conn.commit()

    def pop(self):
        c = self.conn.cursor()

        c.execute("SELECT * FROM calendar ORDER BY event_id ASC LIMIT 1")
        event = c.fetchone()
        c.execute("DELETE FROM calendar WHERE event_id = (SELECT min(event_id) FROM calendar)")
        
        self.conn.commit()
        
        return event

class Tasking(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
        self.calendar = CalendarDB()
        self.session = aiohttp.ClientSession()

    #===Tasks===#

    @tasks.loop(hours = 1)
    async def attendanceTask(self):
        logger.debug("attendanceTask called")
        targetTimeslot = [17, 20] #5pm -> 8pm

        now = datetime.utcnow()
        #now = datetime(2020, 4, 25, 17)
        if now.weekday() == 5: #Saturday
            if now.hour >= targetTimeslot[0] and now.hour <= targetTimeslot[1]:
                logger.debug("Called within timeslot")
                await self.attendancePost()

    @attendanceTask.before_loop
    async def before_attendanceTask(self):
        """Sync up attendanceTask to on the hour"""
        logger.debug("before_attendanceTask called")
        await self.bot.wait_until_ready()

        now = datetime.utcnow()
        #now = datetime(now.year, now.month, now.day, 16, 59, 55)
        future = datetime(now.year, now.month, now.day, now.hour + 1, 1)
        logger.debug("{} seconds until attendanceTask called".format((future - now).seconds))

        await asyncio.sleep((future - now).seconds)
    
    @tasks.loop(minutes = 1)
    async def calendarTask(self):
        try:
            lastDatetime = None
            with open('resources/calendar_datetime.json', 'r') as f:
                lastDatetime = json.load(f)
                
                if not ('datetime' in lastDatetime):
                    lastDatetime['datetime'] = "now"
                else:   #Make sure the lastDatetime isn't in the past, otherwise will be announcing old events
                    if lastDatetime['datetime'] != "now":
                        now = datetime.now(tz = timezone("UTC"))
                        lastDT = lastDatetime['datetime'].replace("Z", "+00:00")
                        lastDT = datetime.strptime(lastDT, "%Y-%m-%dT%H:%M:%S%z")

                        if lastDT < now:
                            lastDatetime['datetime'] = "now"

            self.calendar.storeCalendar(lastDatetime['datetime'])
            newAnnouncement = True

            while newAnnouncement:
                newAnnouncement = False
                event = self.calendar.pop()

                if event:
                    now = datetime.now(tz = timezone("UTC"))
                    eventStartTime = event[2].replace("Z", "+00:00")
                    eventStartTime = datetime.strptime(eventStartTime, "%Y-%m-%dT%H:%M:%S%z")

                    timeUntil = eventStartTime - now
                    if timeUntil <= timedelta(days = 0, hours = 1, minutes = 0) and timeUntil >= timedelta(days = 0, hours = 0, minutes = 10):
                        newAnnouncement = True
                        lastDatetime['datetime'] = event[3]
                        newTask = asyncio.Task(self.announce(timeUntil, event[1], event[2], event[3]))
                else:
                    logger.debug('No event popped')
                    break

            with open('resources/calendar_datetime.json', 'w') as f:
                json.dump(lastDatetime, f)

        except Exception as e:
            logger.warning(e)

    @tasks.loop(hours = 1)
    async def modcheckTask(self):
        logger.debug("modcheckTask called")

        try:
            githubChanged, githubPost = await self.handleGithub()
            cupChanged, cupPost = await self.handleCup()
            steamChanged, steamPost = await self.handleSteam()

            if githubChanged or cupChanged or steamChanged:
                channel = self.utility.STAFF_CHANNEL
                role = self.utility.ADMIN_ROLE_ID
                await self.utility.send_message(channel, "<@&{}>\n{}{}{}".format(role, githubPost, cupPost, steamPost))
        except Exception as e:
            logger.error(traceback.format_exc())
    
    @tasks.loop(hours = 24)
    async def recruitTask(self):
        logger.debug("recruitTask called")

        targetDays = [0, 2, 4] #Monday, Wednesday, Friday
        now = datetime.utcnow()
        #now = datetime(2020, 4, 22) #A Wednesday
        if now.weekday() in targetDays:
            logger.debug("Called within targetDays")
            channel = self.utility.STAFF_CHANNEL
            await self.recruitmentPost(channel, pingAdmins = True)

    @recruitTask.before_loop
    async def before_recruitTask(self):
        """Sync up recruitTask to targetHour:targetMinute:00"""
        logger.debug("before_recruitTask called")
        await self.bot.wait_until_ready()

        targetHour = 17
        targetMinute = 0
        
        now = datetime.utcnow()
        #now = datetime(now.year, now.month, now.day, 16, 59, 55)
        future = datetime(now.year, now.month, now.day, targetHour, targetMinute, 0, 0)

        if now.hour >= targetHour and now.minute > targetMinute:
            logger.debug("Missed timeslot, adding a day")
            future += timedelta(days = 1)

        logger.debug("{} seconds until recruitTask called".format((future - now).seconds))

        await asyncio.sleep((future - now).seconds)
    
    #===Utility===#

    async def announce(self, timeUntil, summary, startTime, endTime):
        startTime = datetime.strptime(startTime, "%Y-%m-%dT%H:%M:%S%z").astimezone(timezone("UTC"))
        startTimeString = startTime.strftime('%H:%M:%S')

        endTime = datetime.strptime(endTime, "%Y-%m-%dT%H:%M:%S%z").astimezone(timezone("UTC"))
        endTimeString = endTime.strftime('%H:%M:%S')

        timeUntilStr = str(timeUntil).split(".")[0] #Remove microseconds

        if re.search("recruit", summary.lower()) != None:
            ping = "<@&{}>".format(self.utility.RECRUIT_ROLE_ID)
        elif re.search("training", summary.lower()) != None:
            ping = "<@&{}>".format(self.utility.TRAINING_ROLE_ID)
        else:
            ping = "@here"

        outString = "{}\n```md\n# {}\n\nStarting in {}\n\nStart: {} UTC\nEnd:   {} UTC```".format(ping, summary, timeUntilStr, startTimeString, endTimeString)
        channel = self.utility.OP_NEWS_CHANNEL
        #outString = "{}\n```md\n# {}\n\nStarting in {}```".format(ping, summary, timeUntil)
        await self.utility.send_message(channel, outString)

        await asyncio.sleep((timeUntil - timedelta(minutes = 5)).seconds)

        outString = "{}\n```md\n# {}\n\nStarting in 5 minutes```".format(ping, summary)
        await self.utility.send_message(channel, outString)

    async def attendancePost(self):
        logger.debug("attendancePost called")

        channel = self.utility.ADMIN_CHANNEL
        role = self.utility.ADMIN_ROLE_ID
        outString = "<@&{}> Collect attendance!".format(role)

        await self.utility.send_message(channel, outString)
            
    async def recruitmentPost(self, channel, pingAdmins = False):
        logger.debug("recruitmentPost called")
        if pingAdmins:
            role = self.utility.ADMIN_ROLE_ID
            introString = "<@&{}> Post recruitment on <https://www.reddit.com/r/FindAUnit>".format(role)
        else:
            introString = "Post recruitment on <https://www.reddit.com/r/FindAUnit>"
        
        await channel.send(introString, file = File("resources/recruit_post.md", filename = "recruit_post.md"))
    
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
                if response.status == 200: #Repo has been updated
                    logger.info("Response 200 Success: {}".format(mod))
                    repoChanged = True

                    lastModified['github'][mod] = response.headers['Last-Modified']
                    response = await response.json()
                    
                    changelogUrl = "https://github.com/{}/releases/tag/{}".format(mod, response['tag_name'])
                    updatePost += "**{}** has released a new version ({})\n<{}>\n".format(mod, response['tag_name'], changelogUrl)
                elif response.status == 304: #Repo hasn't been updated
                    None
                    #logger.info("Response 304 - Not Changed: {}".format(mod))
                else:
                    logger.warning("{} GET error: {} {} - {}".format(mod, response.status, response.reason, await response.text()))
                
        with open('resources/last_modified.json', 'w') as f:
            json.dump(lastModified, f)

        return repoChanged, updatePost
    
    async def handleCup(self):
        logger.debug("handleCup called")

        lastModified = {}

        with open('resources/last_modified.json', 'r') as f:
            lastModified = json.load(f)

        updatePost = ""
        repoChanged = False

        async with self.session.get('http://cup-arma3.org/download') as response:
            if response.status == 200:
                logger.info("Response 200 - Success")
                soup = BeautifulSoup(await response.text(), features = "lxml")
                for row in soup.find('table', {'class': 'table'}).find_all('tr'):
                    td = row.find('td')
                    if td:
                        version = re.search(r' ([0-9.]+)(\S+)?', td.text).group(0)
                        name = re.sub(version, '', td.text)
                        version = version[1:] # Remove whitespace
                        
                        if name in lastModified['cup']:
                            if version != lastModified['cup'][name]:
                                logger.info("Mod '{}' has been updated".format(name))

                                repoChanged = True
                                lastModified['cup'][name] = version

                                urlName = name.replace(" ", "_")
                                changelogUrl = "<http://cup-arma3.org/downloads/CUP_{}-{}-changelog.txt>".format(urlName, version)
                                updatePost += "**{}** has released a new version ({})\n{}\n".format("CUP - {}".format(name), version, changelogUrl)
                            else:
                                None
                                #logger.info("Mod '{}' has not been updated".format(name))
                        else:
                            logger.debug("Mod '{}' not in lastModified".format(name))
                            lastModified['cup'][name] = version
            else:
                logger.warning("cup GET error: {} {} - {}".format(response.status, response.reason, await response.text()))
        
        with open('resources/last_modified.json', 'w') as f:
            json.dump(lastModified, f)

        return repoChanged, updatePost
    
    async def handleSteam(self):
        logger.debug("handleSteam called")
        steamUrl = 'https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/' # https://partner.steamgames.com/doc/webapi/ISteamRemoteStorage
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
                            logger.info("Mod '{}' has been updated".format(modName))

                            repoChanged = True
                            lastModified['steam'][modName] = timeUpdated

                            updatePost += "**{}** has released a new version ({})\n{}\n".format(modName, "", '<https://steamcommunity.com/sharedfiles/filedetails/changelog/{}>'.format(mod['publishedfileid']))
                            updatePost += "```\n{}```\n".format(await self.getSteamChangelog(mod['publishedfileid']))
                        else:
                            None
                            #logger.info("Mod '{}' has not been updated".format(modName))
                    else:
                        lastModified['steam'][modName] = timeUpdated
            else:
                logger.warning("steam POST error: {} {} - {}".format(response.status, response.reason, await response.text()))
            
        with open('resources/last_modified.json', 'w') as f:
            json.dump(lastModified, f)

        return repoChanged, updatePost
    
    async def getSteamChangelog(self, modId):
        steamUrl = "https://steamcommunity.com/sharedfiles/filedetails/changelog/{}".format(modId)

        async with self.session.get(steamUrl) as response:
            if response.status == 200:
                soup = BeautifulSoup(await response.text(), features = "lxml")
                headline = soup.find("div", {"class" : "changelog headline"})
                return headline.findNext("p").get_text(separator = "\n")
            else:
                print("steam GET error: {} {} - {}".format(response.status, response.reason, await response.text()))

        return ""

    #===Listeners===#

    @commands.Cog.listener()
    async def on_ready(self):
        self.utility = self.bot.get_cog("Utility")

        self.calendar.remake()
        self.calendar.storeCalendar()
        
        self.calendarTask.start()
        self.attendanceTask.start()
        self.modcheckTask.start()
        self.recruitTask.start()

def setup(bot):
    bot.add_cog(Tasking(bot))