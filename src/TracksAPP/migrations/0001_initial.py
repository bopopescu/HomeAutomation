# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2018-05-14 09:41
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('DevicesAPP', '0004_auto_20180430_1112'),
    ]

    operations = [
        migrations.CreateModel(
            name='Beacons',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('Identifier', models.CharField(error_messages={'unique': 'Invalid Beacon name - This name already exists in the DB.'}, max_length=20, unique=True)),
                ('Latitude', models.FloatField()),
                ('Longitude', models.FloatField()),
                ('WeatherObserver', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='device2beacons', to='DevicesAPP.Devices')),
            ],
        ),
    ]
