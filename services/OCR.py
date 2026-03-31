from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from models.OCR import OCRResponse
from models.order import OrderDB
from utils.OCR import ReadSettings, ocr_reader
from utils.config import readYaml
from utils.imei import is_valid_imei, normalize_imei


async def getDataFromOCR(order_id: int, img: str, current_order: OrderDB, search_keys: list[str], field: str):
    if not current_order:
        return OCRResponse(
            status="error",
            hint=f"Order #{order_id} not found or you have no permission",
            boxes=[]
        )
    if (current_order.status == "success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The check has already been completed. No changes can be committed",
        )
    try:
        settings = ReadSettings.from_base64(img, ocr_reader)
        settings_yaml = readYaml("setting_schemas/samsung_en.yaml")
        values = settings.locate(settings_yaml, search_keys)
        if field == 'imei':
            imei = normalize_imei(values["IMEI 1"])
            check_result = is_valid_imei(imei)
            if not check_result:
                return OCRResponse(
                    status="error",
                    hint=f"Check for imei '{imei}' failed: read again or input manually",
                    boxes=[]
                )
            values["IMEI 1"] = imei

        return OCRResponse(
            status="success",
            hint={
                key: value.text
                for key, value in values.items()
            },
            boxes=[
                box
                for box in values.values()
            ]
        )
    except KeyError as e:
        return OCRResponse(
            status="error",
            hint=f"Не вижу нужных данных. Прокрутите экран вниз.",
            boxes=[]
        )