from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.SiteLoginView.as_view(), name="login"),
    path("logout/", views.SiteLogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),
    path("profile/", views.profile, name="profile"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path(
        "password/",
        views.SitePasswordChangeView.as_view(),
        name="password_change",
    ),
]
