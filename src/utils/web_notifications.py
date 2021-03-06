import json
from django.utils import timezone

import logging
logger = logging.getLogger("project")

class NotificationManager(object):
    
    @staticmethod
    def getUsers():
        from authtools.models import User
        return User.objects.filter(profile__notifications=True)
        
    @staticmethod
    def send_web_push(users, title, message_body,timestamp=None,tag=None,url=None):
        if timestamp==None:
            timestamp=timezone.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        else:
            timestamp=timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')
            
        try:
            for user in users:
                if user.profile.notifications and user.profile.subscription_token!=None and user.profile.subscription_token!="":
                    from pywebpush import webpush, WebPushException
                    from django.conf import settings
                    
                    if not isinstance(user.profile.subscription_token,dict):
                        import ast
                        token=ast.literal_eval(user.profile.subscription_token)
                    else:
                        token=user.profile.subscription_token
                        
                    #logger.info("Token: " + str(token))
                    VAPID_PRIVATE_KEY = open(settings.WEBPUSH_SETTINGS["VAPID_PRIVATE_KEY_PATH"], "r+").readline().strip("\n")
                    #logger.info("VAPID: " + str(VAPID_PRIVATE_KEY))
                    webpush(
                        subscription_info=token,
                        data=json.dumps({'body':message_body,'title':title,'timestamp':timestamp,'tag':tag,'url':url}),
                        vapid_private_key=VAPID_PRIVATE_KEY,
                        vapid_claims={"sub":"mailto:"+settings.WEBPUSH_SETTINGS["VAPID_ADMIN_EMAIL"]},
                    )
        except WebPushException as ex:
            #logger.debug("I'm sorry honey, but I can't do that: "+str(ex))
            # Mozilla returns additional information in the body of the response.
            if ex.response and ex.response.json():
                extra = ex.response.json()
                logger.debug("Remote service replied with a "+str(extra.code)+" " + str(extra.errno)+" " +str(extra.message))