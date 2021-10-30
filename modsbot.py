import logging
import re
import threading
import time
import traceback

import discord
import schedule
from discord.ext import commands
from ruamel import yaml

import sqlite3

cfgfile = open("config/config.yml")
config = yaml.safe_load(cfgfile)


class MODSBot(commands.Bot):
    def __init__(self, prefix):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(prefix, intents=intents)
        self.config = config
        logging.basicConfig(level=logging.INFO, format='[%(name)s %(levelname)s] %(message)s')
        self.logger = logging.getLogger('bot')
        try:
            with open(f'config/{config["blacklist"]}', 'r') as blacklist:
                self.blacklist = list(map(
                    int, filter(lambda x: x.strip(), blacklist.readlines())
                ))
        except IOError:
            self.blacklist = []

    async def on_ready(self):
        self.logger.info('Connected to Discord')
        self.logger.info('Guilds  : {}'.format(len(self.guilds)))
        self.logger.info('Users   : {}'.format(len(set(self.get_all_members()))))
        self.logger.info('Channels: {}'.format(len(list(self.get_all_channels()))))
        await self.set_presence("MODSBot: use -help")

        # Set up some stuff in data/modsdb.db
        db = sqlite3.connect('data/modsdb.db')
        cursor = db.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
            setting CHAR(20) PRIMARY KEY NOT NULL,
            value TEXT
            )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS potd_ping (
            user_id CHAR(20) PRIMARY KEY NOT NULL,
            categories CHAR(4),
            min INT,
            max INT
            )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS potd_info (
            potd_id TEXT NOT NULL,
            problem_msg_id TEXT,
            source_msg_id TEXT,
            ping_msg_id TEXT
            )''')
        db.commit()

        for cog in self.config['cogs']:
            try:
                self.load_extension(cog)
            except Exception:
                self.logger.exception('Failed to load cog {}.'.format(cog))
            else:
                self.logger.info('Loaded cog {}.'.format(cog))

    async def on_message(self, message):
        if message.author.bot: return
        
        # Mute for spam
        spam = False
        if re.search(r'http://|https://', message.content):
            if re.search('discord', message.content, re.I) and re.search('nitro', message.content, re.I):
                spam = True
            for i in message.embeds:
                print(i.title + i.description)
                if re.search('discord', i.title + i.description, re.I) and re.search('nitro', i.title + i.description, re.I):
                    spam = True
        if spam:
            try:
                log_message = f'Muted {message.author.mention} ({message.author.id}) for spam:\n```{message.content}```'
                await message.delete()
                await message.author.add_roles(message.guild.get_role(self.config['muted_role']))
                await message.guild.get_channel(self.config['log_channel']).send(log_message)
                await message.guild.get_channel(self.config['warn_channel']).send(log_message)
            except Exception:
                pass
            return
        
        if message.author.id in self.blacklist: return
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
                    await ctx.send('Permissions error: `{}`'.format(exception))
                except discord.Forbidden:
                    # we can't send messages in that channel
                    pass
                return

            elif isinstance(exception.original, discord.HTTPException):
                try:
                    await ctx.send('Sorry, I can\'t send that.')
                except discord.Forbidden:
                    pass

                return

            # Print to log then notify developers
            try:
                lines = traceback.format_exception(type(exception),
                                                   exception,
                                                   exception.__traceback__)
            except RecursionError:
                raise exception

            self.logger.error(''.join(lines))

            return

        if isinstance(exception, commands.CheckFailure):
            await ctx.send("You are not authorised to use this command. ")
        elif isinstance(exception, commands.CommandOnCooldown):
            exception: commands.CommandOnCooldown
            await ctx.send(f'You\'re going too fast! Try again in {exception.retry_after:.5f} seconds.')

        elif isinstance(exception, commands.CommandNotFound):
            if isinstance(ctx.channel, discord.DMChannel):
                await ctx.send("Command not recognised, please type `-help` for help.")

        elif isinstance(exception, commands.UserInputError):
            error = ' '.join(exception.args)
            error_data = re.findall('Converting to \"(.*)\" failed for parameter \"(.*)\"\.', error)
            if not error_data:
                await ctx.send('Huh? {}'.format(' '.join(exception.args)))
            else:
                await ctx.send('Huh? I thought `{1}` was supposed to be a `{0}`...'.format(*error_data[0]))
        else:
            info = traceback.format_exception(type(exception), exception, exception.__traceback__, chain=False)
            self.logger.error('Unhandled command exception - {}'.format(''.join(info)))


def executor():
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    with open(f'config/{config["token"]}') as tokfile:
        token = tokfile.readline().rstrip('\n')

    x = threading.Thread(target=executor, args=(), daemon=True)
    x.start()
    MODSBot(config['prefix']).run(token)
