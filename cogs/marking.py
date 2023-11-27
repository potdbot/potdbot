import random
from collections import defaultdict
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import BucketType

from cogs.config import Config as cfg

Cog = commands.Cog

from utils import potd_utils


# Commands involving todo/read/solved lists
class Marking(Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Adds/updates status of POTD
    async def potd_status_update(self, ctx, user_input, status):
        # Parse input
        try:
            potd_numbers = [int(i) for i in user_input.split(",")]
        except ValueError:
            await ctx.send("Error: The input contains non-integer values.")
            return

        if len(potd_numbers) > 200:
            await ctx.send("Please don't send more than 200 POTDs in each call.")
            return

        sorted_potds = {"added": [], "already": [], "no_potd": [], "has_discussion": []}
        # Update/add/check status in potd_status table
        values = await potd_utils.get_potd_values()
        async with cfg.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                for potd_number in potd_numbers:
                    mark_data = {
                        "author": ctx.author.id,
                        "potd": potd_number,
                        "status": status,
                        "datetime": datetime.now(),
                    }

                    await cursor.execute(
                        """SELECT status FROM potd_status
                           WHERE user_id = :author AND potd_id = :potd""",
                        mark_data,
                    )
                    result = await cursor.fetchone()
                    if result and result[0] == status:
                        sorted_potds["already"].append(str(potd_number))
                    else:
                        if result:
                            await cursor.execute(
                                """UPDATE potd_status SET status = :status, datetime = :datetime
                                   WHERE user_id = :author AND potd_id = :potd""",
                                mark_data,
                            )
                        else:
                            await cursor.execute(
                                """INSERT INTO potd_status
                                    (user_id, potd_id, status, datetime) 
                                    VALUES (:author, :potd, :status, :datetime)""",
                                mark_data,
                            )
                        sorted_potds["added"].append(str(potd_number))

                        potd_row = await potd_utils.get_potd_row(potd_number, values)
                        if (
                            potd_row is None
                            or len(potd_row) <= cfg.config["potd_sheet_statement_col"]
                        ):
                            sorted_potds["no_potd"].append(str(potd_number))
                        else:
                            if potd_row is not None:
                                if (
                                    len(potd_row)
                                    > cfg.config["potd_sheet_discussion_col"]
                                    and potd_row[
                                        cfg.config["potd_sheet_discussion_col"]
                                    ]
                                    is not None
                                    and potd_row[
                                        cfg.config["potd_sheet_discussion_col"]
                                    ]
                                    != ""
                                ):
                                    sorted_potds["has_discussion"].append(
                                        str(potd_number)
                                    )

        # Send confirm message
        messages = []
        if len(sorted_potds["added"]) != 0:
            if len(sorted_potds["added"]) == 1:
                if status == "todo":
                    messages.append(
                        f"POTD {sorted_potds['added'][0]} is added to your {status} list."
                    )
                else:
                    messages.append(
                        f"POTD {sorted_potds['added'][0]} is added to your {status} list. Use `-rate {sorted_potds['added'][0]} <rating>` if you want to rate the difficulty of this problem."
                    )
            else:
                messages.append(
                    f'POTD {",".join(sorted_potds["added"])} are added to your {status} list.'
                )
        if len(sorted_potds["already"]) != 0:
            if len(sorted_potds["already"]) == 1:
                messages.append(
                    f'POTD {sorted_potds["already"][0]} is already in your {status} list.'
                )
            else:
                messages.append(
                    f'POTD {",".join(sorted_potds["already"])} are already in your {status} list.'
                )
        if len(sorted_potds["no_potd"]) != 0:
            if len(sorted_potds["no_potd"]) == 1:
                messages.append(
                    f'There is no POTD {sorted_potds["no_potd"][0]}. Are you sure you have inputted the correct number?'
                )
            else:
                messages.append(
                    f'There are no POTD  {",".join(sorted_potds["no_potd"])}. Are you sure you have inputted the correct number?'
                )

        # Give discussion if marked as done
        if status != "todo":
            if len(sorted_potds["has_discussion"]) != 0:
                if len(sorted_potds["has_discussion"]) == 1:
                    messages.append(
                        f'There is discussion for POTD {sorted_potds["has_discussion"][0]}. Use `-discussion {sorted_potds["has_discussion"][0]}` to see the discussion.'
                    )
                else:
                    messages.append(
                        f"There are discussions for POTD {','.join(sorted_potds['has_discussion'])}. Use `-discussion <number>` to see the discussions."
                    )
        message = "\n".join(messages)
        await ctx.send(message)

    @commands.command(aliases=["mark"], brief="Mark the POTD you have solved")
    @commands.cooldown(1, 5, BucketType.user)
    async def potd_mark(self, ctx, *, user_input: str):
        await self.potd_status_update(ctx, user_input, "solved")

    @commands.command(aliases=["read"], brief="Mark the POTD you have read")
    @commands.cooldown(1, 5, BucketType.user)
    async def potd_read(self, ctx, *, user_input: str):
        await self.potd_status_update(ctx, user_input, "read")

    @commands.command(aliases=["todo"], brief="Mark the POTD into your TODO list")
    @commands.cooldown(1, 5, BucketType.user)
    async def potd_todo(self, ctx, *, user_input: str):
        await self.potd_status_update(ctx, user_input, "todo")

    async def potd_status_remove(self, ctx, user_input, status):
        # Parse input
        try:
            potd_numbers = [int(i) for i in user_input.split(",")]
        except ValueError:
            await ctx.send("Error: The input contains non-integer values.")
            return

        if len(potd_numbers) > 200:
            await ctx.send("Please don't send more than 200 POTDs in each call.")
            return

        async with cfg.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                for potd_id in potd_numbers:
                    await cursor.execute(
                        """DELETE FROM potd_status
                           WHERE user_id = ? AND potd_id = ?
                           AND status = ?""",
                        (ctx.author.id, potd_id, status),
                    )

        # Send confirm message
        if len(potd_numbers) == 1:
            await ctx.send(
                f"POTD {potd_numbers[0]} is removed from your {status} list. "
            )
        else:
            await ctx.send(f"POTDs {user_input} are removed from your {status} list. ")

    @commands.command(aliases=["unmark"], brief="Unmark the POTD from your solved list")
    @commands.cooldown(1, 5, BucketType.user)
    async def potd_unmark(self, ctx, *, user_input: str):
        await self.potd_status_remove(ctx, user_input, "solved")

    @commands.command(aliases=["unread"], brief="Unmark the POTD from your read list")
    @commands.cooldown(1, 5, BucketType.user)
    async def potd_unread(self, ctx, *, user_input: str):
        await self.potd_status_remove(ctx, user_input, "read")

    @commands.command(aliases=["untodo"], brief="Unmark the POTD from your TODO list")
    @commands.cooldown(1, 5, BucketType.user)
    async def potd_untodo(self, ctx, *, user_input: str):
        await self.potd_status_remove(ctx, user_input, "todo")

    @commands.command(
        aliases=["solved"],
        brief="Show the POTDs you have solved or read",
        help="`-solved`: Show the POTDs you have solved or read.\n"
        "`-solved d`: Show the POTDs you have solved or read, ordered by difficulties.\n"
        "`-solved s`: Show the POTDs you have solved or read, divided into the four subjects.\n",
    )
    @commands.cooldown(1, 5, BucketType.user)
    async def potd_solved(self, ctx, flag=None):
        solved = await potd_utils.get_potd_status("solved", ctx)
        read = await potd_utils.get_potd_status("read", ctx)

        potd_rows = await potd_utils.get_potd_values()
        current_potd = int(potd_rows[0][0])

        if len(solved) > 0:
            await self.generate_potd_list_output_string(
                solved, potd_rows, current_potd, flag, "solved", ctx
            )
        if len(read) > 0:
            await self.generate_potd_list_output_string(
                read, potd_rows, current_potd, flag, "read", ctx
            )
        if len(solved) == 0 and len(read) == 0:
            await ctx.send("Your solved list and read list are empty.")

    @commands.command(
        aliases=["mytodo"],
        brief="Show the POTDs in your TODO list",
        help="`-mytodo`: Show the POTDs in your TODO list.\n"
        "`-mytodo d`: Show the POTDs in your TODO list, ordered by difficulties.\n"
        "`-mytodo s`: Show the POTDs in your TODO list, divided into the four subjects.\n",
    )
    @commands.cooldown(1, 5, BucketType.user)
    async def potd_mytodo(self, ctx, flag=None):
        todo = await potd_utils.get_potd_status("todo", ctx)

        potd_rows = await potd_utils.get_potd_values()
        current_potd = int(potd_rows[0][0])

        if len(todo) > 0:
            await self.generate_potd_list_output_string(
                todo, potd_rows, current_potd, flag, "TODO", ctx, True
            )
        else:
            await ctx.send("Your TODO list is empty.")

    @commands.command(
        aliases=["unrated"],
        brief="Fetch a random POTD that you have solved/read but not yet rated",
        help="`-unrated`: Fetch a random POTD that you have solved/read but not yet rated.\n",
    )
    @commands.cooldown(1, 5, BucketType.user)
    async def potd_unrated(self, ctx, flag=None):
        solved = await potd_utils.get_potd_status("solved", ctx)
        read = await potd_utils.get_potd_status("read", ctx)
        rated = await potd_utils.get_potd_rated(ctx)

        unrated = [x for x in (solved + read) if x not in rated]

        picked_potd = random.choice(unrated)
        await potd_utils.potd_fetch(ctx, int(picked_potd))

    @commands.command(
        aliases=["unrated_list"],
        brief="Get the list of POTD that you have solved/read but not yet rated",
        help="`-unrated_list`: Get the list of POTD that you have solved/read but not yet rated.\n"
        "`-unrated_list d`: Get the list of POTD that you have solved/read but not yet rated, ordered by difficulties.\n"
        "`-unrated_list s`: Get the list of POTD that you have solved/read but not yet rated, divided into the four subjects.\n",
    )
    @commands.cooldown(1, 5, BucketType.user)
    async def potd_unrated_list(self, ctx, flag=None):
        solved = await potd_utils.get_potd_status("solved", ctx)
        read = await potd_utils.get_potd_status("read", ctx)
        rated = await potd_utils.get_potd_rated(ctx)

        solved_unrated = [x for x in solved if x not in rated]
        read_unrated = [x for x in read if x not in rated]

        potd_rows = await potd_utils.get_potd_values()
        current_potd = int(potd_rows[0][0])

        if len(solved_unrated) > 0:
            await self.generate_potd_list_output_string(
                solved_unrated,
                potd_rows,
                current_potd,
                flag,
                "unrated (solved)",
                ctx,
                True,
            )
        if len(read_unrated) > 0:
            await self.generate_potd_list_output_string(
                read_unrated, potd_rows, current_potd, flag, "unrated (read)", ctx, True
            )
        if len(solved_unrated) == 0 and len(read_unrated) == 0:
            await ctx.send("You have no unrated POTDs.")

    # Given a list of POTD numbers, print them by difficulty/subject
    async def generate_potd_list_output_string(
        self, potd_list, potd_rows, current_potd, flag, adjective, ctx, show_total=True
    ):
        potd_rows = await potd_utils.get_potd_values()
        if flag == "d":
            solved_by_difficulty = defaultdict(list)
            for number in potd_list:
                if number > current_potd or number <= 0:
                    difficulty = "(Unknown)"
                else:
                    potd_row = await potd_utils.get_potd_row(number, potd_rows)
                    if len(potd_row) > cfg.config["potd_sheet_difficulty_col"]:
                        difficulty = potd_row[cfg.config["potd_sheet_difficulty_col"]]
                    else:
                        difficulty = "(Unknown)"

                solved_by_difficulty[difficulty].append(number)

            sorted_keys = sorted(
                solved_by_difficulty.keys(),
                key=lambda x: (x.isnumeric(), int(x) if x.isnumeric() else x),
                reverse=True,
            )

            output_string = f"# __Your {adjective} POTD__ \n"
            for key in sorted_keys:
                if show_total:
                    total = len(
                        [
                            potd
                            for potd in potd_rows
                            if len(potd) > cfg.config["potd_sheet_difficulty_col"]
                            and potd[cfg.config["potd_sheet_difficulty_col"]] == key
                        ]
                    )
                    output_string += (
                        "**D"
                        + key
                        + ":** "
                        + f"{solved_by_difficulty[key]} ({len(solved_by_difficulty[key])}/{total})"
                        + "\n"
                    )
                else:
                    output_string += (
                        "**D" + key + ":** " + f"{solved_by_difficulty[key]} " + "\n"
                    )
            if show_total:
                output_string += f"(Total: {len(potd_list)}/{len(potd_rows)})"

        elif flag == "s":
            solved_by_genre = {"A": [], "C": [], "G": [], "N": []}
            for number in potd_list:
                if number > current_potd or number <= 0:
                    genre = "(Unknown)"
                else:
                    potd_row = potd_rows[current_potd - number]
                    if len(potd_row) > cfg.config["potd_sheet_genre_col"]:
                        genre = potd_row[cfg.config["potd_sheet_genre_col"]]
                    else:
                        genre = "(Unknown)"

                for subj in "ACGN":
                    if subj in genre:
                        solved_by_genre[subj].append(number)

            output_string = f"# __Your {adjective} POTD__ \n"
            for key in solved_by_genre:
                if show_total:
                    total = len(
                        [
                            potd
                            for potd in potd_rows
                            if len(potd) > cfg.config["potd_sheet_genre_col"]
                            and key in potd[cfg.config["potd_sheet_genre_col"]]
                        ]
                    )
                    output_string += (
                        "**"
                        + key
                        + ":** "
                        + f"{solved_by_genre[key]} ({len(solved_by_genre[key])}/{total})"
                        + "\n"
                    )
                else:
                    output_string += (
                        "**" + key + ":** " + f"{solved_by_genre[key]} " + "\n"
                    )
            if show_total:
                output_string += f"(Total: {len(potd_list)}/{len(potd_rows)})"

        elif flag == "sd":
            solved_ordered = {
                "A": defaultdict(list),
                "C": defaultdict(list),
                "G": defaultdict(list),
                "N": defaultdict(list),
            }
            for number in potd_list:
                if number > current_potd or number <= 0:
                    genre = "(Unknown)"
                    difficulty = "(Unknown)"
                else:
                    potd_row = potd_rows[current_potd - number]
                    if len(potd_row) > cfg.config["potd_sheet_genre_col"]:
                        genre = potd_row[cfg.config["potd_sheet_genre_col"]]
                    else:
                        genre = "(Unknown)"
                    if len(potd_row) > cfg.config["potd_sheet_difficulty_col"]:
                        difficulty = potd_row[cfg.config["potd_sheet_difficulty_col"]]
                    else:
                        difficulty = "(Unknown)"

                for subj in "ACGN":
                    if subj in genre:
                        solved_ordered[subj][difficulty].append(number)

            output_string = f"# __Your {adjective} POTD__ \n"
            for subj in solved_ordered:
                output_string += f"## {subj}: \n"
                sorted_keys = sorted(
                    solved_ordered[subj].keys(),
                    key=lambda x: (x.isnumeric(), int(x) if x.isnumeric() else x),
                    reverse=True,
                )
                for diff in sorted_keys:
                    if show_total:
                        total = len(
                            [
                                potd
                                for potd in potd_rows
                                if len(potd) > cfg.config["potd_sheet_difficulty_col"]
                                and len(potd) > cfg.config["potd_sheet_genre_col"]
                                and subj in potd[cfg.config["potd_sheet_genre_col"]]
                                and potd[cfg.config["potd_sheet_difficulty_col"]]
                                == diff
                            ]
                        )
                        output_string += (
                            "**D"
                            + diff
                            + ":** "
                            + f"{solved_ordered[subj][diff]} ({len(solved_ordered[subj][diff])}/{total})"
                            + "\n"
                        )
                    else:
                        output_string += f"**{diff}:** {solved_ordered[subj][diff]} \n"
                if show_total:
                    probs = [potd for l in solved_ordered[subj].values() for potd in l]
                    total_subj = len(
                        [
                            potd
                            for potd in potd_rows
                            if len(potd) > cfg.config["potd_sheet_genre_col"]
                            and potd[cfg.config["potd_sheet_genre_col"]] == subj
                        ]
                    )
                    output_string += f"(Total: {len(probs)}/{total_subj}) \n"
        else:
            if show_total:
                output_string = f"__**Your {adjective} POTD**__ \n{potd_list}" + "\n"
            else:
                output_string = f"__**Your {adjective} POTD**__ \n{potd_list}" + "\n"
            if show_total:
                output_string += f"(Total: {len(potd_list)}/{len(potd_rows)})"
        await self.send_potd_solved(ctx, output_string)

    # send message in batches of 1900+e characters because of 2k character
    # limit
    async def send_potd_solved(self, ctx, output_string):
        i = 0
        output_batch = ""
        while i < len(output_string):
            if output_batch == "":
                jump = min(1900, len(output_string) - i)
                output_batch += output_string[i : i + jump]
                i += jump
            else:
                output_batch += output_string[i]
                i += 1
            if (
                output_batch[-1] == ","
                or output_batch[-1] == "]"
                or len(output_batch) == 2000
                or i == len(output_string)
            ):  # we end a batch at "," or "]"
                await ctx.send(output_batch)
                output_batch = ""


async def setup(bot):
    await bot.add_cog(Marking(bot))
