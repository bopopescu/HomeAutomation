# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-08-31 07:41
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Eventmodel',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('DeviceName', models.CharField(max_length=50)),
                ('DatagramId', models.CharField(max_length=50)),
                ('variable_pos', models.IntegerField()),
                ('boolean_expression', models.CharField(max_length=50)),
                ('label', models.CharField(max_length=50)),
            ],
        ),
    ]
