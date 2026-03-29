FROM ghcr.io/astral-sh/uv:alpine

ENV UV_NO_DEV=1

WORKDIR /bot
COPY pyproject.toml uv.lock* ./
RUN uv sync --locked

COPY . /bot

CMD ["uv", "run", "main.py"]
