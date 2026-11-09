from django.urls import path

from .views import (
    BookView,
    CancelView,
    ChatView,
    FactDetailView,
    FactListCreateView,
    FlaggedChatsView,
    HandoffView,
    LeadChatView,
    ReviewChatView,
)

urlpatterns = [
    path("public/chat/", ChatView.as_view()),
    path("public/chat/book/", BookView.as_view()),
    path("public/chat/cancel/", CancelView.as_view()),
    path("public/chat/handoff/", HandoffView.as_view()),
    path("leads/<int:lead_id>/chat/", LeadChatView.as_view()),
    path("chats/flagged/", FlaggedChatsView.as_view()),
    path("chats/<int:conversation_id>/review/", ReviewChatView.as_view()),
    path("facts/", FactListCreateView.as_view()),
    path("facts/<int:fact_id>/", FactDetailView.as_view()),
]