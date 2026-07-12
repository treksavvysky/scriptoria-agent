FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY scriptoria/ ./scriptoria/
RUN pip install --no-cache-dir .

EXPOSE 8020
CMD ["uvicorn", "scriptoria.api:app", "--host", "0.0.0.0", "--port", "8020"]
