FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY data ./data
ENV DB_PATH=/data/store_intel.db \
    POS_CSV=/srv/data/pos_transactions.csv \
    LAYOUT_PATH=/srv/data/store_layout.json \
    SEED_EVENTS=/srv/data/events.jsonl
EXPOSE 8000
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
