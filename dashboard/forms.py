import re

from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.forms import inlineformset_factory
from django.utils.html import strip_tags

from resources.models import Category, DownloadLink, Resource, Tag, UpdateLog

TAG_SPLIT_RE = re.compile(r"[,，;；]")


class SoftwareForm(forms.ModelForm):
    tags_text = forms.CharField(
        label="标签",
        required=False,
        widget=forms.TextInput(
            attrs={"class": "input", "placeholder": "用逗号分隔，例如：开源, 轻量, Win11"}
        ),
        help_text="不存在的标签会自动创建；首页筛选标签固定来自这里。",
    )

    class Meta:
        model = Resource
        fields = (
            "title",
            "summary",
            "description",
            "version",
            "category",
            "cover_image",
            "is_public",
        )
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "input", "placeholder": "软件名称，例如：7-Zip 压缩工具"}
            ),
            "summary": forms.TextInput(
                attrs={"class": "input", "placeholder": "一句话简短标题，可留空"}
            ),
            "description": forms.Textarea(
                attrs={"class": "input textarea", "rows": 7, "placeholder": "软件简介、本版特点…"}
            ),
            "version": forms.TextInput(
                attrs={"class": "input", "placeholder": "例如：24.08"}
            ),
            "category": forms.Select(attrs={"class": "input"}),
            "cover_image": forms.ClearableFileInput(
                attrs={"class": "input", "accept": "image/*"}
            ),
            "is_public": forms.CheckboxInput(attrs={"class": "switch-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].empty_label = "未分类"
        self.fields["category"].queryset = Category.objects.order_by("order", "id")
        if not self.instance.pk:
            self.fields["is_public"].initial = True
        else:
            self.fields["tags_text"].initial = "、".join(
                self.instance.tags.values_list("name", flat=True)
            )

    def clean_title(self):
        title = (self.cleaned_data.get("title") or "").strip()
        if not title:
            raise forms.ValidationError("请填写软件名称。")
        return title

    def clean_tags_text(self):
        raw = self.cleaned_data.get("tags_text") or ""
        names = []
        for part in TAG_SPLIT_RE.split(raw.replace("、", ",")):
            name = part.strip()
            if not name:
                continue
            if len(name) > 40:
                raise forms.ValidationError(f"标签「{name[:12]}…」超过 40 个字符。")
            if name not in names:
                names.append(name)
        if len(names) > 12:
            raise forms.ValidationError("单个软件最多 12 个标签。")
        return names

    def save(self, commit=True):
        resource = super().save(commit=commit)
        if commit:
            names = self.cleaned_data.get("tags_text") or []
            tags = [Tag.objects.get_or_create(name=name)[0] for name in names]
            resource.tags.set(tags)
        return resource


class DownloadLinkForm(forms.ModelForm):
    class Meta:
        model = DownloadLink
        fields = ("label", "link_type", "file", "url", "extract_code", "order", "is_active")
        widgets = {
            "label": forms.TextInput(
                attrs={"class": "input", "placeholder": "例如：本地下载 / 百度网盘"}
            ),
            "link_type": forms.Select(attrs={"class": "input"}),
            "file": forms.ClearableFileInput(attrs={"class": "input", "accept": "*/*"}),
            "url": forms.URLInput(
                attrs={"class": "input", "placeholder": "https://…"}
            ),
            "extract_code": forms.TextInput(
                attrs={"class": "input", "placeholder": "可留空"}
            ),
            "order": forms.NumberInput(attrs={"class": "input", "min": 0}),
            "is_active": forms.CheckboxInput(attrs={"class": "switch-input"}),
        }


class UpdateLogForm(forms.ModelForm):
    class Meta:
        model = UpdateLog
        fields = ("version", "content")
        widgets = {
            "version": forms.TextInput(
                attrs={"class": "input", "placeholder": "例如：24.08"}
            ),
            "content": forms.Textarea(
                attrs={"class": "input textarea", "rows": 3, "placeholder": "一条一行"}
            ),
        }


class LibraryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name", "description", "order")
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "input", "placeholder": "例如：系统工具"}
            ),
            "description": forms.TextInput(
                attrs={"class": "input", "placeholder": "可选，一句话说明"}
            ),
            "order": forms.NumberInput(attrs={"class": "input", "min": 0}),
        }


class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ("name",)
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "input", "placeholder": "例如：开源"}
            ),
        }


class SiteSettingsForm(forms.Form):
    site_name = forms.CharField(
        label="站点名称",
        max_length=60,
        widget=forms.TextInput(attrs={"class": "input", "placeholder": "资源小站"}),
    )
    homepage_slogan = forms.CharField(
        label="首页 Slogan",
        max_length=160,
        widget=forms.TextInput(
            attrs={"class": "input", "placeholder": "只分享干净、无捆绑的资源"}
        ),
    )

    def clean_site_name(self):
        value = strip_tags(self.cleaned_data.get("site_name") or "").strip()
        if not value:
            raise forms.ValidationError("站点名称不能为空。")
        return value

    def clean_homepage_slogan(self):
        return strip_tags(self.cleaned_data.get("homepage_slogan") or "").strip()


class StyledPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            "old_password": "当前密码",
            "new_password1": "新密码",
            "new_password2": "确认新密码",
        }
        for name, field in self.fields.items():
            field.label = labels.get(name, field.label)
            field.widget.attrs.setdefault("class", "input")
        self.fields["new_password1"].help_text = "至少 8 位，不能是纯数字或常见密码。"


DownloadLinkFormSet = inlineformset_factory(
    Resource,
    DownloadLink,
    form=DownloadLinkForm,
    extra=2,
    can_delete=True,
)

UpdateLogFormSet = inlineformset_factory(
    Resource,
    UpdateLog,
    form=UpdateLogForm,
    extra=1,
    can_delete=True,
)