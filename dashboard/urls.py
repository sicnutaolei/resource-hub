from django.urls import path

from . import views

app_name = "manage"

urlpatterns = [
    path("", views.index, name="index"),
    path("software/", views.software_list, name="software_list"),
    path("software/new/", views.software_create, name="software_create"),
    path("software/<int:pk>/edit/", views.software_edit, name="software_edit"),
    path("software/<int:pk>/delete/", views.software_delete, name="software_delete"),
    path("libraries/", views.library_list, name="library_list"),
    path("libraries/new/", views.library_create, name="library_create"),
    path("libraries/<int:pk>/edit/", views.library_edit, name="library_edit"),
    path("libraries/<int:pk>/delete/", views.library_delete, name="library_delete"),
    path("tags/", views.tag_list, name="tag_list"),
    path("tags/new/", views.tag_create, name="tag_create"),
    path("tags/<int:pk>/edit/", views.tag_edit, name="tag_edit"),
    path("tags/<int:pk>/delete/", views.tag_delete, name="tag_delete"),
    path("settings/", views.site_settings, name="settings"),
    path("account/", views.account, name="account"),
]