FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY kinopub_bot.py .

CMD ["python", "kinopub_bot.py"]
