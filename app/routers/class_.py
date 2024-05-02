from uuid import uuid4
from typing import List

from fastapi import APIRouter
from sqlalchemy import select, insert, update, delete

from app.core.errors import error
from app.core.logger import logger
from app.core.redis import redis_cache, key_builder
from app.core.db.session import AsyncScopedSession
from app.core.db.session import AsyncScopedSession
from app.models.schemas.common import BaseResponse, HttpResponse, ErrorResponse
from app.models.schemas.class_ import (
    ClassReq,
    ClassResp,
    ClassNoticeReq,
    ClassNoticeResp,
)
from app.models.db.class_ import Class, ClassNotice

router = APIRouter()


@router.post(
    "",
    response_model=BaseResponse[ClassResp],
    responses={400: {"model": ErrorResponse}},
)
async def create_class(
    request_body: ClassReq,
) -> BaseResponse[ClassResp]:
    class_id = uuid4().hex
    async with AsyncScopedSession() as session:
        try:
            stmt = (
                insert(Class)
                .values(
                    class_id=class_id,
                    class_name=request_body.className,
                    teacher_id=request_body.teacherId,
                )
                .returning(Class)
            )

            result: Class = (await session.execute(stmt)).scalar()
            await session.commit()
        except Exception as e:
            logger.error(e)
            await session.rollback()
            raise error.ClassCreationFailed()

    return HttpResponse(
        content=ClassResp(
            classId=result.class_id,
            className=result.class_name,
            teacherId=result.teacher_id,
            createdAt=result.created_at,
        )
    )


@router.get(
    "/list",
    response_model=BaseResponse[List[ClassResp]],
    responses={400: {"model": ErrorResponse}},
)
async def read_class_list() -> BaseResponse[List[ClassResp]]:
    _key = key_builder("read_class_list")

    if await redis_cache.exists(_key):
        result = await redis_cache.get(_key)
        logger.debug(f"Cache hit: {_key}")
    else:
        logger.debug("Cache miss")
        async with AsyncScopedSession() as session:
            stmt = select(Class)
            result = (await session.execute(stmt)).scalars().all()
            if result is not None:
                await redis_cache.set(_key, result, ttl=60)
            logger.debug(f"Cache miss: {_key}")

    if result is None:
        raise error.ClassNotFoundException()

    return HttpResponse(
        content=[
            ClassResp(
                classId=class_.class_id,
                className=class_.class_name,
                teacherId=class_.teacher_id,
                createdAt=class_.created_at,
            )
            for class_ in result
        ]
    )


@router.get(
    "/{class_id}",
    response_model=BaseResponse[ClassResp],
    responses={400: {"model": ErrorResponse}},
)
async def read_class(
    class_id: str,
) -> BaseResponse[ClassResp]:
    _key = key_builder("read_class", class_id)

    if await redis_cache.get(_key):
        logger.debug("Cache hit")
        result = await redis_cache.get(_key)
    else:
        async with AsyncScopedSession() as session:
            stmt = select(Class).where(Class.class_id == class_id)
            result = (await session.execute(stmt)).scalar()

        await redis_cache.set(_key, result, ttl=60)

    if result is None:
        raise error.ClassNotFoundException()

    return HttpResponse(
        content=ClassResp(
            classId=result.class_id,
            className=result.class_name,
            teacherId=result.teacher_id,
            createdAt=result.created_at,
        )
    )


@router.post(
    "/notice/{class_id}",
    response_model=BaseResponse[ClassNoticeResp],
    responses={400: {"model": ErrorResponse}},
)
async def create_class_notice(
    class_id: str,
    request_body: ClassNoticeReq,
) -> BaseResponse[ClassNoticeResp]:
    async with AsyncScopedSession() as session:
        try:
            stmt = (
                insert(ClassNotice)
                .values(class_id=class_id, message=request_body.message)
                .returning(ClassNotice)
            )

            result: ClassNotice = (await session.execute(stmt)).scalar()
            await session.commit()
        except Exception as e:
            logger.error(e)
            await session.rollback()
            raise error.ClassNoticeCreationFailed()

    return HttpResponse(
        content=ClassNoticeResp(
            id=result.id,
            classId=result.class_id,
            message=result.message,
            createdAt=result.created_at,
            updatedAt=result.updated_at,
        )
    )


@router.get(
    "/notice/{class_id}/list",
    response_model=BaseResponse[List[ClassNoticeResp]],
    responses={400: {"model": ErrorResponse}},
)
async def read_class_notice_list(
    class_id: str,
) -> BaseResponse[List[ClassNoticeResp]]:
    async with AsyncScopedSession() as session:
        stmt = (
            select(ClassNotice)
            .where(ClassNotice.class_id == class_id)
            .order_by(ClassNotice.created_at.desc())
        )
        result = (await session.execute(stmt)).scalars().all()

    if not result:
        raise error.ClassNoticeNotFound()

    return HttpResponse(
        content=[
            ClassNoticeResp(
                id=notice.id,
                classId=notice.class_id,
                message=notice.message,
                createdAt=notice.created_at,
                updatedAt=notice.updated_at,
            )
            for notice in result
        ]
    )


@router.put(
    "/notice/{class_id}/{notice_id}",
    response_model=ClassNoticeResp,
    responses={400: {"model": ErrorResponse}},
)
async def update_class_notice(
    class_id: str,
    notice_id: int,
    request_body: ClassNoticeReq,
) -> ClassNoticeResp:
    async with AsyncScopedSession() as session:
        try:
            stmt = (
                update(ClassNotice)
                .where(ClassNotice.id == notice_id, ClassNotice.class_id == class_id)
                .values(message=request_body.message)
                .returning(ClassNotice)
            )
            result: ClassNotice = (await session.execute(stmt)).scalar()
            await session.commit()
        except Exception as e:
            logger.error(e)
            await session.rollback()
            raise error.ClassNoticeUpdateFailed()

        if result is None:
            raise error.ClassNoticeNotFound()

    return HttpResponse(
        content=ClassNoticeResp(
            id=result.id,
            classId=result.class_id,
            message=result.message,
            createdAt=result.created_at,
            updatedAt=result.updated_at,
        )
    )


@router.delete(
    "/notice/{class_id}/{notice_id}",
    response_model=ClassNoticeResp,
    responses={400: {"model": ErrorResponse}},
)
async def delete_class_notice(
    class_id: str,
    notice_id: int,
) -> ClassNoticeResp:
    async with AsyncScopedSession() as session:
        try:
            stmt = (
                delete(ClassNotice)
                .where(ClassNotice.id == notice_id, ClassNotice.class_id == class_id)
                .returning(ClassNotice)
            )
            result: ClassNotice = (await session.execute(stmt)).scalar()
            await session.commit()
        except Exception as e:
            logger.error(e)
            await session.rollback()
            raise error.ClassNoticeDeleteFailed()

    if result is None:
        raise error.ClassNoticeNotFound()

    return HttpResponse(
        content=ClassNoticeResp(
            id=result.id,
            classId=result.class_id,
            message=result.message,
            createdAt=result.created_at,
            updatedAt=result.updated_at,
        )
    )
