"""迁移前备份 SQLite 数据库。

使用 sqlite3 的在线备份 API，能把 WAL 中尚未 checkpoint 的内容一并写入备份文件，
比直接 cp 更可靠。备份写到数据库同级的 backups/ 目录，默认保留最近 20 份。
"""

import sqlite3
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "把当前 SQLite 数据库备份到 data/backups/（迁移前自动执行）。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep", type=int, default=20, help="保留最近多少份备份，默认 20"
        )
        parser.add_argument(
            "--output-dir", default=None, help="自定义备份目录"
        )

    def handle(self, *args, **options):
        db_path = Path(settings.DATABASES["default"]["NAME"])
        if not db_path.exists():
            self.stdout.write("数据库文件尚不存在，跳过备份。")
            return

        output_dir = Path(options["output_dir"]) if options["output_dir"] else db_path.parent / "backups"
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = output_dir / f"db-{timestamp}.sqlite3"

        source = sqlite3.connect(str(db_path), timeout=30)
        destination = sqlite3.connect(str(target))
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()

        size = target.stat().st_size
        if size <= 0:
            target.unlink(missing_ok=True)
            raise RuntimeError("备份文件为空，已中止。")

        self.stdout.write(self.style.SUCCESS(f"数据库已备份：{target}（{size} 字节）"))
        self._prune(output_dir, max(options["keep"], 1))

    def _prune(self, output_dir: Path, keep: int):
        backups = sorted(output_dir.glob("db-*.sqlite3"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in backups[keep:]:
            old.unlink(missing_ok=True)