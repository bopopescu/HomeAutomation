# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-09-04 09:41
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('Devices', '0002_auto_20170904_1139'),
        ('LocalDevices', '0005_auto_20170901_1429'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='devicemodel',
            name='DeviceType',
        ),
        migrations.AddField(
            model_name='devicemodel',
            name='Type',
            field=models.ForeignKey(default='DHT11', on_delete=django.db.models.deletion.CASCADE, related_name='Local', to='Devices.DeviceTypeModel'),
            preserve_default=False,
        ),
    ]
