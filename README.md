# Discord Radio

This is a Discord bot that takes raw pcm samples from a udp port and sends them to a voice channel in Discord.

## Running Discord Radio Bot

Step 1: Follow the steps from the [discord.py Python library](https://discordpy.readthedocs.io/en/stable/discord.html) for creating a
Discord bot. Save the token that it instructs you to create.

Step 2: Run `python stereo_fm.py <token>` (or use the out of date Dockerfile)

Step 3: Join a voice channel in the same server as your bot and send it commands. Enjoy!

## Commands

* `!start` starts the radio.

* `!stop` stops the radio.
