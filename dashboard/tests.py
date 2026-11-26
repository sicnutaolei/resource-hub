from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from core.models import SiteSetting
from resources.models import Category, DownloadLink, Resource, Tag

from .forms import SoftwareForm

User = get_user_model()


def make_resource(title, *, public=True, category=None, tags=None):
    resource = Resource.objects.create(
        title=title, is_public=public, category=category
    )
    if tags:
        resource.tags.set(tags)
    return resource


class DashboardAccessTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser(
            username="admin", email="a@example.com", password="Str0ngPass!2026"
        )
        self.normal = User.objects.create_user(
            username="normal", password="Str0ngPass!2026"
        )

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse("manage:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_staff_can_open_dashboard(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("manage:index")).status_code, 200)

    def test_non_staff_is_logged_out(self):
        self.client.force_login(self.normal)
        response = self.client.get(reverse("manage:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_permission_and_group_routes_removed(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get("/admin/auth/group/").status_code, 404)
        self.assertEqual(self.client.get("/admin/auth/user/").status_code, 404)
        self.assertEqual(self.client.get("/manage/users/").status_code, 404)
        self.assertEqual(self.client.get("/manage/groups/").status_code, 404)

    def test_old_admin_index_redirects(self):
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/manage/")


class SoftwareFormTests(TestCase):
    def test_new_form_is_public_by_default(self):
        form = SoftwareForm()
        self.assertTrue(form.fields["is_public"].initial)

    def test_tags_text_is_split_and_created(self):
        form = SoftwareForm(
            data={
                "title": "标签测试",
                "summary": "",
                "description": "",
                "version": "",
                "category": "",
                "tags_text": "开源, 轻量，免费",
                "is_public": "on",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        resource = form.save()
        self.assertEqual(
            sorted(resource.tags.values_list("name", flat=True)),
            sorted(["开源", "轻量", "免费"]),
        )

    def test_more_than_12_tags_rejected(self):
        form = SoftwareForm(
            data={
                "title": "标签太多",
                "tags_text": ", ".join(f"标签{i}" for i in range(13)),
                "is_public": "on",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("tags_text", form.errors)


class SoftwareManagementTests(TestCase):
    def setUp(self):
        cache.clear()
        self.staff = User.objects.create_superuser(
            username="admin", email="a@example.com", password="Str0ngPass!2026"
        )
        self.client.force_login(self.staff)
        self.library_a = Category.objects.create(name="资源库 A", order=1)
        self.library_b = Category.objects.create(name="资源库 B", order=2)
        self.tag = Tag.objects.create(name="工具")
        self.public = make_resource(
            "公开 Alpha", category=self.library_a, tags=[self.tag]
        )
        self.private = make_resource(
            "私有 Alpha", public=False, category=self.library_b
        )
        self.other = make_resource("公开 Beta", category=self.library_a)

    def _base_post(self, title, **extra):
        data = {
            "title": title,
            "summary": "",
            "description": "",
            "version": "",
            "category": "",
            "tags_text": "",
            "is_public": "on",
            "links-TOTAL_FORMS": "0",
            "links-INITIAL_FORMS": "0",
            "links-MIN_NUM_FORMS": "0",
            "links-MAX_NUM_FORMS": "1000",
            "logs-TOTAL_FORMS": "0",
            "logs-INITIAL_FORMS": "0",
            "logs-MIN_NUM_FORMS": "0",
            "logs-MAX_NUM_FORMS": "1000",
        }
        data.update(extra)
        return data

    def test_list_search_visibility_and_library_combine(self):
        response = self.client.get(
            reverse("manage:software_list"),
            {
                "q": "Alpha",
                "visibility": "public",
                "library": self.library_a.pk,
            },
        )
        self.assertEqual(response.status_code, 200)
        titles = [item.title for item in response.context["page_obj"].object_list]
        self.assertEqual(titles, ["公开 Alpha"])

    def test_create_public_software(self):
        response = self.client.post(
            reverse("manage:software_create"),
            self._base_post("新公开软件", is_public="on", tags_text="开源, 新标签"),
        )
        self.assertEqual(response.status_code, 302)
        resource = Resource.objects.get(title="新公开软件")
        self.assertTrue(resource.is_public)
        self.assertEqual(resource.tags.count(), 2)

    def test_create_private_software_when_checkbox_off(self):
        data = self._base_post("新私有软件")
        data.pop("is_public")
        response = self.client.post(reverse("manage:software_create"), data)
        self.assertEqual(response.status_code, 302)
        resource = Resource.objects.get(title="新私有软件")
        self.assertFalse(resource.is_public)

    def test_create_software_with_download_link_formset(self):
        data = self._base_post(
            "带链接软件",
            **{
                "links-TOTAL_FORMS": "1",
                "links-0-id": "",
                "links-0-label": "外链下载",
                "links-0-link_type": "external",
                "links-0-url": "https://example.com/file",
                "links-0-extract_code": "abcd",
                "links-0-order": "10",
                "links-0-is_active": "on",
            },
        )
        response = self.client.post(reverse("manage:software_create"), data)
        self.assertEqual(response.status_code, 302)
        resource = Resource.objects.get(title="带链接软件")
        link = resource.links.get()
        self.assertEqual(link.url, "https://example.com/file")
        self.assertEqual(link.extract_code, "abcd")

    def test_edit_toggles_private(self):
        data = self._base_post("公开 Alpha")
        data.pop("is_public")
        response = self.client.post(
            reverse("manage:software_edit", args=[self.public.pk]), data
        )
        self.assertEqual(response.status_code, 302)
        self.public.refresh_from_db()
        self.assertFalse(self.public.is_public)

    def test_delete_software(self):
        response = self.client.post(
            reverse("manage:software_delete", args=[self.other.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Resource.objects.filter(pk=self.other.pk).exists())

    def test_library_with_resources_cannot_be_deleted(self):
        response = self.client.post(
            reverse("manage:library_delete", args=[self.library_a.pk]), follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Category.objects.filter(pk=self.library_a.pk).exists())

    def test_empty_library_can_be_deleted(self):
        empty = Category.objects.create(name="空资源库")
        response = self.client.post(
            reverse("manage:library_delete", args=[empty.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Category.objects.filter(pk=empty.pk).exists())

    def test_tag_in_use_cannot_be_deleted(self):
        response = self.client.post(
            reverse("manage:tag_delete", args=[self.tag.pk]), follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Tag.objects.filter(pk=self.tag.pk).exists())

    def test_settings_update_takes_effect_on_home(self):
        response = self.client.post(
            reverse("manage:settings"),
            {"site_name": "新站名", "homepage_slogan": "新首页口号"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SiteSetting.get("site_name"), "新站名")
        self.assertEqual(SiteSetting.get("homepage_slogan"), "新首页口号")
        self.client.logout()
        home = self.client.get(reverse("resources:home"))
        self.assertContains(home, "新首页口号")

    def test_account_password_change(self):
        response = self.client.post(
            reverse("manage:account"),
            {
                "old_password": "Str0ngPass!2026",
                "new_password1": "BrandNewPass!2026",
                "new_password2": "BrandNewPass!2026",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.check_password("BrandNewPass!2026"))
        self.assertFalse(self.staff.must_change_password)

    def test_private_resource_visible_in_dashboard(self):
        response = self.client.get(reverse("manage:software_list"))
        self.assertContains(response, self.private.title)
        self.assertContains(response, "非公开")

    def test_all_management_pages_render(self):
        urls = [
            reverse("manage:index"),
            reverse("manage:software_list"),
            reverse("manage:software_create"),
            reverse("manage:software_edit", args=[self.public.pk]),
            reverse("manage:library_list"),
            reverse("manage:library_create"),
            reverse("manage:library_edit", args=[self.library_a.pk]),
            reverse("manage:tag_list"),
            reverse("manage:tag_create"),
            reverse("manage:tag_edit", args=[self.tag.pk]),
            reverse("manage:settings"),
            reverse("manage:account"),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

        form_page = self.client.get(reverse("manage:software_create"))
        self.assertContains(form_page, "新建软件默认公开")
        self.assertContains(form_page, "添加下载链接")
        self.assertContains(form_page, "links-TOTAL_FORMS")