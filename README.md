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

- `/absent <rank> <name...> <YYYY-MM-DD> <reason...>` to mark someone absent for a date.
- `/present <rank> <name...> <YYYY-MM-DD>` to remove an absence for a date.
