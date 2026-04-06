# Discord Giveaway Bot

A feature-rich Discord giveaway bot built with Python and discord.py.

## Features
- Start giveaways with custom duration, winners count, prize, and per-winner amount
- End giveaways early with `!gend`
- Reroll winners with `!greroll`
- Pre-select guaranteed winners with `!gaddwinner`
- Log channel support - all participant joins and events logged
- Support for up to 100 winners per giveaway

## Commands
- `!gstart duration:<time> winners:<num> prize:<name> [perwinners:<amount>]`
- `!gend [message_id]` - End giveaway early
- `!greroll [message_id] [count]` - Reroll winners
- `!gaddwinner @user [message_id]` - Pre-select a guaranteed winner
- `!gremovewinner @user [message_id]` - Remove pre-selected winner
- `!glist` - List all active giveaways
- `!setlog #channel` - Set log channel
- `!ghelp` - Show help

## Setup
1. Add `DISCORD_TOKEN` secret with your bot token
2. Invite bot with Administrator permissions
3. Set log channel with `!setlog #channel`

## Tech Stack
- Python 3.11
- discord.py 2.x
- JSON file-based storage (giveaways.json, config.json)

## Files
- `bot.py` - Main bot file
- `giveaways.json` - Active/past giveaway data
- `config.json` - Server configuration (log channels)
- `requirements.txt` - Python dependencies
