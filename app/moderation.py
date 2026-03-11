from __future__ import annotations

import io
from typing import Any

import easyocr
from PIL import Image, UnidentifiedImageError
from openai import AsyncOpenAI

try:
    from nudenet import NudeDetector
except Exception:  # pragma: no cover
    NudeDetector = None


class ModerationService:
    def __init__(
        self,
        nsfw_threshold: float,
        image_max_side: int,
        ocr_languages: list[str],
        use_gpu: bool,
        openai_model: str,
        openai_timeout_seconds: float,
    ) -> None:
        self.nsfw_threshold = nsfw_threshold
        self.image_max_side = image_max_side
        self.ocr_languages = ocr_languages
        self.use_gpu = use_gpu
        self.openai_model = openai_model
        self.openai_timeout_seconds = openai_timeout_seconds

        self._ocr_reader: easyocr.Reader | None = None
        self._nsfw_detector: Any = None
        self._openai_client = AsyncOpenAI(timeout=openai_timeout_seconds)

    def _load_ocr_reader(self) -> easyocr.Reader:
        if self._ocr_reader is None:
            self._ocr_reader = easyocr.Reader(self.ocr_languages, gpu=self.use_gpu)
        return self._ocr_reader

    def _load_nsfw_detector(self) -> Any:
        if self._nsfw_detector is None:
            if NudeDetector is None:
                raise RuntimeError('NudeNet dependency failed to import.')
            self._nsfw_detector = NudeDetector()
        return self._nsfw_detector

    def preprocess_image(self, image_bytes: bytes) -> Image.Image:
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        except UnidentifiedImageError as exc:
            raise ValueError('Uploaded file is not a valid image.') from exc

        width, height = image.size
        max_side = max(width, height)
        if max_side > self.image_max_side:
            scale = self.image_max_side / max_side
            new_size = (int(width * scale), int(height * scale))
            image = image.resize(new_size)
        return image

    def detect_nsfw(self, image: Image.Image) -> float:
        detector = self._load_nsfw_detector()
        detections = detector.detect(image)
        if not detections:
            return 0.0

        nsfw_labels = {
            'FEMALE_BREAST_EXPOSED',
            'FEMALE_GENITALIA_EXPOSED',
            'MALE_GENITALIA_EXPOSED',
            'ANUS_EXPOSED',
            'BUTTOCKS_EXPOSED',
        }
        score = 0.0
        for detection in detections:
            if detection.get('class') in nsfw_labels:
                score = max(score, float(detection.get('score', 0.0)))
        return score

    def extract_text(self, image: Image.Image) -> str:
        reader = self._load_ocr_reader()
        results = reader.readtext(image, detail=0, paragraph=True)
        return ' '.join(fragment.strip() for fragment in results if fragment.strip())

    async def analyze_text(self, text: str) -> bool:
        if not text.strip():
            return False

        response = await self._openai_client.moderations.create(
            model=self.openai_model,
            input=text,
        )
        return bool(response.results and response.results[0].flagged)
