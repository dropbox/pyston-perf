#!/usr/bin/env python
import os
import sys

BENCHMARK_SUITE_DIR = os.path.dirname(__file__)
# pyston changes:  add our testsite dir to sys.path, as well as the lib/ directory so we can locate django
sys.path.extend([os.path.join(BENCHMARK_SUITE_DIR, "django_migrate_testsite"),
                 os.path.join(BENCHMARK_SUITE_DIR, "lib")])

# pyston change: clear the sqlite db so we'll re-run the migration
db_path = os.path.join(BENCHMARK_SUITE_DIR, "django_migrate_testsite/db.sqlite3")
assert not os.path.exists(db_path), os.remove(db_path)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "testsite.settings")

from django.core.management import execute_from_command_line

execute_from_command_line([BENCHMARK_SUITE_DIR, "migrate"])

os.remove(db_path)
