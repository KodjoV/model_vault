FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HOME=/tmp HF_HOME=/tmp/hf-cache XDG_CACHE_HOME=/tmp/.cache
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY vault.py /app/vault.py
COPY models.json /app/models.json
EXPOSE 8787
CMD ["python", "-u", "/app/vault.py", "serve"]
