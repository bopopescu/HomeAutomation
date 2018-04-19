#!/usr/bin/env python
# coding: utf-8
import os
import sys


if __name__ == "__main__":
    # CHANGED manage.py will use development settings by
    # default. Change the DJANGO_SETTINGS_MODULE environment variable
    # for using the environment specific settings file.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "MainAPP.settings.production")
    os.environ.__setitem__("DJANGO_SETTINGS_MODULE", "MainAPP.settings.production")
    
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
