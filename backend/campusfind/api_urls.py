"""Version-neutral API root routes."""
from django.urls import include, path


urlpatterns = [
    path("auth/", include("accounts.urls")),
    path("items/", include("items.urls")),
    path("matching/", include("matching.urls")),
    path("notifications/", include("notifications.urls")),
    path("recovery/", include("recovery.urls")),
]
