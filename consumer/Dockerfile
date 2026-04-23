FROM python:3.12-alpine

WORKDIR /consumer

RUN pip install uv

COPY pyproject.toml ./

RUN uv sync

COPY . .

CMD ["uv", "run", "consumer.py"]