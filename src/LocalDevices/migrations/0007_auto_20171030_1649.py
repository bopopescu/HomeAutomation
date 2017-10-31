# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-10-30 15:49
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('LocalDevices', '0006_auto_20170904_1141'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='devicemodel',
            options={'permissions': (('view_devices', 'Can see available devices'), ('change_state', 'Can change the state of the devices'), ('add_device', 'Can add new devices to the installation')), 'verbose_name': 'Local device', 'verbose_name_plural': 'Local devices'},
        ),
    ]
