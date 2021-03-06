# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2019-11-07 21:16
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('MainAPP', '0046_additionalcalculations_scale'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='ETH_DHCP',
            field=models.BooleanField(default=True, help_text='Includes the server in the DHCP pool', verbose_name='Enable DHCP on the LAN network'),
        ),
        migrations.AlterField(
            model_name='sitesettings',
            name='ETH_GATE',
            field=models.GenericIPAddressField(default='1.1.1.1', help_text='This is the gateway IP of the LAN network that is providing the internet access.', protocol='IPv4', verbose_name='Gateway of the LAN network'),
        ),
        migrations.AlterField(
            model_name='sitesettings',
            name='ETH_IP',
            field=models.GenericIPAddressField(default='1.1.1.2', help_text='This is the IP for the LAN network that is providing the internet access.', protocol='IPv4', verbose_name='IP address for the LAN network'),
        ),
    ]
