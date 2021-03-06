# coding: utf-8
import logging

from django.conf import settings
from django.db.models.signals import post_save,post_delete
from django.dispatch import receiver

from . import models


logger = logging.getLogger("project")


@receiver(post_save, sender=settings.AUTH_USER_MODEL,dispatch_uid="create_user_profile")
def create_profile_handler(sender, instance, created, **kwargs):
    if not created:
        return
    # Create the profile object, only if it is newly created
    profile = models.Profile(user=instance)
    profile.save()
    logger.info('New user profile for {} created'.format(instance))

@receiver(post_delete, sender=settings.AUTH_USER_MODEL,dispatch_uid="delete_user_profile")
def delete_user_handler(sender, instance, **kwargs):
    logger.info('User {} deleted'.format(instance))