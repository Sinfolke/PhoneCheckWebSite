from pydantic import BaseModel
from typing import List

# То, что присылает фронтенд
class OCRRequest(BaseModel):
    image: str  # Base64 строка (фотография)
    step: str   # Например: "settings_about"

# Квадратик с текстом
class OCRBox(BaseModel):
    text: str
    x: int
    y: int
    w: int
    h: int

# То, что мы отвечаем фронтенду
class OCRResponse(BaseModel):
    status: str       # "success", "partial", "error"
    hint: str | dict[str, str]         # Подсказка для инспектора
    boxes: List[OCRBox]