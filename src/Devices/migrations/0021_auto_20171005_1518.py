# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-10-05 13:18
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Devices', '0020_auto_20171005_1444'),
    ]

    operations = [
        migrations.AlterField(
            model_name='reportmodel',
            name='DataAggregation',
            field=models.PositiveSmallIntegerField(choices=[(0, 'No aggregation'), (1, 'Hourly'), (2, 'Daily'), (4, 'Monthly')], help_text='Setup the aggregation of the data'),
        ),
        migrations.AlterField(
            model_name='reportmodel',
            name='Periodicity',
            field=models.PositiveSmallIntegerField(choices=[(2, 'Every day'), (3, 'Every week'), (4, 'Every month')], help_text='Setup the periodicity'),
        ),
    ]
