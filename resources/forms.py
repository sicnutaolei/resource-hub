from django import forms

from .models import Comment


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ("content",)
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": "input textarea",
                    "rows": 3,
                    "maxlength": 1000,
                    "placeholder": "说点什么…（文明发言，支持换行）",
                }
            )
        }

    def clean_content(self):
        content = self.cleaned_data["content"].strip()
        if len(content) < 2:
            raise forms.ValidationError("评论太短了，至少 2 个字。")
        return content
