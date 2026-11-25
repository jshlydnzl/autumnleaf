from django.http import JsonResponse
from django.urls import include, path
from django.views.decorators.http import require_safe


@require_safe
def health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("api/health/", health, name="health"),
    path("api/", include("identity.urls")),
    path("api/", include("pipelines.urls")),
    path("api/", include("pipelines.kaggle_urls")),
]
