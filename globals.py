import discord
from discord.ext import commands
from quart import Quart
import os

from config import load_config

CONFIG = load_config()
BOT = commands.Bot(command_prefix="!", intents=discord.Intents.default())
PREVIOUS_NC_FILES = set()
NC_INITIALIZED = False

WEB_APP = Quart("__main__")
WEB_APP.secret_key = os.urandom(24)
INDEX_HTML = "index.html"