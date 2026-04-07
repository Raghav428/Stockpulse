FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl

RUN pip install uv

COPY pyproject.toml uv.lock ./

RUN uv sync

COPY . .

CMD ["./start.sh"]
