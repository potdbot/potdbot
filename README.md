# POTDBot

POTDBot is a Discord bot used for fetching and managing [mathematical olympiad problems](http://bit.ly/potd-history). This is a fork of [MODSBot](https://github.com/Mathematical-Olympiads-Discord-Server/modsbot-rewrite), which served a similar role in the [Mathematical Olympiads Discord Server (MODS)](https://discord.gg/mods). However, this bot was created to achieve the same functionality as MODSBot, to users outside of MODS.

If you would like to add POTDBot to your server, contact A Fellow Human on Github or on Discord. Alternatively, read below if you want to self-host POTDBot.

## Features

Apart from simply fetching problems, POTDBot has numerous features:
- Searching problems by difficulty, genre, or words in the problem statement
- Saving problems as todo, read, or solved
- Rating problems on a difficulty scale, and using individual ratings to create a community-generated difficulty rating
- Generating mocks of competitions such as the IMO, APMO, IGO, BMO2, or USA(J)MO, with equivalent difficulties and genre distributions
- And more!

## Getting Started

The following are some instructions to help setting up a local version of POTDbot.
The instructions are made for Linux (but should nevertheless be useful for other operating systems) and some of the commands may have errors which you may need to try Googling.

1. Clone this repository and enter the directory. Ideally you should use python3.9 (Note: python3.11 definitely doesn't work, and python3.9 definitely does, but other Python versions have not been verified.)
2. Setup a python venv, source it and install the requirements
   ```zsh
   python3.9 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Create a Discord bot and keep the token safe, or just regenerate it in the next step. [Follow this guide if you are unsure how to create a Discord bot](https://www.freecodecamp.org/news/create-a-discord-bot-with-python/). You should also create a server for the bot and add the bot to it.
4. Install a LaTeX distribution. This distribution must include the [standalone package](https://ctan.org/pkg/standalone?lang=en). For example, on Ubuntu, you can install `tex-live-extra`.
5. Install `poppler`. See [here](https://pdf2image.readthedocs.io/en/latest/installation.html#installing-poppler) for OS-specific instructions on how to do so.
5. Make sure the venv is activated and that the current directory is the root directory of the cloned repository. Then, run the setup script:
   ```zsh
   python setup_modsbot.py
   ```
6. Setup a google API service account:
    1. Create a GMail account if you don't already have one.
    2. Go to https://console.cloud.google.com/ and agree to the Terms of Service.
    3. At the top of the screen, click `select a project` and then click `NEW PROJECT` and give the project a suitable name like `MODSBOT testing`. You don't need to add an organisation.
        ![image of google cloud console website](https://github.com/Mathematical-Olympiads-Discord-Server/modsbot-rewrite/blob/master/images/google_cloud_console_setup_1.png?raw=true)
    4. After waiting a few seconds, you should be able to click `select a project` at the top of the screen and then select the project we just created. Under Quick access, click `APIs and services`, and then click `ENABLE APIS AND SERVICES` on the next page
        ![image of google cloud console website](https://github.com/Mathematical-Olympiads-Discord-Server/modsbot-rewrite/blob/master/images/google_cloud_console_setup_2.png?raw=true)
        ![image of google cloud console website](https://github.com/Mathematical-Olympiads-Discord-Server/modsbot-rewrite/blob/master/images/google_cloud_console_setup_3.png?raw=true)
    5. In the search box, search for "drive" and hit enter. Select "Google Drive API" and then enable it. Repeat this also for the "Google Sheets API".
        ![image of google cloud console website](https://github.com/Mathematical-Olympiads-Discord-Server/modsbot-rewrite/blob/master/images/google_cloud_console_setup_4.png?raw=true)
    6. Now click the `Credentials` button on the left of the screen
        ![image of google cloud console website](https://github.com/Mathematical-Olympiads-Discord-Server/modsbot-rewrite/blob/master/images/google_cloud_console_setup_5.png?raw=true)
    7. Click `CREATE CREDENTIALS` and then `Service account`. The only required details in the first section is the service addount ID which can be anything.
        ![image of google cloud console website](https://github.com/Mathematical-Olympiads-Discord-Server/modsbot-rewrite/blob/master/images/google_cloud_console_setup_6.png?raw=true)
    8. The other steps can be skipped.
        ![image of google cloud console website](https://github.com/Mathematical-Olympiads-Discord-Server/modsbot-rewrite/blob/master/images/google_cloud_console_setup_7.png?raw=true)
    9. You should now be back on the Credentials page from earlier. Under the `Service Accounts` list, select the new entry. Then click `KEYS` at the top of the screen
        ![image of google cloud console website](https://github.com/Mathematical-Olympiads-Discord-Server/modsbot-rewrite/blob/master/images/google_cloud_console_setup_8.png?raw=true)
    10. Now click `ADDKEY` then `Create new key` and select `JSON` for the key type. Click `CREATE` and then save the file into `config/credentials.json` in the directory where you cloned this repository.
        ![image of google cloud console website](https://github.com/Mathematical-Olympiads-Discord-Server/modsbot-rewrite/blob/master/images/google_cloud_console_setup_9.png?raw=true)
    11. Open your `credentials.json` and remove the JSON row containing `universe_domain` (see [here](https://github.com/omarryhan/aiogoogle/issues/126) for more info).
    12. All done for this section!
7. You should now be able to run the bot with `python potdbot.py` (just make sure you've activated the venv).