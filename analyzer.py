import json
import sys
import time
from typing import List
from anthropic import Anthropic, APIError, APITimeoutError
from config import ANTHROPIC_API_KEY
from logger import api_logger
from exceptions import InternalServerError, GatewayTimeoutError

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

CLAUDE_API_TIMEOUT = 30  # seconds


class ReviewAnalyzer:
    def __init__(self):
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = "claude-haiku-4-5-20251001"
        self.system_prompt = """Ты эксперт по анализу отзывов клиентов на русском языке.

Твоя задача:
1. Определить тональность каждого отзыва: positive (позитивный), negative (негативный) или neutral (нейтральный)
2. Выявить 3-5 главных тем/проблем, упоминаемых в отзывах
3. Для каждой проблемы определить её частоту и преобладающую тональность
4. Определить лучший позитивный и худший негативный отзывы

Возвращай ТОЛЬКО валидный JSON без дополнительного текста в следующем формате:
{
    "sentiments": [
        {
            "review": "текст отзыва",
            "sentiment": "positive|neutral|negative"
        }
    ],
    "main_issues": [
        {
            "issue": "описание проблемы/темы",
            "frequency": количество_упоминаний,
            "sentiment": "positive|negative|neutral"
        }
    ],
    "top_positive": "самый лучший позитивный отзыв или его часть",
    "top_negative": "самый худший негативный отзыв или его часть"
}

Важно:
- Анализируй содержание и контекст отзывов
- Группируй похожие проблемы/темы под одну категорию
- Частота должна быть реальным числом упоминаний
- Будь объективен в определении тональности
"""

    def analyze_reviews(self, reviews: List[str]) -> dict:
        """
        Анализирует список отзывов и возвращает структурированные результаты.

        Args:
            reviews: Список отзывов для анализа

        Returns:
            dict: Структурированный анализ с тональностью, проблемами и выводами

        Raises:
            GatewayTimeoutError: If request exceeds timeout
            InternalServerError: If Claude API returns error
        """
        if not reviews:
            api_logger.debug("Empty reviews list provided")
            return {
                "sentiments": [],
                "main_issues": [],
                "top_positive": None,
                "top_negative": None
            }

        reviews_text = "\n".join([f"{i+1}. {review}" for i, review in enumerate(reviews)])

        api_logger.info(f"Starting analysis of {len(reviews)} reviews")
        start_time = time.time()

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=self.system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": f"""Проанализируй следующие отзывы клиентов:

{reviews_text}

Верни JSON с анализом."""
                    }
                ],
                timeout=CLAUDE_API_TIMEOUT
            )

            response_text = message.content[0].text.strip()

            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1

            if json_start != -1 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                result = json.loads(json_str)
            else:
                api_logger.error(f"Failed to parse JSON response from Claude API")
                raise InternalServerError(
                    detail="Failed to parse Claude API response. Please try again."
                )

            elapsed_time = time.time() - start_time
            api_logger.info(f"Analysis completed in {elapsed_time:.2f}s for {len(reviews)} reviews")

            return result

        except APITimeoutError as e:
            elapsed_time = time.time() - start_time
            api_logger.error(f"Claude API timeout after {elapsed_time:.2f}s: {str(e)}")
            raise GatewayTimeoutError(
                detail=f"Claude API request timed out after {CLAUDE_API_TIMEOUT} seconds. "
                       "Please try again with fewer reviews or check your connection."
            )
        except APIError as e:
            api_logger.error(f"Claude API error: {str(e)}")
            raise InternalServerError(
                detail=f"Claude API error: {str(e)}. Please try again.",
                original_error=e
            )
        except (json.JSONDecodeError, ValueError) as e:
            api_logger.error(f"JSON parsing error: {str(e)}")
            raise InternalServerError(
                detail="Failed to parse API response. The response format was invalid.",
                original_error=e
            )
        except Exception as e:
            api_logger.error(f"Unexpected error during analysis: {str(e)}")
            raise InternalServerError(
                detail="An unexpected error occurred during analysis. Please try again.",
                original_error=e
            )


if __name__ == "__main__":
    test_reviews = [
        "Отличный сервис! Быстрая доставка и качественный товар. Спасибо!",
        "Разочарован. Товар не соответствует описанию. Плохое качество упаковки.",
        "Нормально. Ничего особенного, но и не плохо. Цена адекватная.",
        "Просто супер! Это лучший сервис, который я когда-либо использовал!",
        "Ужасно. Ждал товар месяц, а потом он оказался сломан. Никому не рекомендую.",
        "Хорошее соотношение цены и качества. Доставка была быстрой.",
        "Очень недоволен. Клиентская поддержка не ответила на мои вопросы.",
        "Просто замечательно! Буду заказывать снова. Всё отлично!",
        "Продукт хороший, но доставка заняла слишком много времени.",
        "Не впечатлён. Много лучше вариантов на рынке.",
        "Отличный выбор товаров, быстрая доставка, хороший сервис!",
        "Кошмар. Получил совсем не то, что заказывал. Требует возврата.",
        "Адекватный сервис. Буду пользоваться и дальше.",
        "Потрясающе! Лучше не бывает. Рекомендую всем своим друзьям!",
        "Средненько. Товар пришёл с задержкой, качество оставляет желать лучшего.",
    ]

    analyzer = ReviewAnalyzer()
    print("Анализирую отзывы...")
    result = analyzer.analyze_reviews(test_reviews)

    print("\n" + "="*80)
    print("РЕЗУЛЬТАТЫ АНАЛИЗА")
    print("="*80)

    print("\n[АНАЛИЗ ТОНАЛЬНОСТИ]:")
    sentiments_count = {
        "positive": sum(1 for s in result["sentiments"] if s["sentiment"] == "positive"),
        "negative": sum(1 for s in result["sentiments"] if s["sentiment"] == "negative"),
        "neutral": sum(1 for s in result["sentiments"] if s["sentiment"] == "neutral")
    }
    print(f"  Позитивные: {sentiments_count['positive']}")
    print(f"  Негативные: {sentiments_count['negative']}")
    print(f"  Нейтральные: {sentiments_count['neutral']}")

    print("\n[ГЛАВНЫЕ ПРОБЛЕМЫ/ТЕМЫ]:")
    for i, issue in enumerate(result["main_issues"], 1):
        print(f"  {i}. {issue['issue']}")
        print(f"     Частота: {issue['frequency']}, Тональность: {issue['sentiment']}")

    print("\n[ЛУЧШИЙ ПОЗИТИВНЫЙ ОТЗЫВ]:")
    print(f"  {result['top_positive']}")

    print("\n[ХУДШИЙ НЕГАТИВНЫЙ ОТЗЫВ]:")
    print(f"  {result['top_negative']}")

    print("\n[ПОЛНЫЙ JSON]:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
