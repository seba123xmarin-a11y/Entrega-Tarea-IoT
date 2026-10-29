from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from django.views.static import serve as serve_static

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("monitoring/", include("monitoring.urls")),
    path("", RedirectView.as_view(url="/monitoring/", permanent=False)),
]

# Uploaded branding images served directly by gunicorn (no separate nginx/object
# storage in this stack) — fine at this project's scale. Wired directly (not via
# django.conf.urls.static.static(), which refuses to run when DEBUG=False) since
# this stack has no other way to serve media in a non-DEBUG deployment.
urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", serve_static, {"document_root": settings.MEDIA_ROOT}),
]
