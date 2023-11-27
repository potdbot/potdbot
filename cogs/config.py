import json
import os
from datetime import datetime, timezone

import asqlite
from aiogoogle import Aiogoogle
from aiogoogle.auth.creds import ServiceAccountCreds
from discord.ext import commands
from ruamel import yaml

Cog = commands.Cog


def timestamp(dt: datetime):
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return int((dt - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds())


class Config(Cog):
    config = None

    def __init__(self, bot):
        with open("config/config.yml") as cfgfile:
            Config.config = yaml.safe_load(cfgfile)
        self.bot = bot

    async def cog_load(self):
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        secret_file = os.path.join(os.getcwd(), "config/credentials.json")
        service_account_key = json.load(open(secret_file, "r"))
        creds = ServiceAccountCreds(scopes=scopes, **service_account_key)
        async with Aiogoogle(service_account_creds=creds) as aiogoogle:
            Config.service = await aiogoogle.discover("sheets", "v4")
            Config.aiogoogle = aiogoogle
        Config.spreadsheet = Config.service.spreadsheets

    @commands.command(
        aliases=["cfl"],
        brief="Gets a config variable from the loaded config.yml file. ",
    )
    async def config_load(self, ctx, name):
        if name not in Config.config:
            await ctx.send("No config with that name found!")
        else:
            await ctx.send(str(Config.config[name]))


async def setup(bot):
    await bot.add_cog(Config(bot))
    Config.pool = await asqlite.create_pool(f'data/{Config.config["dbname"]}.db')
