FROM python:3.12-slim

WORKDIR /app

# System deps for lxml, pyarrow, and kaleido (headless Chrome renderer)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libxml2-dev libxslt1-dev \
    libglib2.0-0 libnss3 libdbus-1-3 \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libasound2 libpango-1.0-0 libcairo2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# cache/ and outputs/ are mounted as Docker volumes — not baked into image
VOLUME ["/app/cache", "/app/outputs"]

EXPOSE 8501

CMD ["streamlit", "run", "dashboard.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
