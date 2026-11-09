from django.urls import path

from .detail_views import LeadDetailView
from .views import ImportLeadsView, LeadListCreateView, PublicIntakeView

urlpatterns = [
    path("leads/", LeadListCreateView.as_view()),
    path("leads/import/", ImportLeadsView.as_view()),
    path("leads/<int:lead_id>/", LeadDetailView.as_view()),
    path("public/leads/", PublicIntakeView.as_view()),
]