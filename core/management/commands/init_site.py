from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import SiteSetting


class Command(BaseCommand):
    help = "写入默认站点设置（站点名称 / 首页 slogan），已存在则不覆盖。"

    DEFAULTS = {
        "site_name": lambda: settings.SITE_NAME,
        "homepage_slogan": lambda: settings.SITE_SLOGAN,
    }

    def handle(self, *args, **options):
        created = []
        for key, factory in self.DEFAULTS.items():
            if SiteSetting.objects.filter(key=key).exists():
                continue
            value = factory()
            SiteSetting.set(key, value)
            created.append(f"{key}={value}")

        if created:
            self.stdout.write(
                self.style.SUCCESS("已写入默认站点设置：" + "；".join(created))
            )
        else:
            self.stdout.write("站点设置已存在，未做修改。")