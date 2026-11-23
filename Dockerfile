
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local


COPY . .


COPY supervisord.prod.conf /etc/supervisor/conf.d/supervisord.prod.conf
COPY supervisord.dev.conf /etc/supervisor/conf.d/supervisord.dev.conf


EXPOSE 8000


CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.prod.conf"]
