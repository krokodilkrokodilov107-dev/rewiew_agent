import json
from typing import List
from io import BytesIO
import pandas as pd


class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass


def load_reviews_from_json(data: dict) -> List[str]:
    """
    Load reviews from JSON data.

    Args:
        data: Dictionary with 'reviews' key containing list of review strings

    Returns:
        List of validated review strings

    Raises:
        ValidationError: If validation fails
    """
    reviews = data.get("reviews", [])

    if not isinstance(reviews, list):
        raise ValidationError("'reviews' must be a list")

    return _validate_reviews(reviews)


def load_reviews_from_csv(file_bytes: bytes) -> List[str]:
    """
    Load reviews from CSV file.

    Expected format:
    - Required column: 'review'
    - Optional columns: 'date', 'source'

    Args:
        file_bytes: Raw bytes from CSV file upload

    Returns:
        List of validated review strings

    Raises:
        ValidationError: If validation or parsing fails
    """
    try:
        df = pd.read_csv(BytesIO(file_bytes), encoding='utf-8')
    except UnicodeDecodeError:
        raise ValidationError("CSV file must be UTF-8 encoded")
    except pd.errors.EmptyDataError:
        raise ValidationError("CSV file is empty")
    except Exception as e:
        raise ValidationError(f"Failed to parse CSV: {str(e)}")

    if "review" not in df.columns:
        raise ValidationError("CSV must contain 'review' column")

    reviews = df["review"].astype(str).tolist()
    return _validate_reviews(reviews)


def _validate_reviews(reviews: List[str]) -> List[str]:
    """
    Validate reviews list.

    Requirements:
    - Minimum 10 reviews
    - Maximum 1000 reviews
    - Each review: 15-500 characters

    Args:
        reviews: List of review strings to validate

    Returns:
        List of validated reviews

    Raises:
        ValidationError: If validation fails
    """
    # Check minimum and maximum count
    if len(reviews) < 10:
        raise ValidationError(f"Minimum 10 reviews required, got {len(reviews)}")

    if len(reviews) > 1000:
        raise ValidationError(f"Maximum 1000 reviews allowed, got {len(reviews)}")

    # Validate each review
    validated = []
    for i, review in enumerate(reviews):
        if not isinstance(review, str):
            raise ValidationError(f"Review {i}: must be a string, got {type(review).__name__}")

        review = review.strip()

        if len(review) < 15:
            raise ValidationError(f"Review {i}: minimum 15 characters required, got {len(review)}")

        if len(review) > 500:
            raise ValidationError(f"Review {i}: maximum 500 characters allowed, got {len(review)}")

        validated.append(review)

    return validated
