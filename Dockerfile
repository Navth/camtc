FROM python:3.11-slim

WORKDIR /app

RUN mkdir -p /app/camtc

COPY requirements.txt /app/camtc/requirements.txt
RUN pip install --no-cache-dir -r /app/camtc/requirements.txt

COPY . /app/camtc

# Ensure the camtc package is resolvable from /app
ENV PYTHONPATH=/app

EXPOSE 8000 8080

CMD ["python", "-m", "camtc.main", "--train"]
