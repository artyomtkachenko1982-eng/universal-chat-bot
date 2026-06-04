"""
app/schemas/ — все Pydantic схемы собраны здесь
"""

from app.schemas.user import (
    AuthRequest, AuthResponse,
    UserProfile,
    SearchRequest, SearchResult, SearchResponse,
    AiQuestion, AiAnswer,
    AdOrderRequest, AdPriceItem,
    NewsSuggestionRequest,
    UserStatsResponse,
)
