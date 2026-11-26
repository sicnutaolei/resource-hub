from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.SiteLoginView.as_view(), name="login"),
    path("logout/", views.SiteLogoutView.as_view(), name="logout"),
    # 旧个人中心入口兼容到新后台；注册入口已彻底移除（访问将 404）。
    path(
        "profile/",
        RedirectView.as_view(pattern_name="manage:index", permanent=False),
        name="legacy_profile",
    ),
    path(
        "profile/edit/",
        RedirectView.as_view(pattern_name="manage:account", permanent=False),
        name="legacy_profile_edit",
    ),
    path(
        "password/",
        RedirectView.as_view(pattern_name="manage:account", permanent=False),
        name="legacy_password",
    ),
]