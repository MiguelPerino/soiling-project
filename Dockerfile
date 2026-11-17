# Imagem única: compila o front (React) e serve tudo pela API (FastAPI). Build: docker compose build
FROM node:22-slim AS front
WORKDIR /f
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ .
COPY --from=front /f/dist /app/frontend_dist
# Modelo grande (ONNX): vai DENTRO da imagem para a nuvem. Os pesos não ficam no git: antes do build rode
# scripts/download-model.sh (baixa da release indicada em models/server/model.lock e confere o SHA-256).
# O build FALHA se o modelo faltar ou não for o do model.lock: na Azure o modo Servidor é o único que funciona.
# Para construir sem modelo de propósito: docker build --build-arg ALLOW_NO_MODEL=1 .
# No docker compose local a pasta é montada por cima, então trocar o modelo lá não exige rebuild.
ARG ALLOW_NO_MODEL=0
COPY models/server /models/server
RUN cd /models/server && if awk '$1=="sha256"{print $2"  "$3}' model.lock | sha256sum -c --quiet - ; then \
        echo "modelo grande conferido: $(awk '$1=="tag"{print $2}' model.lock)"; \
    elif [ "$ALLOW_NO_MODEL" = "1" ]; then \
        echo "AVISO: imagem SEM o modelo grande (ALLOW_NO_MODEL=1): o modo Servidor ficará indisponível"; \
        rm -f model.onnx labels.json model_card.json; \
    else \
        echo "ERRO: models/server/ não tem o modelo esperado pelo model.lock. Rode scripts/download-model.sh antes do build" \
             "(ou use --build-arg ALLOW_NO_MODEL=1 para construir sem ele)."; exit 1; \
    fi
ENV FRONTEND_DIR=/app/frontend_dist STORAGE_DIR=/data/images SERVER_MODEL_DIR=/models/server
RUN useradd -r -u 10001 app && mkdir -p /data/images && chown -R app /data
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health').status==200 else 1)"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]