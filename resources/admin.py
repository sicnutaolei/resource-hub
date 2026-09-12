from django.contrib import admin, messages
from django.db.models import Count
from django.utils.html import format_html

from .models import (
    Category,
    Comment,
    DownloadLink,
    Favorite,
    Resource,
    Tag,
    UpdateLog,
)
from .utils import BROKEN, STATUS_LABEL, check_links


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "order", "resource_count", "created_at")
    list_editable = ("order",)
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(_total=Count("resources", distinct=True))
        )

    @admin.display(description="资源数", ordering="_total")
    def resource_count(self, obj):
        return obj._total


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "resource_count", "created_at")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(_total=Count("resources", distinct=True))
        )

    @admin.display(description="资源数", ordering="_total")
    def resource_count(self, obj):
        return obj._total


class DownloadLinkInline(admin.TabularInline):
    model = DownloadLink
    extra = 1
    fields = (
        "label",
        "link_type",
        "file",
        "url",
        "extract_code",
        "order",
        "is_active",
        "size_display",
        "is_broken",
        "last_checked_at",
        "downloads",
    )
    readonly_fields = ("size_display", "is_broken", "last_checked_at", "downloads")
    classes = ("collapse",)

    @admin.display(description="文件大小")
    def size_display(self, obj):
        return obj.size_display or "—"


class UpdateLogInline(admin.TabularInline):
    model = UpdateLog
    extra = 1
    fields = ("version", "content", "created_at")
    ordering = ("-created_at",)


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "version",
        "link_summary",
        "comment_count",
        "views",
        "is_pinned",
        "is_published",
        "updated_at",
    )
    list_editable = ("is_pinned", "is_published")
    list_filter = ("is_published", "is_pinned", "category", "tags")
    search_fields = ("title", "summary", "description", "version", "tags__name")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("tags",)
    inlines = (DownloadLinkInline, UpdateLogInline)
    date_hierarchy = "updated_at"
    actions = (
        "action_publish",
        "action_unpublish",
        "action_pin",
        "action_unpin",
        "action_check_links",
    )
    fieldsets = (
        (
            "基本信息",
            {
                "fields": (
                    "title",
                    "slug",
                    "category",
                    "tags",
                    "version",
                    "summary",
                )
            },
        ),
        ("内容", {"fields": ("description", "cover_image")}),
        ("状态", {"fields": ("is_published", "is_pinned", "views")}),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("category")
            .prefetch_related("tags")
            .annotate(
                _comments=Count("comments", distinct=True),
                _links=Count("links", distinct=True),
            )
        )

    @admin.display(description="下载入口", ordering="_links")
    def link_summary(self, obj):
        return f"{obj._links} 个"

    @admin.display(description="评论", ordering="_comments")
    def comment_count(self, obj):
        return obj._comments

    @admin.action(description="发布选中的资源")
    def action_publish(self, request, queryset):
        updated = queryset.update(is_published=True)
        self.message_user(request, f"已发布 {updated} 个资源。", messages.SUCCESS)

    @admin.action(description="下架选中的资源")
    def action_unpublish(self, request, queryset):
        updated = queryset.update(is_published=False)
        self.message_user(request, f"已下架 {updated} 个资源。", messages.WARNING)

    @admin.action(description="首页置顶")
    def action_pin(self, request, queryset):
        updated = queryset.update(is_pinned=True)
        self.message_user(request, f"已置顶 {updated} 个资源。", messages.SUCCESS)

    @admin.action(description="取消置顶")
    def action_unpin(self, request, queryset):
        updated = queryset.update(is_pinned=False)
        self.message_user(request, f"已取消置顶 {updated} 个资源。", messages.SUCCESS)

    @admin.action(description="检查选中资源的外链状态")
    def action_check_links(self, request, queryset):
        links = list(DownloadLink.objects.filter(resource__in=queryset).select_related("resource"))
        if not links:
            self.message_user(request, "选中的资源没有下载链接。", messages.WARNING)
            return

        results = check_links(links, apply=True)
        broken = [item for item in results if item["status"] == BROKEN]

        self.message_user(
            request,
            f"已检测 {len(results)} 个下载入口，其中 {len(broken)} 个疑似失效。",
            messages.WARNING if broken else messages.SUCCESS,
        )
        for item in broken[:10]:
            self.message_user(
                request,
                f"疑似失效：{item['resource']} · {item['label']} → {item['detail']}",
                messages.WARNING,
            )


@admin.register(DownloadLink)
class DownloadLinkAdmin(admin.ModelAdmin):
    list_display = (
        "resource",
        "label",
        "link_type",
        "target",
        "is_active",
        "broken_badge",
        "downloads",
        "last_checked_at",
    )
    list_filter = ("link_type", "is_active", "is_broken")
    search_fields = ("resource__title", "label", "url")
    autocomplete_fields = ("resource",)
    actions = ("action_check_selected", "action_mark_available")

    @admin.display(description="指向")
    def target(self, obj):
        if obj.link_type == DownloadLink.LOCAL:
            return obj.file.name.split("/")[-1] if obj.file else "—"
        return format_html('<a href="{}" target="_blank" rel="noopener">外链 ↗</a>', obj.url)

    @admin.display(description="外链状态", ordering="is_broken")
    def broken_badge(self, obj):
        if obj.link_type == DownloadLink.LOCAL:
            return "—"
        if obj.is_broken:
            return format_html('<b style="color:#c0392b">{}</b>', "疑似失效")
        return "正常"

    @admin.action(description="检查选中的外链状态")
    def action_check_selected(self, request, queryset):
        results = check_links(list(queryset.select_related("resource")), apply=True)
        broken = [item for item in results if item["status"] == BROKEN]
        detail = "、".join(
            f"{item['label']}({STATUS_LABEL[item['status']]})" for item in results[:8]
        )
        self.message_user(
            request,
            f"检测完成：{len(results)} 个，疑似失效 {len(broken)} 个。{detail}",
            messages.WARNING if broken else messages.SUCCESS,
        )

    @admin.action(description="把选中项标记为正常")
    def action_mark_available(self, request, queryset):
        updated = queryset.update(is_broken=False)
        self.message_user(request, f"已标记 {updated} 个链接为正常。", messages.SUCCESS)


@admin.register(UpdateLog)
class UpdateLogAdmin(admin.ModelAdmin):
    list_display = ("resource", "version", "short_content", "created_at")
    list_filter = ("created_at", "resource__category")
    search_fields = ("resource__title", "version", "content")
    autocomplete_fields = ("resource",)
    date_hierarchy = "created_at"

    @admin.display(description="内容")
    def short_content(self, obj):
        text = " ".join(obj.content.split())
        return text[:50] + ("…" if len(text) > 50 else "")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("resource", "user", "short_content", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("resource__title", "user__username", "content")
    autocomplete_fields = ("resource", "user")
    actions = ("action_show", "action_hide")
    date_hierarchy = "created_at"

    @admin.display(description="内容")
    def short_content(self, obj):
        return obj.content[:50] + ("…" if len(obj.content) > 50 else "")

    @admin.action(description="显示选中的评论")
    def action_show(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"已显示 {updated} 条评论。", messages.SUCCESS)

    @admin.action(description="隐藏选中的评论")
    def action_hide(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"已隐藏 {updated} 条评论。", messages.WARNING)


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("user", "resource", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "resource__title")
    autocomplete_fields = ("user", "resource")
    date_hierarchy = "created_at"
