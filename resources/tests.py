import shutil
import tempfile
from datetime import timedelta
from io import BytesIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms import modelform_factory
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from core.models import SiteSetting
from core.validators import human_size, validate_image_upload, validate_upload_size

from .models import Category, DownloadLink, Resource, Tag, UpdateLog

User = get_user_model()


def make_resource(title, *, public=True, category=None, tags=None, **kwargs):
    resource = Resource.objects.create(
        title=title, is_public=public, category=category, **kwargs
    )
    if tags:
        resource.tags.set(tags)
    return resource


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

    def test_tag_url_points_to_home_filter(self):
        tag = Tag.objects.create(name="绿色版")
        self.assertEqual(tag.get_absolute_url(), f"/?tag={tag.pk}")

    def test_is_public_defaults_true(self):
        resource = Resource.objects.create(title="默认公开")
        self.assertTrue(resource.is_public)


class DownloadLinkTests(TestCase):
    def setUp(self):
        self.resource = make_resource("测试软件")

    def test_external_link_requires_url(self):
        link = DownloadLink(
            resource=self.resource, label="网盘", link_type=DownloadLink.EXTERNAL
        )
        with self.assertRaises(ValidationError):
            link.full_clean()

    def test_local_link_requires_file(self):
        link = DownloadLink(
            resource=self.resource, label="本地", link_type=DownloadLink.LOCAL
        )
        with self.assertRaises(ValidationError):
            link.full_clean()

    def test_file_size_display(self):
        link = DownloadLink(resource=self.resource, file_size=12_345_678)
        self.assertEqual(link.size_display, "11.8 MB")


class UploadValidationTests(TestCase):
    """上传体积与类型校验。"""

    def setUp(self):
        self.resource = Resource.objects.create(title="上传校验测试资源")

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
        upload = SimpleUploadedFile("mid.bin", b"x" * (2 * 1024 * 1024))
        with override_settings(MAX_UPLOAD_SIZE_MB=1):
            with self.assertRaises(ValidationError):
                validate_upload_size(upload)
        with override_settings(MAX_UPLOAD_SIZE_MB=10):
            validate_upload_size(upload)

    def test_none_and_sizeless_values_are_ignored(self):
        validate_upload_size(None)
        validate_upload_size("not-a-file")

    def test_image_extension_whitelist(self):
        for name in ("cover.png", "cover.JPG", "cover.webp", "cover.gif", "cover.bmp"):
            validate_image_upload(SimpleUploadedFile(name, b"data"))

    def test_non_image_rejected(self):
        for name in ("payload.exe", "script.php", "archive.zip", "note.txt"):
            with self.assertRaises(ValidationError):
                validate_image_upload(SimpleUploadedFile(name, b"data"))

    def test_svg_rejected_because_it_can_carry_scripts(self):
        with self.assertRaises(ValidationError):
            validate_image_upload(SimpleUploadedFile("evil.svg", b"<svg/>"))

    def test_image_upload_also_checks_size(self):
        with override_settings(MAX_UPLOAD_SIZE_MB=1):
            big = SimpleUploadedFile("big.png", b"x" * (2 * 1024 * 1024))
            with self.assertRaises(ValidationError):
                validate_image_upload(big)

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
        form = form_class(files={"avatar": SimpleUploadedFile("evil.svg", b"<svg/>")})
        self.assertFalse(form.is_valid())
        self.assertIn("avatar", form.errors)

    def test_human_size(self):
        self.assertEqual(human_size(0), "0 B")
        self.assertEqual(human_size(512), "512 B")
        self.assertEqual(human_size(1024), "1.0 KB")
        self.assertEqual(human_size(12_345_678), "11.8 MB")
        self.assertEqual(human_size(3 * 1024**3), "3.0 GB")


class VisibilityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.staff = User.objects.create_superuser(
            username="admin", email="a@example.com", password="Str0ngPass!2026"
        )
        self.public_tag = Tag.objects.create(name="公开标签")
        self.private_tag = Tag.objects.create(name="私有标签")
        self.public = make_resource("公开播放器", tags=[self.public_tag])
        self.private = make_resource(
            "私有播放器", public=False, tags=[self.private_tag]
        )
        self.private_link = DownloadLink.objects.create(
            resource=self.private,
            label="私有外链",
            link_type=DownloadLink.EXTERNAL,
            url="https://example.com/private",
        )

    def test_anonymous_home_only_public(self):
        response = self.client.get(reverse("resources:home"))
        self.assertContains(response, self.public.title)
        self.assertNotContains(response, self.private.title)

    def test_staff_home_includes_private_with_badge(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("resources:home"))
        self.assertContains(response, self.public.title)
        self.assertContains(response, self.private.title)
        self.assertContains(response, "非公开")

    def test_anonymous_detail_gate(self):
        self.assertEqual(
            self.client.get(self.public.get_absolute_url()).status_code, 200
        )
        self.assertEqual(
            self.client.get(self.private.get_absolute_url()).status_code, 404
        )

    def test_staff_can_view_private_detail(self):
        self.client.force_login(self.staff)
        self.assertEqual(
            self.client.get(self.private.get_absolute_url()).status_code, 200
        )

    def test_anonymous_search_does_not_leak_private(self):
        response = self.client.get(reverse("resources:home"), {"q": "播放器"})
        self.assertContains(response, self.public.title)
        self.assertNotContains(response, self.private.title)

    def test_anonymous_tag_filter_does_not_leak_private(self):
        response = self.client.get(
            reverse("resources:home"), {"tag": self.private_tag.pk}
        )
        self.assertEqual(response.context["page_obj"].paginator.count, 0)
        self.assertNotContains(response, self.private.title)

    def test_private_download_gate(self):
        url = reverse("resources:download", args=[self.private_link.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.staff)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://example.com/private")


class HomeQueryTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_default_page_size_is_24(self):
        for index in range(25):
            make_resource(f"软件 {index:02d}")
        response = self.client.get(reverse("resources:home"))
        self.assertEqual(response.context["page_size"], 24)
        self.assertEqual(len(response.context["page_obj"].object_list), 24)
        self.assertEqual(response.context["page_obj"].paginator.num_pages, 2)

    def test_page_size_20_page_two(self):
        for index in range(25):
            make_resource(f"软件 {index:02d}")
        response = self.client.get(
            reverse("resources:home"), {"size": 20, "page": 2}
        )
        self.assertEqual(len(response.context["page_obj"].object_list), 5)

    def test_invalid_size_falls_back_to_default(self):
        response = self.client.get(reverse("resources:home"), {"size": 999})
        self.assertEqual(response.context["page_size"], settings.PAGE_SIZE)

    def test_order_by_updated_desc(self):
        older = make_resource("较早更新")
        newer = make_resource("较新更新")
        Resource.objects.filter(pk=older.pk).update(
            updated_at=timezone.now() - timedelta(days=2)
        )
        Resource.objects.filter(pk=newer.pk).update(updated_at=timezone.now())
        response = self.client.get(reverse("resources:home"))
        titles = [item.title for item in response.context["page_obj"].object_list]
        self.assertEqual(titles, ["较新更新", "较早更新"])

    def test_search_matches_title_summary_description_and_tag(self):
        tag = Tag.objects.create(name="独特标签词")
        make_resource("独特标题词", summary="普通简介")
        make_resource("普通标题一", summary="独特摘要词")
        make_resource("普通标题二", description="正文里有独特描述词")
        tagged = make_resource("普通标题三")
        tagged.tags.set([tag])

        for query, expected in [
            ("独特标题词", "独特标题词"),
            ("独特摘要词", "普通标题一"),
            ("独特描述词", "普通标题二"),
            ("独特标签词", "普通标题三"),
        ]:
            response = self.client.get(reverse("resources:home"), {"q": query})
            titles = [item.title for item in response.context["page_obj"].object_list]
            self.assertIn(expected, titles)

    def test_search_and_tag_and_page_size_combine(self):
        keep_tag = Tag.objects.create(name="组合标签")
        other_tag = Tag.objects.create(name="另一个标签")
        for index in range(22):
            item = make_resource(f"组合软件 {index:02d}", tags=[keep_tag])
        make_resource("组合软件 排除项", tags=[other_tag])

        response = self.client.get(
            reverse("resources:home"),
            {"q": "组合软件", "tag": keep_tag.pk, "size": 20},
        )
        self.assertEqual(response.context["page_obj"].paginator.count, 22)
        self.assertEqual(len(response.context["page_obj"].object_list), 20)
        self.assertEqual(response.context["page_obj"].paginator.num_pages, 2)

    def test_home_does_not_show_recent_update_logs(self):
        resource = make_resource("日志软件")
        UpdateLog.objects.create(
            resource=resource, version="1.0", content="首页不应出现的日志内容"
        )
        response = self.client.get(reverse("resources:home"))
        self.assertNotContains(response, "首页不应出现的日志内容")

    def test_page_size_choices_are_rendered(self):
        response = self.client.get(reverse("resources:home"))
        self.assertContains(response, "每页 20")
        self.assertContains(response, "每页 24")
        self.assertContains(response, "每页 30")

    def test_configured_default_page_size_is_one_of_allowed_values(self):
        self.assertIn(settings.PAGE_SIZE, settings.PAGE_SIZE_CHOICES)


class SloganAndSiteSettingTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_slogan_change_is_visible_on_home(self):
        SiteSetting.set("homepage_slogan", "新的首页口号")
        response = self.client.get(reverse("resources:home"))
        self.assertContains(response, "新的首页口号")

    def test_slogan_is_escaped(self):
        SiteSetting.set("homepage_slogan", "<script>alert(1)</script>")
        response = self.client.get(reverse("resources:home"))
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")

    def test_site_setting_cache_is_invalidated_on_set(self):
        SiteSetting.set("site_name", "缓存站")
        self.assertEqual(SiteSetting.get("site_name"), "缓存站")
        SiteSetting.set("site_name", "新名字")
        self.assertEqual(SiteSetting.get("site_name"), "新名字")


class ThumbnailTests(TestCase):
    def setUp(self):
        cache.clear()
        self.tmpdir = tempfile.mkdtemp(prefix="rh-media-")
        self.override = override_settings(MEDIA_ROOT=self.tmpdir)
        self.override.enable()
        buffer = BytesIO()
        Image.new("RGB", (800, 500), (160, 190, 240)).save(buffer, format="PNG")
        buffer.seek(0)
        self.png = buffer.getvalue()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_thumbnail_is_generated_and_used_by_card(self):
        resource = Resource.objects.create(
            title="带图软件",
            cover_image=SimpleUploadedFile(
                "cover.png", self.png, content_type="image/png"
            ),
        )
        self.assertIn("-640x400.jpg", resource.thumbnail_url)
        self.assertTrue(resource.thumbnail_url.startswith(settings.MEDIA_URL))

        response = self.client.get(reverse("resources:home"))
        self.assertContains(response, 'loading="lazy"')
        self.assertContains(response, 'width="640"')
        self.assertContains(response, 'height="400"')


class DownloadGateTests(TestCase):
    def setUp(self):
        cache.clear()
        self.staff = User.objects.create_superuser(
            username="admin", email="a@example.com", password="Str0ngPass!2026"
        )
        self.public = make_resource("公开软件")
        self.private = make_resource("私有软件", public=False)

    def test_public_external_link_redirects_and_counts(self):
        link = DownloadLink.objects.create(
            resource=self.public,
            label="外链",
            link_type=DownloadLink.EXTERNAL,
            url="https://example.com/file",
        )
        response = self.client.get(reverse("resources:download", args=[link.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://example.com/file")
        link.refresh_from_db()
        self.assertEqual(link.downloads, 1)

    def test_inactive_link_returns_404(self):
        link = DownloadLink.objects.create(
            resource=self.public,
            label="外链",
            link_type=DownloadLink.EXTERNAL,
            url="https://example.com/file",
            is_active=False,
        )
        response = self.client.get(reverse("resources:download", args=[link.pk]))
        self.assertEqual(response.status_code, 404)

    def test_local_link_with_missing_file_returns_404(self):
        link = DownloadLink.objects.create(
            resource=self.public,
            label="本地",
            link_type=DownloadLink.LOCAL,
            file="files/missing.bin",
            file_size=10,
        )
        response = self.client.get(reverse("resources:download", args=[link.pk]))
        self.assertEqual(response.status_code, 404)


class LegacyRedirectTests(TestCase):
    def test_old_list_keeps_query(self):
        response = self.client.get("/list/?q=test&page=2")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/?q=test&page=2")

    def test_old_tag_redirects_to_home_filter(self):
        tag = Tag.objects.create(name="旧标签")
        response = self.client.get(f"/t/{tag.pk}/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"/?tag={tag.pk}")

    def test_changelog_and_tags_redirect_home(self):
        self.assertEqual(self.client.get("/changelog/")["Location"], "/")
        self.assertEqual(self.client.get("/tags/")["Location"], "/")
        self.assertEqual(self.client.get("/c/1/")["Location"], "/")


class IndexTests(TestCase):
    def test_resource_indexes_are_defined(self):
        names = {index.name for index in Resource._meta.indexes}
        self.assertIn("resources_public_updated_idx", names)
        self.assertIn("resources_title_idx", names)