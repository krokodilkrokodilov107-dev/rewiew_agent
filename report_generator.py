import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]

    def __bool__(self):
        return self.is_valid


class ReportGenerator:
    """Генератор итогового отчёта из обработанных данных анализа"""

    def __init__(self, use_claude: bool = False):
        """
        Args:
            use_claude: Использовать ли Claude для генерации рекомендаций
        """
        self.use_claude = use_claude
        self._anthropic_client = None

    def generate(
        self, processed_analysis: Dict[str, Any], processing_time: float
    ) -> Dict[str, Any]:
        """
        Генерирует итоговый отчёт из обработанных данных анализа.

        Args:
            processed_analysis: Результат AnalysisProcessor.process()
            processing_time: Время обработки в секундах (float)

        Returns:
            Полный JSON отчёт с валидацией
        """
        total_reviews = processed_analysis.get("total_reviews", 0)

        # 1. Metadata
        metadata = self._generate_metadata(total_reviews, processing_time)

        # 2. Sentiment summary
        sentiment_summary = self._process_sentiment_summary(
            processed_analysis.get("sentiment_summary", {})
        )

        # 3. Top issues с примерами
        top_issues = self._process_top_issues(
            processed_analysis.get("top_issues", []),
            processed_analysis.get("_reviews", []),  # Используем исходные отзывы
        )

        # 4. Recommendations
        recommendations = self._generate_recommendations(top_issues)

        # 5. Sentiment by source (если есть)
        report = {
            "metadata": metadata,
            "sentiment_summary": sentiment_summary,
            "top_issues": top_issues,
            "recommendations": recommendations,
        }

        if "sentiment_by_source" in processed_analysis:
            report["sentiment_by_source"] = processed_analysis[
                "sentiment_by_source"
            ]

        # Валидация
        validation = self._validate_report(report)
        if not validation:
            raise ValueError(f"Report validation failed: {validation.errors}")

        return report

    def _generate_metadata(
        self, total_reviews: int, processing_time: float
    ) -> Dict[str, Any]:
        """Генерирует блок metadata"""
        return {
            "total_reviews": total_reviews,
            "analysis_date": datetime.utcnow().isoformat() + "Z",
            "processing_time_sec": round(processing_time, 3),
        }

    def _process_sentiment_summary(
        self, sentiment_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Обрабатывает и валидирует sentiment_summary"""
        result = {
            "positive": sentiment_summary.get("positive", 0),
            "neutral": sentiment_summary.get("neutral", 0),
            "negative": sentiment_summary.get("negative", 0),
            "positive_percent": round(
                sentiment_summary.get("positive_percent", 0), 1
            ),
            "neutral_percent": round(
                sentiment_summary.get("neutral_percent", 0), 1
            ),
            "negative_percent": round(
                sentiment_summary.get("negative_percent", 0), 1
            ),
        }

        # Корректируем проценты если сумма не 100%
        total_percent = (
            result["positive_percent"]
            + result["neutral_percent"]
            + result["negative_percent"]
        )
        if abs(total_percent - 100.0) > 0.1:
            # Нормализуем проценты
            if total_percent > 0:
                result["positive_percent"] = round(
                    (result["positive"] / (result["positive"] + result["neutral"] + result["negative"]) * 100),
                    1,
                )
                result["neutral_percent"] = round(
                    (result["neutral"] / (result["positive"] + result["neutral"] + result["negative"]) * 100),
                    1,
                )
                result["negative_percent"] = round(
                    (result["negative"] / (result["positive"] + result["neutral"] + result["negative"]) * 100),
                    1,
                )

        return result

    def _process_top_issues(
        self, top_issues: List[Dict[str, Any]], reviews: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Обрабатывает top_issues и добавляет примеры.

        Args:
            top_issues: Список проблем/преимуществ
            reviews: Исходные отзывы для извлечения примеров

        Returns:
            Обработанный список с примерами
        """
        if not reviews:
            reviews = []

        processed = []

        for issue in top_issues:
            # Извлекаем примеры из отзывов
            examples = self._extract_examples(
                issue.get("issue", ""), reviews, max_examples=2
            )

            processed.append(
                {
                    "issue": issue.get("issue", ""),
                    "frequency": issue.get("frequency", 0),
                    "percentage": round(issue.get("percentage", 0), 1),
                    "sentiment": issue.get("sentiment", "neutral"),
                    "examples": examples,
                }
            )

        return processed

    def _extract_examples(
        self, issue_text: str, reviews: List[str], max_examples: int = 2
    ) -> List[str]:
        """
        Извлекает примеры отзывов, содержащих упомянутую проблему.

        Args:
            issue_text: Текст проблемы/преимущества
            reviews: Список отзывов
            max_examples: Максимальное количество примеров

        Returns:
            Список примеров (до max_examples)
        """
        if not reviews or not issue_text:
            return []

        examples = []
        issue_lower = issue_text.lower()

        # Ищем отзывы, содержащие ключевые слова из проблемы
        keywords = [
            w.strip().lower()
            for w in issue_lower.split()
            if len(w.strip()) > 3
        ]

        for review in reviews:
            review_lower = review.lower()

            # Проверяем наличие хотя бы одного ключевого слова
            if any(keyword in review_lower for keyword in keywords):
                # Обрезаем отзыв если он слишком длинный
                if len(review) > 150:
                    example = review[:150] + "..."
                else:
                    example = review

                examples.append(example)

                if len(examples) >= max_examples:
                    break

        return examples

    def _generate_recommendations(
        self, top_issues: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Генерирует рекомендации на основе top_issues.

        Args:
            top_issues: Список проблем/преимуществ

        Returns:
            Список из 2-3 практичных рекомендаций
        """
        if self.use_claude:
            return self._generate_recommendations_with_claude(top_issues)
        else:
            return self._generate_recommendations_heuristic(top_issues)

    def _generate_recommendations_heuristic(
        self, top_issues: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Генерирует рекомендации на основе эвристики (без Claude).

        Используется когда use_claude=False.
        """
        recommendations = []

        # Берём проблемы по типам тональности
        negative_issues = [
            issue
            for issue in top_issues
            if issue.get("sentiment") == "negative"
        ]
        positive_issues = [
            issue
            for issue in top_issues
            if issue.get("sentiment") == "positive"
        ]
        neutral_issues = [
            issue
            for issue in top_issues
            if issue.get("sentiment") == "neutral"
        ]

        # Рекомендация 1: устранение главной проблемы (или нейтральной)
        if negative_issues:
            main_issue = negative_issues[0]
            freq = main_issue.get("frequency", 0)
            issue_text = main_issue.get("issue", "")
            rec = self._issue_to_recommendation(issue_text, freq)
            recommendations.append(rec)
        elif neutral_issues:
            main_issue = neutral_issues[0]
            freq = main_issue.get("frequency", 0)
            issue_text = main_issue.get("issue", "")
            rec = f"Обратить внимание на: {issue_text} ({freq} упоминаний). Проанализировать и определить направления улучшения."
            recommendations.append(rec)

        # Рекомендация 2: усиление преимущества или вторая проблема
        if positive_issues:
            main_strength = positive_issues[0]
            freq = main_strength.get("frequency", 0)
            issue_text = main_strength.get("issue", "")
            rec = f"Продолжить и усилить: {issue_text} ({freq} упоминаний). Это ваше конкурентное преимущество."
            recommendations.append(rec)
        elif len(negative_issues) > 1:
            second_issue = negative_issues[1]
            freq = second_issue.get("frequency", 0)
            issue_text = second_issue.get("issue", "")
            rec = f"Обучить команду по: {issue_text} ({freq} упоминаний). Реализовать систему контроля качества."
            recommendations.append(rec)

        # Рекомендация 3: дополнительное улучшение
        if len(recommendations) < 3:
            if len(negative_issues) > 1:
                second_issue = negative_issues[1]
                freq = second_issue.get("frequency", 0)
                issue_text = second_issue.get("issue", "")
                rec = f"Систематически решать: {issue_text} ({freq} упоминаний). Разработать план действий."
                recommendations.append(rec)
            elif positive_issues and len(positive_issues) > 1:
                second_strength = positive_issues[1]
                freq = second_strength.get("frequency", 0)
                issue_text = second_strength.get("issue", "")
                rec = f"Развивать также: {issue_text} ({freq} упоминаний). Масштабировать успешные подходы."
                recommendations.append(rec)
            else:
                recommendations.append(
                    "Регулярно собирать отзывы клиентов для выявления областей улучшения."
                )

        # Fallback: гарантируем минимум 2 рекомендации
        if len(recommendations) < 2:
            recommendations.append(
                "Повысить качество и скорость обслуживания в соответствии с отзывами клиентов."
            )

        return recommendations[:3]

    def _issue_to_recommendation(self, issue_text: str, frequency: int) -> str:
        """
        Преобразует проблему в практичную рекомендацию.

        Args:
            issue_text: Описание проблемы
            frequency: Количество упоминаний

        Returns:
            Строка с рекомендацией
        """
        issue_lower = issue_text.lower()

        # Кодирование общих проблем в рекомендации
        recommendations_map = {
            "долг": f"Оптимизировать процесс обработки ({frequency} упоминаний о задержках). Пересмотреть workflow и ресурсы.",
            "ожидан": f"Сократить время ожидания ({frequency} отзывов). Увеличить численность или оптимизировать процесс.",
            "медлен": f"Повысить скорость обработки ({frequency} жалоб). Автоматизировать рутинные операции.",
            "проблем": f"Систематически решать проблемы ({frequency} упоминаний). Внедрить систему управления проблемами.",
            "бага": f"Исправить критические ошибки ({frequency} упоминаний). Усилить QA-тестирование перед релизом.",
            "интеграц": f"Улучшить интеграцию систем ({frequency} упоминаний). Проверить совместимость компонентов.",
            "сервис": f"Улучшить качество сервиса ({frequency} упоминаний). Пересмотреть стандарты обслуживания.",
        }

        # Ищем подходящую рекомендацию по ключевым словам
        for key, rec_template in recommendations_map.items():
            if key in issue_lower:
                return rec_template

        # Дефолтная рекомендация
        return f"Устранить проблему: {issue_text} ({frequency} упоминаний). Разработать действенный план улучшений."

    def _generate_recommendations_with_claude(
        self, top_issues: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Генерирует рекомендации используя Claude API.

        ПРИМЕЧАНИЕ: Требует наличия ANTHROPIC_API_KEY в env и активного интернета.

        Args:
            top_issues: Список проблем/преимуществ

        Returns:
            Список из 2-3 практичных рекомендаций
        """
        try:
            from anthropic import Anthropic

            client = Anthropic()

            # Формируем контекст для Claude
            issues_text = "\n".join(
                [
                    f"- {issue['issue']} ({issue['frequency']} упоминаний, "
                    f"{issue['sentiment']})"
                    for issue in top_issues
                ]
            )

            prompt = f"""На основе анализа отзывов клиентов были выявлены следующие ключевые проблемы и преимущества:

{issues_text}

Дай 2-3 конкретных, практичных рекомендации для владельца ресторана/магазина по улучшению.

Формат ответа - JSON array со строками (без нумерации, просто текст)."""

            message = client.messages.create(
                model="claude-opus-4-1",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = message.content[0].text

            # Парсим JSON ответ
            try:
                import re

                json_match = re.search(
                    r"\[[\s\S]*\]", response_text
                )  # Ищем JSON array
                if json_match:
                    recommendations = json.loads(json_match.group())
                    if isinstance(recommendations, list):
                        return [str(r)[:200] for r in recommendations[:3]]  # Обрезаем длинные рекомендации
            except (json.JSONDecodeError, AttributeError):
                pass

            # Fallback если парсинг не удался
            return self._generate_recommendations_heuristic(top_issues)

        except ImportError:
            # Если anthropic не установлен, используем эвристику
            return self._generate_recommendations_heuristic(top_issues)
        except Exception as e:
            # При любой ошибке API используем fallback
            print(f"Warning: Claude recommendation generation failed: {e}")
            return self._generate_recommendations_heuristic(top_issues)

    def _validate_report(self, report: Dict[str, Any]) -> ValidationResult:
        """
        Валидирует сгенерированный отчёт.

        Args:
            report: Сгенерированный отчёт

        Returns:
            ValidationResult с информацией об ошибках
        """
        errors = []

        # Проверка 1: наличие обязательных полей
        required_fields = [
            "metadata",
            "sentiment_summary",
            "top_issues",
            "recommendations",
        ]
        for field in required_fields:
            if field not in report:
                errors.append(f"Missing required field: {field}")

        # Проверка 2: проценты в sentiment_summary = 100% (±0.1%)
        if "sentiment_summary" in report:
            sentiment = report["sentiment_summary"]
            total_percent = (
                sentiment.get("positive_percent", 0)
                + sentiment.get("neutral_percent", 0)
                + sentiment.get("negative_percent", 0)
            )

            if abs(total_percent - 100.0) > 0.1:
                errors.append(
                    f"Sentiment percentages sum to {total_percent}%, "
                    f"should be ~100%"
                )

            # Проверка что counts совпадают с процентами
            counts_sum = (
                sentiment.get("positive", 0)
                + sentiment.get("neutral", 0)
                + sentiment.get("negative", 0)
            )
            total_reviews = report.get("metadata", {}).get("total_reviews", 0)

            if total_reviews > 0 and counts_sum != total_reviews:
                errors.append(
                    f"Sentiment counts sum ({counts_sum}) doesn't match "
                    f"total_reviews ({total_reviews})"
                )

        # Проверка 3: top_issues имеют примеры и валидные данные
        if "top_issues" in report:
            for i, issue in enumerate(report["top_issues"]):
                # Проверяем обязательные поля
                required_issue_fields = [
                    "issue",
                    "frequency",
                    "percentage",
                    "sentiment",
                ]
                for field in required_issue_fields:
                    if field not in issue:
                        errors.append(
                            f"top_issues[{i}] missing field: {field}"
                        )

                # Проверяем что примеры содержат ключевые слова из проблемы
                issue_text = issue.get("issue", "").lower()
                examples = issue.get("examples", [])

                if issue_text and examples:
                    # Ищем хотя бы одно ключевое слово в примерах
                    keywords = [
                        w.strip().lower()
                        for w in issue_text.split()
                        if len(w.strip()) > 3
                    ]

                    found_keyword = False
                    for example in examples:
                        example_lower = example.lower()
                        if any(
                            keyword in example_lower
                            for keyword in keywords
                        ):
                            found_keyword = True
                            break

                    if keywords and not found_keyword:
                        errors.append(
                            f"top_issues[{i}] examples don't contain issue keywords"
                        )

        # Проверка 4: recommendations не пусты
        if "recommendations" in report:
            if not report["recommendations"]:
                errors.append("Recommendations list is empty")
            elif len(report["recommendations"]) < 2:
                errors.append(
                    "Recommendations should have 2-3 items, "
                    f"found {len(report['recommendations'])}"
                )

        # Проверка 5: metadata содержит валидную дату ISO 8601
        if "metadata" in report:
            metadata = report["metadata"]

            if "analysis_date" not in metadata:
                errors.append("metadata missing analysis_date")
            else:
                try:
                    analysis_date = metadata["analysis_date"]
                    # Проверяем что это похоже на ISO 8601
                    if not (
                        "T" in analysis_date and "Z" in analysis_date
                    ):
                        errors.append(
                            f"analysis_date not in ISO 8601 format: "
                            f"{analysis_date}"
                        )
                except Exception as e:
                    errors.append(f"Invalid analysis_date: {e}")

            if "processing_time_sec" not in metadata:
                errors.append("metadata missing processing_time_sec")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def to_json(self, report: Dict[str, Any]) -> str:
        """
        Конвертирует отчёт в JSON строку.

        Args:
            report: Сгенерированный отчёт

        Returns:
            JSON строка с красивым форматированием
        """
        return json.dumps(report, indent=2, ensure_ascii=False)


# Демонстрация работы ReportGenerator
def demonstrate_report_generator():
    """Демонстрирует работу ReportGenerator на примере 100 отзывов"""
    from processor import demonstrate_processor

    print("\n" + "=" * 70)
    print("[REPORT_GENERATOR] ДЕМОНСТРАЦИЯ")
    print("=" * 70)

    # Получаем обработанные данные от AnalysisProcessor
    processed_analysis = demonstrate_processor()

    # Мимикрируем исходные отзывы для примеров
    sample_reviews = [
        "Долгое ожидание, но в целом хорошо",
        "Отличный сервис, проблем не было",
        "Очень долго готовили, чуть не ушли",
        "Быстрое решение, спасибо!",
        "Интеграция работает, но не всегда стабильно",
    ]

    # Добавляем исходные отзывы в processed_analysis для примеров
    processed_analysis["_reviews"] = sample_reviews

    # Создаём генератор отчётов
    generator = ReportGenerator(use_claude=False)  # Не используем Claude API

    # Имитируем время обработки
    processing_time = 2.345

    # Генерируем отчёт
    report = generator.generate(processed_analysis, processing_time)

    print("\n" + "=" * 70)
    print("[REPORT] СГЕНЕРИРОВАННЫЙ ОТЧЁТ")
    print("=" * 70)
    print(generator.to_json(report))

    # Валидация
    print("\n" + "=" * 70)
    print("[VALIDATION] ПРОВЕРКА ЦЕЛОСТНОСТИ ОТЧЁТА")
    print("=" * 70)

    validation = generator._validate_report(report)
    if validation:
        print("[✓ PASS] Отчёт валиден!")
    else:
        print("[✗ FAIL] Ошибки валидации:")
        for error in validation.errors:
            print(f"   - {error}")

    # Дополнительные проверки
    print("\n" + "=" * 70)
    print("[CHECKS] ДОПОЛНИТЕЛЬНЫЕ ПРОВЕРКИ")
    print("=" * 70)

    sentiment = report["sentiment_summary"]
    total_percent = (
        sentiment["positive_percent"]
        + sentiment["neutral_percent"]
        + sentiment["negative_percent"]
    )
    print(
        f"[✓] Сумма процентов тональности: {total_percent}% "
        f"(должно быть ~100%)"
    )

    total_count = (
        sentiment["positive"] + sentiment["neutral"] + sentiment["negative"]
    )
    print(
        f"[✓] Сумма количеств: {total_count} "
        f"(должно быть {report['metadata']['total_reviews']})"
    )

    print(f"[✓] Найдено top issues: {len(report['top_issues'])}")
    print(f"[✓] Найдено recommendations: {len(report['recommendations'])}")

    # Проверка примеров
    print(f"\n[ПРОВЕРКА ПРИМЕРОВ В TOP ISSUES]")
    for i, issue in enumerate(report["top_issues"], 1):
        examples_count = len(issue.get("examples", []))
        print(
            f"   {i}. {issue['issue'][:40]}... "
            f"({examples_count} примеров)"
        )
        if issue.get("examples"):
            for j, example in enumerate(issue["examples"], 1):
                print(f"      Пример {j}: {example[:80]}...")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    demonstrate_report_generator()
