# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2018-04-18 14:08
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ReportingAPP', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='reportitems',
            options={'ordering': ('fromDate',), 'permissions': (('view_report_items', 'Can view report items generated'),), 'verbose_name': 'Generated report', 'verbose_name_plural': 'Generated reports'},
        ),
    ]
