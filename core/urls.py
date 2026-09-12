from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("about/", views.about, name="about"),
    path("healthz", views.healthz, name="healthz"),
    path("robots.txt", views.robots_txt, name="robots"),
]
