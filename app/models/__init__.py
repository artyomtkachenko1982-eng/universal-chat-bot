"""
app/models/ — все SQLAlchemy модели собраны здесь
"""

from app.models.database import Base, BotUser, UserState, AdRequest, NewsSuggestion, UserStats

# Чтобы было удобно импортировать:
# from app.models import Base, BotUser, UserState, ...
