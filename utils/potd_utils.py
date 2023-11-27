import asyncio
import io
import os
import random
import re
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import aiohttp
import discord
from pdf2image import convert_from_path

from cogs.config import Config as cfg

POTD_RANGE = "POTD!A2:S"
CURATOR_RANGE = "Curators!A3:E"


# Create png from latex string locally
async def generate_latex(latex, channel, spoiler):
    with open(f"config/{cfg.config['preamble']}", "r") as preamble:
        full_doc = preamble.read() + "\n" + latex + "\n" + r"\end{document}"
    file_name = str(uuid.uuid4())
    # Bots only spoil images if "SPOILER_" is in front
    if spoiler:
        file_name = "SPOILER_" + file_name

    # Run PDFLaTeX on tex code
    with open(f"{file_name}.tex", "w") as latex_file:
        latex_file.write(full_doc)
    pdflatex = await asyncio.create_subprocess_exec(
        "pdflatex",
        f"{file_name}.tex",
        "--interaction=nonstopmode",
        stdout=open(os.devnull, "wb"),
    )
    await pdflatex.wait()

    pic = convert_from_path(f"{file_name}.pdf", 500)[0]
    width, height = pic.size
    # Crop out white lines on edge of picture for some reason
    left = 5
    right = width - 5
    top = 5
    bottom = height - 5
    pic = pic.crop((left, top, right, bottom))
    pic.save(f"{file_name}.png")

    with open(f"{file_name}.png", "rb") as f:
        render = discord.File(f)
        await channel.send(file=render)

    # Delete files
    for fname in os.listdir("."):
        if fname.startswith(file_name):
            os.remove(fname)


async def texify_potd(potd_row, channel, spoiler) -> None:
    latex = (
        "\\textbf{Day "
        + str(potd_row[cfg.config["potd_sheet_id_col"]])
        + "} --- "
        + str(potd_row[cfg.config["potd_sheet_day_col"]])
        + " "
        + str(potd_row[cfg.config["potd_sheet_date_col"]])
        + "\\vspace{11pt}\\\\\\setlength\\parindent{1.5em}"
        + str(potd_row[cfg.config["potd_sheet_statement_col"]])
    )
    await generate_latex(latex, channel, spoiler)


def curator_id(curators, value):
    value = str(value)
    if value == "":
        return None
    for i in curators:
        for j in range(min(len(i), 4)):
            if value == str(i[j]):
                return i[0]
    return None


async def blacklist(caller_id):
    async with cfg.pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                """SELECT blacklisted_user_id
                FROM potd_rater_blacklist
                WHERE user_id = ?""",
                caller_id,
            )
            blacklisted_users = list(map(lambda x: x[0], await cursor.fetchall()))
            return blacklisted_users


async def unblacklisted_ratings(caller_id, potd):
    blacklisted_users = await blacklist(caller_id)
    # Create string "(?, ?, ..., ?)" with as many question marks as we need
    placeholders = "(" + ",".join(["?"] * len(blacklisted_users)) + ")"

    async with cfg.pool.acquire() as conn:
        async with conn.cursor() as cursor:
            if len(blacklisted_users) > 0:
                await cursor.execute(
                    f"""SELECT * FROM ratings 
                    WHERE potd_id = ? AND user_id not in {placeholders}
                    ORDER BY rating""",
                    (potd, *blacklisted_users),
                )
            else:
                await cursor.execute(
                    """SELECT * FROM ratings
                    WHERE potd_id = ? ORDER BY rating""",
                    potd,
                )
            result = await cursor.fetchall()
    return [list(row) for row in result]


# Create an embed showing info on a POTD
async def generate_source(potd_row, display=True, caller_id=0):
    # Figure out whose potd it is
    async with cfg.aiogoogle as aiogoogle:
        curators = (
            await cfg.aiogoogle.as_service_account(
                cfg.spreadsheet.values.get(
                    spreadsheetId=cfg.config["potd_sheet"], range=CURATOR_RANGE
                )
            )
        ).get("values", [])
    curator = curator_id(curators, potd_row[cfg.config["potd_sheet_curator_col"]])
    if curator is None:
        curator = "Unknown Curator"
    else:
        curator = f"<@!{curator}>"
    difficulty_length = len(potd_row[cfg.config["potd_sheet_genre_col"]]) + len(
        potd_row[cfg.config["potd_sheet_difficulty_col"]]
    )
    padding = " " * (max(35 - len(potd_row[cfg.config["potd_sheet_source_col"]]), 1))

    source = discord.Embed()
    source.add_field(name="Curator", value=curator)

    if display:
        source.add_field(
            name="Source",
            value=f'||`{potd_row[cfg.config["potd_sheet_source_col"]]}{padding}`||',
        )
        source.add_field(
            name="Difficulty",
            value=f'||`{str(potd_row[cfg.config["potd_sheet_difficulty_col"]]).ljust(5)}`||',
        )
        source.add_field(
            name="Genre",
            value=f'||`{str(potd_row[cfg.config["potd_sheet_genre_col"]]).ljust(5)}`||',
        )
    else:
        source.add_field(name="Source", value=f"(To be revealed)")
        source.add_field(name="Difficulty", value=f"(To be revealed)")
        source.add_field(name="Genre", value=f"(To be revealed)")

    # Community Rating footer
    results = await unblacklisted_ratings(
        caller_id, potd_row[cfg.config["potd_sheet_id_col"]]
    )
    community_rating = ""

    if len(results) > 0:
        community_rating += f"There are {len(results)} community difficulty ratings. "
        if display:
            try:
                underrate_count = sum(
                    row[2] < int(potd_row[cfg.config["potd_sheet_difficulty_col"]])
                    for row in results
                )
                if underrate_count > 0:
                    community_rating += (
                        f"{underrate_count} rated lower than current rating. "
                    )
                overrate_count = sum(
                    row[2] > int(potd_row[cfg.config["potd_sheet_difficulty_col"]])
                    for row in results
                )
                if overrate_count > 0:
                    community_rating += (
                        f"{overrate_count} rated higher than current rating. "
                    )
            except BaseException:
                pass
        community_rating += "\n"

    # Final footer
    source.set_footer(
        text=f"{community_rating}Use -rating "
        f'{potd_row[cfg.config["potd_sheet_id_col"]]} to check the '
        f"community difficulty rating of this problem or -rate "
        f'{potd_row[cfg.config["potd_sheet_id_col"]]} rating to rate it'
        f" yourself. React with a 👍 if you liked the problem. "
    )

    return source


async def edit_source(bot, potd):
    potd_row = await get_potd_row(potd)
    try:
        if datetime.now() - timedelta(hours=10, days=1) > datetime.strptime(
            potd_row[cfg.config["potd_sheet_date_col"]], "%d %b %Y"
        ):
            potd_source = await generate_source(potd_row, True)
        else:
            potd_source = await generate_source(potd_row, False)

        async with cfg.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """SELECT channel_id, potd_message_id FROM potd_info
                                         WHERE potd_id = ?""",
                    potd,
                )
                for channel_id, potd_message_id in cursor:
                    potd_source_msg = await bot.get_channel(channel_id).fetch_message(
                        potd_message_id
                    )
                    await potd_source_msg.edit(embed=potd_source)
    except:
        pass


async def get_potd_values():
    async with cfg.aiogoogle as aiogoogle:
        sheet = await aiogoogle.as_service_account(
            cfg.spreadsheet.values.get(
                spreadsheetId=cfg.config["potd_sheet"], range=POTD_RANGE
            )
        )
        values = sheet.get("values", [])
    return values


async def get_potd_row(number, values=None):
    # Output of get_potd_values() was not fed into get_potd_row
    if values is None:
        values = await get_potd_values()

    # this will be the top left cell which indicates the latest added potd
    current_potd = int(values[0][0])

    if number > current_potd or number < 1:
        return None

    try:
        # this gets the row requested
        potd_row = values[current_potd - number]
        return potd_row
    except IndexError:
        return None


def check_for_image_link(potd_row) -> Optional[str]:
    if len(potd_row) >= 19 and potd_row[
        cfg.config["potd_sheet_image_link_col"]
    ] not in [None, ""]:
        return potd_row[cfg.config["potd_sheet_image_link_col"]]
    else:
        return None


async def potd_fetch(ctx, number: int, flag: str = ""):
    potd_row = await get_potd_row(number)

    if potd_row is None:
        await ctx.send(f"There is no potd for day {number}. ")
        return
    else:
        # Create the message to send
        try:
            # if there is image link, just send it out
            image_link = check_for_image_link(potd_row)
            if image_link and "t" not in flag:
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_link) as resp:
                        if resp.status != 200:
                            return await ctx.send("Could not download file...")
                        data = io.BytesIO(await resp.read())
                        if "s" not in flag:
                            await ctx.send(file=discord.File(data, f"potd{number}.png"))
                        else:
                            await ctx.send(
                                file=discord.File(data, f"SPOILER_potd{number}.png")
                            )
            # if no image link, send tex
            else:
                if "s" not in flag:
                    await texify_potd(potd_row, ctx.channel, False)
                else:
                    await texify_potd(potd_row, ctx.channel, False)
        except IndexError:
            await ctx.send(f"There is no potd for day {number}. ")
            return


async def get_potd_status(status, ctx):
    async with cfg.pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                """SELECT potd_id FROM potd_status
                                    WHERE user_id = ? AND status = ?""",
                (ctx.author.id, status),
            )

            return [row[0] for row in await cursor.fetchall()]


async def get_potd_rated(ctx):
    async with cfg.pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT potd_id FROM ratings WHERE user_id = ?", ctx.author.id
            )
            return [row[0] for row in await cursor.fetchall()]


async def pick_potd(
    diff_lower_bound_filter,
    diff_upper_bound_filter,
    genre_filter,
    potds,
    already_picked,
    ctx,
    search_unsolved: bool,
):
    solved_potd = []
    if search_unsolved:
        get_solved_potd = await get_potd_status("solved", ctx)
        get_read_potd = await get_potd_status("read", ctx)
        solved_potd = get_solved_potd + get_read_potd

    def match_genre(x, genre_filter):
        for genre in genre_filter:
            if len(
                set(x[cfg.config["potd_sheet_genre_col"]]).intersection(genre)
            ) == len(genre):
                return True
        return False

    today = datetime.strptime(datetime.now().strftime("%d %b %Y"), "%d %b %Y")

    # filter by genre and difficulty
    if isinstance(diff_upper_bound_filter, int):
        filtered_potds = [
            x
            for x in potds
            if len(x)
            > max(
                cfg.config["potd_sheet_difficulty_col"],
                cfg.config["potd_sheet_genre_col"],
            )
            and x[cfg.config["potd_sheet_difficulty_col"]].isnumeric()
            and int(x[cfg.config["potd_sheet_difficulty_col"]])
            >= diff_lower_bound_filter
            and int(x[cfg.config["potd_sheet_difficulty_col"]])
            <= diff_upper_bound_filter
            and match_genre(x, genre_filter)
            and datetime.strptime(x[cfg.config["potd_sheet_date_col"]], "%d %b %Y")
            < today
        ]
    else:  # if diff bound is "T"
        filtered_potds = [
            x
            for x in potds
            if len(x)
            > max(
                cfg.config["potd_sheet_difficulty_col"],
                cfg.config["potd_sheet_genre_col"],
            )
            and (
                (
                    x[cfg.config["potd_sheet_difficulty_col"]].isnumeric()
                    and int(x[cfg.config["potd_sheet_difficulty_col"]])
                    >= diff_lower_bound_filter
                )
                or not x[cfg.config["potd_sheet_difficulty_col"]].isnumeric()
            )
            and match_genre(x, genre_filter)
            and datetime.strptime(x[cfg.config["potd_sheet_date_col"]], "%d %b %Y")
            < today
        ]

    # pick a POTD
    if len(filtered_potds) > 0:
        filtered_potds_id = list(
            map(lambda x: int(x[cfg.config["potd_sheet_id_col"]]), filtered_potds)
        )
        unsolved_potds_id = [
            x
            for x in filtered_potds_id
            if x not in solved_potd
            if x not in already_picked
        ]
        if len(unsolved_potds_id) > 0:
            picked_potd = int(random.choice(unsolved_potds_id))
        else:
            not_repeated_potds_id = [
                x for x in filtered_potds_id if x not in already_picked
            ]
            if len(not_repeated_potds_id) > 0:
                picked_potd = int(random.choice(not_repeated_potds_id))
            else:
                picked_potd = int(random.choice(filtered_potds_id))
        return picked_potd
    else:
        return None
