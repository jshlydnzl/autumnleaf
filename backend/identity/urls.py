from django.urls import path

from . import views

urlpatterns = [
    path("auth/csrf/", views.csrf),
    path("auth/session/", views.session),
    path("auth/login/", views.sign_in),
    path("auth/logout/", views.sign_out),
    path("auth/setup/", views.set_password),
    path("accounts/", views.accounts),
    path("accounts/<uuid:account_id>/", views.manage_account),
    path("workspaces/<uuid:account_id>/", views.workspace),
]
