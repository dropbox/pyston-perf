#!/usr/bin/env python
import os
import sys

# pyston changes:  add our testsite dir to sys.path, as well as the lib/ directory so we can locate django
sys.path.extend([os.path.join(os.path.dirname(__file__), "django_migrate_testsite"),
                 os.path.join(os.path.dirname(__file__), "lib")])

# pyston change: clear the sqlite db so we'll re-run the migration
try:
    os.remove("benchmark_suite/django_migrate_testsite/db.sqlite3")
except:
    pass

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "testsite.settings")

from django.core.management import execute_from_command_line

execute_from_command_line(["django_migrate_testsite/manage.py", "migrate"])
