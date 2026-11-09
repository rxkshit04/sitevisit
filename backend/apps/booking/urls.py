from django.urls import path

from .staff_views import VisitOutcomeView
from .views import FreeSlotsView, HealthView

urlpatterns = [
    path("health/", HealthView.as_view()),
    path("projects/<int:project_id>/slots/", FreeSlotsView.as_view()),
    path("bookings/<int:booking_id>/outcome/", VisitOutcomeView.as_view()),
]