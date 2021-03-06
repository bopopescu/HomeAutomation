# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2018-12-17 13:19
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('MainAPP', '0031_auto_20181217_1417'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sitesettings',
            name='OWM_TOKEN',
            field=models.CharField(blank=True, default='', help_text='The token assigned by the OpenWeatherMap service. You should ask yours following https://openweathermap.org/appid', max_length=100, verbose_name='Token for the openweathermap page'),
        ),
    ]
