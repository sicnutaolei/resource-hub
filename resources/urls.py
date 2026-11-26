from django.urls import path

from . import views

app_name = "resources"

urlpatterns = [
    path("", views.home, name="home"),
    path("r/<str:key>/", views.resource_detail, name="detail"),
    path("download/<int:pk>/", views.download, name="download"),
    # 旧站链接兼容：统一回到新的首页/详情
    path("list/", views.legacy_list, name="legacy_list"),
    path("changelog/", views.legacy_home, name="legacy_changelog"),
    path("tags/", views.legacy_home, name="legacy_tags"),
    path("c/<str:key>/", views.legacy_category, name="legacy_category"),
    path("t/<str:key>/", views.legacy_tag, name="legacy_tag"),
]