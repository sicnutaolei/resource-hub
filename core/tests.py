import shutil
import sqlite3
import tempfile
from io import StringIO
from pathlib import Path

from django.conf import settings as django_settings
from django.core.management import call_command
from django.test import TestCase, override_settings


class CustomErrorPageTests(TestCase):
    def test_custom_404_page(self):
        response = self.client.get("/definitely-not-a-real-page/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "404 · 这个页面不存在", status_code=404)


class BackupCommandTests(TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="rh-backup-"))
        self.db_path = self.tmpdir / "db.sqlite3"
        connection = sqlite3.connect(str(self.db_path))
        connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT)")
        connection.execute("INSERT INTO sample (name) VALUES ('kept')")
        connection.commit()
        connection.close()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_backup_creates_copy_with_data(self):
        backup_dir = self.tmpdir / "backups"
        databases = {
            "default": {
                **django_settings.DATABASES["default"],
                "NAME": str(self.db_path),
            }
        }
        with override_settings(DATABASES=databases):
            out = StringIO()
            call_command("backup_db", "--output-dir", str(backup_dir), stdout=out)

        backups = list(backup_dir.glob("db-*.sqlite3"))
        self.assertEqual(len(backups), 1)
        self.assertGreater(backups[0].stat().st_size, 0)

        connection = sqlite3.connect(str(backups[0]))
        rows = list(connection.execute("SELECT name FROM sample"))
        connection.close()
        self.assertEqual(rows, [("kept",)])
        self.assertIn("数据库已备份", out.getvalue())