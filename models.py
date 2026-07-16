from dataclasses import dataclass
from typing import List, Optional, Dict, Any


@dataclass
class AnalyzeRequest:
    reviews: List[str]

    @classmethod
    def from_dict(cls, data: dict) -> "AnalyzeRequest":
        return cls(reviews=data.get("reviews", []))


@dataclass
class AnalyzeResponse:
    sentiments: List[Dict[str, Any]]
    main_issues: List[Dict[str, Any]]
    top_positive: Optional[str]
    top_negative: Optional[str]

    def to_dict(self) -> dict:
        return {
            "sentiments": self.sentiments,
            "main_issues": self.main_issues,
            "top_positive": self.top_positive,
            "top_negative": self.top_negative
        }

    @classmethod
    def from_analysis(cls, analysis: dict) -> "AnalyzeResponse":
        """Create response from analyzer results"""
        return cls(
            sentiments=analysis.get("sentiments", []),
            main_issues=analysis.get("main_issues", []),
            top_positive=analysis.get("top_positive"),
            top_negative=analysis.get("top_negative")
        )
