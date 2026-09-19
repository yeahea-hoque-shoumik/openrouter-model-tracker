FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY sql ./sql
COPY scripts ./scripts
RUN useradd --system --no-create-home tracker
USER tracker
CMD ["python", "-m", "app.main"]
