from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.moderation import ModerationService

settings = get_settings()
app = FastAPI(title=settings.app_name)
service = ModerationService(
    nsfw_threshold=settings.nsfw_threshold,
    image_max_side=settings.image_max_side,
    ocr_languages=settings.easyocr_languages,
    use_gpu=settings.use_gpu,
    openai_model=settings.openai_model,
    openai_timeout_seconds=settings.openai_timeout_seconds,
)


@app.get('/health')
async def healthcheck() -> dict[str, str]:
    return {'status': 'ok'}


@app.post('/moderate')
async def moderate_image(file: UploadFile = File(...)) -> JSONResponse:
    try:
        image_bytes = await file.read()
        image = service.preprocess_image(image_bytes)

        nsfw_score = service.detect_nsfw(image)
        if nsfw_score >= settings.nsfw_threshold:
            return JSONResponse(
                {
                    'is_safe': False,
                    'nsfw_score': nsfw_score,
                    'extracted_text': '',
                    'text_violation_flag': False,
                    'final_decision': 'Reject',
                    'reason': 'NSFW',
                }
            )

        extracted_text = service.extract_text(image)
        text_violation_flag = await service.analyze_text(extracted_text) if extracted_text else False
        final_decision = 'Reject' if text_violation_flag else 'Approve'

        return JSONResponse(
            {
                'is_safe': final_decision == 'Approve',
                'nsfw_score': nsfw_score,
                'extracted_text': extracted_text,
                'text_violation_flag': text_violation_flag,
                'final_decision': final_decision,
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail='Upstream moderation timeout.') from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Moderation failed: {exc}') from exc
