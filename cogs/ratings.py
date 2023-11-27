import statistics
from datetime import datetime, timezone

import discord
from discord.ext import commands
from discord.ext.commands import BucketType

from cogs.config import Config as cfg

Cog = commands.Cog

from utils import potd_utils


class Ratings(Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def format(self, rating):
        if rating >= 10:
            return f"d||`{rating}`||"
        return f"d||`{rating} `||"

    @commands.command(aliases=["rate"], brief="Rates a potd based on difficulty. ")
    async def potd_rate(self, ctx, potd: int, rating: int, overwrite: bool = False):
        if rating < 0 or rating > 14:
            await ctx.send(
                f"<@{ctx.author.id}> POTD rating is only allowed from 0 to 14."
            )
            return

        # Delete messages if it's in a guild
        if ctx.guild is not None:
            await ctx.message.delete()

        async with cfg.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                rating_info = {"potd_id": potd, "user": ctx.author.id, "rating": rating}
                await cursor.execute(
                    f"SELECT * FROM ratings where potd_id = :potd_id and user_id = :user",
                    rating_info,
                )
                result = await cursor.fetchone()
                # print(result)
                if result is None:
                    await cursor.execute(
                        "INSERT INTO ratings (potd_id, user_id, rating) VALUES (:potd_id, :user, :rating)",
                        rating_info,
                    )
                    await ctx.send(
                        f"<@{ctx.author.id}> You have rated POTD {potd} {self.format(rating)}."
                    )
                else:
                    if not overwrite:
                        await ctx.send(
                            f"<@{ctx.author.id}> You already rated this POTD {self.format(rating)}. "
                            f"If you wish to overwrite append `True` to your previous message, like `-rate {potd} <rating> True` "
                        )
                    else:
                        await cursor.execute(
                            """UPDATE ratings SET rating = :rating
                                WHERE potd_id = :potd_id AND user_id = :user""",
                            rating_info,
                        )
                        await ctx.send(
                            f"<@{ctx.author.id}> You have rated POTD {potd} {self.format(rating)}."
                        )
        await potd_utils.edit_source(self.bot, potd)

    def formatting_error(self, string):
        return f'There seems to be a formatting error with "||`{string}`||". All lines should be of the form `[potd day]      [rating]`.'

    @commands.command(
        aliases=["mass_rate"],
        brief="Rate multiple POTDs at a time",
        help="`-mass_rate`: Rate up to 200 POTDs at a time\n"
        "\n"
        "Usage: List out POTDs and your corresponding rating, split by rows\n"
        "e.g.\n"
        "\n"
        "-mass_rate\n"
        "1 1\n"
        "2            2\n"
        "3   13\n"
        "\n"
        "Would allow you to rate POTD 1 as d1, POTD 2 as d2, and POTD 3 as d13.",
    )
    @commands.cooldown(1, 30, BucketType.user)
    async def potd_mass_rate(self, ctx, *, user_input: str):
        # Delete messages if it's in a guild
        if ctx.guild is not None:
            await ctx.message.delete()

        potds = user_input.split("\n")
        if len(potds) > 200:
            await ctx.send("Please don't send more than 200 POTDs per call.")
            return
        rating_dicts = []
        for string in potds:
            if string != "":
                data = string.split()
                if len(data) != 2:
                    await ctx.send(self.formatting_error(string))
                try:
                    rating_dicts.append(
                        {
                            "potd_id": int(data[0]),
                            "rating": int(data[1]),
                            "user_id": ctx.author.id,
                        }
                    )
                except ValueError:
                    await ctx.send(self.formatting_error(string))

        # Fetch all ratings already given
        async with cfg.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT potd_id FROM ratings WHERE user_id = ?", (ctx.author.id)
                )
                rated_all = await cursor.fetchall()
                # Flatten rated_all
                rated_all = [potd[0] for potd in rated_all]

                unrated = [
                    data for data in rating_dicts if data["potd_id"] not in rated_all
                ]
                already_rated = [
                    data for data in rating_dicts if data["potd_id"] in rated_all
                ]

                for rating_dict in unrated:
                    await cursor.execute(
                        "INSERT INTO ratings (potd_id, user_id, rating) VALUES (:potd_id, :user_id, :rating)",
                        rating_dict,
                    )

        if len(unrated) == 1:
            await ctx.send(
                f"You have rated POTD {unrated[0]['potd_id']} {self.format(unrated[0]['rating'])}. \n"
            )
        elif len(unrated) > 1:
            await ctx.send(
                f"You have rated POTDs {', '.join(str(potd_dict['potd_id']) for potd_dict in unrated)}."
            )

        if len(already_rated) == 1:
            potd = already_rated[0]["potd_id"]
            await ctx.send(
                f"You have already rated POTD {potd}. Use `-rate {potd} <rating> True` to change your rating."
            )
        elif len(already_rated) > 1:
            await ctx.send(
                f"You have already rated POTDs {', '.join(str(potd_dict['potd_id']) for potd_dict in already_rated)}. Use `-rate [potd] <rating> True` to individually re-rate each one."
            )

    @commands.command(aliases=["rating"], brief="Finds the median of a POTD's ratings")
    async def potd_rating(self, ctx, potd: int, full: bool = True):
        result = await potd_utils.unblacklisted_ratings(ctx.author.id, potd)
        if len(result) == 0:
            await ctx.send(f"No ratings for POTD {potd} yet. ")
        else:
            # Convert to float so there's always a trailing .0 or .5
            median = float(statistics.median([row[2] for row in result]))

            await ctx.send(
                f"Median community rating for POTD {potd} is {self.format(median)}. "
            )
            if full:
                embed = discord.Embed()
                embed.add_field(
                    name=f"Full list of community rating for POTD {potd}",
                    value="\n".join(
                        [f"<@!{row[1]}>: {self.format(row[2])}" for row in result]
                    ),
                )
                await ctx.send(embed=embed)

    @commands.command(aliases=["myrating"], brief="Checks your rating of a potd. ")
    async def potd_rating_self(self, ctx, potd: int):
        async with cfg.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT rating FROM ratings WHERE potd_id = ? AND user_id = ?",
                    (potd, ctx.author.id),
                )
                result = await cursor.fetchone()
        if result is None:
            await ctx.author.send(f"You have not rated potd {potd}. ")
        else:
            await ctx.author.send(
                f"You have rated potd {potd} as difficulty level {result[0]}."
            )

    @commands.command(aliases=["myratings"], brief="Checks all your ratings. ")
    async def potd_rating_all(self, ctx):
        async with cfg.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT potd_id, rating FROM ratings WHERE user_id = ?",
                    (ctx.author.id),
                )
                result = await cursor.fetchall()
        if len(result) == 0:
            await ctx.author.send("You have not rated any problems!")
        else:
            ratings = "\n".join([f"{i[0]:<6}{i[1]}" for i in result])
            await ctx.author.send(
                f"Your ratings: ```Potd  Rating\n{ratings}```You have rated {len(result)} potds. "
            )

    @commands.command(
        aliases=["rmrating", "unrate"], brief="Removes your rating for a potd. "
    )
    async def potd_rating_remove(self, ctx, potd: int):
        remove_info = {"potd_id": potd, "user_id": ctx.author.id}
        async with cfg.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """SELECT rating FROM ratings 
                    WHERE potd_id = :potd_id AND user_id = :user_id""",
                    remove_info,
                )
                result = await cursor.fetchone()
                if result is None:
                    await ctx.author.send(f"You have not rated potd {potd}. ")
                else:
                    await cursor.execute(
                        "DELETE FROM ratings WHERE potd_id = :potd_id AND user_id = :user_id",
                        remove_info,
                    )
                    await ctx.author.send(
                        f"Removed your rating of difficulty level {result[0]} for potd {potd}. "
                    )
                    await potd_utils.edit_source(self.bot, potd)

    @commands.command(
        aliases=["blacklist", "rater_blacklist"],
        brief="Blacklist a user from community rating. ",
    )
    async def potd_rater_blacklist(self, ctx, user_id: int):
        user = self.bot.get_user(user_id)
        if user is not None:
            blacklisted_users = await potd_utils.blacklist(ctx.author.id)
            if str(user_id) not in blacklisted_users:
                async with cfg.pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute(
                            """INSERT INTO potd_rater_blacklist (user_id, blacklisted_user_id, datetime)
                            VALUES (?, ?, ?)""",
                            (ctx.author.id, user_id, datetime.now()),
                        )
                await ctx.send(f"User {user.display_name} is added to your blacklist.")
            else:
                await ctx.send(
                    f"User {user.display_name} is already in your blacklist."
                )
        else:
            await ctx.send(f"User with ID {user_id} is not found!")

    @commands.command(
        aliases=["unblacklist", "rater_unblacklist"],
        brief="Unblacklist a user from community rating. ",
    )
    async def potd_rater_unblacklist(self, ctx, user_id: int):
        async with cfg.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """DELETE FROM potd_rater_blacklist
                    WHERE blacklisted_user_id = ? AND user_id = ?""",
                    (user_id, ctx.author.id),
                )

        user = self.bot.get_user(user_id)
        await ctx.send(f"User {user} is removed from your blacklist.")

    @commands.command(aliases=["myblacklist"], brief="Get your potd rating blacklist.")
    async def potd_myblacklist(self, ctx):
        blacklisted_users = await potd_utils.blacklist(ctx.author.id)

        embed = discord.Embed()
        embed.add_field(
            name=f"{ctx.author.display_name}'s POTD rating blacklist",
            value="\n".join(
                [
                    f"<@!{blacklisted_users[i][0]}>"
                    for i in range(len(blacklisted_users))
                ]
            ),
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Ratings(bot))
