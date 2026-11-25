from django.urls import path

from . import views

urlpatterns = [
    path("analysis/snapshot/", views.snapshot),
    path("analysis/queries/", views.queries),
    path("analysis/report/", views.report),
    path("analysis/export/", views.export),
]
