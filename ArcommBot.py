import configparser
from dotenv import load_dotenv
import logging
import logging.handlers
import os
import subprocess
import sys

import discord
from discord.ext import commands

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

config = configparser.ConfigParser()
config.read('resources/config.ini')

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix = '.', case_insensitive = True, intents = intents)

@bot.event
async def on_message(message):
    try:
        await bot.process_commands(message)
    except Exception as e:
        exc = sys.exc_info()
        await message.channel.send("Type [{}], Value [{}]\nTraceback[{}]".format(exc[0], exc[1], exc[2]))

def setupLogging():
    logger = logging.getLogger('discord')
    logger.setLevel(logging.DEBUG)
    handler = logging.handlers.TimedRotatingFileHandler(filename = 'logs/discord.log', when = 'h', interval = 8, backupCount = 3, encoding = 'utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
    logger.addHandler(handler)

    logger = logging.getLogger('bot')
    logger.setLevel(logging.DEBUG)
    handler = logging.handlers.TimedRotatingFileHandler(filename = 'logs/bot.log', when = 'h', interval = 8, backupCount = 3, encoding = 'utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
    logger.addHandler(handler)

def loadExtensions():
    logger = logging.getLogger('bot')
    startupExtensions = config['cogs']
    
    for extension in startupExtensions:
        try:
            bot.load_extension("cogs." + extension)
            logger.info("=========Loaded {} extension=========".format(extension))
        except Exception as e:
            print(e)
            logger.critical("Failed to load {} extension\n".format(extension))
            logger.critical(e)   

def restart():
    subprocess.call(["python", os.path.join(sys.path[0], __file__)] + sys.argv[1:])

if __name__ == "__main__":
    setupLogging()
    loadExtensions()

    while True:     
        bot.loop.run_until_complete(bot.start(TOKEN))
        
        print("Reconnecting")
        bot.client = commands.Bot(command_prefix = '.', case_insensitive = True, intents = intents, loop = bot.loop)