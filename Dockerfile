from python:3.8.16-slim-bullseye

COPY . /app
COPY requirements.txt ./app

WORKDIR /app

RUN pip install --user --no-cache-dir -r requirements.txt


