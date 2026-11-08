FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils tesseract-ocr tesseract-ocr-hin \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt requirements-security.txt requirements.lock ./
RUN python -m pip install --no-cache-dir --upgrade "pip>=26.2,<27" \
    && python -m pip install --no-cache-dir --require-hashes -r requirements.lock

COPY . .
RUN mkdir -p data/output data/job_inputs

EXPOSE 8000
CMD ["uvicorn", "web.api:app", "--host", "0.0.0.0", "--port", "8000"]
