import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.forms import modelform_factory
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core.validators import human_size, validate_image_upload, validate_upload_size

from .models import Category, Comment, DownloadLink, Favorite, Resource, Tag, UpdateLog

User = get_user_model()


class SlugBehaviourTests(TestCase):
    """中文标题 slugify 后为空，URL 必须回退到数字 ID。"""

    def test_chinese_title_falls_back_to_pk_url(self):
        resource = Resource.objects.create(title="纯净解压工具")
        self.assertEqual(resource.slug, "")
        self.assertEqual(resource.get_absolute_url(), f"/r/{resource.pk}/")

    def test_ascii_title_gets_slug(self):
        resource = Resource.objects.create(title="7-Zip Portable")
        self.assertEqual(resource.slug, "7-zip-portable")
        self.assertEqual(resource.get_absolute_url(), "/r/7-zip-portable/")

    def test_duplicate_slug_is_suffixed(self):
        first = Resource.objects.create(title="Test Tool")
        second = Resource.objects.create(title="Test Tool")
        self.assertEqual(first.slug, "test-tool")
        self.assertEqual(second.slug, "test-tool-2")

    def test_category_and_tag_urls(self):
        category = Category.objects.create(name="系统工具")
        tag = Tag.objects.create(name="绿色版")
        self.assertEqual(category.get_absolute_url(), f"/c/{category.pk}/")
        self.assertEqual(tag.get_absolute_url(), f"/t/{tag.pk}/")


class DownloadLinkTests(TestCase):
    def setUp(self):
        self.resource = Resource.objects.create(title="测试资源")

    def test_external_link_requires_url(self):
        link = DownloadLink(resource=self.resource, label="网盘", link_type=DownloadLink.EXTERNAL)
        with self.assertRaises(ValidationError):
            link.full_clean()

    def test_local_link_requires_file(self):
        link = DownloadLink(resource=self.resource, label="本地", link_type=DownloadLink.LOCAL)
        with self.assertRaises(ValidationError):
            link.full_clean()

    def test_file_size_display(self):
        link = DownloadLink(resource=self.resource, file_size=12_345_678)
        self.assertEqual(link.size_display, "11.8 MB")

    def test_download_view_rejects_external_link(self):
        link = DownloadLink.objects.create(
            resource=self.resource,
            label="网盘",
            link_type=DownloadLink.EXTERNAL,
            url="https://example.com/file",
        )
        response = self.client.get(reverse("resources:download", args=[link.pk]))
        self.assertEqual(response.status_code, 404)


class UploadValidationTests(TestCase):
    """
    上传体积与类型校验。

    背景：MAX_UPLOAD_SIZE_MB 一度只是个「被读进 settings 但没人用」的环境变量，
    配了等于没配。这组测试把「真正生效」这件事锁住：
    既直接测校验器，也断言字段确实挂上了校验器、且走真实表单提交会被拦下。
    """

    def setUp(self):
        self.resource = Resource.objects.create(title="上传校验测试资源")

    # ---- 体积上限 ----

    def test_oversized_upload_is_rejected(self):
        with override_settings(MAX_UPLOAD_SIZE_MB=1):
            big = SimpleUploadedFile("big.bin", b"x" * (2 * 1024 * 1024))
            with self.assertRaises(ValidationError) as ctx:
                validate_upload_size(big)
            self.assertIn("超过上限", str(ctx.exception))
            self.assertIn("2.0 MB", str(ctx.exception))
            self.assertIn("1.0 MB", str(ctx.exception))

    def test_upload_within_limit_passes(self):
        with override_settings(MAX_UPLOAD_SIZE_MB=1):
            validate_upload_size(SimpleUploadedFile("small.bin", b"x" * (512 * 1024)))

    def test_limit_is_read_from_settings_at_call_time(self):
        """改配置应当立刻生效，而不是被 import 时的常量锁死。"""
        upload = SimpleUploadedFile("mid.bin", b"x" * (2 * 1024 * 1024))
        with override_settings(MAX_UPLOAD_SIZE_MB=1):
            with self.assertRaises(ValidationError):
                validate_upload_size(upload)
        with override_settings(MAX_UPLOAD_SIZE_MB=10):
            validate_upload_size(upload)

    def test_none_and_sizeless_values_are_ignored(self):
        validate_upload_size(None)
        validate_upload_size("not-a-file")

    # ---- 图片类型白名单 ----

    def test_image_extension_whitelist(self):
        for name in ("cover.png", "cover.JPG", "cover.webp", "cover.gif", "cover.bmp"):
            validate_image_upload(SimpleUploadedFile(name, b"data"))

    def test_non_image_rejected(self):
        for name in ("payload.exe", "script.php", "archive.zip", "note.txt"):
            with self.assertRaises(ValidationError):
                validate_image_upload(SimpleUploadedFile(name, b"data"))

    def test_svg_rejected_because_it_can_carry_scripts(self):
        """SVG 可内嵌 script，且 media 与站点同源，因此必须挡掉。"""
        with self.assertRaises(ValidationError):
            validate_image_upload(SimpleUploadedFile("evil.svg", b"<svg/>"))

    def test_image_upload_also_checks_size(self):
        with override_settings(MAX_UPLOAD_SIZE_MB=1):
            big = SimpleUploadedFile("big.png", b"x" * (2 * 1024 * 1024))
            with self.assertRaises(ValidationError):
                validate_image_upload(big)

    # ---- 校验器真的挂在字段上 ----

    def test_model_fields_actually_carry_the_validators(self):
        self.assertIn(
            validate_upload_size, DownloadLink._meta.get_field("file").validators
        )
        self.assertIn(
            validate_image_upload, Resource._meta.get_field("cover_image").validators
        )
        self.assertIn(
            validate_image_upload, User._meta.get_field("avatar").validators
        )

    # ---- 走真实表单提交（管理员上传走的就是这条路）----

    def test_upload_through_model_form_is_blocked(self):
        form_class = modelform_factory(
            DownloadLink, fields=["resource", "label", "link_type", "file"]
        )
        with override_settings(MAX_UPLOAD_SIZE_MB=1):
            form = form_class(
                data={
                    "resource": self.resource.pk,
                    "label": "本地直链",
                    "link_type": DownloadLink.LOCAL,
                },
                files={"file": SimpleUploadedFile("big.bin", b"x" * (2 * 1024 * 1024))},
            )
            self.assertFalse(form.is_valid())
            self.assertIn("file", form.errors)

    def test_avatar_form_rejects_svg(self):
        form_class = modelform_factory(User, fields=["avatar"])
        form = form_class(
            files={"avatar": SimpleUploadedFile("evil.svg", b"<svg/>")}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("avatar", form.errors)

    # ---- 体积格式化 ----

    def test_human_size(self):
        self.assertEqual(human_size(0), "0 B")
        self.assertEqual(human_size(512), "512 B")
        self.assertEqual(human_size(1024), "1.0 KB")
        self.assertEqual(human_size(12_345_678), "11.8 MB")
        self.assertEqual(human_size(3 * 1024**3), "3.0 GB")


class ResourceViewTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="系统工具")
        self.tag = Tag.objects.create(name="轻量")
        self.user = User.objects.create_user(
            username="tester", password="test12345", email="t@example.com"
        )

    def _make_resource(self, index, **kwargs):
        resource = Resource.objects.create(
            title=f"资源 {index}",
            category=self.category,
            summary="摘要",
            views=index,
            **kwargs,
        )
        resource.tags.add(self.tag)
        DownloadLink.objects.create(
            resource=resource,
            label="百度网盘",
            link_type=DownloadLink.EXTERNAL,
            url="https://example.com/demo",
            extract_code="ab12",
        )
        UpdateLog.objects.create(resource=resource, version="1.0", content="首次发布")
        return resource

    def test_home_renders(self):
        self._make_resource(1, is_pinned=True)
        response = self.client.get(reverse("resources:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "资源 1")

    def test_list_renders_and_filters(self):
        self._make_resource(1)
        self._make_resource(2, is_published=False)

        response = self.client.get(reverse("resources:list"))
        self.assertContains(response, "资源 1")
        self.assertNotContains(response, "资源 2")

        response = self.client.get(reverse("resources:list"), {"category": self.category.slug or self.category.pk})
        self.assertContains(response, "资源 1")

        response = self.client.get(reverse("resources:list"), {"tag": self.tag.slug or self.tag.pk})
        self.assertContains(response, "资源 1")

        response = self.client.get(reverse("resources:list"), {"q": "资源"})
        self.assertContains(response, "资源 1")

        response = self.client.get(reverse("resources:list"), {"q": "不存在的词"})
        self.assertNotContains(response, "资源 1")

    def test_unpublished_is_hidden_from_detail(self):
        resource = self._make_resource(1, is_published=False)
        response = self.client.get(resource.get_absolute_url())
        self.assertEqual(response.status_code, 404)

    def test_detail_accessible_by_slug_and_pk(self):
        resource = Resource.objects.create(title="Portable App", category=self.category)
        self.assertEqual(self.client.get("/r/portable-app/").status_code, 200)
        self.assertEqual(self.client.get(f"/r/{resource.pk}/").status_code, 200)

    def test_detail_bumps_views(self):
        resource = self._make_resource(1)
        self.client.get(resource.get_absolute_url())
        resource.refresh_from_db()
        self.assertEqual(resource.views, 2)  # 初始 views=1，访问后 +1

    def test_list_query_count_does_not_grow_with_rows(self):
        """
        核心断言：列表页用 prefetch_related 预取标签，
        查询次数必须与资源数量无关（不随行数增长 = 没有 N+1）。
        """
        for index in range(1, 3):
            self._make_resource(index)
        with CaptureQueriesContext(connection) as small:
            self.client.get(reverse("resources:list"))

        for index in range(3, 10):
            self._make_resource(index)
        with CaptureQueriesContext(connection) as large:
            self.client.get(reverse("resources:list"))

        self.assertEqual(
            len(small),
            len(large),
            f"查询次数随资源数量增长了：2 条时 {len(small)} 次，8 条时 {len(large)} 次，存在 N+1",
        )
        self.assertLessEqual(len(large), 20, "列表页查询次数过多，检查是否漏了预取")

    def test_home_query_count_does_not_grow_with_rows(self):
        """
        首页同理。

        注意：两种规模必须都处于「有置顶、也有非置顶资源」的状态，
        否则会走到不同的模板分支（空态 vs 列表），比较就失去意义。
        """
        self._make_resource(0, is_pinned=True)
        for index in range(1, 3):
            self._make_resource(index)
        with CaptureQueriesContext(connection) as small:
            self.client.get(reverse("resources:home"))

        for index in range(3, 10):
            self._make_resource(index)
        with CaptureQueriesContext(connection) as large:
            self.client.get(reverse("resources:home"))

        self.assertEqual(
            len(small),
            len(large),
            f"首页查询次数增长了：3 条时 {len(small)} 次，9 条时 {len(large)} 次，存在 N+1",
        )
        self.assertLessEqual(len(large), 20, "首页查询次数过多，检查是否漏了预取")

    def test_tag_prefetch_actually_avoids_extra_queries(self):
        """标签是多对多，只有 prefetch_related 能避免 N+1。"""
        for index in range(1, 6):
            self._make_resource(index)

        with CaptureQueriesContext(connection) as ctx:
            self.client.get(reverse("resources:list"))

        tag_queries = [
            query["sql"] for query in ctx.captured_queries if "resources_tag" in query["sql"]
        ]
        # 标签查询只应有一次（预取），而不是每个资源一次
        self.assertLessEqual(
            len(tag_queries), 2, f"标签查询了 {len(tag_queries)} 次，存在 N+1"
        )


class CommentAndFavoriteTests(TestCase):
    def setUp(self):
        self.resource = Resource.objects.create(title="可评论资源")
        self.user = User.objects.create_user(
            username="tester", password="test12345", email="t@example.com"
        )

    def test_comment_requires_login(self):
        response = self.client.post(
            reverse("resources:comment_create", args=[self.resource.pk]),
            {"content": "好用"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])
        self.assertEqual(Comment.objects.count(), 0)

    def test_logged_in_user_can_comment(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("resources:comment_create", args=[self.resource.pk]),
            {"content": "确实好用"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Comment.objects.count(), 1)

    def test_too_short_comment_rejected(self):
        self.client.force_login(self.user)
        self.client.post(
            reverse("resources:comment_create", args=[self.resource.pk]), {"content": "好"}
        )
        self.assertEqual(Comment.objects.count(), 0)

    def test_favorite_toggle(self):
        self.client.force_login(self.user)
        url = reverse("resources:toggle_favorite", args=[self.resource.pk])

        response = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertJSONEqual(response.content, {"ok": True, "favorited": True, "total": 1, "message": "已加入收藏"})
        self.assertEqual(Favorite.objects.count(), 1)

        response = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertTrue(response.json()["favorited"] is False)
        self.assertEqual(Favorite.objects.count(), 0)

    def test_guest_cannot_favorite(self):
        url = reverse("resources:toggle_favorite", args=[self.resource.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Favorite.objects.count(), 0)

    def test_hidden_comment_not_rendered(self):
        Comment.objects.create(
            resource=self.resource, user=self.user, content="被隐藏的评论", is_active=False
        )
        response = self.client.get(self.resource.get_absolute_url())
        self.assertNotContains(response, "被隐藏的评论")


class UpdatedLogTests(TestCase):
    def test_lines_property_strips_bullets(self):
        resource = Resource.objects.create(title="日志测试")
        log = UpdateLog.objects.create(
            resource=resource, version="1.1", content="- 修复 A\n2. 优化 B\n\n- 新增 C"
        )
        self.assertEqual(log.lines, ["修复 A", "2. 优化 B", "新增 C"])

    def test_changelog_page(self):
        resource = Resource.objects.create(title="日志资源")
        UpdateLog.objects.create(resource=resource, version="1.0", content="首次发布")
        response = self.client.get(reverse("resources:changelog"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "首次发布")


class LocalDownloadTests(TestCase):
    """
    本地文件下载测试。

    用临时 MEDIA_ROOT，避免测试上传的文件污染项目真实的 media/ 目录。
    """

    @classmethod
    def setUpClass(cls):
        cls._media_dir = tempfile.mkdtemp(prefix="rh-test-media-")
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_dir)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        shutil.rmtree(cls._media_dir, ignore_errors=True)

    def setUp(self):
        self.resource = Resource.objects.create(title="本地文件资源")

    def test_local_download_streams_file(self):
        link = DownloadLink.objects.create(
            resource=self.resource,
            label="本地下载",
            link_type=DownloadLink.LOCAL,
            file=SimpleUploadedFile("demo.txt", b"hello resource-hub"),
        )
        response = self.client.get(reverse("resources:download", args=[link.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Disposition"][:10], "attachment")
        link.refresh_from_db()
        self.assertEqual(link.downloads, 1)

    def test_disabled_link_returns_404(self):
        link = DownloadLink.objects.create(
            resource=self.resource,
            label="本地下载",
            link_type=DownloadLink.LOCAL,
            file=SimpleUploadedFile("demo.txt", b"x"),
            is_active=False,
        )
        response = self.client.get(reverse("resources:download", args=[link.pk]))
        self.assertEqual(response.status_code, 404)
