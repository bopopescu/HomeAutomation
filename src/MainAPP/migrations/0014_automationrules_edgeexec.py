# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2018-05-22 12:03
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('MainAPP', '0013_auto_20180522_1135'),
    ]

    operations = [
        migrations.AddField(
            model_name='automationrules',
            name='EdgeExec',
            field=models.BooleanField(default=False),
        ),
    ]