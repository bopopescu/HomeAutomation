# -*- coding: utf-8 -*-
# Generated by Django 1.10 on 2019-01-27 20:52
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('DevicesAPP', '0012_devicecommands_label'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='parametervalues',
            unique_together=set([('Parameter', 'Command')]),
        ),
    ]
