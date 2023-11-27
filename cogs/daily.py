# Code's borked, not rewriting now.

import re
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
import schedule
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import BucketType

from cogs import config as cfg
from utils import potd_utils

Cog = commands.Cog


# Implementation of daily POTD posting
class Daily(Cog):
    def __init__(self, bot: commands.Bot):
        self.listening_in_channel = -1
        self.to_send = ""
        self.bot = bot
        self.ping_daily = False
        self.late = False
        self.requested_number = -1
        self.dm_list = []
        self.timer = None

        values = await potd_utils.get_potd_values()
        self.latest_potd = int(values[0][0])

        schedule.every().day.at("10:00", "UTC").do(self.schedule_potd).tag("cogs.potd")

    async def reset_potd(self, ctx=None):
        self.requested_number = -1
        self.listening_in_channel = -1
        self.to_send = ""
        self.late = False
        self.ping_daily = False
        self.dm_list = []
        try:
            self.timer.cancel()
        except Exception:
            pass
        self.timer = None

    def reset_if_necessary(self):
        if self.listening_in_channel != -1:
            self.bot.loop.create_task(self.reset_potd())

    async def prepare_dms(self, potd_row):
        def should_dm(x):
            for i in range(4):
                if (["a", "c", "g", "n"][i] in potd_row[5].lower()) and not (
                    x[1][4 * i] == "x"
                ):
                    if (
                        int(x[1][4 * i : 4 * i + 2])
                        <= d
                        <= int(x[1][4 * i + 2 : 4 * i + 4])
                    ):
                        return True
            return False

        try:
            d = int(potd_row[cfg.config["potd_sheet_difficulty_col"]])
        except Exception:
            return

        async with cfg.pool.acquire() as conn:
            async with conn.execute("SELECT * FROM potd_ping2") as cursor:
                result = await cursor.fetchall()
        self.dm_list = [i[0] for i in filter(should_dm, result)]

    def schedule_potd(self, mode=None):
        self.bot.loop.create_task(self.check_potd(mode))

    async def check_potd(self):
        # Get the potds from the sheet (API call)
        potds = await potd_utils.get_potd_values()
        bot_log = cfg.config["log_channel"]

        # Check today's potd
        next = datetime.now()
        date = next.strftime("%d %b %Y")
        soon = [(next + timedelta(days=i)).strftime("%d %b %Y") for i in range(1, 4)]
        potd_row = None
        fail = False
        j = 1
        for potd in potds:
            j += 1
            if len(potd) < 2:
                await self.bot.get_channel(cfg.config["log_channel"]).send(
                    f"Invalid entry at row {j}, potd = {potd}"
                )
                pass
            if passed_current:
                # Then there has not been a potd on that day.
                if len(potd) < 8:
                    fail = True
                    await curator_role.edit(mentionable=True)
                    await self.bot.get_channel(cfg.config["log_channel"]).send(
                        f"There was no potd on {potd[1]}!"
                    )
                    await curator_role.edit(mentionable=False)
            if potd[1] == date:
                passed_current = True
                potd_row = potd
                if len(potd) < 8 and (mode is None):  # There is no potd.
                    fail = True
                    await curator_role.edit(mentionable=True)
                    await self.bot.get_channel(cfg.config["log_channel"]).send(
                        f"There is no potd today!"
                    )
                    await curator_role.edit(mentionable=False)
                soon.remove(potd[1])
        if soon != []:
            await self.bot.get_channel(cfg.config["log_channel"]).send(
                f"Insufficient rows in the potd sheet! "
            )
        if fail:
            return

        # Otherwise, everything has passed and we are good to go.
        # Finish up
        self.requested_number = int(potd_row[0])
        self.latest_potd = int(potd_row[0])
        await self.prepare_dms(potd_row)
        self.to_send = await potd_utils.generate_source(potd_row, False)
        self.listening_in_channel = cfg.config["potd_channel"]
        self.ping_daily = True
        self.late = False
        potd_channel = self.bot.get_channel(cfg.config["potd_channel"])
        await potd_utils.texify_potd(potd_row, potd_channel, False)
        await self.create_potd_forum_post(self.requested_number)
        await potd_utils.edit_source(self.bot, self.requested_number - 1)
        # In case Paradox unresponsive
        self.timer = threading.Timer(20, self.reset_if_necessary)
        self.timer.start()

    async def create_potd_forum_post(self, number):
        forum = self.bot.get_channel(cfg.config["potd_forum"])
        await forum.create_thread(name=f"POTD {number}", content="potd")

    # Send embed after Paradox sends

    # TODO: Move this to check_potd
    @Cog.listener()
    async def on_message(self, message: discord.Message):
        if (
            message.channel.id == self.listening_in_channel
            and int(message.author.id) == cfg.config["paradox_id"]
        ):
            self.listening_in_channel = -1  # Prevent reset
            source_msg = await message.channel.send(embed=self.to_send)
            await source_msg.add_reaction("👍")
            if self.late:
                await source_msg.add_reaction("⏰")

            if message.channel.id == cfg.config["potd_channel"]:
                async with cfg.pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute(
                            "INSERT INTO potd_info (potd_id, channel_id, source_msg_id) VALUES",
                            (self.latest_potd, message.channel.id, source_msg.id),
                        )

            bot_log = self.bot.get_channel(cfg.config["log_channel"])

            ping_msg = None
            if self.ping_daily:
                r = self.bot.get_guild(cfg.config["potd_guild"]).get_role(
                    cfg.config["potd_role"]
                )
                await r.edit(mentionable=True)
                ping_msg = await message.channel.send(
                    "<@&{}>".format(cfg.config["potd_role"])
                )
                await r.edit(mentionable=False)

                bot_spam = self.bot.get_channel(cfg.config["bot_spam_channel"])
                potd_discussion_channel = self.bot.get_channel(
                    cfg.config["potd_discussion_channel"]
                )

                ping_embed = discord.Embed(
                    title=f"POTD {self.latest_potd} has been posted: ",
                    description=f"{potd_discussion_channel.mention}\n{message.jump_url}",
                    colour=0xDCDCDC,
                )
                for field in self.to_send.to_dict()["fields"]:
                    ping_embed.add_field(name=field["name"], value=field["value"])
                if message.attachments == []:
                    await bot_log.send("No attachments found! ")
                else:
                    ping_embed.set_image(url=message.attachments[0].url)
                    dm_failed = []
                    for id in self.dm_list:
                        user = self.bot.get_user(int(id))
                        try:
                            await user.send(embed=ping_embed)
                        except Exception:
                            dm_failed.append(id)
                    if dm_failed != []:
                        msg = "Remember to turn on DMs from this server to get private notifications! "
                        for id in dm_failed:
                            msg += f"<@{id}> "
                        await bot_spam.send(msg, embed=ping_embed)

            await self.reset_potd()
            await bot_log.send("POTD execution successful.")


async def setup(bot):
    await bot.add_cog(Daily(bot))
