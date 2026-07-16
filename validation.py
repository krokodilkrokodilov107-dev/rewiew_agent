from typing import List
from config import MIN_REVIEWS, MAX_REVIEWS, MIN_REVIEW_LENGTH, MAX_REVIEW_LENGTH
from exceptions import (
    BadRequestError,
    InvalidReviewCountError,
    PayloadTooLargeError,
    InvalidReviewLengthError,
    InvalidFormatError
)


def validate_json_format(data: dict) -> None:
    """
    Validate JSON request format.

    Args:
        data: Dictionary from JSON request

    Raises:
        BadRequestError: If data is None or invalid format
        InvalidFormatError: If 'reviews' key is missing
    """
    if data is None:
        raise BadRequestError(
            detail="Request body cannot be empty. Provide valid JSON with 'reviews' key."
        )

    if not isinstance(data, dict):
        raise BadRequestError(
            detail="Request body must be a JSON object."
        )

    if "reviews" not in data:
        raise InvalidFormatError(
            detail="Missing 'reviews' key. Provide JSON: {\"reviews\": [...]}"
        )


def validate_reviews_list(reviews: list) -> None:
    """
    Validate that reviews is a list.

    Args:
        reviews: Object to validate

    Raises:
        InvalidFormatError: If not a list
    """
    if not isinstance(reviews, list):
        raise InvalidFormatError(
            detail="'reviews' must be an array of strings."
        )


def validate_review_count(reviews: List[str]) -> None:
    """
    Validate review count (minimum 10, maximum 1000).

    Args:
        reviews: List of reviews

    Raises:
        InvalidReviewCountError: If < 10 reviews
        PayloadTooLargeError: If > 1000 reviews
    """
    count = len(reviews)

    if count == 0:
        raise InvalidReviewCountError(
            detail=f"Review list is empty. Minimum {MIN_REVIEWS} reviews required."
        )

    if count < MIN_REVIEWS:
        raise InvalidReviewCountError(
            detail=f"Insufficient reviews provided. Got {count}, minimum {MIN_REVIEWS} required. "
                   f"Add {MIN_REVIEWS - count} more reviews."
        )

    if count > MAX_REVIEWS:
        raise PayloadTooLargeError(
            detail=f"Too many reviews provided. Got {count}, maximum {MAX_REVIEWS} allowed. "
                   f"Remove {count - MAX_REVIEWS} reviews."
        )


def validate_review_length(review: str, review_index: int) -> None:
    """
    Validate individual review length (15-500 characters).

    Args:
        review: Review text to validate
        review_index: Index in the list (for error message)

    Raises:
        InvalidReviewLengthError: If outside 15-500 character range
    """
    length = len(review.strip())

    if length < MIN_REVIEW_LENGTH:
        raise InvalidReviewLengthError(
            detail=f"Review {review_index} is too short. Got {length} characters, "
                   f"minimum {MIN_REVIEW_LENGTH} required. Make it longer."
        )

    if length > MAX_REVIEW_LENGTH:
        raise InvalidReviewLengthError(
            detail=f"Review {review_index} is too long. Got {length} characters, "
                   f"maximum {MAX_REVIEW_LENGTH} allowed. Make it shorter."
        )


def validate_reviews(reviews: List[str]) -> List[str]:
    """
    Complete validation of reviews list.

    Args:
        reviews: List of review strings

    Returns:
        List of validated and cleaned reviews

    Raises:
        Various APIException subclasses on validation failure
    """
    validate_reviews_list(reviews)
    validate_review_count(reviews)

    validated = []
    for i, review in enumerate(reviews):
        if not isinstance(review, str):
            raise InvalidFormatError(
                detail=f"Review {i} must be a string, got {type(review).__name__}."
            )

        review_clean = review.strip()
        validate_review_length(review_clean, i)
        validated.append(review_clean)

    return validated


def validate_csv_file(filename: str) -> None:
    """
    Validate CSV file format.

    Args:
        filename: Filename to validate

    Raises:
        BadRequestError: If no file provided or invalid extension
    """
    if not filename or filename == "":
        raise BadRequestError(
            detail="No file provided. Upload a CSV file with 'file' parameter."
        )

    if not filename.lower().endswith(".csv"):
        raise InvalidFormatError(
            detail="File must be in CSV format. Supported extension: .csv"
        )
