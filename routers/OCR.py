# 2. САМ РОУТ
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from models.OCR import OCRResponse, OCRBox
from repositories.database import get_db
from models.order import OrderDB
from services.OCR import getDataFromOCR
from utils import hashing
from utils.OCR import ReadSettings, ocr_reader
from utils.config import readYaml
from sqlalchemy import select

from utils.imei import is_valid_imei

router = APIRouter()


async def get_current_order(order_id: int, user_session, db: AsyncSession):
    stmt = select(OrderDB).where(
        OrderDB.id == order_id,
        OrderDB.inspector_id == user_session.id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
@router.post("/inspector/report/{order_id}/ocr/{field}")
async def analyze_ocr(
    order_id: int,
    field: str,
    img: str = Body(..., embed=True),
    user_session=Depends(hashing.user_by_jwt_token),
    db: AsyncSession = Depends(get_db)
):
    current_order = await get_current_order(order_id, user_session, db)

    if not current_order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order #{order_id} not found or you have no permission to access it",
        )

    ocr_map = readYaml("ocr_map.yaml")
    search_keys = ocr_map.get(field)

    if not search_keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported OCR field: {field}",
        )

    if isinstance(search_keys, str):
        search_keys = [search_keys]
    return await getDataFromOCR(order_id=order_id, img=img, current_order=current_order, search_keys=search_keys, field=field)