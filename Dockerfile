FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY app.py /app
COPY openapi.json /app
COPY lib/ /app/lib
COPY schema/ /app/schema
COPY ui/ /app/ui

EXPOSE 5020

ENTRYPOINT []

CMD ["gunicorn", "--bind", "0.0.0.0:5020", "--access-logfile", "-", "app:app"]
