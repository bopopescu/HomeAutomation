# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2018-04-04 13:57
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='ReportItems',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fromDate', models.DateTimeField(blank=True, editable=False, null=True)),
                ('toDate', models.DateTimeField(blank=True, editable=False, null=True)),
                ('data', models.CharField(blank=True, help_text='Data of the report in JSON format', max_length=20000, null=True)),
            ],
            options={
                'ordering': ('fromDate',),
                'verbose_name_plural': 'Generated reports',
                'verbose_name': 'Generated report',
            },
        ),
        migrations.CreateModel(
            name='Reports',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('Title', models.CharField(error_messages={'unique': 'Invalid report title - This title already exists in the DB.'}, max_length=50, unique=True)),
                ('Periodicity', models.PositiveSmallIntegerField(choices=[(2, 'Every day'), (3, 'Every week'), (4, 'Every month')], help_text='How often the report will be generated')),
                ('DataAggregation', models.PositiveSmallIntegerField(choices=[(0, 'No aggregation'), (1, 'Hourly'), (2, 'Daily'), (4, 'Monthly')], help_text='Data directly from the DB or averaged over a period')),
                ('ContentJSON', models.CharField(help_text='Content of the report in JSON format', max_length=20000)),
            ],
            options={
                'verbose_name': 'Report',
                'permissions': (('view_reports', 'Can view reports configured'),),
                'verbose_name_plural': 'Reports',
            },
        ),
        migrations.AddField(
            model_name='reportitems',
            name='Report',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ReportingAPP.Reports'),
        ),
        migrations.AlterUniqueTogether(
            name='reportitems',
            unique_together=set([('Report', 'fromDate', 'toDate')]),
        ),
    ]
