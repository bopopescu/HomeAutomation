from django.db.models import Q
from django.db import models
from django.db.utils import OperationalError
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone
from django.utils.functional import lazy
from django.core.cache import cache
from django.core.validators import MinValueValidator,MaxValueValidator
import datetime
import sys
import os
import json
from EventsAPP.consumers import PublishEvent

from django.dispatch import receiver
from django.db.models.signals import pre_save,post_save,post_delete,pre_delete
from django.contrib.contenttypes.fields import GenericRelation

from MainAPP.constants import REGISTERS_DB_PATH,SUBSYSTEMS_CHOICES

import MainAPP.signals

import utils.BBDD

import pandas as pd
import numpy as np

import logging
from abc import abstractstaticmethod

logger = logging.getLogger("project")
                                           

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

# settings from https://steelkiwi.com/blog/practical-application-singleton-design-pattern/
class SingletonModel(models.Model):
    class Meta:
        abstract = True
        
    def save(self, *args, **kwargs):
        self.pk = 1
        super(SingletonModel, self).save(*args, **kwargs)
        self.set_cache()
    
    def set_cache(self):
        cache.set(self.__class__.__name__, self)
    
    @classmethod
    def checkIfExists(cls):
        try:
            obj = cls.objects.get(pk=1)
            return True
        except cls.DoesNotExist:
            return False
    
    @classmethod
    def load(cls):
        if cache.get(cls.__name__) is None:
            obj, created = cls.objects.get_or_create(pk=1)
            if not created:
                obj.set_cache()
        return cache.get(cls.__name__)

class SiteSettings(SingletonModel):
    class Meta:
        verbose_name = _('Settings')

    FACILITY_NAME= models.CharField(verbose_name=_('Name of the installation'),max_length=100,
                                    help_text=_('Descriptive name for the installation.'),default='My house')
    SITE_DNS= models.CharField(verbose_name=_('Name of the domain to access the application'),
                                help_text=_('This is the DNS address that gives access to the application from the internet.'),
                                max_length=100,default='myDIY4dot0House.net')
    
    VERSION_AUTO_DETECT=models.BooleanField(verbose_name=_('Autodetect new software releases'),
                                help_text=_('Automatically checks the repository for new software'),default=True)
    VERSION_AUTO_UPDATE=models.BooleanField(verbose_name=_('Apply automatically new software releases'),
                                help_text=_('Automatically updates to (and applies) the latest software'),default=False)
    VERSION_CODE= models.CharField(verbose_name=_('Code of the version of the application framework'),
                                max_length=100,default='',blank=True)
    VERSION_DEVELOPER=models.BooleanField(verbose_name=_('Follow the beta development versions'),
                                help_text=_('Tracks the development versions (may result in unstable behaviour)'),default=False)
    NTPSERVER_RESTART_TIMEDELTA=models.PositiveSmallIntegerField(verbose_name=_('NTP server restart time delta'),
                                help_text=_('Time difference in minutes that will trigger a restart of the NTP server'),default=5)
    
    WIFI_SSID= models.CharField(verbose_name=_('WIFI network identificator'),
                                help_text=_('This is the name of the WiFi network generated to communicate with the subordinates'),
                                max_length=50,default='DIY4dot0')
    WIFI_PASSW= models.CharField(verbose_name=_('WIFI network passphrase'),
                                help_text=_('This is the encryption password for the WIFI network'),
                                max_length=50,default='DIY4dot0')
    WIFI_IP= models.GenericIPAddressField(verbose_name=_('IP address for the WIFI network'),
                                help_text=_('This is the IP address for the WiFi network generated to communicate with the subordinates'),
                                protocol='IPv4', default='10.10.10.1')
    WIFI_MASK= models.GenericIPAddressField(verbose_name=_('WIFI network mask'),
                                help_text=_('This is the mask of the WiFi network generated to communicate with the subordinates'),
                                protocol='IPv4', default='255.255.255.0')
    WIFI_GATE= models.GenericIPAddressField(verbose_name=_('WIFI network gateway'),
                                help_text=_('This is the gateway for the WiFi network generated to communicate with the subordinates'),
                                protocol='IPv4', default='10.10.10.1')
    
    ETH_DHCP=models.BooleanField(verbose_name=_('Enable DHCP on the LAN network'),
                                help_text=_('Includes the server in the DHCP pool'),default=True)
    ETH_IP= models.GenericIPAddressField(verbose_name=_('IP address for the LAN network'),
                                help_text=_('This is the IP for the LAN network that is providing the internet access.'),
                                protocol='IPv4', default='1.1.1.2')
    ETH_MASK= models.GenericIPAddressField(verbose_name=_('Mask for the LAN network'),
                                help_text=_('This is the mask for the LAN network that is providing the internet access.'),
                                protocol='IPv4', default='255.255.255.0')
    ETH_GATE= models.GenericIPAddressField(verbose_name=_('Gateway of the LAN network'),
                                help_text=_('This is the gateway IP of the LAN network that is providing the internet access.'),
                                protocol='IPv4', default='1.1.1.1')
    
    PROXY_AUTO_DENYIP=models.BooleanField(verbose_name=_('Enable automatic IP blocking'),
                                help_text=_('Feature that blocks automatically WAN IPs with more than certain denied attempts in 24 h.'),default=True)
    AUTODENY_ATTEMPTS=models.PositiveSmallIntegerField(verbose_name=_('Number of denied attempts needed to block an IP'),
                                help_text=_('The number of denied accesses in 24h that will result in an IP being blocked.'),default=40)
    PROXY_CREDENTIALS=models.BooleanField(verbose_name=_('Require credentials to access the server'),
                                help_text=_('Increased access security by including an additional barrier on the proxy.'),default=True)
    PROXY_USER1=models.CharField(verbose_name=_('Username 1'),
                                max_length=10,help_text=_('First username enabled to get through the proxy barrier.'),default='user1')
    PROXY_PASSW1=models.CharField(verbose_name=_('Password for username 1'),
                                max_length=10,help_text=_('First username password.'),default='DIY4dot0')
    PROXY_USER2=models.CharField(verbose_name=_('Username 2'),
                                max_length=10,help_text=_('First username enabled to get through the proxy barrier.'),default='user2')
    PROXY_PASSW2=models.CharField(verbose_name=_('Password for username 2'),
                                max_length=10,help_text=_('First username password.'),default='DIY4dot0')
    
    TELEGRAM_TOKEN=models.CharField(verbose_name=_('Token for the telegram bot'),blank=True,
                                max_length=100,help_text=_('The token assigned by the BothFather'),default='')
    
    TELEGRAM_CHATID=models.CharField(verbose_name=_('Chat ID'),blank=True,
                                max_length=100,help_text=_('The ID of the chat to use'),default='')
    
    IBERDROLA_USER=models.CharField(verbose_name=_('Iberdrola username'),blank=True,
                                max_length=50,help_text=_('Username registered into the Iberdrola Distribucion webpage'),default='')
    IBERDROLA_PASSW=models.CharField(verbose_name=_('Iberdrola password'),blank=True,
                                max_length=50,help_text=_('Password registered on the Iberdrola Distribucion webpage'),default='')
    
    OWM_TOKEN=models.CharField(verbose_name=_('Token for the openweathermap page'),blank=True,
                                max_length=100,help_text=_('The token assigned by the OpenWeatherMap service. You should ask yours following https://openweathermap.org/appid'),default='')
    
    ESIOS_TOKEN=models.CharField(verbose_name=_('Token for the ESIOS page'),blank=True,
                                max_length=100,help_text=_('The token assigned by the ESIOS service. You should ask for yours to: Consultas Sios <consultasios@ree.es>'),default='')
    
    def store2DB(self,update_fields=None):
        try:
            self.save(update_fields=update_fields)
        except OperationalError:
            logger.error("Operational error on Django. System restarted")
            import os
            os.system("sudo reboot")
        
        if update_fields!=None:
            self.applyChanges(update_fields=update_fields)
    
    @classmethod
    def onBootTasks(cls):
        cls.checkInternetConnection()
        IP=cls.getMyLANIP()
        SETTINGS=cls.load()
        if IP != SETTINGS.ETH_IP:
            SETTINGS.applyChanges(update_fields=['ETH_IP',])
        
    
    def dailyTasks(self):
        self.checkRepository()
        self.checkDeniableIPs(attempts=self.AUTODENY_ATTEMPTS,hours=24)
    
    def hourlyTasks(self):
        self.checkDeniableIPs(attempts=self.AUTODENY_ATTEMPTS/10,hours=1)
        
    def set_TELEGRAM_CHATID(self,value):
        self.TELEGRAM_CHATID=str(value)
        self.store2DB()
    
    @staticmethod
    def getMyLANIP():
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('192.0.0.8', 1027))
        except socket.error:
            return None
        return s.getsockname()[0]

    @staticmethod
    def checkInternetConnection():
        import requests
        try:
            r = requests.get('http://google.com',timeout=1)
            if r.status_code==200:
                return True
            else:
                return False
        except: 
            return False
        
    def checkRepository(self,force=False):
        from django.core.cache import cache
        cache.set(key='loading',value=True,timeout=60)
        if self.VERSION_AUTO_DETECT or force:
            from utils.GitHub import checkDeveloperUpdates,checkReleaseUpdates,updateDeveloper,updateRelease
            from .constants import GIT_PATH
            if self.VERSION_DEVELOPER:
                release=checkDeveloperUpdates(root=GIT_PATH)
            else:
                release=checkReleaseUpdates(root=GIT_PATH,currentVersion=self.VERSION_CODE)
            if release['tag']!=None:
                self.VERSION_CODE=release['tag']
                self.save(update_fields=['VERSION_CODE',])
            if release['update'] and (self.VERSION_AUTO_UPDATE or force):
                from utils.Watchdogs import WATCHDOG
                from DevicesAPP.constants import POLLING_WATCHDOG_TIMER,POLLING_WATCHDOG_VAR
                #process=WATCHDOG(name='PollingWatchdog',interval=POLLING_WATCHDOG_TIMER,cachevar=POLLING_WATCHDOG_VAR)
                #process.pause()
                try:
                    if self.VERSION_DEVELOPER:
                        revision=updateDeveloper(root=GIT_PATH)
                    else:
                        revision=updateRelease(root=GIT_PATH,tag=release['tag'])
                        
                    if revision!=None:
                        self.VERSION_CODE=revision
                        self.save(update_fields=['VERSION_CODE',])
                except Exception as exc:
                    logger.error('Error checking repository: ' + str(exc))
                #process.resume()
        cache.set(key='loading',value=False,timeout=None)
    
    def addressInNetwork(self,ip2check):
        import ipaddress
        "Is an address from the ETH network"
        CIDR=sum([bin(int(x)).count("1") for x in self.ETH_MASK.split(".")])
        host = ipaddress.ip_interface(self.ETH_IP+'/'+str(CIDR))
        return ipaddress.ip_address(ip2check) in host.network.hosts()

    def checkDeniableIPs(self,attempts,hours):
        if self.PROXY_AUTO_DENYIP:
            from utils.combinedLog import CombinedLogParser
            updated=False
            instance=CombinedLogParser()
            for element in instance.getNginxAccessIPs(hours=int(hours),codemin=400):
                if element['trials']>=attempts and not self.addressInNetwork(ip2check=element['IP']):
                    from utils.Nginx import NginxManager
                    if NginxManager.blockIP(IP=element['IP'])!=-1:
                        updated=True
            if updated:
                NginxManager.reload()
    @staticmethod
    def update_hostapd(WIFI_SSID,WIFI_PASSW,updated):
        from .constants import HOSTAPD_CONF_PATH,HOSTAPD_GENERIC_CONF_PATH
        try:
            f1 = open(HOSTAPD_GENERIC_CONF_PATH, 'r') 
            open(HOSTAPD_CONF_PATH, 'w').close()  # deletes the contents
            f2 = open(HOSTAPD_CONF_PATH, 'w')    
        except:
            text=_('Error opening the file ') + HOSTAPD_CONF_PATH
            PublishEvent(Severity=2,Text=text,Persistent=True,Code='FileIOError-0')
            return
           
        for line in f1:
            f2.write(line.replace('WIFI_SSID', WIFI_SSID)
                            .replace('WIFI_PASSW', WIFI_PASSW))
            
        f1.close()
        f2.close()
        
        if 'WIFI_SSID' in updated:
            text='Modified Hostapd field WIFI_SSID to ' + str(WIFI_SSID)
            PublishEvent(Severity=0,Text=text,Persistent=True,Code='Hostapd-WIFI_SSID')
        if 'WIFI_PASSW' in updated:
            text='Modified Hostapd field WIFI_PASSW to ' + str(WIFI_PASSW)
            PublishEvent(Severity=0,Text=text,Persistent=True,Code='Hostapd-WIFI_PASSW')

    @staticmethod
    def execute_certbot():
        from subprocess import Popen, PIPE
        from .constants import CERTBOT_PATH
        cmd='sudo ' + CERTBOT_PATH + ' --nginx --no-self-upgrade'
        process = Popen(cmd, shell=True,
                        stdout=PIPE,stdin=PIPE, stderr=PIPE,universal_newlines=True)
        stdout, err = process.communicate(input='1')

        if 'Some challenges have failed.' in err:
            text=_('Some challenge failed. Check that the domain is directed to the WAN IP and the port 80 is directed to the DIY4dot0 server')
            PublishEvent(Severity=0,Text=text,Persistent=True,Code='Certbot-Fail')
            
    @staticmethod
    def update_interfaces(ETH_DHCP,ETH_IP,ETH_MASK,ETH_GATE,WIFI_IP,WIFI_MASK,WIFI_GATE,updated):
        from .constants import INTERFACES_CONF_PATH,INTERFACES_GENERIC_CONF_PATH
        try:
            f1 = open(INTERFACES_GENERIC_CONF_PATH, 'r') 
            open(INTERFACES_CONF_PATH, 'w').close()  # deletes the contents
            f2 = open(INTERFACES_CONF_PATH, 'w')    
        except:
            text=_('Error opening the file ') + INTERFACES_CONF_PATH
            PublishEvent(Severity=2,Text=text,Persistent=True,Code='FileIOError-0')
            return
        
        if not ETH_DHCP:
            for line in f1:
                f2.write(line.replace('ETH_IP', ETH_IP)
                                .replace('ETH_MASK', ETH_MASK)
                                .replace('ETH_GATE', ETH_GATE)
                                .replace('WIFI_IP', WIFI_IP)
                                .replace('WIFI_MASK', WIFI_MASK)
                                .replace('WIFI_GATE', WIFI_GATE))
        else:
            for line in f1:
                f2.write(line.replace('iface eth0 inet static', 'iface eth0 inet dhcp')
                                .replace('address ETH_IP', '')
                                .replace('netmask ETH_MASK', '')
                                .replace('gateway ETH_GATE', '')
                                .replace('WIFI_IP', WIFI_IP)
                                .replace('WIFI_MASK', WIFI_MASK)
                                .replace('WIFI_GATE', WIFI_GATE))
                    
        f1.close()
        f2.close()
        
        if ('ETH_DHCP' in updated) or ('ETH_IP' in updated) or ('ETH_MASK' in updated) or ('ETH_GATE' in updated):
            text='Reconfiguring LAN interface eth0'
            PublishEvent(Severity=0,Text=text,Persistent=False,Code='Interfaces-ETH_ETH0')
            #os.system('sudo ip addr flush eth0')
            #os.system('sudo systemctl restart networking')
        if ('WIFI_IP' in updated) or ('WIFI_MASK' in updated) or ('WIFI_GATE' in updated):
            text='Reconfiguring WIFI interface wlan0'
            PublishEvent(Severity=0,Text=text,Persistent=False,Code='Interfaces-ETH_WLAN0')
            #os.system('sudo ip addr flush wlan0')
            #os.system('sudo systemctl restart networking')
             
        if 'ETH_DHCP' in updated:
            text='Modified Interfaces field ETH_DHCP to ' + str(ETH_DHCP)
            PublishEvent(Severity=0,Text=text,Persistent=True,Code='Interfaces-ETH_DHCP')
        if 'ETH_IP' in updated:
            text='Modified Interfaces field ETH_IP to ' + str(ETH_IP)
            PublishEvent(Severity=0,Text=text,Persistent=True,Code='Interfaces-ETH_IP')
        if 'ETH_MASK' in updated:
            text='Modified Interfaces field ETH_MASK to ' + str(ETH_MASK)
            PublishEvent(Severity=0,Text=text,Persistent=True,Code='Interfaces-ETH_MASK')
        if 'ETH_GATE' in updated:
            text='Modified Interfaces field ETH_GATE to ' + str(ETH_GATE)
            PublishEvent(Severity=0,Text=text,Persistent=True,Code='Interfaces-ETH_GATE')
        if 'WIFI_IP' in updated:
            text='Modified Interfaces field WIFI_IP to ' + str(WIFI_IP)
            PublishEvent(Severity=0,Text=text,Persistent=True,Code='Interfaces-WIFI_IP')
        if 'WIFI_MASK' in updated:
            text='Modified Interfaces field WIFI_MASK to ' + str(WIFI_MASK)
            PublishEvent(Severity=0,Text=text,Persistent=True,Code='Interfaces-WIFI_MASK')
        if 'WIFI_GATE' in updated:
            text='Modified Interfaces field WIFI_GATE to ' + str(WIFI_GATE)
            PublishEvent(Severity=0,Text=text,Persistent=True,Code='Interfaces-WIFI_GATE')
            
    def applyChanges(self,update_fields):
        from django.core.cache import cache
        cache.set(key='loading',value=True,timeout=60)
        if ('SITE_DNS' in update_fields):
            SiteSettings.execute_certbot()
            
        if ('SITE_DNS' in update_fields) or ('ETH_IP' in update_fields):
            # update /etc/nginx/sites-available/HomeAutomation.nginxconf
            from utils.Nginx import NginxManager
            NginxManager.editConfigFile(SITE_DNS=getattr(self,'SITE_DNS'),ETH_IP=getattr(self,'ETH_IP')) # yet does not work, it does not write the file
            NginxManager.reload()
            # update allowed_hosts in settings.local.env
            from .constants import LOCALENV_PATH
            self.editUniqueKeyedFile(path=LOCALENV_PATH,key='ALLOWED_HOSTS',delimiter='=',
                                     newValue=getattr(self,'SITE_DNS')+','+getattr(self,'ETH_IP')+',127.0.0.1',
                                     endChar='\n',addKey=True)
        
        if (('ETH_DHCP' in update_fields) or ('ETH_IP' in update_fields) or ('ETH_MASK' in update_fields) or ('ETH_GATE' in update_fields) or
            ('WIFI_IP' in update_fields) or ('WIFI_MASK' in update_fields) or ('WIFI_GATE' in update_fields)):
            SiteSettings.update_interfaces(ETH_DHCP=getattr(self,'ETH_DHCP'),
                                            ETH_IP=getattr(self,'ETH_IP'),ETH_MASK=getattr(self,'ETH_MASK'),
                                           ETH_GATE=getattr(self,'ETH_GATE'),WIFI_IP=getattr(self,'WIFI_IP'),
                                           WIFI_MASK=getattr(self,'WIFI_MASK'),WIFI_GATE=getattr(self,'WIFI_GATE'),
                                           updated=update_fields)
        
        if ('WIFI_SSID' in update_fields) or ('WIFI_PASSW' in update_fields):
            SiteSettings.update_hostapd(WIFI_SSID=getattr(self,'WIFI_SSID'),WIFI_PASSW=getattr(self,'WIFI_PASSW')
                                    ,updated=update_fields)
        # update /etc/nginx/sites-available/HomeAutomation.nginxconf
        if ('PROXY_CREDENTIALS' in update_fields):
            from utils.Nginx import NginxManager
            NginxManager.setProxyCredential(PROXY_CREDENTIALS=getattr(self,'PROXY_CREDENTIALS'))
            NginxManager.reload()
                
        if (('PROXY_USER1' in update_fields) or ('PROXY_PASSW1' in update_fields) or
            ('PROXY_USER2' in update_fields) or ('PROXY_PASSW2' in update_fields)):
            if getattr(self,'PROXY_CREDENTIALS'):
                from utils.Nginx import NginxManager
                NginxManager.createUser(user=self.PROXY_USER1,passw=self.PROXY_PASSW1,firstUser=True)
                NginxManager.createUser(user=self.PROXY_USER2,passw=self.PROXY_PASSW2,firstUser=False)
                NginxManager.reload()
        
        if ('VERSION_DEVELOPER' in update_fields):
            self.checkRepository(force=True)
        
        for field in update_fields:
            if field in ['TELEGRAM_TOKEN','IBERDROLA_USER','IBERDROLA_PASSW','OWM_TOKEN','ESIOS_TOKEN']:
                value=getattr(self,field).strip()
                if value!='':
                    # update TELEGRAM_TOKEN in settings.local.env
                    from .constants import LOCALENV_PATH
                    self.editUniqueKeyedFile(path=LOCALENV_PATH,key=field,delimiter='=',
                                             newValue=value,
                                             endChar='\n',addKey=True)
        
        cache.set(key='loading',value=False,timeout=None)
        
    @staticmethod
    def editKeyedFile(path,key,newValue,endChar=' ',nextLine=True):
        '''
            :param key: determines the text to look for the place to write 
            :param nextLine: determines if once the key is found, it is the next line where it should write 
        '''
        try:
            file = open(path, 'r') 
        except:
            text=_('Error opening the file ') + path
            PublishEvent(Severity=2,Text=text,Persistent=True,Code='FileIOError-0')
        
        lines=file.readlines()
        if len(lines)>0:
            keyFound=False
            for i,line in enumerate(lines):
                if key in line or keyFound:
                    if not nextLine:
                        lines[i]=newValue+key+endChar
                        keyFound=False
                    elif keyFound:
                        lines[i]=newValue+endChar
                        keyFound=False
                    else:
                        keyFound=True
        fileString=''.join(lines)
        file.close()
        from subprocess import Popen, PIPE
        cmd="echo '"+fileString+"' | sudo tee "+ path
        process = Popen(cmd, shell=True,
                    stdout=PIPE,stdin=PIPE, stderr=PIPE,universal_newlines=True)
        stdout, err = process.communicate()
        if err=='':
            text='The key '+key+' on the file ' + path+ ' has been modified to ' +newValue
            severity=0
        else:
            text='Error updating key ' + key+ 'on the file ' + path+ 'Error: ' + err
            severity=3
        PublishEvent(Severity=severity,Text=text,Persistent=True,Code='EditFile-'+key)
    
    @staticmethod
    def editUniqueKeyedFile(path,key,delimiter,newValue,endChar='',addKey=True):
        try:
            file = open(path, 'r') 
        except:
            text=_('Error opening the file ') + path
            PublishEvent(Severity=2,Text=text,Persistent=True,Code='FileIOError-0')
        
        lines=file.readlines()
        if len(lines)>0:
            keyFound=False
            for i,line in enumerate(lines):
                contents=line.split(delimiter)
                if len(contents)==2:
                    thisKey=contents[0]
                    if thisKey==key:
                        keyFound=True
                        lines[i]=key+delimiter+newValue+endChar
            if not keyFound and addKey:
                if not '\n' in lines[-1]:
                    lines[-1]=lines[-1]+'\n'
                lines.append(key+delimiter+newValue+endChar)
                
        fileString=''.join(lines)
        file.close()
        from subprocess import Popen, PIPE
        cmd="echo '"+fileString+"' | sudo tee "+ path
        #logger.info(cmd)
        process = Popen(cmd, shell=True,
                    stdout=PIPE,stdin=PIPE, stderr=PIPE,universal_newlines=True)
        stdout, err = process.communicate()
        if err=='':
            text='The key '+key+' on the file ' + path+ ' has been modified to ' +newValue
            severity=0
        else:
            text='Error updating key ' + key+ ' on the file ' + path+ 'Error: ' + err
            severity=3
        PublishEvent(Severity=severity,Text=text,Persistent=True,Code='EditFile-'+key)

@receiver(post_save, sender=SiteSettings, dispatch_uid="update_SiteSettings")
def update_SiteSettings(sender, instance, update_fields,**kwargs):
    pass
         
    
class Permissions(models.Model):
    class Meta:
        verbose_name = _('Permission')
        verbose_name_plural = _('Permissions') 
        permissions = (
            ("view_heating_subsystem", "Can view the Heating subsystem"),
            ("view_garden_subsystem", "Can view the Garden subsystem"),
            ("view_access_subsystem", "Can view the Access subsystem"),
            ("view_user_track", "Can view the position of the tracked users"),
            ("reset_system", "Can force a reset of the system"),
            ("check_updates", "Can check for updates of the system"),
            ("view_devicesapp", "Can view the devicesAPP"),
            ("view_reportingapp", "Can view the reportingAPP"),
            ("view_subsystemsapp", "Can view the subsystemsAPP"),
            ("view_configurationapp", "Can access to the configurationAPP"),
            ("change_automationvar", "Can change the value of an automation variable"),
        )
        
class Subsystems(models.Model):
    class Meta:
        verbose_name = _('Subsystem')
        verbose_name_plural = _('Subsystems') 

    content_type = models.ForeignKey(ContentType)
    object_id = models.CharField(max_length=50)
    content_object = GenericForeignKey('content_type', 'object_id')
    Name = models.PositiveSmallIntegerField(choices=SUBSYSTEMS_CHOICES)

    @staticmethod
    def getName2Display(Name):
        for name in SUBSYSTEMS_CHOICES:
            if name[0]==Name:
                return name[1]
        return None
    
    def __str__(self):
        return self.get_Name_display()
    
class AdditionalCalculations(models.Model):
    class Meta:
        verbose_name = _('Additional calculation')
        verbose_name_plural = _('Additional calculations')
    
    TIMESPAN_CHOICES=(
        (0,_('An hour')),
        (1,_('A day')),
        (2,_('A week')),
        (3,_('A month')),
    )
    
    PERIODICITY_CHOICES=(
        (0,_('With every new value')),
        (1,_('Every hour')),
        (2,_('Every day at 0h')),
        (3,_('Every week')),
        (4,_('Every month')),
    )
      
    CALCULATION_CHOICES=(
        (0,_('Duty cycle OFF')),
        (1,_('Duty cycle ON')),
        (2,_('Mean value')),
        (3,_('Max value')),
        (4,_('Min value')),
        (5,_('Cummulative sum')),
        (6,_('Integral over time')),
        (7,_('Operation with two variables')),
    )
    
    TWOVARS_OPERATION_CHOICES=(
        (0,_('Sum')),
        (1,_('Substraction')),
        (2,_('Product')),
        (3,_('Division')),
        (4,_('Sum then sum')),
        (5,_('Product then sum')),
    )
    
    SinkVar= models.ForeignKey('MainAPP.AutomationVariables',on_delete=models.CASCADE,related_name='sinkvar',blank=True,null=True) # variable that holds the calculation
    SourceVar= models.ForeignKey('MainAPP.AutomationVariables',on_delete=models.DO_NOTHING,related_name='sourcevar') # variable whose change triggers the calculation
    Scale=models.FloatField(help_text=_('Constant to multiply the result of the calculation'),default=1)
    Timespan= models.PositiveSmallIntegerField(help_text=_('What is the time span for the calculation'),choices=TIMESPAN_CHOICES,default=1)
    Periodicity= models.PositiveSmallIntegerField(help_text=_('How often the calculation will be updated'),choices=PERIODICITY_CHOICES)
    Calculation= models.PositiveSmallIntegerField(choices=CALCULATION_CHOICES)
    Delay= models.PositiveSmallIntegerField(help_text=_('What is the delay (in hours) for the calculation from 00:00 h'),default=0,validators=[MinValueValidator(0),MaxValueValidator(23)])
    
    Miscelaneous = models.CharField(max_length=1000,blank=True,null=True) # field that gathers data in json for calculations on more variables
    
    def __init__(self,*args,**kwargs):
        try:
            self.df=kwargs.pop('df')
            self.key=kwargs.pop('key')
        except:
            self.df=pd.DataFrame()
            self.key=''
  
        super(AdditionalCalculations, self).__init__(*args, **kwargs)
      
    def store2DB(self):
        from DevicesAPP.constants import DTYPE_FLOAT
        label= str(self)
        if self.SinkVar:
            sinkVAR=self.SinkVar
            if self.Calculation==7: # it is a two var calculation
                Misc=json.loads(self.Miscelaneous)
                sinkVAR.updateLabel(label)
                sinkVAR.updateUnits(Misc['Units'])
            else:
                sinkVAR.updateLabel(label)
        else:
            if not self.Calculation in [0,1,7]: # it is not a duty calculation nor a two var calc
                data={'Label':label,'Value':0,'DataType':DTYPE_FLOAT,'Units':self.SourceVar.Units,'UserEditable':False}
            elif self.Calculation==7: # it is a two var calculation
                Misc=json.loads(self.Miscelaneous)
                data={'Label':label,'Value':0,'DataType':DTYPE_FLOAT,'Units':Misc['Units'],'UserEditable':False}
            else:
                data={'Label':label,'Value':0,'DataType':DTYPE_FLOAT,'Units':'%','UserEditable':False}
            MainAPP.signals.SignalCreateMainDeviceVars.send(sender=None,Data=data)
            sinkVAR=AutomationVariables.objects.get(Label=label)
        self.SinkVar=sinkVAR
        try:
            self.save()
        except OperationalError:
            logger.error("Operational error on Django. System restarted")
            import os
            os.system("sudo reboot")
        
         
    def __str__(self):
        try:
            if self.Calculation!=7:
                return str(self.get_Calculation_display())+'('+self.SourceVar.Label + ')'
            else:
                Misc=json.loads(self.Miscelaneous)
                AVAR=AutomationVariables.objects.get(pk=int(Misc['SourceVar2']))
                operation=str(self.TWOVARS_OPERATION_CHOICES[int(Misc['TwoVarsOperation'])][1])
                return operation+'('+self.SourceVar.Label +' vs ' +AVAR.Label+')'
        except:
            return self.key
      
    def checkTrigger(self):
#         if self.Calculation==7:
#             return True
        if self.Periodicity==0:
            return False
        else:
            import datetime
            now=datetime.datetime.now()
            if self.Periodicity==1 and now.minute==0: # hourly calculation launched at minute XX:00
                return True
            elif now.hour==self.Delay and now.minute==0:
                if self.Periodicity==2: # daily calculation launched on next day at 00:00
                    return True
                elif self.Periodicity==3 and now.weekday()==0: # weekly calculation launched on Monday at 00:00
                    return True
                elif self.Periodicity==4 and now.day==1: # monthly calculation launched on 1st day at 00:00
                    return True
        return False
    
    def initializeDB(self):
        import datetime
        import calendar
        import pytz
        from tzlocal import get_localzone
        local_tz=get_localzone()
        localdate = local_tz.localize(datetime.datetime.now())
                    
        now=datetime.datetime.now()
        start_date = '01-01-' + str(now.year)+' 00:00:00'
        date_format = '%d-%m-%Y %H:%M:%S'
        if self.Timespan==0: # Every hour
            offset=datetime.timedelta(hours=1)        
        elif self.Timespan==1: # Every day
            offset=datetime.timedelta(hours=24)
        elif self.Timespan==2: # Every week
            offset=datetime.timedelta(weeks=1)
        elif self.Timespan==3: # Every month
            days=calendar.monthrange(now.year, 1)[1]
            offset=datetime.timedelta(hours=days*24)
        else:
            return
        
        toDate=pytz.utc.localize(datetime.datetime.strptime(start_date, date_format))+offset-localdate.utcoffset() 
        
        while toDate<=pytz.utc.localize(datetime.datetime.now()):
            now=toDate
            if self.Timespan==0: # Every hour
                offset=datetime.timedelta(hours=1)   
            elif self.Timespan==1: # Every day
                offset=datetime.timedelta(hours=24)
            elif self.Timespan==2: # Every week
                offset=datetime.timedelta(weeks=1)
            elif self.Timespan==3: # Every month
                days=calendar.monthrange(now.year, now.month)[1]
                offset=datetime.timedelta(hours=days*24)
            try:
                self.calculate(toDate=toDate)
            except Exception as exc:
                logger.error(str(exc))
                return
            toDate=toDate+offset
        
    def calculate(self,DBDate=None,toDate=None):
        import datetime
        import calendar

        if toDate==None:
            toDate=timezone.now()-datetime.timedelta(hours=self.Delay)
            now=datetime.datetime.now()
        else:
            now=toDate
        #toDate=datetime.datetime(year=2019,month=4,day=7)
        
        if self.Timespan==0: # Every hour
            offset=datetime.timedelta(hours=1)
        elif self.Timespan==1: # Every day
            offset=datetime.timedelta(hours=24)
        elif self.Timespan==2: # Every week
            offset=datetime.timedelta(weeks=1)
        elif self.Timespan==3: # Every month           
            days=calendar.monthrange(now.year, now.month)[1]
            offset=datetime.timedelta(hours=days*24)
        else:
            return
            
        fromDate=toDate-offset
        if DBDate==None:
            DBDate=toDate-offset/2
        
        toDate=toDate-datetime.timedelta(minutes=1)
        query=self.SourceVar.getQuery(fromDate=fromDate,toDate=toDate)
        self.df=pd.read_sql_query(sql=query['sql'],con=query['conn'],index_col='timestamp')
        if not self.df.empty:
            self.key=self.SourceVar.Tag
            # TO FORCE THAT THE INITIAL ROW CONTAINS THE INITIAL DATE
            addedtime=pd.to_datetime(arg=self.df.index.values[0])-fromDate.replace(tzinfo=None)
            if addedtime>datetime.timedelta(minutes=1):
                ts = pd.to_datetime(fromDate.replace(tzinfo=None))
                new_row = pd.DataFrame([[self.df[self.key].iloc[0]]], columns = [self.key], index=[ts])
                self.df=pd.concat([pd.DataFrame(new_row),self.df], ignore_index=False)
                  
            # TO FORCE THAT THE LAST ROW CONTAINS THE END DATE
            addedtime=toDate.replace(tzinfo=None)-pd.to_datetime(arg=self.df.index.values[-1])
            if addedtime>datetime.timedelta(minutes=1):
                ts = pd.to_datetime(toDate.replace(tzinfo=None))
                new_row = pd.DataFrame([[self.df[self.key].iloc[-1]]], columns = [self.key], index=[ts])
                self.df=pd.concat([self.df,pd.DataFrame(new_row)], ignore_index=False)
              
            # RESAMPLING DATA TO 1 MINUTE RESOLUTION AND INTERPOLATING VALUES
            df_resampled=self.df.resample('1T').mean()
            self.df_interpolated=df_resampled.interpolate(method='zero')
                      
            if self.Calculation==0:     # Duty cycle OFF
                result= self.duty(level=False)*self.Scale
            if self.Calculation==1:     # Duty cycle ON
                result= self.duty(level=True)*self.Scale
            elif self.Calculation==2:   # Mean value
                result= self.df_interpolated.mean()[0]*self.Scale
            elif self.Calculation==3:   # Max value
                result= self.df.max()[0]*self.Scale
            elif self.Calculation==4:   # Min value
                result= self.df.min()[0]*self.Scale
            elif self.Calculation==5:   # Cummulative sum
                result= self.df[self.key].cumsum().iloc[-1]*self.Scale
            elif self.Calculation==6:   # integral over time
                from scipy import integrate
                result=integrate.trapz(y=self.df_interpolated[self.key], x=self.df_interpolated[self.key].index.astype(np.int64) / 10**9)*self.Scale
            elif self.Calculation==7:   # two var calculation
                Misc=json.loads(self.Miscelaneous)
                var2_pk=Misc['SourceVar2']
                TwoVarsOperation=Misc['TwoVarsOperation']
                VAR2=AutomationVariables.objects.get(pk=int(var2_pk))
                query=VAR2.getQuery(fromDate=fromDate,toDate=toDate)
                self.df[VAR2.Tag]=pd.read_sql_query(sql=query['sql'],con=query['conn'],index_col='timestamp')
                self.df=self.df.fillna(method='ffill').fillna(method='bfill')
                if int(TwoVarsOperation)==0: # sum
                    self.df['result']=self.df[self.key]+self.df[VAR2.Tag]
                    result=(self.df['result']*self.Scale).to_frame()
                elif int(TwoVarsOperation)==1: # substraction
                    self.df['result']=self.df[self.key]-self.df[VAR2.Tag]
                    result=(self.df['result']*self.Scale).to_frame()
                elif int(TwoVarsOperation)==2: # product
                    self.df['result']=self.df[self.key]*self.df[VAR2.Tag]
                    result=(self.df['result']*self.Scale).to_frame()
                elif int(TwoVarsOperation)==3: # division
                    self.df['result']=self.df[self.key]/self.df[VAR2.Tag]
                    result=(self.df['result']*self.Scale).to_frame()
                elif int(TwoVarsOperation)==4: # sum then sum
                    self.df['result']=self.df[self.key]+self.df[VAR2.Tag]
                    result=self.df['result'].sum()*self.Scale
                elif int(TwoVarsOperation)==5: # product then sum
                    self.df['result']=self.df[self.key]*self.df[VAR2.Tag]
                    result=self.df['result'].sum()*self.Scale
        else:
            if self.Calculation<=1:     # Duty cycle OFF,ON
                result=0
            else:
                result= None
        
        if not isinstance(result, pd.DataFrame):
            MainAPP.signals.SignalUpdateValueMainDeviceVars.send(sender=None,Tag=self.SinkVar.Tag,timestamp=DBDate,
                                                                 newValue=result,force=True)
        else:
            for index, row in result.iterrows():
                MainAPP.signals.SignalUpdateValueMainDeviceVars.send(sender=None,Tag=self.SinkVar.Tag,timestamp=index.to_pydatetime(),
                                                                 newValue=float(row[0]),force=True)
                
        return result
              
    def duty(self,level=False,decimals=2,absoluteValue=False):
        if not self.df.empty:
            totalTime=(self.df.iloc[-1].name-self.df.iloc[0].name)
            totalTime=totalTime.days*86400+totalTime.seconds
            value=next(self.df.iterrows())[1]
            if not isinstance(value[0], list):
                time=0
                islist=False
            else:
                time=[]
                for data in value[0]:
                    time.append(0)
                islist=True
                      
            previousDate=self.df.index.values[0]
            for index, row in self.df.iterrows():
                date=row.name
                sampletime=date-previousDate
                if not islist:
                    time+=int(row[self.key]==level)*(sampletime.days*86400+sampletime.seconds)
                else:
                    for i,data in enumerate(row[self.key]):
                        time[i]+=int(data==level)*(sampletime.days*86400+sampletime.seconds)
                previousDate=date
                      
            if absoluteValue==True:
                return time
            else:
                if not islist:
                    return round(time/totalTime*100,decimals)
                else:
                    return [round(x/totalTime*100,decimals) for x in time]
        else:
            return None
  

@receiver(post_save, sender=AdditionalCalculations, dispatch_uid="update_AdditionalCalculations")
def update_AdditionalCalculations(sender, instance, update_fields,**kwargs):
    if not kwargs['created']:   # an instance has been modified
        pass
            
@receiver(post_delete, sender=AdditionalCalculations, dispatch_uid="postdelete_AdditionalCalculations")
def predelete_AdditionalCalculations(sender, instance, **kwargs):   
    MainAPP.signals.SignalDeleteMainDeviceVars.send(sender=AdditionalCalculations,Tag=instance.SinkVar.Tag)


class AutomationVariables(models.Model):
    class Meta:
        unique_together = ('Tag','BitPos','Table')
        verbose_name = _('Automation variable')
        verbose_name_plural = _('Automation variables')
        
    Label = models.CharField(max_length=150)
    Tag = models.CharField(max_length=50)
    Device = models.CharField(max_length=50)
    Table = models.CharField(max_length=50)
    BitPos = models.PositiveSmallIntegerField(null=True,blank=True)
    Sample = models.PositiveSmallIntegerField(default=0)
    Units = models.CharField(max_length=10,help_text=str(_('Units of the variable.')),blank=True,null=True)
    UserEditable = models.BooleanField(default=True)
    OverrideTime = models.PositiveSmallIntegerField(default=3600)
    Tendency = models.SmallIntegerField(null=True,blank=True,default=0)
    numSamples = models.PositiveSmallIntegerField(default=2,validators=[MinValueValidator(1),])
    CalculateDuty = models.BooleanField(default=False)
    Subsystem = GenericRelation(Subsystems,related_query_name='automationvariables')
    
    def __str__(self):
        return self.Label
    
    def store2DB(self):
        self.full_clean()
        try:
            super().save()
        except OperationalError:
            logger.error("Operational error on Django. System restarted")
            import os
            os.system("sudo reboot") 
    
    def updateLabel(self,newLabel):
        self.Label=newLabel
        self.save(update_fields=['Label'])
        MainAPP.signals.SignalAutomationVariablesUpdated.send(sender=None,**{"Tag":self.Tag,"Label":self.Label,
                                                                             "Device":self.Device,"Units":self.Units})
    
    def updateUnits(self,newUnits):
        self.Units=newUnits
        self.save(update_fields=['Units'])
        MainAPP.signals.SignalAutomationVariablesUpdated.send(sender=None,**{"Tag":self.Tag,"Label":self.Label,
                                                                             "Device":self.Device,"Units":self.Units})
            
    def calculateDuty(self):
        #logger.info("Enters calculateDuty for var "+str(self))
        if self.CalculateDuty:
            sql='SELECT a.* FROM "*table*" AS a WHERE a."*tag*" == *value* ORDER BY a.timestamp DESC LIMIT 2'
            from utils.BBDD import getRegistersDBInstance
            DB=getRegistersDBInstance()
            now=DB.executeTransaction(SQLstatement=sql.replace("*table*",self.Table)
                                                        .replace("*value*",self.getLatestValueString())
                                                        .replace("*tag*",self.Tag)
                                                        )
            if now != []:
                now=now[0][0]
                prevValue=int(not self.getLatestValue())
                prev=DB.executeTransaction(SQLstatement=sql.replace("*table*",self.Table)
                                                        .replace("*value*",str(prevValue))
                                                        .replace("*tag*",self.Tag)
                                                        )
                if prev != []:
                    try:
                        prev=prev[1][0]
                    except:
                        prev=prev[0][0]
                
                    seg=(now-prev).seconds
                    dias=(now-prev).days
                    horas=0
                    mins=0
                    if seg/60>=1:
                        mins=int(seg/60)
                        seg=seg-mins*60
                        if mins/60>=1:
                            horas=int(mins/60)
                            mins=mins-horas*60
                    if dias!=0:
                        text=str(_('The variable "%s" has kept the value of %i during %id and %ih')) % (self.Label,prevValue,dias,horas)
                    elif horas!=0 and mins!=0 and seg!=0:
                        text=str(_('The variable "%s" has kept the value of %i during %ih, %im and %is')) % (self.Label,prevValue,horas,mins,seg)
                    elif horas==0 and mins!=0:
                        text=str(_('The variable "%s" has kept the value of %i during %im and %is')) % (self.Label,prevValue,mins,seg)
                    else:
                        text=str(_('The variable "%s" has kept the value of %i during %is')) % (self.Label,prevValue,seg)
                    PublishEvent(Severity=0,Text=text,Code=str(self.pk)+'duty'+str(prevValue),Webpush=True)
        
    def checkAdditionalCalculations(self):
        ACALCs=AdditionalCalculations.objects.filter(SourceVar=self,Periodicity=0)
        now=timezone.now()
        for ACALC in ACALCs:
            ACALC.calculate(DBDate=now)
        
    def updateValue(self,newValue=None,overrideTime=None,force=None):
        if self.UserEditable:
            MainAPP.signals.SignalToggleAVAR.send(sender=None,Tag=self.Tag,Device=self.Device,newValue=newValue,force=force)
            #logger.info("About to Override variable "+ str(self) + " for " + str(overrideTime) + " seconds to the value " + str(newValue))
            if overrideTime!=None:
                AutomationVarWeeklySchedules.override(var=self,value=True,duration=overrideTime)
        
    def checkSubsystem(self,Name):
        SSYTMs=Subsystems.objects.filter(automationvariables=self)
        exist=False
        if SSYTMs.count():
            for SSYTM in SSYTMs:
                if SSYTM.Name==Name:
                    exist=True
                    break
        return exist
        
    def createSubsystem(self,Name):
        if not self.checkSubsystem(Name=Name):
            subsystem=Subsystems(Name=Name,content_object=self)
            subsystem.save()
        
    def getLatestData(self,localized=True):
        Data={}
        name=self.Tag
        Data[name]={}
        table=self.Table
        vars='"timestamp","'+name+'"'
        sql='SELECT '+vars+' FROM "'+ table +'" WHERE "'+name +'" not null ORDER BY timestamp DESC LIMIT 1'
        from utils.BBDD import getRegistersDBInstance
        DB=getRegistersDBInstance()
        row=DB.executeTransaction(SQLstatement=sql)
        if row != []:
            row=row[0]
            timestamp=row[0]
            if self.BitPos!=None:
                from utils.dataMangling import checkBit
                row=checkBit(number=row[1],position=self.BitPos)
            else:
                row=row[1]
        else:
            timestamp=None
            row=None
        if localized and timestamp!=None:
            from tzlocal import get_localzone
            local_tz=get_localzone()
            timestamp = local_tz.localize(timestamp)
            timestamp=timestamp+timestamp.utcoffset() 
        Data[name]['timestamp']=timestamp
        Data[name]['value']=row
        Data[name]['label']=self.Label
        return Data
    
    def getCurrentData(self,localized=True):
        Data={}
        name=self.Tag
        Data[name]={}
        now=timezone.now()
        rows=self.getValues(fromDate=now-datetime.timedelta(hours=1),
                           toDate=now,localized=False)

        if type(rows) is list and rows!=[]:
            row=rows[-1]
        else:
            row=[]
            
        if row != []:
            timestamp=row[0]
            if self.BitPos!=None:
                from utils.dataMangling import checkBit
                try:
                    row=checkBit(number=row[1],position=self.BitPos)
                except:
                    row=None
            else:
                row=row[1]
        else:
            timestamp=None
            row=None
        if localized and timestamp!=None:
            from tzlocal import get_localzone
            local_tz=get_localzone()
            timestamp = local_tz.localize(timestamp)
            timestamp=timestamp+timestamp.utcoffset() 
        Data[name]['timestamp']=timestamp
        Data[name]['value']=row
        Data[name]['label']=self.Label
        return Data
    
    def getLatestValue(self):
        data=self.getLatestData()
        return data[self.Tag]['value']
    
    def getLatestValueString(self):
        value=self.getLatestValue()
        if value!=None:
            return str(value)
        else:
            return str(5)
         
    def getValues(self,fromDate=None,toDate=None,number=None,localized=True):
        from utils.BBDD import getRegistersDBInstance
        DB=getRegistersDBInstance()
        if fromDate!=None and toDate!=None:
            sql='SELECT timestamp,"'+self.Tag+'" FROM "'+ self.Table +'" WHERE timestamp BETWEEN "' + str(fromDate).split('+')[0]+'" AND "'+str(toDate).split('+')[0] + '" ORDER BY timestamp ASC'
        elif number!=None:
            sql='SELECT timestamp,"'+self.Tag+'" FROM "'+ self.Table +'" WHERE "'+self.Tag +'" not null ORDER BY timestamp DESC LIMIT '+ str(number)
        else:
            return None
        data_rows=DB.executeTransaction(SQLstatement=sql)
        if localized and len(data_rows)>0:
            from tzlocal import get_localzone
            local_tz=get_localzone()
            for row in data_rows:
                row=list(row)
                row[0] = local_tz.localize(row[0])
                row[0]=row[0]+row[0].utcoffset() 
        return data_rows
    
    def setTendency(self):
        numberSamples=self.numSamples
        if self.BitPos==None and self.Table!='inputs' and self.Table!='outputs': #and self.UserEditable:   # the variable is not DIGITAL
            values=self.getValues(number=numberSamples*2)
            if len(values)==numberSamples*2:
                last=0
                first=0
                for i in range(0,numberSamples):
                    last=last+values[i][1]
                    first=first+values[numberSamples+i][1]            
                last=round(last/(numberSamples),1)
                first=round(first/(numberSamples),1)
                if last>first:
                    self.Tendency=1
                elif first>last:
                    self.Tendency=-1
                else:
                    self.Tendency=0
                self.store2DB()
            
    def getQuery(self,fromDate,toDate):
        from utils.BBDD import getRegistersDBInstance
        DB=getRegistersDBInstance()
        sql='SELECT timestamp,"'+self.Tag+'" FROM "'+ self.Table +'" WHERE timestamp BETWEEN "' + str(fromDate).split('+')[0]+'" AND "'+str(toDate).split('+')[0] + '" ORDER BY timestamp ASC'
        return {'conn':DB.getConn(),'sql':sql}
        
    def executeAutomationRules(self):
        rules=RuleItems.objects.filter((Q(Var1=self)) | (Q(Var2=self)))
        if len(rules)>0:
            now=timezone.now()
            for rule in rules:
                #if not '"ActionType": "z"' in rule.Rule.Action:
                rule.Rule.execute()


class AutomationVarWeeklySchedules(models.Model):
    class Meta:
        verbose_name = _('Automation var weekly schedule')
        verbose_name_plural = _('Automation var weekly schedules') 
        unique_together = (('Label', 'Var'))
        permissions = (
            ("view_AutomationVarWeeklySchedules", "Can see available automation schedules"),
            ("activate_AutomationVarWeeklySchedules", "Can change the state of the schedules"),
        )
        
    Label = models.CharField(max_length=100)
    Active = models.BooleanField(default=False)
    Var = models.ForeignKey('MainAPP.AutomationVariables',on_delete=models.CASCADE,limit_choices_to={'UserEditable': True})
    LValue = models.DecimalField(max_digits=6, decimal_places=2)
    HValue = models.DecimalField(max_digits=6, decimal_places=2)
    Overriden = models.BooleanField(default=False)
    Days = models.ManyToManyField('inlineDaily',blank=True)
 
    Subsystem = GenericRelation(Subsystems,related_query_name='weeklyschedules')
    
    def __str__(self):
        return self.Label
    
    def store2DB(self): 
        self.full_clean() 
        try:
            super().save()
        except OperationalError:
            logger.error("Operational error on Django. System restarted")
            import os
            os.system("sudo reboot")
        if self.Active:
            self.checkThis()
            
    def setActive(self,value=True):
        self.Active=value
        self.save()
         
        if self.Active:
            logger.info('Se ha activado la planificacion semanal ' + str(self.Label) + ' para la variable ' + str(self.Var))
            SCHDs=AutomationVarWeeklySchedules.objects.filter(Var=self.Var)
            for SCHD in SCHDs:
                if SCHD.Label!=self.Label:
                    SCHD.setActive(value=False)
            self.checkThis()
         
    def getTodaysPattern(self):
        import datetime
        timestamp=datetime.datetime.now()
        weekDay=timestamp.weekday()
        hour=timestamp.hour
        dailySchedules=self.inlinedaily_set.all()
        pattern=[]
        for daily in dailySchedules:
            if daily.Day==weekDay:
                for i in range(0,24):
                    Setpoint=getattr(daily,'Hour'+str(i))
                    pattern.append(Setpoint)
                return pattern
        return None
         
    def modify(self,value,sense='+'):
        import decimal
        if value=='LValue':
            if sense=='-':
                self.LValue-=decimal.Decimal.from_float(0.5)
            else:
                self.LValue+=decimal.Decimal.from_float(0.5)
            self.save(update_fields=['LValue',])
            self.checkThis()
        elif value=='HValue':
            if sense=='-':
                self.HValue-=decimal.Decimal.from_float(0.5)
            else:
                self.HValue+=decimal.Decimal.from_float(0.5)
            self.save(update_fields=['HValue',])
            self.checkThis()
        elif value=='REFValue':
            if self.Var.getLatestValue()==self.HValue:
                Value=self.LValue
            else:
                Value=self.HValue
            self.Var.updateValue(newValue=float(Value),force=False)
             
    def getFormset(self):
        from django.forms import inlineformset_factory
        AutomationVarWeeklySchedulesFormset = inlineformset_factory (AutomationVarWeeklySchedules,AutomationVarWeeklySchedules,fk_name)
    
    def checkThis(self,init=False):
        timestamp=datetime.datetime.now()
        weekDay=timestamp.weekday()        
        hour=timestamp.hour
        if self.Active and (not self.Overriden):
            dailySchedules=self.inlinedaily_set.all()
            for daily in dailySchedules:
                if daily.Day==weekDay:
                    Setpoint=getattr(daily,'Hour'+str(hour))
                    if Setpoint==0:
                        Value=float(self.LValue)
                    elif Setpoint==1:
                        Value=float(self.HValue)
                    else:
                        text='The schedule ' + self.Label + ' returned a non-understandable setpoint (0=LOW,1=HIGH). It returned ' + str(Setpoint)
                        PublishEvent(Severity=2,Text=text,Persistent=True,Code=self.getEventsCode()+'101')
                        break
                    if self.Var.getLatestValue()!=Value or init:
                        self.Var.updateValue(newValue=Value,force=init)
                    break
    
    @staticmethod
    def override(var,value,duration=3600):
        logger.info('Enters Override for var ' + str(var) + ' with duration ' + str(duration) +' and value '+str(value))
        SCHs=AutomationVarWeeklySchedules.objects.filter(Var=var,Active=True)
        for SCH in SCHs:
            SCH.Overriden=value
            SCH.save()
            PublishEvent(Severity=3,Text="Schedule " + str(SCH)+" is now overriden at time "+str(datetime.datetime.now()),Persistent=True,Code=str(SCH)+'o')
        if value:
            id='Overriding-'+str(var.pk)
            logger.info('Enters Overriding thread ' + id)
            from utils.asynchronous_tasks import BackgroundTimer
            
            Timer=BackgroundTimer(interval=duration,threadName=id,callable=AutomationVarWeeklySchedules.overrideTimeout,callablekwargs={'var':var})

    @staticmethod
    def overrideTimeout(var):
        if var:
            SCHs=AutomationVarWeeklySchedules.objects.filter(Var=var,Active=True)
            for SCH in SCHs:
                SCH.Overriden=False
                SCH.save()
                try:
                    SCHu=AutomationVarWeeklySchedules.objects.get(pk=SCH.pk)    # refreshing the instance
                    SCHu.checkThis()
                except:
                    e = sys.exc_info()[0]
                    PublishEvent(Severity=0,Text="Schedule " + str(SCH)+" failed to be checked. Error: " + str(e),Persistent=True,Code=str(SCH)+'r')
                PublishEvent(Severity=0,Text="Schedule " + str(SCH)+" is now released at time "+str(datetime.datetime.now()),Persistent=True,Code=str(SCH)+'r')
        
    @classmethod
    def initialize(cls):
        schedules=cls.objects.all()
        for schedule in schedules:
            schedule.Overriden=False
            schedule.save()
                        
    @classmethod
    def checkAll(cls,init=False):
        schedules=cls.objects.filter(Active=True)
        for schedule in schedules:
            schedule.checkThis(init=init)


            
@receiver(post_save, sender=AutomationVarWeeklySchedules, dispatch_uid="update_AutomationVarWeeklySchedules")
def update_AutomationVarWeeklySchedules(sender, instance, update_fields,**kwargs):
    timestamp=timezone.now() #para hora con info UTC
    if not kwargs['created']:   # an instance has been modified
        pass
    else:
        logger.info('Se ha creado la planificacion semanal ' + str(instance.Label))


class inlineDaily(models.Model):
    class Meta:
        unique_together = ('Day', 'Weekly')
        verbose_name = _('Automation var hourly schedule')
        verbose_name_plural = _('Automation var hourly schedules')
        
    WEEKDAYS = (
      (0, _("Monday")),
      (1, _("Tuesday")),
      (2, _("Wednesday")),
      (3, _("Thursday")),
      (4, _("Friday")),
      (5, _("Saturday")),
      (6, _("Sunday")),
    )
    STATE_CHOICES=(
        (0,_('LOW')),
        (1,_('HIGH'))
    )
    Day = models.PositiveSmallIntegerField(choices=WEEKDAYS)
    Weekly = models.ForeignKey(AutomationVarWeeklySchedules, on_delete=models.CASCADE)
    Hour0 = models.PositiveSmallIntegerField(choices=STATE_CHOICES,default=0)
    Hour1 = models.PositiveSmallIntegerField(choices=STATE_CHOICES,default=0)
    Hour2 = models.PositiveSmallIntegerField(choices=STATE_CHOICES,default=0)
    Hour3 = models.PositiveSmallIntegerField(choices=STATE_CHOICES,default=0)
    Hour4 = models.PositiveSmallIntegerField(choices=STATE_CHOICES,default=0)
    Hour5 = models.PositiveSmallIntegerField(choices=STATE_CHOICES,default=0)
    Hour6 = models.PositiveSmallIntegerField(choices=STATE_CHOICES,default=0)
    Hour7 = models.PositiveSmallIntegerField(choices=STATE_CHOICES,default=0)
    Hour8 = models.PositiveSmallIntegerField(choices=STATE_CHOICES,default=0)
    Hour9 = models.PositiveSmallIntegerField(choices=STATE_CHOICES,default=0)
    Hour10 = models.PositiveSmallIntegerField(choices=STATE_CHOICES,default=0)
    Hour11 = models.PositiveSmallIntegerField(choices=STATE_CHOICES,default=0)
    Hour12 = models.PositiveSmallIntegerField(choices=STATE_CHOICES,default=0)
    Hour13 = models.PositiveSmallIntegerField(choices=STATE_CHOICES,default=0)
    Hour14 = models.PositiveSmallIntegerField(choices=STATE_CHOICES,default=0)
    Hour15 = models.PositiveSmallIntegerField(choices=STATE_CHOICES,default=0)
    Hour16 = models.PositiveSmallIntegerField(choices=STATE_CHOICES,default=0)
    Hour17 = models.PositiveSmallIntegerField(choices=STATE_CHOICES,default=0)
    Hour18 = models.PositiveSmallIntegerField(choices=STATE_CHOICES,default=0)
    Hour19 = models.PositiveSmallIntegerField(choices=STATE_CHOICES,default=0)
    Hour20 = models.PositiveSmallIntegerField(choices=STATE_CHOICES,default=0)
    Hour21 = models.PositiveSmallIntegerField(choices=STATE_CHOICES,default=0)
    Hour22 = models.PositiveSmallIntegerField(choices=STATE_CHOICES,default=0)
    Hour23 = models.PositiveSmallIntegerField(choices=STATE_CHOICES,default=0)
     
    def __str__(self):
        return self.get_Day_display()
     
    def setInlineHours(self,hours):
        if len(hours)!=24:
            text = "Error in setting an inline. The string passed " +hours + " does not have 24 elements" 
            raise DevicesAppException(text)
        else:
            for i,hour in enumerate(hours):
                if int(hour)>0:
                    setattr(self,'Hour'+str(i),1)
                else:
                    setattr(self,'Hour'+str(i),0)
                    
class Thermostats(models.Model):
    class Meta:
        verbose_name = _('Thermostat')
        verbose_name_plural = _('Thermostats')
     
    RITM = models.OneToOneField('MainAPP.RuleItems',help_text=str(_('The rule item that the thermostat is linked to.')),
                           on_delete=models.CASCADE,related_name='ruleitem2thermostat',unique=True,null=False,blank=False,
                           limit_choices_to={'Var2__UserEditable': True})
    StatusVar = models.ForeignKey('MainAPP.AutomationVariables',on_delete=models.CASCADE,limit_choices_to={'Units': None})
    Inverted = models.BooleanField(default=False)
    
    def __str__(self):
        return str(self.RITM.Rule) + ' - ' + str(self.RITM.Var1) + ' VS ' + str(self.RITM.Var2)
            
        
    
class RuleItems(models.Model):
    PREFIX_CHOICES=(
        ('',''),
        ('not ','NOT'),
    )
    OPERATOR_CHOICES=(
        ('==','=='),
        ('>','>'),
        ('>=','>='),
        ('<','<'),
        ('<=','<='),
        ('!=','!='),
    )
    BOOL_OPERATOR_CHOICES=(
        ('&',_('AND')),
        ('|',_('OR')),
    )
    Rule = models.ForeignKey('MainAPP.AutomationRules', on_delete=models.CASCADE)
    Order = models.PositiveSmallIntegerField(help_text=_('Order of execution'))
    PreVar1 = models.CharField(choices=PREFIX_CHOICES,default='',max_length=3,blank=True)
    Var1= models.ForeignKey(AutomationVariables,related_name='var1')
    Operator12 = models.CharField(choices=OPERATOR_CHOICES+BOOL_OPERATOR_CHOICES,max_length=2)
    PreVar2 = models.CharField(choices=PREFIX_CHOICES,default='',max_length=3,blank=True)
    Var2= models.ForeignKey(AutomationVariables,related_name='var2',blank=True,null=True)
    Var2Hyst= models.FloatField(default=0.5)
    IsConstant = models.BooleanField(default = False)
    Constant = models.FloatField(blank=True,null=True)
    Operator3 = models.CharField(choices=BOOL_OPERATOR_CHOICES,max_length=2,blank=True,null=True)
    
    def __str__(self):
        return str(self.Rule) + '.' + str(self.Order)
    
    def save(self):
        super().save()
        self.createThermostat()
        
    def store2DB(self):
        self.full_clean()
        self.save()
        
    def createThermostat(self):
        
        units1=self.Var1.Units
        try:
            units2=self.Var2.Units
        except:
            units2=None
        
        import json
        action=json.loads(self.Rule.Action)
        if action['ActionType']=='a':
            StatusVar=AutomationVariables.objects.get(Tag=action['IO'],Device='MainGPIOs')
            if (units1=='\u00baC' or units2=='\u00baC') and self.IsConstant==False and self.Var2.UserEditable :
                THRMST,created=Thermostats.objects.get_or_create(RITM=self,StatusVar=StatusVar)
        
    def evaluate(self):
        import datetime
        from utils.dataMangling import checkBit
        now = timezone.now()
        evaluableTRUE=''
        evaluableFALSE=''
        data=self.Var1.getLatestData(localized=True)[self.Var1.Tag]
        timestamp1=data['timestamp']
        value1=data['value']
        
        if self.Var1.Sample>0:
            if value1==None or (now-timestamp1>datetime.timedelta(seconds=int(2.5*self.Var1.Sample))):
                #logger.warning('The rule ' + self.Rule.Identifier + ' was evaluated with data older than expected')
                #logger.warning('    The latest timestamp for the variable ' + str(self.Var1) + ' is ' + str(timestamp1))
                return {'TRUE':eval(str(self.Rule.OnError)),'FALSE':eval('not ' + str(self.Rule.OnError)),'ERROR':'Too old data from var ' + str(self.Var1)}
        
        if self.Var1.BitPos!=None:
            value1=checkBit(number=int(value1),position=self.Var1.BitPos)
         
        if self.Var2!= None:
            data=self.Var2.getLatestData(localized=True)[self.Var2.Tag]
            timestamp2=data['timestamp']
            value2=data['value']
            if self.Var2.Sample>0:
                if value2==None or (now-timestamp2>datetime.timedelta(seconds=int(2.5*self.Var2.Sample))):
                    #logger.warning('The rule ' + self.Rule.Identifier + ' was evaluated with data older than expected')
                    #logger.warning('    The latest timestamp for the variable ' + str(self.Var2) + ' is ' + str(timestamp2))
                    return {'TRUE':eval(str(self.Rule.OnError)),'FALSE':eval('not ' + str(self.Rule.OnError)),'ERROR':'Too old data from var ' + str(self.Var2)}
                    
            if self.Var2.BitPos!=None:
                value2=checkBit(number=int(value2),position=self.Var2.BitPos)
        else:
            value2=self.Constant
                
        if self.Operator12.find('>')>=0:
            histeresisTRUE='+' + str(self.Var2Hyst)
            histeresisFALSE='-' + str(self.Var2Hyst)
        elif self.Operator12.find('<')>=0:
            histeresisTRUE='-' + str(self.Var2Hyst)
            histeresisFALSE='+' + str(self.Var2Hyst)
        else:
            histeresisTRUE=''
            histeresisFALSE=''
        
        if self.Operator12.find('&')>=0 or self.Operator12.find('|')>=0:
            value1=int(value1)
            value2=int(value2)
            
        evaluableTRUE+='('+ self.PreVar1 +' '+str(value1) + ' ' + self.Operator12 + ' ' + self.PreVar2 + str(value2) + histeresisTRUE + ')'
        evaluableFALSE+='not ('+ self.PreVar1 +' '+str(value1) + ' ' + self.Operator12 + ' ' + self.PreVar2 + str(value2) + histeresisFALSE + ')'
        
        try:
            return {'TRUE':eval(evaluableTRUE),'FALSE':eval(evaluableFALSE),'ERROR':''}
        except:
            return {'TRUE':eval(str(self.Rule.OnError)),'FALSE':eval('not ' + str(self.Rule.OnError)),'ERROR':'Unknown'}
            
    class Meta:
        verbose_name = _('Automation expression')
        verbose_name_plural = _('Automation expressions')
                
class AutomationRules(models.Model):
    class Meta:
        verbose_name = _('Automation rule')
        verbose_name_plural = _('Automation rules')
        permissions = (
            ("view_rules", "Can see available automation rules"),
            ("activate_rules", "Can change the state of the rules"),
        )
        
    BOOL_OPERATOR_CHOICES=(
        ('&',_('AND')),
        ('|',_('OR')),
    )
    ONERROR_CHOICES=(
        (0,_('False')),
        (1,_('True')),
    )
    Identifier = models.CharField(max_length=50,unique=True)
    Active = models.BooleanField(default=False)
    OnError = models.PositiveSmallIntegerField(choices=ONERROR_CHOICES,default=0)
    PreviousRule= models.ForeignKey('AutomationRules',related_name='previous_rule',blank=True,null=True)
    OperatorPrev = models.CharField(choices=BOOL_OPERATOR_CHOICES,max_length=2,blank=True,null=True)
    RuleItems = models.ManyToManyField(RuleItems)
    Action = models.CharField(max_length=500,blank=True) # receives a json object describind the action desired
    EdgeExec = models.BooleanField(default=False)
    LastEval = models.BooleanField(default=False)
    
    _timestamp1=None
    _timestamp2=None
    
    def __str__(self):
        return self.Identifier
    
    def setActive(self,value):
        if value:
            self.Active=True
        else:
            self.Active=False
        self.save()
        
    def store2DB(self):
        self.full_clean()
        try:
            super().save()
        except OperationalError:
            logger.error("Operational error on Django. System restarted")
            import os
            os.system("sudo reboot")
        
    def printEvaluation(self):
        result=self.evaluate()
        if result['ERROR']==[]:
            result.pop('ERROR', None)
        return result
        
    def switchBOOLOperator(self,operator):
        if '&' in operator:
            return operator.replace('&','|')
        elif '|' in operator:
            return operator.replace('|','&')
        else:
            return operator
    
    def setLastEval(self,value):
        self.LastEval=value
        self.save()
    
    def getEventsCode(self):
        return 'ARULE'+str(self.pk)
        
    def evaluate(self):
        if self.Active:
            evaluableTRUE=''
            evaluableFALSE=''
            if self.PreviousRule!=None:
                result=self.PreviousRule.evaluate()
                evaluableTRUE+=str(result['TRUE']) + ' ' + self.OperatorPrev
                evaluableFALSE+=str(result['FALSE']) + ' ' + self.switchBOOLOperator(operator=self.OperatorPrev)
                errors=[result['ERROR']]
            else:
                errors=[]
            Items=RuleItems.objects.filter(Rule=self.pk).order_by('Order')
                
            if len(Items):
                
                for item in Items:
                    result=item.evaluate()
                    resultTRUE=result['TRUE']
                    resultFALSE=result['FALSE']
                    if item.Operator3!=None:
                        evaluableTRUE+=' ' + str(resultTRUE) + ' ' + item.Operator3
                        evaluableFALSE+=' ' + str(resultFALSE) + ' ' + self.switchBOOLOperator(operator=item.Operator3)
                    else:
                        evaluableTRUE+=' ' + str(resultTRUE)
                        evaluableFALSE+=' ' + str(resultFALSE)
                            
                    if result['ERROR']!='':
                        text='The evaluation of rule ' + self.Identifier + ' evaluated to Error on item ' + str(item)+'. Error: ' + str(result['ERROR'])
                        PublishEvent(Severity=3,Text=text,Persistent=True,Code=self.getEventsCode(),Webpush=True)
                        errors.append(result['ERROR'])
                
                evaluableTRUE=evaluableTRUE.strip()
                evaluableFALSE=evaluableFALSE.strip()
                if len(evaluableTRUE)>1:
                    if evaluableTRUE[-1]=='&' or evaluableTRUE[-1]=='|':
                        evaluableTRUE=evaluableTRUE[:-1]
                    if evaluableTRUE[0]=='&' or evaluableTRUE[0]=='|':
                        evaluableTRUE=evaluableTRUE[1:]
                if len(evaluableFALSE)>1:
                    if evaluableFALSE[-1]=='&' or evaluableFALSE[-1]=='|':
                        evaluableFALSE=evaluableFALSE[:-1]
                    if evaluableFALSE[0]=='&' or evaluableFALSE[0]=='|':
                        evaluableFALSE=evaluableFALSE[1:]
                try:
                    return {'TRUE':evaluableTRUE.strip(),'FALSE':evaluableFALSE.strip(),'ERROR':errors}
                except:
                    return {'TRUE':None,'FALSE':None,'ERROR':'Unknown'}
            else:
                return {'TRUE':'','FALSE':'','ERROR':'The rule has no items associated. Cannot be evaluated'}
        else:
            return {'TRUE':'','FALSE':'','ERROR':'Inactive Rule'}
    
    def execute(self,error=None):
        if error!=None:
            resultTRUE=eval(self.get_OnError_display())
            resultFALSE=eval('not ' + self.get_OnError_display())
        else:
            result=self.evaluate()
            resultTRUE=result['TRUE']
            resultFALSE=result['FALSE']
            
        try:
            resultTRUE=eval(resultTRUE)
            resultFALSE=eval(resultFALSE)
        except:
            resultTRUE=eval(self.get_OnError_display())
            resultFALSE=eval('not ' + self.get_OnError_display())
        
        if (resultTRUE==True and (not self.EdgeExec or not self.LastEval)):
            Action=json.loads(self.Action)
            if Action['IO']!=None and Action['ActionType']=='a':
                #logger.info("Rule evaluated True: Signal to set GPIO sent")
                MainAPP.signals.SignalSetGPIO.send(sender=None,pk=Action['IO'],Value=int(Action['IOValue']))
            text='The rule ' + self.Identifier + ' evaluated to True. Action executed.'
            if result['ERROR']==[] and not self.LastEval and Action.get('NotificationTrue')==True:
                PublishEvent(Severity=0,Text=text,Persistent=True,Code=self.getEventsCode(),Webpush=True)
            
            self.setLastEval(value=True)
        elif (resultFALSE==True and (not self.EdgeExec or self.LastEval)):
            Action=json.loads(self.Action)
            if Action['IO']!=None and Action['ActionType']=='a':
                #logger.info("Rule evaluated False: Signal to set GPIO sent")
                MainAPP.signals.SignalSetGPIO.send(sender=None,pk=Action['IO'],Value=int(not int(Action['IOValue'])))
            text='The rule ' + self.Identifier + ' evaluated to False. Action executed.'
            if result['ERROR']==[] and self.LastEval and Action.get('NotificationFalse')==True:
                PublishEvent(Severity=0,Text=text,Persistent=True,Code=self.getEventsCode(),Webpush=True)
            
            self.setLastEval(value=False)
    
    @classmethod
    def initAll(cls):
        RULs=cls.objects.filter(Active=True)
        if len(RULs)>0:
            for RUL in RULs:
                if not '"ActionType": "z"' in RUL.Action:
                    RUL.execute() 
                
@receiver(post_save, sender=AutomationRules, dispatch_uid="update_AutomationRuleModel")
def update_AutomationRuleModel(sender, instance, update_fields,**kwargs):    
    if not kwargs['created']:   # an instance has been modified
        pass
        #logger.info('Se ha modificado la regla de automatizacion ' + str(instance.Identifier))
    else:
        logger.info('Se ha creado la regla de automatizacion ' + str(instance.Identifier))
    #if instance.Active==False:
    #    instance.execute(error=True)
        
