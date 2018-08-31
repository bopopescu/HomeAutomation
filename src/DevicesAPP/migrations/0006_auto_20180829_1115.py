# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2018-08-29 09:15
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('DevicesAPP', '0005_auto_20180810_1313'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cronexpressions',
            name='DayOfMonth',
            field=models.CharField(blank=True, default='*', help_text='Days that it would trigger.  "1-3" would trigger it on the 1st, 2nd and 3rd day of the month, "1,3" would trigger it only on 1st and 3rd, "*/2" would trigger every two days, leaving it blank or setting an "*" would trigger it every day.', max_length=20),
        ),
        migrations.AlterField(
            model_name='cronexpressions',
            name='DayOfWeek',
            field=models.CharField(blank=True, default='?', help_text='Days in the week that it would trigger.  "1-3" would trigger it on Mon., Tue. and Wed. of the week, "1,3" would trigger it only on Mon. and Wed., "*/2" would trigger every two days, leaving it blank or setting an "*" would trigger it every day.', max_length=20),
        ),
        migrations.AlterField(
            model_name='cronexpressions',
            name='Hours',
            field=models.CharField(blank=True, default='0', help_text='Hours that it would trigger.  "1-3" would trigger it at 1, 2 and 3 a.m., "1,3" would trigger it only at 1 and 3 p.m., "*/2" would trigger every two hours, leaving it blank or setting an "*" would trigger it every hour.', max_length=20),
        ),
        migrations.AlterField(
            model_name='cronexpressions',
            name='Minutes',
            field=models.CharField(blank=True, default='0', help_text='Minutes that it would trigger.  "1-3" would trigger it at minutes 1, 2 and 3, "1,3" would trigger it only at minutes 1 and 3 , "*/2" would trigger every two minutes, leaving it blank or setting an "*" would trigger it every minute.', max_length=20),
        ),
        migrations.AlterField(
            model_name='cronexpressions',
            name='Month',
            field=models.CharField(blank=True, default='*', help_text='Months that it would trigger.  "1-3" would trigger it on Jan., Febr. and March, "1,3" would trigger it only on Jan. and March, "*/2" would trigger every two months, leaving it blank or setting an "*" would trigger it every month.', max_length=20),
        ),
        migrations.AlterField(
            model_name='cronexpressions',
            name='Seconds',
            field=models.CharField(blank=True, default='0', help_text='Seconds that it would trigger.  "1-3" would trigger it at seconds 1, 2 and 3, "1,3" would trigger it only at seconds 1 and 3 , "*/2" would trigger every two seconds, Setting an "*" would trigger it every second.', max_length=20),
        ),
    ]
