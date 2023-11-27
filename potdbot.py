import logging
import math
import re
import threading
import time
import traceback
from datetime import datetime

import asqlite
import discord
import schedule
from discord.ext import commands
from ruamel import yaml

cfgfile = open("config/config.yml")
config = yaml.safe_load(cfgfile)


class POTDBot(commands.Bot):
    def __init__(self, prefix):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(prefix, intents=intents)
        self.config = config
        logging.basicConfig(
            level=logging.INFO, format="[%(name)s %(levelname)s] %(message)s"
        )
        self.logger = logging.getLogger("bot")
        self.commands_run = 0
        self.startrun = datetime.now()

    async def on_ready(self):
        self.logger.info("Connected to Discord")
        self.logger.info("Guilds  : {}".format(len(self.guilds)))
        self.logger.info("Users   : {}".format(len(set(self.get_all_members()))))
        self.logger.info("Channels: {}".format(len(list(self.get_all_channels()))))
        await self.set_presence("POTDBot: use -help for help.")

        # Set up some stuff in db
        DATABASES_TO_CREATE = [
            """
            CREATE TABLE IF NOT EXISTS potd_ping2 (
                user_id INTEGER PRIMARY KEY,
                criteria TEXT
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS potd_info (
                potd_id INTEGER, 
                channel_id INTEGER, 
                source_message_id INTEGER, 
                PRIMARY KEY (potd_id, channel_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS potd_status (
                user_id INTEGER, 
                potd_id INTEGER, 
                status TEXT,
                datetime TEXT, 
                PRIMARY KEY (user_id, potd_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS ratings (
                potd_id INTEGER, 
                user_id INTEGER, 
                rating INTEGER,  
                PRIMARY KEY (potd_id, user_id)
            );
            """,
            """CREATE TABLE IF NOT EXISTS potd_rater_blacklist (
                user_id INTEGER, 
                blacklisted_user_id INTEGER, 
                datetime TEXT
            );""",
            """CREATE TABLE IF NOT EXISTS tags (
                tag TEXT,
                value TEXT
            );""",
        ]
        async with asqlite.connect(f'data/{config["dbname"]}.db') as conn:
            async with conn.cursor() as cursor:
                for database_creation_command in DATABASES_TO_CREATE:
                    await cursor.execute(database_creation_command)

        # Load cogs
        for cog in self.config["cogs"]:
            try:
                await self.load_extension(cog)
            except Exception:
                self.logger.exception("Failed to load cog {}.".format(cog))
            else:
                self.logger.info("Loaded cog {}.".format(cog))

        await self.tree.sync()

    async def on_message(self, message):
        if message.author.bot:
            return

        await self.process_commands(message)

    async def set_presence(self, text):
        game = discord.Game(name=text)
        await self.change_presence(activity=game)

    async def on_command_error(self, ctx: commands.Context, exception: Exception):
        if isinstance(exception, commands.CommandInvokeError):
            # all exceptions are wrapped in CommandInvokeError if they are not a subclass of CommandError
            # you can access the original exception with .original
            exception: commands.CommandInvokeError
            if isinstance(exception.original, discord.Forbidden):
                # permissions error
                try:
                    await ctx.send("Permissions error: `{}`".format(exception))
                except discord.Forbidden:
                    # we can't send messages in that channel
                    pass
                return

            elif isinstance(exception.original, discord.HTTPException):
                try:
                    await ctx.send("Sorry, I can't send that.")
                except discord.Forbidden:
                    pass

                return

            # Print to log then notify developers
            try:
                log_message = "".join(
                    traceback.format_exception(
                        type(exception), exception, exception.__traceback__
                    )
                )
            except RecursionError:
                raise exception

            self.logger.error(log_message)
            try:
                # send log messages in chunks to prevent hitting 2k char limit
                for i in range(0, min(len(log_message), 9500), 1900):
                    await ctx.send(f"```{log_message[i:i+1900]}```")
            except Exception:
                try:
                    await ctx.send("Failed to send error message.")
                except Exception:
                    pass

            return

        if isinstance(exception, commands.CheckFailure):
            await ctx.send("You are not authorised to use this command. ")
        elif isinstance(exception, commands.CommandOnCooldown):
            exception: commands.CommandOnCooldown
            await ctx.send(
                f"You're going too fast! Try again in {exception.retry_after:.5f} seconds."
            )

        elif isinstance(exception, commands.CommandNotFound):
            if isinstance(ctx.channel, discord.DMChannel):
                await ctx.send(
                    f"Command not recognised, please type `{config['prefix']}help` for help."
                )

        elif isinstance(exception, commands.UserInputError):
            error = " ".join(exception.args)
            error_data = re.findall(
                'Converting to "(.*)" failed for parameter "(.*)"\\.', error
            )
            if not error_data:
                await ctx.send("Huh? {}".format(" ".join(exception.args)))
            else:
                await ctx.send(
                    "Huh? I thought `{1}` was supposed to be a `{0}`...".format(
                        *error_data[0]
                    )
                )
        else:
            info = traceback.format_exception(
                type(exception), exception, exception.__traceback__, chain=False
            )
            log_message = "Unhandled command exception - {}".format("".join(info))
            self.logger.error(log_message)
            try:
                await ctx.send(f"```{log_message}```")
            except Exception:
                try:
                    await ctx.send("Failed to send error message.")
                except Exception:
                    pass

    async def on_command(self, ctx):
        self.commands_run += 1


def executor():
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    with open(f'config/{config["token"]}') as tokfile:
        token = tokfile.readline().rstrip("\n")

    x = threading.Thread(target=executor, args=(), daemon=True)
    x.start()
    POTDBot(config["prefix"]).run(token)
