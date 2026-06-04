"""
app/handlers/ — обработчики команд
"""

from app.handlers.commands import (
    handle_start,
    handle_auth,
    handle_profile,
    handle_search,
    handle_clear_chat,
    handle_settings,
    handle_stats,
    handle_channels,
    # Админка:
    handle_admin_message,
    handle_ad_prices,
    handle_ad_submit,
    handle_news_suggest,
    handle_admin_panel,
    handle_admin_list_messages,
    handle_admin_view_message,
    handle_admin_respond,
    # Админ-панель 2.0:
    handle_admin_welcome,
    handle_admin_panel_data,
    handle_admin_approve_ad,
    handle_admin_reject_ad,
    handle_admin_approve_news,
    handle_admin_reject_news,
    # Мои обращения:
    handle_my_requests,
    handle_my_notifications,
    # Чат с админом:
    handle_get_chat,
    handle_get_chat_list,
    handle_admin_chat_reply,
)
