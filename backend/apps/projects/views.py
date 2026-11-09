from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Project


def payload(p):
    return {"id": p.id, "name": p.name, "rera_number": p.rera_number, "address": p.address}


class PublicProjectListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response([payload(p) for p in Project.objects.order_by("id")])


class PublicProjectDetailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, project_id):
        return Response(payload(get_object_or_404(Project, pk=project_id)))