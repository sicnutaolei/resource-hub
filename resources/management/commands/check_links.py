from django.core.management.base import BaseCommand
from django.utils import timezone

from resources.models import DownloadLink
from resources.utils import BROKEN, OK, SKIPPED, STATUS_LABEL, check_links


class Command(BaseCommand):
    help = "批量检测外链网盘的可达性。默认只预览不改库，确认无误后加 --apply 写回结果。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="把检测结果写回数据库（更新 is_broken 与 last_checked_at）。不加此参数只输出报告。",
        )
        parser.add_argument(
            "--timeout", type=int, default=None, help="单个链接的超时秒数，默认取 EXTERNAL_LINK_CHECK_TIMEOUT"
        )
        parser.add_argument(
            "--only-broken",
            action="store_true",
            help="只复检上轮被标记为疑似失效的链接",
        )
        parser.add_argument(
            "--limit", type=int, default=0, help="最多检测多少个链接，0 表示不限制"
        )

    def handle(self, *args, **options):
        apply = options["apply"]
        queryset = (
            DownloadLink.objects.filter(
                link_type=DownloadLink.EXTERNAL, is_active=True
            )
            .select_related("resource")
            .order_by("resource__title", "order")
        )
        if options["only_broken"]:
            queryset = queryset.filter(is_broken=True)
        if options["limit"]:
            queryset = queryset[: options["limit"]]

        links = list(queryset)
        if not links:
            self.stdout.write(self.style.WARNING("没有需要检测的外链。"))
            return

        mode = "写回数据库" if apply else "预览模式（不改库）"
        self.stdout.write(f"共 {len(links)} 个外链待检测，当前为【{mode}】\n")

        started = timezone.now()
        results = check_links(links, timeout=options["timeout"], apply=apply)
        elapsed = (timezone.now() - started).total_seconds()

        counters = {OK: 0, BROKEN: 0, SKIPPED: 0}
        for item in results:
            counters[item["status"]] += 1
            if item["status"] == BROKEN:
                style = self.style.ERROR
            elif item["status"] == OK:
                style = self.style.SUCCESS
            else:
                style = self.style.WARNING
            self.stdout.write(
                f"{style(STATUS_LABEL[item['status']])}  "
                f"[#{item['id']}] {item['resource']} · {item['label']}  →  {item['detail']}"
            )

        self.stdout.write("")
        summary = (
            f"检测完成：可达 {counters[OK]}，疑似失效 {counters[BROKEN]}，"
            f"跳过 {counters[SKIPPED]}，耗时 {elapsed:.1f}s"
        )
        self.stdout.write(self.style.SUCCESS(summary) if not counters[BROKEN] else self.style.WARNING(summary))

        if counters[BROKEN] and not apply:
            self.stdout.write(
                self.style.NOTICE(
                    "\n以上为预览结果。确认规则无误后，加 --apply 参数重新执行即可写回数据库。"
                )
            )
            self.stdout.write(
                "提示：网盘分享过期后部分平台仍返回 200，检测结果仅供参考，"
                "标记为失效的链接只是加了一个提示徽标，不会自动删除或隐藏。"
            )
