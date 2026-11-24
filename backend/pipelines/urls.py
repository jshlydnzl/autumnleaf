from django.urls import path

from . import views

urlpatterns = [
    path("warehouse/", views.warehouse_tables),
    path("pipelines/", views.pipeline_runs),
    path("pipelines/compare/", views.pipeline_compare),
    path("pipelines/samples/<str:filename>/", views.pipeline_sample),
    path("pipelines/<uuid:run_id>/", views.pipeline_detail),
    path("pipelines/<uuid:run_id>/advance/", views.pipeline_advance),
    path("pipelines/<uuid:run_id>/automate/", views.pipeline_automate),
    path("pipelines/<uuid:run_id>/sync/", views.pipeline_sync),
    path("pipelines/<uuid:run_id>/publish/", views.pipeline_publish),
]
