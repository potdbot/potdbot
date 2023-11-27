from datetime import datetime

import discord
import psutil
from discord.ext import commands

from cogs.config import Config as cfg

Cog = commands.Cog


# Miscellaneous commands
class Misc(Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def record(self):
        g = self.bot.get_guild(cfg.config["mods_guild"])

    # TODO: Make a database for tags
    @commands.command(
        aliases=["t"], brief="Sends the message associated with the given tag. "
    )
    async def retrieve_tag(self, ctx, *, tag):
        async with cfg.pool.acquire() as conn:
            async with conn.execute("SELECT tag, value FROM tags") as cursor:
                tag_dict = await cursor.fetchall()
        tag_dict = {t[0]: t[1] for t in tag_dict}

        if tag == "all":
            await ctx.send(f"Available tags: {tag_dict.keys()}")
        elif tag in tag_dict.keys():
            await ctx.send(tag_dict[tag])
        else:
            await ctx.send("I don't recognise that tag!")

    @commands.command(brief="Return my User ID")
    async def myid(self, ctx):
        name = ctx.author.name
        id = ctx.author.id
        await ctx.send(f"{name}'s User ID: {id}")

    @commands.command(brief="Gets information about POTDbot's status")
    async def info(self, ctx):
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        string = (
            "Use `-help` to get a list of commands, or `-t all` to find all tags.\n"
        )
        string += f"\n`   Developer:` a.fellow.human"
        string += f"\n` No. servers:` {len(self.bot.guilds)}"
        string += f"\n`   No. users:` {len(set(self.bot.get_all_members()))}"
        string += f"\n`      Uptime:` {str(datetime.now()-self.bot.startrun)}"
        string += f"\n`Commands run:` {self.bot.commands_run}"
        string += f"\n`Memory usage:` {(mem.total-mem.available)/(10**6):.0f} MB ({mem.percent}%) of {mem.total/(10**6):.0f} MB used"
        string += f"\n`  Disk usage:` {(disk.used)/(10**9):.2f} GB ({disk.percent}%) of {disk.total/(10**9):.2f} GB used"
        string += f"\n\n[Github Link]({cfg.config['github_link']}) | [Support my Patreon!]({cfg.config['patreon_link']})"

        embed = discord.Embed(title="About POTDBot", description=string, color=0x0097DF)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Misc(bot))
