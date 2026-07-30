FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml requirements.txt README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir .
COPY config ./config
COPY data ./data
COPY web ./web
COPY scripts ./scripts

RUN python scripts/bootstrap_demo.py
EXPOSE 8787
USER 65532:65532
CMD ["python", "-m", "quorava", "serve", "--host", "0.0.0.0", "--port", "8787"]

