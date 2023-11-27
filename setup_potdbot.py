import argparse
import asyncio
import os
import shutil

import asqlite
from ruamel import yaml  # type: ignore

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
]


def ensure_correct_directory() -> None:
    if "potdbot.py" not in os.listdir("."):
        print(
            "Please run this script from the root directory of the cloned "
            "repository."
        )
        exit(1)


def request_integer_input(prompt: str) -> int:
    while True:
        try:
            return int(input(prompt))
        except ValueError:
            print("Please enter an integer.")


def create_config_copy_with_essential_changes() -> None:
    if "config.yml" in os.listdir("config"):
        print(
            "Config file already exists. Skipping this stage.\n"
            "To avoid skipping this stage, delete `config/config.yml` and run "
            "this script again."
        )
        return

    guild_id = request_integer_input("Enter the ID of the guild: ")

    user = request_integer_input("Enter the name of your MySQL username: ")
    sqldb = request_integer_input("Enter the name of your MySQL database: ")

    shutil.copyfile("config/potdbot_config.yml", "config/config.yml")

    with open("config/config.yml") as config_file_read:
        config = yaml.safe_load(config_file_read)

    config["potd_guild"] = guild_id
    config["sqluser"] = user
    config["sqldb"] = db

    with open("config/config.yml", "w") as config_file_write:
        yaml.dump(config, config_file_write)


def write_token_file() -> None:
    with open("config/config.yml") as config_file:
        config = yaml.safe_load(config_file)

    token_file_name = config["token"]

    if token_file_name in os.listdir("config"):
        print(
            "Token file already exists. Skipping token file creation stage.\n"
            f"To avoid skipping this stage, delete `config/{token_file_name}` "
            "and run this script again."
        )
        return

    token = input("Enter the bot token: ")

    with open("config/" + token_file_name, "w") as token_file:
        token_file.write(token)


async def create_databases() -> None:
    with open("config/config.yml") as config_file:
        config = yaml.safe_load(config_file)
    os.makedirs("data", exist_ok=True)

    async with asqlite.connect(f'data/{config["dbname"]}.db') as conn:
        async with conn.cursor() as cursor:
            for database_creation_command in DATABASES_TO_CREATE:
                await cursor.execute(database_creation_command)

    print("Created databases.")


async def main():
    if __name__ == "__main__":
        ensure_correct_directory()
        create_config_copy_with_essential_changes()
        await create_databases()
        write_token_file()


asyncio.run(main())
