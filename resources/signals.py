from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from .models import Resource, Tag
from .selectors import invalidate_filter_tags


@receiver([post_save, post_delete], sender=Tag)
@receiver([post_save, post_delete], sender=Resource)
def _clear_filter_tags_cache(sender, instance, **kwargs):
    invalidate_filter_tags()


@receiver(m2m_changed, sender=Resource.tags.through)
def _clear_filter_tags_on_m2m(sender, instance, action, **kwargs):
    if action in ("post_add", "post_remove", "post_clear"):
        invalidate_filter_tags()