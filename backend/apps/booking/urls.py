from django.urls import path

from .admin_views import ExecutivesView, ProjectsView, SlotDeleteView, SlotListGenerateView
from .staff_views import VisitOutcomeView
from .views import FreeSlotsView, HealthView

urlpatterns = [
    path("health/", HealthView.as_view()),
    path("projects/<int:project_id>/slots/", FreeSlotsView.as_view()),
    path("bookings/<int:booking_id>/outcome/", VisitOutcomeView.as_view()),
    path("admin/slots/", SlotListGenerateView.as_view()),
    path("admin/slots/<int:slot_id>/", SlotDeleteView.as_view()),
    path("admin/executives/", ExecutivesView.as_view()),
    path("admin/projects/", ProjectsView.as_view()),
]