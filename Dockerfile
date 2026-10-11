# Stage 1: build the React frontend.
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: the Python app (web server and voice agent share this image).
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HUB_DISABLE_SYMLINKS_WARNING=1

COPY requirements.txt ./
RUN pip install -r requirements.txt

# Download every model (~1.3 GB) before copying the rest of the app. Docker reuses a step
# from cache only while everything before it is unchanged, so editing agent.py, server.py
# or the frontend no longer downloads the models again. Only the two modules that know how
# to fetch the voices and the embedding model are copied here.
COPY local_speech.py rag.py ./
ARG WHISPER_MODEL_EN=base
ARG WHISPER_MODEL_HI=collabora/faster-whisper-small-hindi
ENV WHISPER_MODEL_EN=${WHISPER_MODEL_EN} WHISPER_MODEL_HI=${WHISPER_MODEL_HI}
RUN python -c "from faster_whisper import WhisperModel; [WhisperModel(name, device='cpu', compute_type='int8', download_root='models/whisper') for name in ('${WHISPER_MODEL_EN}', '${WHISPER_MODEL_HI}')]" \
 && python -c "from local_speech import load_piper_voices; load_piper_voices()" \
 && python -c "from rag import Embedder; Embedder()" \
 && python -c "from livekit.plugins.turn_detector.multilingual import _EUORunnerMultilingual; _EUORunnerMultilingual._download_files()"

# Every model is now in the image, so never contact Hugging Face at runtime: without this,
# each agent process checks for model updates while starting, which slows startup.
ENV HF_HUB_OFFLINE=1

COPY *.py ./
COPY knowledge_base/ knowledge_base/
COPY --from=frontend /frontend/dist frontend/dist

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
