import asyncio
import logging
import os
import sqlite3
import sys
import traceback
import tempfile

from discord.ext import commands
from discord import File
from twitchAPI import Twitch

logger = logging.getLogger('bot')

TWITCH_ID = os.getenv('TWITCH_ID')
TWITCH_SECRET = os.getenv('TWITCH_SECRET')

twitch = Twitch(TWITCH_ID, TWITCH_SECRET)
twitch.authenticate_app([])

DEV_IDS = [173123135321800704]

def is_dev():
    async def predicate(ctx):
        return ctx.author.id in DEV_IDS
    return commands.check(predicate)

class ClipsDB():
    def __init__(self):
        self.conn = sqlite3.connect('resources/clips.db')
        #self.remake()

    def remake(self):
        c = self.conn.cursor()
        try:
            #c.execute("DROP TABLE clips")
            c.execute("CREATE TABLE clips (link STRING PRIMARY KEY, broadcaster STRING NOT NULL, title STRING NOT NULL, view_count INTEGER, duration REAL, video_id INTEGER, date TEXT NOT NULL, time TEXT NOT NULL, type STRING)")
        except Exception as e:
            print(e)

    def storeClip(self, link, broadcaster, title, view_count, duration, video_id, date, time, _type):
        c = self.conn.cursor()

        try:
            c.execute("INSERT OR IGNORE INTO clips (link, broadcaster, title, view_count, duration, video_id, date, time, type) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)", (link, broadcaster, title, view_count, duration, video_id, date, time, _type))
        except Exception as e:
            print(e)

        self.conn.commit()

    def searchClips(self, searchQuery):
        c = self.conn.cursor()
        try:
            c.execute("SELECT * FROM clips {}".format(searchQuery))
            results = c.fetchall()
        except Exception as e:
            print(e)
            return str(e)

        return results

    def runSql(self, query):
        c = self.conn.cursor()
        try:
            c.execute(query)
            results = c.fetchall()
        except Exception as e:
            return e

        return results 

class Clips(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.clips = ClipsDB()
        self.utility = self.bot.get_cog("Utility")

    #===Commands===#

    @commands.command()
    async def clips(self, ctx, *args):
        searchQuery = " ".join(args)
        results = self.clips.searchClips(searchQuery)
        resultString = ""
        for result in results:
            #resultString += (str(result) + "\n")
            if (result[8] == "Clip"):
                resultString += "# {}\nPosted by {} on {} at {}\nDuration: {}\nViews: {}\nLink: https://clips.twitch.tv/{}\nSource: https://www.twitch.tv/videos/{}\n\n".format(result[2], result[1], result[6], result[7], result[4], result[3], result[0], result[5])
            elif (result[8] == "Video"):
                resultString += "# {}\nPosted by {} on {} at {}\nDuration: {}\nViews: {}\nLink: https://www.twitch.tv/videos/{}\n\n".format(result[2], result[1], result[6], result[7], result[4], result[3], result[0])

        await self.postResults(resultString, ctx.channel, len(results))

    @commands.command()
    async def clipsp(self, ctx, *args):
        searchQuery = " ".join(args)
        results = self.clips.searchClips(searchQuery)
        resultString = ""
        
        for result in results:
            resultString += "{}\n\n".format(str(result))
        
        await self.postResults(resultString, ctx.channel, len(results))
        
    @commands.command()
    @is_dev()
    async def clipsdev(self, ctx, *args):
        query = " ".join(args)
        results = self.clips.runSql(query)
        resultString = ""

        for result in results:
            resultString += "{}\n\n".format(str(result))

        await self.postResults(resultString, ctx.channel, len(results))    
    
    @commands.command()
    @is_dev()
    async def count(self, ctx):
        counter = 0
        succ = 0
        err = 0
        miss = 0
        async for message in self.utility.FOOTAGE_CHANNEL.history(limit=None):
            counter += 1
            if counter % 1000 == 0:
                await self.utility.send_message(ctx.channel, "{}, {}, {}, {}".format(counter, succ, miss, err))
            try:
                clip, link = self.getClipAndLinkFromString(message.clean_content)
                if (link != None):
                    if (clip != None):
                        video = self.getVideoFromVideoId(clip['video_id'])
                        videoId = None if (video == None) else clip['video_id']

                        createdDt = clip['created_at'][:-1].split('T')
                        createDate, createdTime = createdDt[0], createdDt[1]

                        self.clips.storeClip(link, clip['broadcaster_name'], clip['title'], clip['view_count'], None, videoId, createDate, createdTime, "Clip")
                        succ += 1
                        #await asyncio.sleep(0.3)
                    else:
                        miss += 1
                else:
                    video, id = self.getVideoAndIdFromString(message.clean_content)
                    if (id != None):
                        if (video != None):
                            createdDt = video['created_at'][:-1].split('T')
                            createDate, createdTime = createdDt[0], createdDt[1]

                            videoType = "Clip" if (str(video['type']) == "VideoType.HIGHLIGHT") else "Video"
                            self.clips.storeClip(video['id'], video['user_name'], video['title'], video['view_count'], video['duration'], video['id'], createDate, createdTime, videoType)
                            succ += 1
                            #await asyncio.sleep(0.3)
                        else:
                            miss += 1

            except Exception as e:
                err += 1
                print(e)
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                await self.utility.send_message(self.utility.TEST_CHANNEL, "{}, {}, {}".format(exc_type, fname, exc_tb.tb_lineno))
        await self.utility.send_message(ctx.channel, "Finished")
        
    #===Utility===#

    def getEmojiCountFromReactionList(self, emoji, reactionList):
        for reaction in reactionList:
            if (emoji == reaction.emoji):
                return reaction.count
        return 0
    
    def getClipAndLinkFromString(self, string):
        clipId = re.search("clips.twitch.tv/(\w+)", string)
        clip = None
        if (clipId):
            link = clipId.group(1)
            clip = twitch.get_clips(clip_id = [link])
            if ('data' in clip):
                clip = clip['data'][0]
                return clip, link
            return None, link
        return None, None

    def getVideoAndIdFromString(self, vidString):
        videoId = re.search("twitch.tv/videos/(\w+)", vidString)
        if (videoId):
            return self.getVideoFromVideoId(videoId.group(1)), videoId
        return None, None

    def getVideoFromVideoId(self, videoId):
        video = twitch.get_videos(ids=[videoId])
        if ('data' in video):
            video = video['data'][0]
            return video
        return None    
    
    async def postResults(self, resultString, channel, numResults):
        resultString = "```md\n{}```".format(resultString)
        
        if (len(resultString) <= 2000):
            await self.utility.send_message(channel, resultString)
        else:
            try:
                with open("resources/clip_results.txt", "w") as resultFile:
                    n = resultFile.write(resultString)
            except Exception as e:
                print(e)
                return

            await channel.send("{} results".format(numResults), file = File("resources/clip_results.txt", filename = "clip_results.txt"))
    
    #===Listeners===#
    
    @commands.Cog.listener()
    async def on_ready(self):
        self.utility = self.bot.get_cog("Utility")
        await self.utility.send_message(self.utility.TEST_CHANNEL, "ArcommBot is fully loaded")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if (payload.emoji.name == "📹"): #:video_camera:
            message = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
            
            if (self.getEmojiCountFromReactionList("👍", message.reactions) == 0):
                try:
                    clip, link = self.getClipAndLinkFromString(message.clean_content)
                    if (link != None):
                        if (clip != None):
                            video = self.getVideoFromVideoId(clip['video_id'])
                            videoId = None if (video == None) else clip['video_id']

                            createdDt = clip['created_at'][:-1].split('T')
                            createDate, createdTime = createdDt[0], createdDt[1]

                            self.clips.storeClip(link, clip['broadcaster_name'], clip['title'], clip['view_count'], None, videoId, createDate, createdTime, "Clip")
                            await message.add_reaction("👍")
                    else:
                        video, id = self.getVideoAndIdFromString(message.clean_content)
                        if (video != None):
                            createdDt = video['created_at'][:-1].split('T')
                            createDate, createdTime = createdDt[0], createdDt[1]

                            videoType = "Clip" if (video['type'] == "highlight") else "Video"
                            self.clips.storeClip(video['id'], video['user_name'], video['title'], video['view_count'], video['duration'], video['id'], createDate, createdTime, videoType)
                            await message.add_reaction("👍")

                except Exception as e:
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                    await self.utility.send_message(self.utility.TEST_CHANNEL, "{}, {}, {}".format(exc_type, fname, exc_tb.tb_lineno))


def setup(bot):
    bot.add_cog(Clips(bot))