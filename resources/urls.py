from django.urls import path

from . import views

app_name = "resources"

urlpatterns = [
    path("", views.home, name="home"),
    path("list/", views.resource_list, name="list"),
    path("changelog/", views.changelog, name="changelog"),
    path("tags/", views.tag_cloud, name="tags"),
    path("c/<str:key>/", views.category_detail, name="category"),
    path("t/<str:key>/", views.tag_detail, name="tag"),
    path("r/<str:key>/", views.resource_detail, name="detail"),
    path("r/<int:pk>/favorite/", views.toggle_favorite, name="toggle_favorite"),
    path("r/<int:pk>/comment/", views.comment_create, name="comment_create"),
    path("download/<int:pk>/", views.download_local, name="download"),
]
