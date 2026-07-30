import asyncio

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request

from app.api.admin import view_sessions
from app.main import database_conflict_handler


def test_admin_invalid_date_returns_422_before_query():
    async def run():
        try:
            await view_sessions(date_from="not-a-date", db=None, admin=None)
        except HTTPException as exc:
            assert exc.status_code == 422
            return
        raise AssertionError("Invalid date did not return HTTP 422")

    asyncio.run(run())


def test_database_integrity_error_returns_safe_409():
    async def run():
        request = Request({
            "type": "http",
            "method": "POST",
            "path": "/api/admin/profiles",
            "headers": [],
        })
        error = IntegrityError("statement", {}, Exception("private database detail"))
        response = await database_conflict_handler(request, error)
        assert response.status_code == 409
        assert b"private database detail" not in response.body

    asyncio.run(run())
