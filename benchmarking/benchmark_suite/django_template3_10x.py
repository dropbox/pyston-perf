import os
import sys

BENCHMARK_SUITE_DIR = os.path.dirname(__file__)
sys.path.extend([os.path.join(BENCHMARK_SUITE_DIR, "django_template2_site"),
                 os.path.join(BENCHMARK_SUITE_DIR, "lib")])

from django.template.base import Origin, Template, Context, TemplateDoesNotExist
from django.conf import settings
from django.apps import apps
import time
import shutil

# Copy the "base" db so we always start with a knownn state:
db_path = os.path.join(BENCHMARK_SUITE_DIR, "django_template2_site/db.sqlite3")
db_base_path = os.path.join(BENCHMARK_SUITE_DIR, "django_template2_site/db_base.sqlite3")
shutil.copy(db_base_path, db_path)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "testsite.settings")

try:
    import __pyston__
    pyston_loaded = True
except:
    pyston_loaded = False

template_source = """
{% extends "admin/base_site.html" %}
{% load i18n admin_static %}

{% block extrastyle %}{{ block.super }}<link rel="stylesheet" type="text/css" href="{% static "admin/css/dashboard.css" %}" />{% endblock %}

{% block coltype %}colMS{% endblock %}

{% block bodyclass %}{{ block.super }} dashboard{% endblock %}

{% block breadcrumbs %}{% endblock %}

{% block content %}
<div id="content-main">

{% if app_list %}
    {% for app in app_list %}
        <div class="app-{{ app.app_label }} module">
        <table>
        <caption>
            <a href="{{ app.app_url }}" class="section" title="{% blocktrans with name=app.name %}Models in the {{ name }} application{% endblocktrans %}">{{ app.name }}</a>
        </caption>
        {% for model in app.models %}
            <tr class="model-{{ model.object_name|lower }}">
            {% if model.admin_url %}
                <th scope="row"><a href="{{ model.admin_url }}">{{ model.name }}</a></th>
            {% else %}
                <th scope="row">{{ model.name }}</th>
            {% endif %}

            {% if model.add_url %}
                <td><a href="{{ model.add_url }}" class="addlink">{% trans 'Add' %}</a></td>
            {% else %}
                <td>&nbsp;</td>
            {% endif %}

            {% if model.admin_url %}
                <td><a href="{{ model.admin_url }}" class="changelink">{% trans 'Change' %}</a></td>
            {% else %}
                <td>&nbsp;</td>
            {% endif %}
            </tr>
        {% endfor %}
        </table>
        </div>
    {% endfor %}
{% else %}
    <p>{% trans "You don't have permission to edit anything." %}</p>
{% endif %}
</div>
{% endblock %}

{% block sidebar %}
<div id="content-related">
    <div class="module" id="recent-actions-module">
        <h2>{% trans 'Recent Actions' %}</h2>
        <h3>{% trans 'My Actions' %}</h3>
            {% load log %}
            {% get_admin_log 10 as admin_log for_user user %}
            {% if not admin_log %}
            <p>{% trans 'None available' %}</p>
            {% else %}
            <ul class="actionlist">
            {% for entry in admin_log %}
            <li class="{% if entry.is_addition %}addlink{% endif %}{% if entry.is_change %}changelink{% endif %}{% if entry.is_deletion %}deletelink{% endif %}">
                {% if entry.is_deletion or not entry.get_admin_url %}
                    {{ entry.object_repr }}
                {% else %}
                    <a href="{{ entry.get_admin_url }}">{{ entry.object_repr }}</a>
                {% endif %}
                <br/>
                {% if entry.content_type %}
                    <span class="mini quiet">{% filter capfirst %}{% trans entry.content_type.name %}{% endfilter %}</span>
                {% else %}
                    <span class="mini quiet">{% trans 'Unknown content' %}</span>
                {% endif %}
            </li>
            {% endfor %}
            </ul>
            {% endif %}
    </div>
</div>
{% endblock %}
"""

apps.populate((
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
))

settings.TEMPLATE_LOADERS = (
    ('django.template.loaders.cached.Loader', (
        'django.template.loaders.filesystem.Loader',
        'django.template.loaders.app_directories.Loader',
    )),
)

elapsed = 0
template = Template(template_source, None, "admin/index.html")

d = {}
from django.contrib.auth.models import User
d['user'] = User(2)
# This list was created by running an empty django instance and seeing what it passed for app_list:
d['app_list'] = [{'app_url': '/admin/auth/', 'models': [{'perms': {'add': True, 'change': True, 'delete': True}, 'admin_url': '/admin/auth/group/', 'object_name': 'Group', 'name': "<name>", 'add_url': '/admin/auth/group/add/'}, {'perms': {'add': True, 'change': True, 'delete': True}, 'admin_url': '/admin/auth/user/', 'object_name': 'User', 'name': "<name>", 'add_url': '/admin/auth/user/add/'}], 'has_module_perms': True, 'name': "<name>", 'app_label': 'auth'}]
context = Context(d)

for i in xrange(4000):
    start = time.time()
    template.render(context)
    elapsed = time.time() - start
print "took %4.1fms for last iteration" % (elapsed * 1000.0,)
