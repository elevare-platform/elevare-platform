FROM python:3.12-slim

WORKDIR /app

# Install system dependencies. Force https:// for the apt sources — this
# build environment only allows outbound HTTPS, and Debian's default
# sources.list entries are plain http://.
RUN find /etc/apt/sources.list.d -type f -exec sed -i 's|http://deb.debian.org|https://deb.debian.org|g' {} + \
    && apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    libmagic1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN python -m spacy download en_core_web_sm

# Copy application code
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]