# ClearView Moderator Service

FastAPI service for multi-stage moderation:
1. NSFW detection (fail-fast)
2. OCR text extraction
3. OpenAI semantic moderation

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=your_key
uvicorn app.main:app --reload
```

## Run with Docker

```bash
docker compose up --build
```

## API

`POST /moderate`
- multipart form field: `file`

Response:

```json
{
  "is_safe": true,
  "nsfw_score": 0.12,
  "extracted_text": "sample text",
  "text_violation_flag": false,
  "final_decision": "Approve"
}
```
