FROM python:3.12-slim

WORKDIR /ingestion

RUN pip install uv

COPY pyproject.toml ./

RUN uv sync

COPY . .

CMD ["uv", "run", "ingestion.py"]