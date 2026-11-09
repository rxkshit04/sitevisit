from django.urls import path

from .views import PublicProjectDetailView, PublicProjectListView

urlpatterns = [
    path("public/projects/", PublicProjectListView.as_view()),
    path("public/projects/<int:project_id>/", PublicProjectDetailView.as_view()),
]