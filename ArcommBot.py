import os
from dotenv import load_dotenv
import logging
import logging.handlers

from discord.ext import commands

load_dotenv()

bot = commands.Bot(command_prefix = '.', case_insensitive = True)

TOKEN = os.getenv("DISCORD_TOKEN")
startup_extensions = ["utility", "dev", "tasking", "staff", "public", "comp"]

def setupLogging():
    logger = logging.getLogger('discord')
    logger.setLevel(logging.DEBUG)
    handler = logging.handlers.TimedRotatingFileHandler(filename = 'logs/discord.log', when = 'h', interval = 6, backupCount = 4, encoding = 'utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
    logger.addHandler(handler)

    logger = logging.getLogger('bot')
    logger.setLevel(logging.DEBUG)
    handler = logging.handlers.TimedRotatingFileHandler(filename = 'logs/bot.log', when = 'h', interval = 6, backupCount = 4, encoding = 'utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
    logger.addHandler(handler)

def loadExtensions():
    logger = logging.getLogger('bot')
    
    for extension in startup_extensions:
        try:
            bot.load_extension("cogs." + extension)
            logger.info("=========Loaded {} extension=========".format(extension))
        except Exception as e:
            logger.critical("Failed to load {} extension\n".format(extension))
            logger.critical(e)   

if __name__ == "__main__":
    setupLogging()
    loadExtensions()

    while True:     
        bot.loop.run_until_complete(bot.start(TOKEN))
        
        print("Reconnecting")
        bot.client = commands.Bot(command_prefix = '.', case_insensitive = True, loop = bot.loop)