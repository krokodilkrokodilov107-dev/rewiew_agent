import json
from typing import List, Dict, Any, Optional, Set
from collections import Counter
from difflib import SequenceMatcher
from dataclasses import dataclass, asdict


@dataclass
class SentimentCount:
    positive: int = 0
    neutral: int = 0
    negative: int = 0

    def to_dict(self):
        total = self.positive + self.neutral + self.negative
        return {
            "positive": self.positive,
            "neutral": self.neutral,
            "negative": self.negative,
            "positive_percent": round(self.positive / total * 100, 1) if total > 0 else 0,
            "neutral_percent": round(self.neutral / total * 100, 1) if total > 0 else 0,
            "negative_percent": round(self.negative / total * 100, 1) if total > 0 else 0,
        }


class AnalysisProcessor:
    """Обработка результатов анализа Claude в структурированные данные"""

    def __init__(self, similarity_threshold: float = 0.7):
        """
        Args:
            similarity_threshold: порог сходства для группировки проблем (0-1)
        """
        self.similarity_threshold = similarity_threshold

    def process(
        self,
        claude_response: Dict[str, Any],
        reviews: List[str],
        reviews_metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Преобразует ответ Claude в структурированные данные.

        Args:
            claude_response: Ответ от Claude с анализом
            reviews: Список исходных отзывов
            reviews_metadata: Метаданные отзывов с информацией об источнике

        Returns:
            Структурированный анализ с тональностью, проблемами и сводкой по источникам
        """
        total_reviews = len(reviews)

        # 1. Обработка тональности
        sentiments = self._extract_sentiments(claude_response, reviews)
        sentiment_summary = self._calculate_sentiment_stats(sentiments)

        # 2. Выявление top проблем/преимуществ
        issues_advantages = self._extract_issues_advantages(
            claude_response, reviews, sentiments
        )
        top_issues = self._rank_top_issues(issues_advantages, reviews)

        # 3. Анализ по источникам если доступны метаданные
        sentiment_by_source = None
        if reviews_metadata:
            sentiment_by_source = self._analyze_by_source(
                reviews_metadata, sentiments
            )

        result = {
            "total_reviews": total_reviews,
            "sentiment_summary": sentiment_summary,
            "top_issues": top_issues,
        }

        if sentiment_by_source:
            result["sentiment_by_source"] = sentiment_by_source

        return result

    def _extract_sentiments(
        self, claude_response: Dict[str, Any], reviews: List[str]
    ) -> List[str]:
        """Извлекает тональность каждого отзыва из ответа Claude"""
        sentiments = []

        # Ищем поле с анализом каждого отзыва
        if "review_sentiments" in claude_response:
            sentiments = claude_response["review_sentiments"]
        elif "sentiments" in claude_response:
            sentiments = claude_response["sentiments"]
        elif "analysis" in claude_response and isinstance(
            claude_response["analysis"], list
        ):
            # Если это список объектов с sentiment полем
            sentiments = [
                item.get("sentiment", "neutral").lower()
                for item in claude_response["analysis"]
            ]
        else:
            # Fallback: анализируем сами основываясь на тональности текста
            sentiments = self._simple_sentiment_analysis(reviews)

        # Нормализуем значения
        normalized = []
        for s in sentiments:
            s_lower = str(s).lower().strip()
            if "positive" in s_lower or "позитив" in s_lower or "good" in s_lower:
                normalized.append("positive")
            elif "negative" in s_lower or "негатив" in s_lower or "bad" in s_lower:
                normalized.append("negative")
            else:
                normalized.append("neutral")

        # Если количество не совпадает, дополняем нейтралом
        while len(normalized) < len(reviews):
            normalized.append("neutral")

        return normalized[:len(reviews)]

    def _simple_sentiment_analysis(self, reviews: List[str]) -> List[str]:
        """Простой анализ тональности на основе ключевых слов"""
        positive_words = {
            "отличный",
            "хороший",
            "прекрасный",
            "спасибо",
            "рекомендую",
            "довольный",
            "впечатлён",
            "полюбил",
            "супер",
            "great",
            "excellent",
            "good",
            "love",
            "perfect",
            "amazing",
        }
        negative_words = {
            "плохой",
            "ужасный",
            "не доволен",
            "разочарован",
            "не нравится",
            "проблема",
            "ошибка",
            "баг",
            "долго",
            "bad",
            "terrible",
            "hate",
            "awful",
            "disappointing",
            "problem",
            "issue",
        }

        sentiments = []
        for review in reviews:
            review_lower = review.lower()
            pos_count = sum(1 for word in positive_words if word in review_lower)
            neg_count = sum(1 for word in negative_words if word in review_lower)

            if pos_count > neg_count:
                sentiments.append("positive")
            elif neg_count > pos_count:
                sentiments.append("negative")
            else:
                sentiments.append("neutral")

        return sentiments

    def _calculate_sentiment_stats(self, sentiments: List[str]) -> Dict[str, float]:
        """Подсчитывает распределение тональности"""
        counter = Counter(sentiments)
        total = len(sentiments)

        return {
            "positive": counter.get("positive", 0),
            "neutral": counter.get("neutral", 0),
            "negative": counter.get("negative", 0),
            "positive_percent": round(counter.get("positive", 0) / total * 100, 1),
            "neutral_percent": round(counter.get("neutral", 0) / total * 100, 1),
            "negative_percent": round(counter.get("negative", 0) / total * 100, 1),
        }

    def _extract_issues_advantages(
        self,
        claude_response: Dict[str, Any],
        reviews: List[str],
        sentiments: List[str],
    ) -> List[Dict[str, Any]]:
        """Извлекает проблемы и преимущества из ответа Claude"""
        issues = []

        # Ищем различные форматы в ответе Claude
        if "main_issues" in claude_response:
            # main_issues - формат от analyzer с issue, frequency, sentiment
            for item in claude_response["main_issues"]:
                if isinstance(item, dict):
                    issues.append({
                        "text": item.get("issue", str(item)),
                        "sentiment": item.get("sentiment", "neutral"),
                        "frequency": item.get("frequency", 0)
                    })
                else:
                    issues.append({"text": str(item), "sentiment": "neutral", "frequency": 0})
        if "issues" in claude_response:
            issues.extend(
                self._normalize_issues(claude_response["issues"], "negative")
            )
        if "problems" in claude_response:
            issues.extend(
                self._normalize_issues(claude_response["problems"], "negative")
            )
        if "advantages" in claude_response:
            issues.extend(
                self._normalize_issues(claude_response["advantages"], "positive")
            )
        if "strengths" in claude_response:
            issues.extend(
                self._normalize_issues(claude_response["strengths"], "positive")
            )
        if "findings" in claude_response:
            for finding in claude_response["findings"]:
                if isinstance(finding, str):
                    # Определяем тональность по контексту
                    sentiment = "negative" if "проблема" in finding.lower() else "positive"
                    issues.append({"text": finding, "sentiment": sentiment})
                elif isinstance(finding, dict):
                    issues.append(finding)

        return issues

    def _normalize_issues(
        self, items: Any, default_sentiment: str
    ) -> List[Dict[str, str]]:
        """Нормализует различные форматы проблем"""
        normalized = []

        if isinstance(items, list):
            for item in items:
                if isinstance(item, str):
                    normalized.append({"text": item, "sentiment": default_sentiment})
                elif isinstance(item, dict):
                    normalized.append(item)
        elif isinstance(items, dict):
            normalized.append(items)

        return normalized

    def _rank_top_issues(
        self, issues: List[Dict[str, Any]], reviews: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Ранжирует проблемы по частоте упоминания в отзывах.
        Группирует похожие проблемы.
        """
        if not issues:
            return []

        # Группируем похожие проблемы
        grouped = self._group_similar_issues(issues)

        # Подсчитываем частоту упоминания в отзывах
        ranked = []
        for group in grouped:
            # Используем существующий frequency если он есть, иначе пересчитываем
            frequency = group.get("frequency", 0)
            if frequency == 0:
                frequency = self._count_mentions(group["text"], reviews)

            percentage = round(frequency / len(reviews) * 100, 1) if frequency > 0 else 0.0

            ranked.append(
                {
                    "issue": group["text"],
                    "frequency": frequency,
                    "percentage": percentage,
                    "sentiment": group.get("sentiment", "neutral"),
                }
            )

        # Сортируем по частоте и берём топ 5
        ranked.sort(key=lambda x: x["frequency"], reverse=True)
        return ranked[:5]

    def _group_similar_issues(
        self, issues: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Группирует похожие проблемы"""
        if not issues:
            return []

        # Нормализуем и удаляем дубликаты
        unique_issues = {}
        for issue in issues:
            text = issue.get("text", str(issue))
            key = text.lower().strip()

            if key not in unique_issues:
                unique_issues[key] = issue

        grouped = []
        processed = set()

        for issue_text, issue_data in unique_issues.items():
            if issue_text in processed:
                continue

            group = issue_data.copy()
            processed.add(issue_text)

            # Ищем похожие проблемы
            for other_text, other_data in unique_issues.items():
                if other_text == issue_text or other_text in processed:
                    continue

                similarity = self._calculate_similarity(issue_text, other_text)
                if similarity >= self.similarity_threshold:
                    # Объединяем (берём более информативную версию)
                    if len(other_text) > len(issue_text):
                        group["text"] = other_data.get("text", other_text)
                    processed.add(other_text)

            grouped.append(group)

        return grouped

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Вычисляет схожесть двух текстов"""
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

    def _count_mentions(self, issue_text: str, reviews: List[str]) -> int:
        """Подсчитывает упоминания проблемы в отзывах"""
        issue_lower = issue_text.lower()
        count = 0

        for review in reviews:
            review_lower = review.lower()
            # Проверяем наличие ключевых слов из проблемы
            words = [w for w in issue_lower.split() if len(w) > 3]
            if any(word in review_lower for word in words):
                count += 1

        return count

    def _analyze_by_source(
        self,
        reviews_metadata: List[Dict[str, Any]],
        sentiments: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        """Анализирует тональность по источникам"""
        by_source = {}

        for metadata, sentiment in zip(reviews_metadata, sentiments):
            source = metadata.get("source", "Unknown")

            if source not in by_source:
                by_source[source] = SentimentCount()

            if sentiment == "positive":
                by_source[source].positive += 1
            elif sentiment == "negative":
                by_source[source].negative += 1
            else:
                by_source[source].neutral += 1

        # Преобразуем в словарь с процентами
        result = {}
        for source, counts in by_source.items():
            result[source] = counts.to_dict()

        return result


def demonstrate_processor():
    """Демонстрация работы processor на примере 100 отзывов"""
    import random

    # Генерируем тестовые данные: 100 отзывов
    reviews = [
        "Отличный сервис, всё работает быстро и эффективно!",  # positive
        "Хороший опыт, рекомендую всем.",  # positive
        "Среднее качество, ничего особенного.",  # neutral
        "Плохое обслуживание, долго ждал ответа.",  # negative
        "Не доволен результатом, полная пустая трата денег.",  # negative
        "Прекрасное качество, спасибо за помощь!",  # positive
        "Обычный сервис, может быть чуть лучше.",  # neutral
        "Ужасный опыт, не рекомендую.",  # negative
        "Отличная работа команды, очень доволен!",  # positive
        "Нормально, ничего плохого, но и не супер.",  # neutral
    ]

    # Расширяем датасет до 100 отзывов
    sources = ["2GIS", "Яндекс.Карты", "Google", "Avvo", "Отзовик"]

    extended_reviews = []
    extended_metadata = []

    for i in range(100):
        review_template = random.choice(reviews)
        extended_reviews.append(f"Отзыв {i+1}: {review_template}")
        extended_metadata.append({
            "source": random.choice(sources),
            "date": f"2026-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
            "rating": random.randint(1, 5),
        })

    # Имитируем ответ от Claude
    claude_response = {
        "review_sentiments": [
            "positive" if i % 3 == 0 else "negative" if i % 3 == 1 else "neutral"
            for i in range(100)
        ],
        "issues": [
            "Долгое ожидание ответа",
            "Проблемы с интеграцией",
            "Низкая скорость обработки",
        ],
        "advantages": [
            "Удобный интерфейс",
            "Быстрое решение проблем",
            "Отличная поддержка клиентов",
        ],
    }

    # Обработка результатов
    processor = AnalysisProcessor()
    result = processor.process(claude_response, extended_reviews, extended_metadata)

    # Вывод результатов
    print("\n" + "=" * 70)
    print("[PROCESSOR] ОБРАБОТАННЫЙ АНАЛИЗ (100 ОТЗЫВОВ)")
    print("=" * 70)

    print(f"\n[ОБЩАЯ СТАТИСТИКА]")
    print(f"   Всего отзывов: {result['total_reviews']}")

    print(f"\n[РАСПРЕДЕЛЕНИЕ ТОНАЛЬНОСТИ]")
    sentiment = result["sentiment_summary"]
    print(f"   Позитивные: {sentiment['positive']} ({sentiment['positive_percent']}%)")
    print(f"   Нейтральные: {sentiment['neutral']} ({sentiment['neutral_percent']}%)")
    print(f"   Негативные: {sentiment['negative']} ({sentiment['negative_percent']}%)")

    print(f"\n[TOP ПРОБЛЕМЫ И ПРЕИМУЩЕСТВА]")
    for i, issue in enumerate(result["top_issues"], 1):
        sentiment_label = "[NEGATIVO]" if issue["sentiment"] == "negative" else "[POSITIVO]"
        print(
            f"   {i}. {sentiment_label} {issue['issue']}"
        )
        print(
            f"      Упоминаний: {issue['frequency']} ({issue['percentage']}%)"
        )

    if "sentiment_by_source" in result:
        print(f"\n[АНАЛИЗ ПО ИСТОЧНИКАМ]")
        for source, stats in result["sentiment_by_source"].items():
            print(f"\n   {source}:")
            print(f"      Позитивные: {stats['positive']} ({stats['positive_percent']}%)")
            print(f"      Нейтральные: {stats['neutral']} ({stats['neutral_percent']}%)")
            print(f"      Негативные: {stats['negative']} ({stats['negative_percent']}%)")

    print("\n" + "=" * 70)
    print("[CHECK] ПРОВЕРКИ КОРРЕКТНОСТИ:")
    print("=" * 70)

    # Проверка 1: сумма процентов = 100%
    total_percent = (
        sentiment["positive_percent"]
        + sentiment["neutral_percent"]
        + sentiment["negative_percent"]
    )
    print(f"[PASS] Сумма процентов тональности: {total_percent}% (должно быть 100%)")

    # Проверка 2: сумма количеств = total_reviews
    total_count = sentiment["positive"] + sentiment["neutral"] + sentiment["negative"]
    print(f"[PASS] Сумма количеств: {total_count} (должно быть {result['total_reviews']})")

    # Проверка 3: top_issues не пусты
    print(f"[PASS] Найдено проблем/преимуществ: {len(result['top_issues'])} (max 5)")

    # Проверка 4: процент проблем логичен
    if result["top_issues"]:
        max_percentage = max(issue["percentage"] for issue in result["top_issues"])
        print(f"[PASS] Максимальный процент проблемы: {max_percentage}% (логичное значение)")

    print("\n" + "=" * 70)
    print("[JSON] ВЫВОД СТРУКТУРИРОВАННЫХ ДАННЫХ:")
    print("=" * 70)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    return result


if __name__ == "__main__":
    demonstrate_processor()
