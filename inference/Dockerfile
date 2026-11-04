# CLARIS Phase 4: S2U units sidecar. torch CPU + upstream CLARIS-Inference
# cloned at build time (research-only, no LICENSE upstream — never copied
# into this repo). Weights come from the host ./models/claris mount.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends git libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY inference/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN git clone --depth 1 https://github.com/Yash-Kumar-tech/CLARIS-Inference.git /opt/claris

COPY inference/app.py ./app.py

ENV CLARIS_CHECKPOINT=wtimit_44spkrs_trained.pt CLARIS_BEAM=5
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8001/healthz')"
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
