# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-11-14 15:30
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('profiles', '0008_auto_20171114_1601'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='Accuracy',
            field=models.FloatField(blank=True, null=True, verbose_name='Last known position accuracy'),
        ),
    ]
