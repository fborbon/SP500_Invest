FROM python:3.12-slim

WORKDIR /app

# System deps for lxml, kaleido, pyarrow
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libxml2-dev libxslt1-dev \
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
