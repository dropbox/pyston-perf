#!/usr/bin/env python
import os
import sys

# pyston changes:  add benchmark_suite to sys.path
sys.path += [os.path.join(os.getcwd(), "benchmark_suite/testsite")]

# pyston change: clear the sqlite db so we'll re-run the migration
try:
    os.remove("benchmark_suite/testsite/db.sqlite3")
except:
    pass

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "testsite.settings")

from django.core.management import execute_from_command_line

execute_from_command_line(["testsite/manage.py", "migrate"])
