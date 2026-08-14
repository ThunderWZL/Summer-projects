from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.contracts import ErrorResponse
from app.domain.case_workflow import (
    CaseNotFound,
    CaseWorkflowError,
    PermissionDenied,
    StaleCaseVersion,
)


def error_response(
    status_code: int,
    code: str,
    message: str,
    current_version: int | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        code=code,
        message=message,
        current_version=current_version,
    )
    return JSONResponse(status_code=status_code, content=body.model_dump())


async def request_validation_exception_handler(
    request: Request,
    error: RequestValidationError,
) -> JSONResponse:
    del request, error
    return error_response(
        status_code=422,
        code="VALIDATION_ERROR",
        message="request validation failed",
    )


async def case_workflow_exception_handler(
    request: Request, error: CaseWorkflowError
) -> JSONResponse:
    del request
    if isinstance(error, CaseNotFound):
        status_code = 404
    elif isinstance(error, StaleCaseVersion):
        status_code = 409
    elif isinstance(error, PermissionDenied):
        status_code = 403
    else:
        status_code = 400
    current_version = (
        error.current if isinstance(error, StaleCaseVersion) else None
    )
    return error_response(
        status_code=status_code,
        code=error.code,
        message=str(error),
        current_version=current_version,
    )
