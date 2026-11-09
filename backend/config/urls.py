from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, Http404
from django.urls import include, path, re_path


def spa(request, path=""):
    """Serve the built React app for every non-API route."""
    index = settings.FRONTEND_DIST / "index.html"
    if not index.exists():
        raise Http404("Frontend not built. Run `npm run build` in frontend/.")
    return FileResponse(open(index, "rb"), content_type="text/html")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/", include("apps.booking.urls")),
    path("api/", include("apps.leads.urls")),
    path("api/", include("apps.chat.urls")),
    path("api/", include("apps.reports.urls")),
    path("api/", include("apps.projects.urls")),
    re_path(r"^(?!api/|admin/|static/).*$", spa),
]