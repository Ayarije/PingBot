import discord
from discord.ext import commands
from quart import Quart

from config import load_config

CONFIG = load_config()
BOT = commands.Bot(command_prefix="!", intents=discord.Intents.default())
PREVIOUS_NC_FILES = set()

WEB_APP = Quart("__main__")
INDEX_HTML = "templates/index.html"