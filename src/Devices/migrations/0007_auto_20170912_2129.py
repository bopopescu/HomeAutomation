# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-09-12 19:29
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('Devices', '0006_auto_20170912_2125'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='datagrammodel',
            unique_together=set([('DeviceType', 'Identifier')]),
        ),
    ]
