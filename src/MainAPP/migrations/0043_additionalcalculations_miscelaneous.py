# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2019-04-16 11:23
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('MainAPP', '0042_auto_20190416_1211'),
    ]

    operations = [
        migrations.AddField(
            model_name='additionalcalculations',
            name='Miscelaneous',
            field=models.CharField(blank=True, max_length=1000, null=True),
        ),
    ]
