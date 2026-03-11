# ClearView Moderator Service

A high-performance **FastAPI** content moderation service that applies a **multi-stage, fail-fast pipeline** for images:

1. **Stage 1 — NSFW detection** (perimeter rejection)
2. **Stage 2 — OCR extraction** (EasyOCR)
3. **Stage 3 — Semantic moderation** (OpenAI `/v1/moderations`)

The service is designed to minimize latency and compute/token spend by exiting early when NSFW confidence is above threshold.

---

## Table of Contents

- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [Configuration](#configuration)
- [Run Locally](#run-locally)
- [Run with Docker](#run-with-docker)
- [API Reference](#api-reference)
- [Moderation Decision Logic](#moderation-decision-logic)
- [Error Handling](#error-handling)
- [Performance Notes](#performance-notes)
- [GPU Notes](#gpu-notes)
- [Troubleshooting](#troubleshooting)

---

## Architecture

### Pipeline Flow

```text
Upload Image -> Preprocess (RGB + resize)
             -> NSFW Detector
                -> score >= threshold ? REJECT (fast return)
                -> score < threshold  ? OCR (EasyOCR)
                                       -> text found ? OpenAI Moderation
                                                    -> final decision
```

### Why this ordering?

- NSFW checks are first to avoid unnecessary OCR + API calls for clearly disallowed images.
- OCR only runs on safe images to reduce CPU/GPU utilization.
- OpenAI moderation only runs when text exists, reducing latency and cost.

---

## Project Structure

```text
.
├── app
│   ├── config.py         # Environment-driven settings
│   ├── main.py           # FastAPI app + endpoints
│   └── moderation.py     # NSFW, OCR, and OpenAI moderation logic
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## Requirements

- Python **3.11+**
- OpenAI API key (`OPENAI_API_KEY`)
- OS libraries required by OCR/OpenCV runtime (installed automatically in Docker image)

Python dependencies:

- `fastapi`
- `uvicorn`
- `easyocr`
- `openai`
- `python-multipart`
- `nudenet`
- `pillow`
- `pydantic-settings`

---

## Configuration

Settings are loaded from environment variables (or `.env` when present).

| Variable | Default | Description |
|---|---:|---|
| `APP_NAME` | `ClearView Moderator Service` | FastAPI title |
| `NSFW_THRESHOLD` | `0.8` | Reject when NSFW score >= threshold |
| `IMAGE_MAX_SIDE` | `1024` | Max side length after resize |
| `OPENAI_MODEL` | `omni-moderation-latest` | OpenAI moderation model |
| `OPENAI_TIMEOUT_SECONDS` | `10.0` | OpenAI request timeout |
| `EASYOCR_LANGUAGES` | `['en']` | OCR language list |
| `USE_GPU` | `false` | Toggle GPU mode for OCR/model runtime |
| `OPENAI_API_KEY` | _required_ | API key for OpenAI moderation |

Example `.env`:

```env
OPENAI_API_KEY=sk-...
NSFW_THRESHOLD=0.8
IMAGE_MAX_SIDE=1024
OPENAI_MODEL=omni-moderation-latest
OPENAI_TIMEOUT_SECONDS=10
USE_GPU=false
```

---

## Run Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=your_key_here
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Health check:

```bash
curl http://localhost:8000/health
```

---

## Run with Docker

### Docker Compose

```bash
docker compose up --build
```

By default service is available at `http://localhost:8000`.

### Docker only

```bash
docker build -t clearview-moderator .
docker run --rm -p 8000:8000 -e OPENAI_API_KEY=your_key_here clearview-moderator
```

---

## API Reference

### `GET /health`

Returns service health status.

**Response**

```json
{
  "status": "ok"
}
```

### `POST /moderate`

Moderates an uploaded image.

- Content type: `multipart/form-data`
- Field name: `file`

#### Example request

```bash
curl -X POST "http://localhost:8000/moderate" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/image.jpg"
```

#### Success response shape

```json
{
  "is_safe": true,
  "nsfw_score": 0.12,
  "extracted_text": "sample text",
  "text_violation_flag": false,
  "final_decision": "Approve"
}
```

#### Fast NSFW rejection response

```json
{
  "is_safe": false,
  "nsfw_score": 0.94,
  "extracted_text": "",
  "text_violation_flag": false,
  "final_decision": "Reject",
  "reason": "NSFW"
}
```

---

## Moderation Decision Logic

1. Preprocess image (decode, convert RGB, optional resize)
2. Compute NSFW score
3. If score >= `NSFW_THRESHOLD`:
   - return reject immediately (`reason: NSFW`)
4. Else run OCR
5. If OCR text is present:
   - call OpenAI moderation endpoint asynchronously
6. Final decision:
   - `Reject` if text is flagged
   - `Approve` otherwise

---

## Error Handling

- `400 Bad Request`: invalid/corrupted/non-image uploads
- `504 Gateway Timeout`: moderation timeout from upstream provider
- `500 Internal Server Error`: unexpected runtime/model errors

This design protects the API surface from leaking low-level internal exceptions while still returning meaningful status codes.

---

## Performance Notes

- **Fail-fast perimeter filter** avoids expensive downstream processing for NSFW inputs.
- **Resize before inference** controls memory and improves throughput on large images.
- **Lazy model loading** initializes OCR/NSFW models only when needed.
- **Async OpenAI calls** prevent blocking the FastAPI event loop during text moderation.

---

## GPU Notes

For GPU-enabled deployments:

- Set `USE_GPU=true`.
- Ensure CUDA-capable runtime/drivers are available on host.
- For Docker GPU execution, use NVIDIA container runtime as appropriate for your environment.

> Note: current Dockerfile is CPU-friendly by default. GPU-ready images generally require CUDA base images and matching driver/toolkit setup.

---

## Troubleshooting

- **`OPENAI_API_KEY` missing**: ensure env variable is exported/passed into container.
- **OCR startup is slow on first request**: EasyOCR model loading is lazy and may download/cache assets initially.
- **Large image latency**: reduce `IMAGE_MAX_SIDE` to lower compute footprint.
- **Too many false positives/negatives**: tune `NSFW_THRESHOLD` for your policy.

---

## Security / Production Hardening Suggestions

- Put service behind an API gateway and auth layer.
- Enforce upload size and content-type checks at ingress.
- Add request rate limiting and structured audit logging.
- Add observability (OpenTelemetry, Prometheus, tracing for each pipeline stage).
- Add warmup/startup hooks for models in high-throughput environments.
