from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db.models import Count

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "nickname",
        "email",
        "favorite_count",
        "comment_count",
        "is_staff",
        "is_active",
        "date_joined",
    )
    list_filter = ("is_staff", "is_superuser", "is_active")
    search_fields = ("username", "nickname", "email")
    ordering = ("-date_joined",)
    readonly_fields = ("date_joined", "last_login")

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("资料", {"fields": ("nickname", "email", "bio", "avatar")}),
        (
            "权限",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("时间", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "nickname",
                    "email",
                    "password1",
                    "password2",
                    "is_staff",
                ),
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(_favorites=Count("favorites", distinct=True))
            .annotate(_comments=Count("comments", distinct=True))
        )

    @admin.display(description="收藏数", ordering="_favorites")
    def favorite_count(self, obj):
        return obj._favorites

    @admin.display(description="评论数", ordering="_comments")
    def comment_count(self, obj):
        return obj._comments
