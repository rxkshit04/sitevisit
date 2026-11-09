from django.urls import path

from .views import ImportLeadsView, LeadListCreateView, PublicIntakeView

urlpatterns = [
    path("leads/", LeadListCreateView.as_view()),
    path("leads/import/", ImportLeadsView.as_view()),
    path("public/leads/", PublicIntakeView.as_view()),
]