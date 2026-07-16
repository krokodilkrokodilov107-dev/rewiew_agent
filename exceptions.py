from typing import Optional


class APIException(Exception):
    """Base exception for API errors"""

    def __init__(
        self,
        error: str,
        detail: str,
        status_code: int,
        original_error: Optional[Exception] = None
    ):
        self.error = error
        self.detail = detail
        self.status_code = status_code
        self.original_error = original_error
        super().__init__(self.detail)

    def to_dict(self) -> dict:
        """Convert exception to JSON response format"""
        return {
            "error": self.error,
            "detail": self.detail,
            "status_code": self.status_code
        }


class BadRequestError(APIException):
    """400 Bad Request - Invalid input format or empty data"""

    def __init__(self, detail: str):
        super().__init__(
            error="Bad Request",
            detail=detail,
            status_code=400
        )


class InvalidReviewCountError(APIException):
    """400 Bad Request - Invalid review count (empty or < 10)"""

    def __init__(self, detail: str):
        super().__init__(
            error="Invalid Review Count",
            detail=detail,
            status_code=400
        )


class PayloadTooLargeError(APIException):
    """413 Payload Too Large - More than 1000 reviews"""

    def __init__(self, detail: str):
        super().__init__(
            error="Payload Too Large",
            detail=detail,
            status_code=413
        )


class UnprocessableEntityError(APIException):
    """422 Unprocessable Entity - Review out of range (15-500 chars)"""

    def __init__(self, detail: str):
        super().__init__(
            error="Unprocessable Entity",
            detail=detail,
            status_code=422
        )


class InternalServerError(APIException):
    """500 Internal Server Error - Claude API error or other server error"""

    def __init__(self, detail: str, original_error: Optional[Exception] = None):
        super().__init__(
            error="Internal Server Error",
            detail=detail,
            status_code=500,
            original_error=original_error
        )


class GatewayTimeoutError(APIException):
    """504 Gateway Timeout - Request to Claude API exceeded timeout"""

    def __init__(self, detail: str):
        super().__init__(
            error="Gateway Timeout",
            detail=detail,
            status_code=504
        )


class InvalidFormatError(APIException):
    """400 Bad Request - Invalid data format (not JSON or CSV)"""

    def __init__(self, detail: str):
        super().__init__(
            error="Invalid Format",
            detail=detail,
            status_code=400
        )


class InvalidReviewLengthError(APIException):
    """422 Unprocessable Entity - Review length out of range"""

    def __init__(self, detail: str):
        super().__init__(
            error="Invalid Review Length",
            detail=detail,
            status_code=422
        )
