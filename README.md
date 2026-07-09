# Parade State Bot

I am tired of sending parade state, time to automate it.

## Getting started

### Prerequisites

- [uv](https://docs.astral.sh/uv)

### Starting the bot

Create an env file with the telegram bot's token:

Then run:

```bash
uv run --env-file=.env main.py
```

### Commands

- `/absent <rank> <name...> <DDMMYY[-DDMMYY]> <reason...>` to mark someone absent for a date or a range of dates, e.g. `/absent CPL John Tan 090726-110726 MC`.
- `/absences <rank> <name...>` to list someone's upcoming absences with buttons to delete them.

### Deployment

Build the container with:

```bash
docker build -t paradestatebot .
```

Then, run:

```bash
docker run --env-file .env --mount type=bind,source=./bot.db,target=/bot/bot.db -d paradestatebot
```
