import os
import sys
from django.db import models
from django.db.utils import OperationalError
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.dispatch import receiver
from django.db.models.signals import post_save,post_delete,pre_delete
from django.db.models.signals import m2m_changed
from django.contrib.contenttypes.fields import GenericRelation

import datetime

import RPi.GPIO as GPIO

from channels.binding.websockets import WebsocketBinding,WebsocketBindingWithMembers 

from EventsAPP.consumers import PublishEvent

import json
import itertools
import utils.BBDD
from MainAPP.constants import REGISTERS_DB_PATH
import MainAPP.models


from .signals import SignalVariableValueUpdated,SignalNewDataFromDevice
from .constants import CONNECTION_CHOICES,LOCAL_CONNECTION,REMOTE_TCP_CONNECTION,REMOTE_RS485_CONNECTION,MEMORY_CONNECTION,\
                        STATE_CHOICES,DEVICES_PROTOCOL,DEVICES_SUBNET,DEVICES_SCAN_IP4BYTE,\
                        DEVICES_CONFIG_FILE,DEVICES_FIRMWARE_WEB,IP_OFFSET,POLLING_SCHEDULER_URL,\
                        STOPPED_STATE,RUNNING_STATE,\
                        DATAGRAMTYPE_CHOICES,DATATYPE_CHOICES,PLOTTYPE_CHOICES,LINE_PLOT,SPLINE_PLOT,DG_ASYNCHRONOUS,DG_SYNCHRONOUS,DG_CRONNED,\
                        DTYPE_DIGITAL,DTYPE_INTEGER,\
                        GPIO_DIRECTION_CHOICES,GPIO_OUTPUT,GPIO_INPUT,GPIO_SENSOR,GPIOVALUE_CHOICES,GPIO_HIGH,GPIO_LOW,\
                        GPIO_IN_DBTABLE,GPIO_OUT_DBTABLE,DECIMAL_POSITIONS
                        
from .apps import DevicesAppException

import logging

logger = logging.getLogger("project")

def getAllVariables():

    info=[]
    DVs=Devices.objects.all()
    IOs=MainGPIOs.objects.all()
    MainVars=MainDeviceVars.objects.all()
    tempvars=[]
    device='MainGPIOs'
    if len(IOs)>0:
        for IO in IOs:
            if IO.Direction==GPIO_INPUT or IO.Direction==GPIO_OUTPUT:
                table=IO.getRegistersDBTable()
                tempvars.append({'device':device,'table':table,'tag':IO.getRegistersDBTag(),
                                'label':[IO.Label,],'extrapolate':0,'type':'digital','plottype':'line',
                                'bitpos':0,'units':None})# this is to tell the template that it is a boolean value
                                
        info.append({'deviceName':device,'variables':tempvars})
    tempvars=[]
    device='MainVars'
    if len(MainVars)>0:
        for VAR in MainVars:
            table=VAR.getRegistersDBTable()
            if VAR.DataType!=DTYPE_DIGITAL:
                tempvars.append({'device':device,'table':table,'tag':VAR.getRegistersDBTag(),
                            'label':VAR.Label,'extrapolate':'keepPrevious','type':'analog','plottype':VAR.PlotType,
                            'bitpos':None,'units':VAR.Units})
            else:
                tempvars.append({'device':device,'table':table,'tag':VAR.getRegistersDBTag(),
                            'label':[VAR.Label,],'extrapolate':0,'type':'digital','plottype':VAR.PlotType,
                            'bitpos':0,'units':None})
                                
        info.append({'deviceName':device,'variables':tempvars})
        
    for DV in DVs:
        DGs=Datagrams.objects.filter(DVT=DV.DVT)
        tempvars=[]
        vars=DV.getDeviceVariables()
        for var in vars:
            if (var['label'].lower()!='spare') and (var['label'].lower()!='timestamp'):
                varinfo=Datagrams.getInfoFromItemName(name=var['name'])
                ITM=DatagramItems.objects.get(pk=varinfo['itempk'])
                if var['bit']!=None:    # its a digital variable
                    tempvars.append({'device':DV.Name,'table':var['table'],'tag':var['name'],'type':'digital','label':var['label'],
                                'plottype':ITM.PlotType,'extrapolate':0,'bitpos':var['bit'],'units':None})
                else:
                    tempvars.append({'device':DV.Name,'table':var['table'],'tag':var['name'],'type':'analog','label':var['label'],
                                'plottype':ITM.PlotType,'extrapolate':0,'bitpos':var['bit'],'units':var['units']})
                    
        info.append({'deviceName':DV.Name,'variables':tempvars})
    return info

class MainDeviceVars(models.Model):
    
    class Meta:
        verbose_name = _('Main device var')
        verbose_name_plural = _('Main device vars')  
    
    SQLcreateRegisterTable = ''' 
                                CREATE TABLE IF NOT EXISTS $ (
                                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                    *
                                    UNIQUE (timestamp)                    
                                ); 
                                '''  # the * will be replaced by the column names and $ by inputs or outputs
    SQLinsertRegister = ''' INSERT INTO %s(*) VALUES(?) ''' # the * will be replaced by the column names and the ? by the values 
    SQLupdateRegister = ''' UPDATE %s SET *=$ WHERE timestamp=? ''' # the * will be replaced by the column name,the ? by the pk and the $ by the value 
    
    Label = models.CharField(max_length=150,unique=True,help_text=str(_('Unique identifier for the variable.')))
    Value = models.FloatField(null=True,help_text=str(_('Value of the variable.')))
    DataType= models.CharField(max_length=20,choices=DATATYPE_CHOICES,help_text=str(_('Type of data of the variable.')))
    PlotType= models.CharField(max_length=10,choices=PLOTTYPE_CHOICES,default=LINE_PLOT,help_text=str(_('The type of plot desired for the variable.')))
    Units = models.CharField(max_length=10,help_text=str(_('Units of the variable.')),blank=True,null=True)
    UserEditable = models.BooleanField(default=True,help_text=str(_('Can the user modify the value??')))
    
    Subsystem = GenericRelation(MainAPP.models.Subsystems,related_query_name='mainvars')
    
    def __str__(self):
        return self.Label
    
    def __init__(self, *args, **kwargs):
        super(MainDeviceVars, self).__init__(*args, **kwargs)
    
    def clean(self):
        if self.DataType==DTYPE_DIGITAL:
            self.Units=None
        else:
            if self.Units=='':
                self.Units=' '
                
    def store2DB(self):
        '''STORES THE OBJECT AND CREATES THE REGISTER DB TABLES IF NEEDED
        '''
        
        self.full_clean()
        try:
            super().save()
        except OperationalError:
            logger.error("Operational error on Django. System restarted")
            import os
            os.system("sudo reboot")
        self.updateAutomationVars()
        self.updateValue(newValue=self.Value,timestamp=timezone.now(),writeDB=True,force=True)
    
    def toggle(self,newValue=None,**kwargs):
        if newValue==None:
            if self.DataType==DTYPE_DIGITAL:
                self.updateValue(newValue=not (self.Value),**kwargs)
        else:
            self.updateValue(newValue=newValue,**kwargs)
        
    def updateLabel(self,newLabel,updateAVARs=True):
        self.Label=newLabel
        self.save(update_fields=['Label'])
        if updateAVARs:
            self.updateAutomationVars()
    
    def updateUnits(self,newUnits,updateAVARs):
        self.Label=newUnits
        self.save(update_fields=['Units'])
        if updateAVARs:
            self.updateAutomationVars()
        
    def updateValue(self,newValue,timestamp=None,writeDB=True,force=False):
        if newValue!=self.Value or force:
            if timestamp==None:
                now=timezone.now()
            else:
                now=timestamp
                
            if writeDB:
                if timestamp==None:
                    self.insertRegister(TimeStamp=now-datetime.timedelta(seconds=1))
                
            if newValue!=self.Value or force:
                if newValue!=None:
                    newValue=round(newValue,DECIMAL_POSITIONS)
                text=str(_('The value of the MainDeviceVar "')) +self.Label+str(_('" has changed. Now it is ')) + str(newValue)
                PublishEvent(Severity=0,Text=text,Code=self.getEventsCode()+'0')
                self.Value=newValue
                self.save(update_fields=['Value',])
                
            if writeDB :
                if timestamp==None:
                    self.insertRegister(TimeStamp=now)
                else:
                    self.insertRegister(TimeStamp=timestamp)
            
            SignalVariableValueUpdated.send(sender='MainVars', timestamp=now,
                                                            Tags=[self.getRegistersDBTag(),],
                                                            Values=[newValue,],Types=[self.DataType,],
                                                            DataTypes=[self.DataType,])
    
    def getEventsCode(self):
        return 'VAR'+str(self.pk)+'-'
    
    
    def getInsertAllRegisterSQL(self):
        sql=self.SQLinsertRegister
        #SQLinsertRegister = ''' INSERT INTO %s(*) VALUES(?) '''   # the * will be replaced by the column names and the $ by the values  
        struct=self.getStructure()
        names=struct['names']
        values=[]
        valuesHolder='?,'
        columns='timestamp,'
        if len(names)>0:
            for i,name in enumerate(names):
                values.append(struct['values'][i])
                columns+='"'+name+'",'
                valuesHolder+='?,'
        columns=columns[:-1]
        valuesHolder=valuesHolder[:-1]
        sql=sql.replace('%s','"'+self.getRegistersDBTable()+'"').replace('*',columns).replace('?',valuesHolder)
        return {'query':sql,'num_args':len(names),'values':values}
    
    def getInsertRegisterSQL(self):
        sql=self.SQLinsertRegister
        #SQLinsertRegister = ''' INSERT INTO %s(*) VALUES(?) '''   # the * will be replaced by the column names and the $ by the values  
        sql=sql.replace('%s','"'+self.getRegistersDBTable()+'"').replace('*','timestamp,'+'"'+self.getRegistersDBTag()+'"').replace('?','?,?')
        return {'query':sql}
    
    def getUpdateRegisterSQL(self,pk):
        sql=self.SQLupdateRegister
        #SQLupdateRegister = ''' UPDATE %s SET *=$ WHERE timestamp=? ''' # the * will be replaced by the column name,the $ by the value and the ? by the pk 
        sql=sql.replace('%s','"'+self.getRegistersDBTable()+'"').replace('*','"'+self.getRegistersDBTag()+'"').replace('$',str(self.Value))
        return {'query':sql}
    
    def checkRegistersDB(self,Database):
        
        rows=Database.retrieve_DB_structure(fields='*')   #('table', 'devices', 'devices', 4, "CREATE TABLE devices...)
        
        required_DGs=[]
        found=False
        table_to_find=self.getRegistersDBTable()
        for row in rows:
            if (row[1]==table_to_find):   # found the table in the DB
                found=True
                struct=self.getStructure()
                Database.checkTableColumns(table=table_to_find,desiredColumns={'names':struct['names'],'datatypes':struct['datatypes']})
                break
        if found is not True:
            self._createRegistersTable(Database=Database)
            logger.info('The table '+table_to_find+' was not created.')
    
    def _createRegistersTable(self,Database):
        """
        Creates the table corresponding to the GPIO Direction
        """
        TableName=self.getRegistersDBTable()

        try:
            struct=self.getStructure()
            temp_string=''
            for i in range(0,len(struct['names'])):
                temp_string+='"'+struct['names'][i] + '" ' + struct['datatypes'][i] + ','
            sql=self.SQLcreateRegisterTable.replace('*',temp_string).replace('$','"'+TableName+'"')
            result=Database.executeTransactionWithCommit(SQLstatement=sql, arg=[])
            if result==0:
                logger.info('Succeded in creating the table "'+TableName+'"') 
        except:
            text = str(_("Error in create_MainVars_table: ")) + str(sys.exc_info()[1]) 
            PublishEvent(Severity=5,Text=text + 'SQL: ' + sql,Persistent=True,Code=self.getEventsCode()+'100')
            raise DevicesAppException(text)
            
    def insertRegister(self,TimeStamp,NULL=False):
        """
        INSERTS A REGISTER IN THE registersDB INTO THE APPROPIATE TABLE.
        """
        try:                              
            TimeStamp=TimeStamp.replace(microsecond=0)
            query=self.getInsertRegisterSQL()
            sql=query['query']
            values=[self.Value,]
            values.insert(0,TimeStamp)
            from utils.BBDD import getRegistersDBInstance,INTEGRITY_ERROR
            DB=getRegistersDBInstance(year=TimeStamp.year)
            self.checkRegistersDB(Database=DB)
            result=DB.executeTransactionWithCommit(SQLstatement=sql, arg=values)
            if result==INTEGRITY_ERROR:
                #logger.warning('Integrity error with MainVar '+str(self)+' and query '+sql)
                query=self.getUpdateRegisterSQL(pk=TimeStamp)
                sql=query['query']
                #logger.warning('Trying to update with query '+sql)
                result=DB.executeTransactionWithCommit(SQLstatement=sql, arg=[TimeStamp,])
        except:
            raise DevicesAppException("Unexpected error in insert_MainVars_register for variable "+self.Label+":" + str(sys.exc_info()[1]))
    
    def insertAllRegisters(self,TimeStamp,NULL=False):
        """
        INSERTS A REGISTER IN THE registersDB INTO THE APPROPIATE TABLE.
        """
        try:                              
            TimeStamp=TimeStamp.replace(microsecond=0)
            query=self.getInsertRegisterSQL()
            sql=query['query']
            num_args=query['num_args']
            values=query['values']
            if NULL==True:
                #logger.info('Inserted NULL values on MainVars ' + self.Label)
                values=[]
                for i in range(0,num_args):  
                    values.append(None)
            values.insert(0,TimeStamp)
            from utils.BBDD import getRegistersDBInstance,INTEGRITY_ERROR
            DB=getRegistersDBInstance(year=TimeStamp.year)
            self.checkRegistersDB(Database=DB)
            result=DB.executeTransactionWithCommit(SQLstatement=sql, arg=values)
#             if result==INTEGRITY_ERROR:
#                 query=self.getUpdateRegisterSQL(field=self.getRegistersDBTag(),pk=Timestamp)
#                 sql=query['query']
#                 result=DB.executeTransactionWithCommit(SQLstatement=sql, arg=self.Value)
        except:
            raise DevicesAppException("Unexpected error in insert_MainVars_register:" + str(sys.exc_info()[1]))
        
    def updateAutomationVars(self):
        SUBSYSTEMs=MainAPP.models.Subsystems.objects.filter(mainvars=self)
        dvar={'Label':self.Label,'Tag':self.getRegistersDBTag(),'Device':'MainVars','Table':self.getRegistersDBTable(),'BitPos':None,'Sample':0,'Units':self.Units}
        try:
            avar=MainAPP.models.AutomationVariables.objects.get(Device='MainVars',Tag=dvar['Tag'],Table=dvar['Table'])
        except MainAPP.models.AutomationVariables.DoesNotExist:
            avar=None
            
        if avar==None:
            avar=MainAPP.models.AutomationVariables(**dvar)
        else:
            avar.Label=dvar['Label']
            avar.Units=dvar['Units']
            
        avar.UserEditable=self.UserEditable
        avar.store2DB()
        
        if SUBSYSTEMs.count():
            for SUBS in SUBSYSTEMs:
                avar.createSubsystem(Name=SUBS.Name)
    
    def deleteAutomationVars(self):
        MainAPP.models.AutomationVariables.objects.get(Device='MainVars',Tag=str(self.pk),Table=self.getRegistersDBTable()).delete()
        
    def getRegistersDBTag(self):
        return str(self.pk)
    
    def getLatestData(self,localized=True):
        Data={}
        name=self.getRegistersDBTag()
        Data[name]={}
        table=self.getRegistersDBTable()
        vars='"timestamp","'+name+'"'
        sql='SELECT '+vars+' FROM "'+ table +'" ORDER BY timestamp DESC LIMIT 1'
        from utils.BBDD import getRegistersDBInstance
        DB=getRegistersDBInstance()
        row=DB.executeTransaction(SQLstatement=sql)
        if row != []:
            row=row[0]
            timestamp=row[0]
            row=row[1]
        else:
            timestamp=None
            row=None
        if localized and timestamp!=None:
            from utils.dataMangling import localizeTimestamp
            timestamp=localizeTimestamp(timestamp) 
            
        Data[name]['timestamp']=timestamp
        Data[name]['value']=row
        Data[name]['label']=self.Label
        return Data
        
    @staticmethod
    def getRegistersDBTable():
        return 'MainVariables'
        
    @classmethod
    def getStructure(cls):
        VARs=cls.objects.all()
        values=[]
        names=[]
        types=[]
        datatypes=[]
        plottypes=[]
        pks=[]
        if VARs.count():
            for instance in VARs:
                pks.append(instance.pk)
                values.append(instance.Value)
                names.append(instance.getRegistersDBTag())
                types.append(instance.DataType)
                if instance.DataType!=DTYPE_DIGITAL:
                    datatypes.append(instance.DataType)
                else:
                    datatypes.append(DTYPE_INTEGER)
                plottypes.append(instance.PlotType)
        return {'pk':pks,'names':names,'values':values,'types':types,'datatypes':datatypes,'plottypes':plottypes} 
    
    @classmethod
    def getCharts(cls,fromDate,toDate):
        VARs=cls.objects.all()
        if VARs.count()>0:
            names=[]
            types=[]
            labels=[]
            plottypes=[]
            units=[]
            for instance in VARs:
                names.append(instance.getRegistersDBTag())
                types.append(instance.DataType)
                labels.append(instance.Label)
                plottypes.append(instance.PlotType)
                table=instance.getRegistersDBTable()
                units.append(instance.Units)
            
            names.insert(0,'timestamp')
            types.insert(0,'datetime')
            labels.insert(0,'timestamp')
            plottypes.insert(0,'timestamp')
            units.insert(0,'timestamp')
            
            from .charting import generateChart
            
            chart=generateChart(table=table,fromDate=fromDate,toDate=toDate,names=names,types=types,
                                labels=labels,plottypes=plottypes,units=units,sampletime=0)
        return chart
    
@receiver(post_save, sender=MainDeviceVars, dispatch_uid="update_MainDeviceVars")
def update_MainDeviceVars(sender, instance, update_fields=[],**kwargs):
    
    if not kwargs['created']:   # an instance has been modified
        #logger.info('Se ha modificado la variable local ' + str(instance) + ' al valor ' + str(instance.Value))
        pass
    else:
        logger.info('Se ha creado la variable local ' + str(instance))
    timestamp=timezone.now() #para hora con info UTC
    #registerDB.insert_VARs_register(TimeStamp=timestamp,VARs=instance)
    
@receiver(post_delete, sender=MainDeviceVars, dispatch_uid="delete_MainDeviceVars")
def delete_MainDeviceVars(sender, instance,**kwargs):
    instance.deleteAutomationVars()
    logger.info('Se ha eliminado la variable ' + str(instance))
    

                    
#set up GPIO using BCM numbering
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
    
class MainGPIOs(models.Model):
    
    class Meta:
        verbose_name = _('Input/Output')
        verbose_name_plural = _('Inputs/Outputs')
        permissions = (
            ("view_maingpios", "Can see available gpios"),
            ("change_state_maingpios", "Can change the state of the GPIOs"),
        )
    SQLcreateRegisterTable = ''' 
                                CREATE TABLE IF NOT EXISTS $ (
                                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                    *
                                    UNIQUE (timestamp)                    
                                ); 
                                '''  # the * will be replaced by the column names and $ by inputs or outputs
    SQLinsertRegister = ''' INSERT INTO %s(*) VALUES(?) ''' # the * will be replaced by the column names and the ? by the values 
    SQLupdateRegister = ''' UPDATE %s SET *=$ WHERE timestamp=? ''' # the * will be replaced by the column name,the ? by the pk and the $ by the value 
    
    Pin = models.PositiveSmallIntegerField(primary_key=True,unique=True,help_text=str(_('The number of the pin following BCM notation.')))
    Label = models.CharField(max_length=50,unique=True,help_text=str(_('Label describing the GPIO functional meaning.')))
    Direction = models.PositiveSmallIntegerField(choices=GPIO_DIRECTION_CHOICES,help_text=str(_('Choose wether the GPIO is to be an output, an input or a sensor interface.')))
    Value = models.PositiveSmallIntegerField(default=0,choices=GPIOVALUE_CHOICES,help_text=str(_('Set the value of the GPIO (only applies to outputs)')))
    
    NotificationTrue=models.BooleanField(default=False,help_text=str(_('Send notification when the rule evaluates to True')))
    LabelTrue = models.CharField(max_length=150,help_text=str(_('Label for the notification when the IO is True.')),blank=True,default="")
    NotificationFalse=models.BooleanField(default=False,help_text=str(_('Send notification when the rule evaluates to False')))
    LabelFalse = models.CharField(max_length=150,help_text=str(_('Label for the notification when the IO is False.')),blank=True,default="")
    
    Subsystem = GenericRelation(MainAPP.models.Subsystems,related_query_name='gpios')
    
    def __init__(self, *args, **kwargs):
        super(MainGPIOs, self).__init__(*args, **kwargs)
    
    def InputChangeEvent(self,*args):
        newValue=int(GPIO.input(self.Pin))
        self.updateValue(newValue=newValue,timestamp=None,writeDB=True)
    
    def updateLabel(self,newLabel):
        self.Label=newLabel
        self.save(update_fields=['Label'])
        self.updateAutomationVars()
         
    def store2DB(self):
        '''STORES THE OBJECT AND CREATES THE REGISTER DB TABLES IF NEEDED
        '''
        self.full_clean()
        try:
            super().save()
        except OperationalError:
            logger.error("Operational error on Django. System restarted")
            import os
            os.system("sudo reboot")
        now=timezone.now()
        if self.Direction==GPIO_INPUT:
            GPIO.setup(int(self.Pin), GPIO.IN, pull_up_down = GPIO.PUD_DOWN)
            self.Value=GPIO.input(int(self.Pin))
        if self.Direction!=GPIO_SENSOR:
            self.updateValue(newValue=self.Value,timestamp=now,writeDB=True,force=True)
            self.updateAutomationVars() 
        
    def setHigh(self):
        if self.Direction==GPIO_OUTPUT:
            GPIO.setup(int(self.Pin), GPIO.OUT)
            GPIO.output(int(self.Pin),GPIO.HIGH)
            newValue=GPIO.HIGH
            self.updateValue(newValue=newValue,timestamp=None,writeDB=True,force=False)
            
    def setLow(self):
        if self.Direction==GPIO_OUTPUT:
            GPIO.setup(int(self.Pin), GPIO.OUT)
            GPIO.output(int(self.Pin),GPIO.LOW)
            newValue=GPIO.LOW
            self.updateValue(newValue=newValue,timestamp=None,writeDB=True,force=False)
            
    def toggle(self,newValue=None):
        if newValue==None:
            # TOGGLE
            if self.Value==GPIO.HIGH:
                self.setLow()
            else:
                self.setHigh()
        elif newValue==1:
            self.setHigh()
        else:
            self.setLow()
            
    def getLatestData(self,localized=True):
        Data={}
        name=self.getRegistersDBTag()
        Data[name]={}
        table=self.getRegistersDBTable()
        vars='"timestamp","'+name+'"'
        sql='SELECT '+vars+' FROM "'+ table +'" ORDER BY timestamp DESC LIMIT 1'
        from utils.BBDD import getRegistersDBInstance
        DB=getRegistersDBInstance()
        row=DB.executeTransaction(SQLstatement=sql)
        if row != []:
            row=row[0]
            timestamp=row[0]
            row=row[1]
        else:
            timestamp=None
            row=None
        if localized and timestamp!=None:
            from utils.dataMangling import localizeTimestamp
            timestamp=localizeTimestamp(timestamp) 
            
        Data[name]['timestamp']=timestamp
        Data[name]['value']=row
        Data[name]['label']=self.Label
        return Data
    
    def getEventsCode(self):
        return 'GPIO'+str(self.pk)+'-'
    
    def updateValue(self,newValue,timestamp=None,writeDB=True,force=False):
        if newValue!=self.Value or force:
            if timestamp==None:
                now=timezone.now()
            else:
                now=timestamp
                
            if writeDB:
                if timestamp==None:
                    self.insertRegister(TimeStamp=now-datetime.timedelta(seconds=1))
                
            if newValue!=self.Value or force:
                self.Value=newValue
                self.save(update_fields=['Value'])
                if not force:
                    webpush=(self.NotificationFalse and newValue==False) or (self.NotificationTrue and newValue==True)
                    if self.NotificationFalse and newValue==False and self.LabelFalse!="":
                        text=self.LabelFalse
                    elif self.NotificationTrue and newValue==True and self.LabelTrue!="":
                        text=self.LabelTrue
                    else:
                        text=str(_('The value of the GPIO "')) +self.Label+str(_('" has changed. Now it is ')) + str(newValue)
                    PublishEvent(Severity=0,Text=text,Code=self.getEventsCode()+'0',Webpush=webpush)
            if writeDB :
                if timestamp==None:
                    self.insertRegister(TimeStamp=now)
                else:
                    self.insertRegister(TimeStamp=timestamp)
                
            if self.Direction==GPIO_OUTPUT:
                GPIO.setup(int(self.Pin), GPIO.OUT)
                if self.Value==1:
                    GPIO.output(int(self.Pin),GPIO.HIGH)
                elif self.Value==0:
                    GPIO.output(int(self.Pin),GPIO.LOW)
            
            SignalVariableValueUpdated.send(sender='MainGPIOs', timestamp=now,
                                                            Tags=[self.getRegistersDBTag(),],
                                                            Values=[newValue,],Types=[DTYPE_DIGITAL,],
                                                            DataTypes=[DTYPE_DIGITAL,])
                
    def getRegistersDBTable(self):
        if self.Direction==GPIO_INPUT:
            table=GPIO_IN_DBTABLE
        elif self.Direction==GPIO_OUTPUT:
            table=GPIO_OUT_DBTABLE
        else:
            raise ValueError(_('Only GPIOs defined as Input or Output can be registered to the DB'))
        return table
    
    def getRegistersDBTag(self):
        return str(self.Pin)
    
    def getStructure(self):
        IOs=MainGPIOs.objects.filter(Direction=self.Direction)
        values=[]
        names=[]
        types=[]
        datatypes=[]
        plottypes=[]
        pks=[]
        if IOs.count():
            for IO in IOs:
                pks.append(IO.pk)
                values.append(IO.Value)
                names.append(IO.getRegistersDBTag())
                types.append(DTYPE_INTEGER)
                datatypes.append(DTYPE_INTEGER)
                plottypes.append(LINE_PLOT)
        return {'pk':pks,'names':names,'values':values,'types':types,'datatypes':datatypes,'plottypes':plottypes}
        
    def _createRegistersTable(self,Database):
        """
        Creates the table corresponding to the GPIO Direction
        """
        TableName=self.getRegistersDBTable()

        try:
            struct=self.getStructure()
            temp_string=''
            for i in range(0,len(struct['names'])):
                temp_string+='"'+struct['names'][i] + '" ' + struct['datatypes'][i] + ','
            sql=self.SQLcreateRegisterTable.replace('*',temp_string).replace('$','"'+TableName+'"')
            result=Database.executeTransactionWithCommit(SQLstatement=sql, arg=[])
            if result==0:
                logger.info('Succeded in creating the table "'+TableName+'"') 
        except:
            text = str(_("Error in create_GPIO_table: ")) + str(sys.exc_info()[1]) 
            raise DevicesAppException(text)
            PublishEvent(Severity=5,Text=text + 'SQL: ' + sql,Persistent=True,Code=self.getEventsCode()+'100')        
            
    def getInsertAllRegisterSQL(self):
        
        sql=self.SQLinsertRegister
        #SQLinsertRegister = ''' INSERT INTO %s(*) VALUES(?) '''   # the * will be replaced by the column names and the $ by the values  
        struct=self.getStructure()
        names=struct['names']
        values=[]
        valuesHolder='?,'
        columns='timestamp,'
        if len(names)>0:
            for i,name in enumerate(names):
                values.append(struct['values'][i])
                columns+='"'+name+'",'
                valuesHolder+='?,'
        columns=columns[:-1]
        valuesHolder=valuesHolder[:-1]
        sql=sql.replace('%s','"'+self.getRegistersDBTable()+'"').replace('*',columns).replace('?',valuesHolder)
        return {'query':sql,'num_args':len(names),'values':values}
    
    def getInsertRegisterSQL(self):
        sql=self.SQLinsertRegister
        #SQLinsertRegister = ''' INSERT INTO %s(*) VALUES(?) '''   # the * will be replaced by the column names and the $ by the values  
        sql=sql.replace('%s','"'+self.getRegistersDBTable()+'"').replace('*','timestamp,'+'"'+self.getRegistersDBTag()+'"').replace('?','?,?')
        return {'query':sql}
    
    def getUpdateRegisterSQL(self,pk):
        sql=self.SQLupdateRegister
        #SQLupdateRegister = ''' UPDATE %s SET *=$ WHERE id=? ''' # the * will be replaced by the column name,the ? by the value and the $ by the pk 
        sql=sql.replace('%s','"'+self.getRegistersDBTable()+'"').replace('*','"'+self.getRegistersDBTag()+'"').replace('$',str(self.Value))
        return {'query':sql}
    
    def checkRegistersDB(self,Database):
        
        rows=Database.retrieve_DB_structure(fields='*')   #('table', 'devices', 'devices', 4, "CREATE TABLE devices...)
        
        required_DGs=[]

        found=False
        table_to_find=self.getRegistersDBTable()
        for row in rows:
            if (row[1]==table_to_find):   # found the table in the DB
                found=True
                struct=self.getStructure()
                Database.checkTableColumns(table=table_to_find,desiredColumns={'names':struct['names'],'datatypes':struct['datatypes']})
                break
        if found is not True:
            self._createRegistersTable(Database=Database)
            logger.info('The table '+table_to_find+' was not created.')
            
    def insertRegister(self,TimeStamp,NULL=False):
        """
        INSERTS A REGISTER IN THE registersDB INTO THE APPROPIATE TABLE.
        """
        try:                              
            TimeStamp=TimeStamp.replace(microsecond=0)
            query=self.getInsertRegisterSQL()
            sql=query['query']
            values=[self.Value,]
            values.insert(0,TimeStamp)
            from utils.BBDD import getRegistersDBInstance,INTEGRITY_ERROR
            DB=getRegistersDBInstance(year=TimeStamp.year)
            self.checkRegistersDB(Database=DB)
            result=DB.executeTransactionWithCommit(SQLstatement=sql, arg=values)
            if result==INTEGRITY_ERROR:
                query=self.getUpdateRegisterSQL(pk=TimeStamp)
                sql=query['query']
                result=DB.executeTransactionWithCommit(SQLstatement=sql, arg=[TimeStamp,])
        except:
            raise DevicesAppException("Unexpected error in insert_GPIO_register:" + str(sys.exc_info()[1]))
        
    def insertAllRegisters(self,TimeStamp,NULL=False):
        """
        INSERTS A REGISTER IN THE registersDB INTO THE APPROPIATE TABLE.
        """
        try:                              
            TimeStamp=TimeStamp.replace(microsecond=0)
            query=self.getInsertRegisterSQL()
            sql=query['query']
            num_args=query['num_args']
            values=query['values']
            if NULL==True:
                logger.info('Inserted NULL values on GPIO ' + self.Label)
                values=[]
                for i in range(0,num_args):  
                    values.append(None)
            values.insert(0,TimeStamp)
            from utils.BBDD import getRegistersDBInstance
            DB=getRegistersDBInstance(year=TimeStamp.year)
            self.checkRegistersDB(Database=DB)
            DB.executeTransactionWithCommit(SQLstatement=sql, arg=values)
        except:
            raise DevicesAppException("Unexpected error in insert_GPIO_register:" + str(sys.exc_info()[1]))
    
    def updateAutomationVars(self):
        table=self.getRegistersDBTable()
        SUBSYSTEMs=MainAPP.models.Subsystems.objects.filter(gpios=self)
        dvar={'Label':self.Label,'Tag':str(self.getRegistersDBTag()),'Device':'MainGPIOs','Table':table,'BitPos':None,'Sample':0,'Units':None}
        try:
            avar=MainAPP.models.AutomationVariables.objects.get(Device='MainGPIOs',Tag=dvar['Tag'],Table=dvar['Table'],BitPos=dvar['BitPos'],Units=dvar['Units'])
        except MainAPP.models.AutomationVariables.DoesNotExist:
            avar=None
            
        if avar==None:
            avar=MainAPP.models.AutomationVariables(**dvar)
        else:
            avar.Label=dvar['Label']
            avar.Units=dvar['Units']
            
        if self.Direction==GPIO_INPUT:
            avar.UserEditable=False
            
        avar.store2DB()
        
        if SUBSYSTEMs.count():
            for SUBS in SUBSYSTEMs:
                found=avar.checkSubsystem(Name=SUBS.Name)
                if found==False:
                    avar.createSubsystem(Name=SUBS.Name)

    @classmethod
    def getCharts(cls,fromDate,toDate):
        charts=[]
        for Direction in (GPIO_INPUT,GPIO_OUTPUT):
            IOs=cls.objects.filter(Direction=Direction)
            if IOs.count()>0:
                names=[]
                types=[]
                labels=[]
                plottypes=[]
                units=[]
                for IO in IOs:
                    names.append(IO.getRegistersDBTag())
                    types.append('digital')
                    labels.append(IO.Label)
                    plottypes.append('line')
                    table=IO.getRegistersDBTable()
                    units.append(None)
                
                names.insert(0,'timestamp')
                types.insert(0,'datetime')
                labels.insert(0,'timestamp')
                plottypes.insert(0,'timestamp')
                units.insert(0,'units')
                
                from .charting import generateChart
                
                chart=generateChart(table=table,fromDate=fromDate,toDate=toDate,names=names,types=types,
                                    labels=labels,plottypes=plottypes,units=units,sampletime=0)
                charts.append(chart)
        return charts
        
    def deleteAutomationVars(self):
        if self.Direction!=GPIO_SENSOR:
            table=self.getRegistersDBTable()
            try:
                avar=MainAPP.models.AutomationVariables.objects.get(Device='MainGPIOs',Tag=str(self.pk),Table=table)
                avar.delete()
            except:
                pass
        
    @staticmethod
    def getIOVariables(self):
        DeviceVars=[]
        IOs=MainGPIOs.objects.filter(Q(Direction=GPIO_INPUT) | Q(Direction=GPIO_OUTPUT))
        for IO in IOs:
            DeviceVars.append({'Label':IO.Label,'Tag':IO.getRegistersDBTag(),'Device':'Main','Table':IO.getRegistersDBTable(),'BitPos':None})
        return DeviceVars        
    
    @staticmethod
    def initializeIOs(declareInputEvent=True):
        IOs=MainGPIOs.objects.all()
        logger.info("There are " + str(len(IOs))+" IOs configured")
        if len(IOs):
            logger.info("Initializing IOs from DB")
            for IO in IOs:
                if IO.Direction==GPIO_OUTPUT:
                    GPIO.setup(int(IO.Pin), GPIO.OUT)
                    GPIO.output(int(IO.Pin),IO.Value)
                    newValue=IO.Value
                    IO.updateValue(newValue=newValue,timestamp=None,writeDB=True,force=True)
                    print("   - Initialized Output on pin " + str(IO.Pin))
                elif IO.Direction==GPIO_INPUT:
                    if declareInputEvent:
                        GPIO.setup(int(IO.Pin), GPIO.IN, pull_up_down = GPIO.PUD_DOWN)
                        #GPIO.remove_event_detect(int(IO.Pin))
                        GPIO.add_event_detect(int(IO.Pin), GPIO.BOTH, callback=IO.InputChangeEvent, bouncetime=200)
                        IO.Value=GPIO.input(int(IO.Pin))
                        newValue=IO.Value
                        IO.updateValue(newValue=newValue,timestamp=None,writeDB=True,force=True)
                    else:
                        GPIO.setup(int(IO.Pin), GPIO.IN, pull_up_down = GPIO.PUD_DOWN)
                        #GPIO.remove_event_detect(int(IO.Pin))
    
                    print("   - Initialized Input on pin " + str(IO.Pin))
                    
    def __str__(self):
        return self.Label + ' on pin ' + str(self.Pin)
        
    

@receiver(post_save, sender=MainGPIOs, dispatch_uid="update_MainGPIOs")
def update_MainGPIOs(sender, instance, update_fields,**kwargs):
    if kwargs['created']:   # new instance is created  
        logger.info('The IO ' + str(instance) + ' has been registered on the process ' + str(os.getpid()))
        if instance.Direction==GPIO_OUTPUT:
            GPIO.setup(int(instance.Pin), GPIO.OUT)
            if instance.Value==GPIO_HIGH:
                GPIO.output(int(instance.Pin),GPIO.HIGH)
            else:
                GPIO.output(int(instance.Pin),GPIO.LOW)
            logger.info("Initialized Output on pin " + str(instance.Pin))
        elif instance.Direction==GPIO_INPUT:
            GPIO.setup(int(instance.Pin), GPIO.IN, pull_up_down = GPIO.PUD_DOWN)
            GPIO.remove_event_detect(int(instance.Pin))
            GPIO.add_event_detect(int(instance.Pin), GPIO.BOTH, callback=instance.InputChangeEvent, bouncetime=200)  
            logger.info("Initialized Input on pin " + str(instance.Pin))
    else:
        pass

@receiver(post_delete, sender=MainGPIOs, dispatch_uid="delete_MainGPIOs")
def delete_MainGPIOs(sender, instance,**kwargs):
    instance.deleteAutomationVars()
    logger.info('Se ha eliminado la IO ' + str(instance))
        
class MainGPIOsBinding(WebsocketBinding):

    model = MainGPIOs
    stream = "GPIO_values"
    fields = ["Pin","Label","Direction","Value"]

    @classmethod
    def group_names(cls, *args, **kwargs):
        return ["GPIO-models",]

    def has_permission(self, user, action, pk):
        return True
    
def path_file_name(instance, filename):
    import os
    from django.core.files.storage import FileSystemStorage as fs
    from django.conf import settings
    filename, file_extension = os.path.splitext(filename)
    path='/'.join(filter(None, (instance.Code, 'thumbnail'+file_extension)))
    return path
    
class DeviceTypes(models.Model):
    
    Code = models.CharField(help_text=str(_('Unique identifier of the device type. Usually between 5 and 8 characters.')),unique=True, max_length=20)
    Description = models.CharField(max_length=100)
    MinSampletime=models.PositiveSmallIntegerField(help_text=str(_('Minimum accepted time between two polls. Refer to the device type documentation.')),default=10)
    Connection= models.PositiveSmallIntegerField(help_text=str(_('''The connection can be: 
                                                                    - LOCAL for devices that connect to a pin of the Main unit.
                                                                    - REMOTE OVER TCP for devices communicating through the WiFi interface.
                                                                    - REMOTE OVER RS485 for devices communicating through the RS485 interface.
                                                                    - MEMORY for devices that reside in the memory of the Main unit.
                                                                    ''')),
                                                 choices=CONNECTION_CHOICES)
    Picture = models.ImageField('DeviceType picture',
                                upload_to=path_file_name,
                                null=True,
                                blank=True)
                                
    def __str__(self):
        return self.Code
    
    def store2DB(self):
        self.full_clean()
        try:
            super().save()
        except OperationalError:
            logger.error("Operational error on Django. System restarted")
            import os
            os.system("sudo reboot")
        
    class Meta:
        permissions = (
                        ("view_devicetypes", "Can see available device types"),
                    )
        verbose_name = _('Device type')
        verbose_name_plural = _('Device types')

@receiver(pre_delete, sender=DeviceTypes, dispatch_uid="delete_DeviceType")
def delete_DeviceType(sender, instance,**kwargs):
    instance.Picture.delete(False)
        
def watchdog():
    from django.core.cache import cache
    from .constants import POLLING_WATCHDOG_TIMER,POLLING_WATCHDOG_VAR
    value=cache.get(POLLING_WATCHDOG_VAR)
    if value==None:
        value=True
    else:
        value=not value
    cache.set(POLLING_WATCHDOG_VAR, value, POLLING_WATCHDOG_TIMER*3)
    
def initialize_polling_devices():
    from .tools import PollingScheduler
    from .constants import POLLING_WATCHDOG_TIMER
    scheduler=PollingScheduler(jobstoreUrl=POLLING_SCHEDULER_URL)
    scheduler.run()
    watchdog()
    scheduler.add_job(func=watchdog,trigger='interval',seconds=POLLING_WATCHDOG_TIMER,id="watchdog",
                        replace_existing=True,max_instances=1,coalesce=True,misfire_grace_time=int(0.5*POLLING_WATCHDOG_TIMER))
    DVs=Devices.objects.all()
    if DVs.count()>0:
        for DV in DVs:
            DV.updateRequests()
                        
def request_callback(DV,DG,jobID,**kwargs): 
    if (DV.DVT.Connection==LOCAL_CONNECTION or DV.DVT.Connection==MEMORY_CONNECTION or DV.DVT.Connection==REMOTE_RS485_CONNECTION):
        import DevicesAPP.callbacks
        class_=getattr(DevicesAPP.callbacks, DV.DVT.Code)
        status={}
        try:
            instance=class_(DV)
            status=instance(**kwargs)
        except Exception as exc:
            status['LastUpdated']=None
            status['Error']=str(exc)
        
    elif DV.DVT.Connection==REMOTE_TCP_CONNECTION:
        status=DV.requestDatagram(DatagramId=DG.Identifier) 
    NextUpdate=DV.getNextUpdate(jobID=jobID) 
    DV.updatePollingStatus(DG=DG,LastUpdated=status['LastUpdated'],Error=status['Error'],NextUpdate=NextUpdate)

def get_list_serialports():
    from utils.USB_mangler import list_serial_ports
    listports=list_serial_ports()
    choices=[]
    for port in listports:
        choices.append((port,port))
    if len(choices)==0:
        choices.append(('No serial port',_('No serial port detected')))
    return choices
        
    
class Devices(models.Model):
                                    
    SQLcreateRegisterTable = ''' 
                                CREATE TABLE IF NOT EXISTS ? (
                                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                    *
                                    UNIQUE (timestamp)                    
                                ); '''  # the * will be replaced by the column names and types
    SQLinsertRegister = ''' INSERT INTO %s(*) VALUES($) '''   # the * will be replaced by the column names and the $ by the values  
    
    class Meta:
        permissions = (
            ("view_devices", "Can see available devices"),
            ("scan_devices", "Can scan for new devices"),
            ("change_state_devices", "Can change the state of the devices"),
        )
        verbose_name = _('Subordinate Device')
        verbose_name_plural = _('Subordinate Devices')
        
    Name = models.CharField(help_text=str(_('Unique identifier of the device. Limited to 50 characters.')),
                            max_length=50,unique=True,error_messages={'unique':_("Invalid device name - This name already exists in the DB.")})
    IO = models.OneToOneField(MainGPIOs,help_text=str(_('The pin of the Main unit to which the device is connected. Only applies to locally connected devices.')),
                            on_delete=models.CASCADE,related_name='pin2device',unique=True,null=True,blank=True,limit_choices_to={'Direction': GPIO_SENSOR})
    Code = models.PositiveSmallIntegerField(help_text=str(_('Identifier of the device. It is used to identify the device within the communication frames.')),
                            blank=True,null=True,error_messages={'unique':_("Invalid device code - This code already exists in the DB.")})
    IP = models.GenericIPAddressField(protocol='IPv4', unique=True,blank=True,null=True,error_messages={'unique':_("Invalid IP - This IP already exists in the DB.")})
    DVT = models.ForeignKey(DeviceTypes,related_name="deviceType",on_delete=models.CASCADE)#limit_choices_to={'Connection': 'LOCAL'}
    State= models.PositiveSmallIntegerField(help_text=str(_('Polling state of the device. STOPPED = no polling.')),
                                            choices=STATE_CHOICES, default=0)
    Sampletime=models.PositiveSmallIntegerField(help_text=str(_('Elapsed time between two polls to the device.')),default=600)
    RTsampletime=models.PositiveSmallIntegerField(help_text=str(_('Elapsed time between two polls to the device on realtime polling.')),default=60)
    
    LastUpdated= models.DateTimeField(blank = True,null=True)
    NextUpdate= models.DateTimeField(blank = True,null=True)
    Connected = models.BooleanField(default=False)  # defines if the device is properly detected and transmits OK
    CustomLabels = models.CharField(max_length=1500,default='',blank=True) # json string containing the user-defined labels for each of the items in the datagrams
    Error= models.CharField(max_length=100,default='',blank=True)
    
    Port=models.CharField(max_length=100,null=True,blank=True,choices=get_list_serialports())
    Baudrate=models.PositiveSmallIntegerField(help_text=str(_('Baudrate for the communication.')),null=True,blank=True,choices=[(110,'110'), (300,'300'), (600,'600'), (1200,'1200'), (2400,'2400'), (4800,'4800'), (9600,'9600'), 
                                                                                                                                (14400,'14400'), (19200,'19200'), (38400,'38400'), (57600,'57600'), (115200,'115200'), (128000,'128000'), (256000,'256000')])
    Parity=models.CharField(max_length=1,null=True,blank=True,choices=[('N',_('None')),('O',_('Odd')),('E',_('Even'))])
    Stopbits=models.PositiveSmallIntegerField(help_text=str(_('Number of stopbits on the frame.')),null=True,blank=True,choices=[(0,'0'),(1,'1'),(2,'2')])
                                                                  
    Subsystem = GenericRelation(MainAPP.models.Subsystems,related_query_name='devices')
    
    def validate_unique(self,exclude=None,*args, **kwargs):
        super(Devices, self).validate_unique(*args, **kwargs)
        if self.DVT.Connection==REMOTE_TCP_CONNECTION:
            DVs=Devices.objects.filter(DVT__Connection=REMOTE_TCP_CONNECTION)
            for DV in DVs:
                if self.pk!=DV.pk and self.IP==DV.IP:
                    raise ValidationError({'IP':_("A device with the same IP already exists on the WiFi network")})
        elif self.DVT.Connection==REMOTE_RS485_CONNECTION:
            DVs=Devices.objects.filter(DVT__Connection=REMOTE_RS485_CONNECTION)
            for DV in DVs:
                if self.pk!=DV.pk and self.Code==DV.Code and self.Port==DV.Port:
                    raise ValidationError({'Code':_("A device with the same Code already exists on the RS485 network")})
        
    
    def _deviceType2Binding(self):
        '''THIS IS TO SEND ON THE DTATABINDING SOCKET THE CODE OF THE DEVICE TYPE. ON DEFAULT, IT SENDS THE pk '''
        return self.DVT.Code
    devicetype2str=property(_deviceType2Binding)
    
    def getEventsCode(self):
        if self.DVT.Connection==LOCAL_CONNECTION:
            return 'IO'+str(self.IO.pk)+'-'
        elif self.DVT.Connection==REMOTE_TCP_CONNECTION:
            return 'IP'+str(self.IP)+'-'
        elif self.DVT.Connection==MEMORY_CONNECTION:
            return self.Name+'-'
        elif self.DVT.Connection==REMOTE_RS485_CONNECTION:
            return 'Code'+str(self.Code)+'-'
        else:
            return None
    
    def clean(self):
        
        if self.DVT.Connection==LOCAL_CONNECTION and self.IO==None:
            raise ValidationError(_('A locally connected device needs to have a GPIO defined'))
        if self.IO!=None:
            if self.IO.Direction!=GPIO_SENSOR:
                raise ValidationError(_('The GPIO selected is not configured as sensor'))
        if self.Sampletime<self.DVT.MinSampletime:
            raise ValidationError({'Sampletime':_('The sample time selected is too low for the '+self.DVT.Code+' sensors. It should be greater than '+str(self.DVT.MinSampletime)+' sec.')})
        if self.RTsampletime<self.DVT.MinSampletime:
            raise ValidationError({'RTsampletime':_('The RT sample time selected is too low for the '+self.DVT.Code+' sensors. It should be greater than '+str(self.DVT.MinSampletime)+' sec.')})
        
    def __str__(self):
        return self.Name
    
    def __init__(self, *args, **kwargs):
        super(Devices, self).__init__(*args, **kwargs)
    
    def setError(self,error):
        self.Error=error
        self.full_clean()
        super().save(update_fields=['Error',]) 
        
    def store2DB(self):
        self.full_clean()
        try:
            super().save()
        except OperationalError:
            logger.error("Operational error on Django. System restarted")
            import os
            os.system("sudo reboot")
        from utils.BBDD import getRegistersDBInstance
        DB=getRegistersDBInstance(year=None)
        self.createRegistersTables(Database=DB)
    
    @staticmethod
    def getScheduler():
        from .tools import PollingScheduler
        scheduler=PollingScheduler(jobstoreUrl=POLLING_SCHEDULER_URL)
        return scheduler
        
    def stopPolling(self):
        if self.State==RUNNING_STATE:
            self.State=STOPPED_STATE
            self.save()
        self.updateRequests()
    
    def startPolling(self):
        if self.State==STOPPED_STATE:
            self.State=RUNNING_STATE
            self.save()
        self.updateRequests()
    
    def togglePolling(self):
        if self.State==STOPPED_STATE:
            self.startPolling()
        else:
            self.stopPolling()
            
    def getPollingJobIDs(self):
        DGs=Datagrams.objects.filter(DVT=self.DVT)
        jobIDs=[]
        if DGs != []:
            for DG in DGs:
                if not DG.isAsynchronous():
                    jobIDs.append({'id':str(self.pk) + '-' + str(DG.pk),'DG':DG})
        return jobIDs
    
    def updateRequests(self):
        
        scheduler=Devices.getScheduler()
        jobIDs=self.getPollingJobIDs()
        process=os.getpid()
        #logger.info("Enters updateRequests on process " + str(process))
        
        if self.State==RUNNING_STATE:
            if jobIDs != []:
                numJobs=len(jobIDs)
                offset=self.Sampletime/numJobs
                now=datetime.datetime.now()
                for i,job in enumerate(jobIDs):
                    id=job['id']
                    DG=job['DG']
                    
                    start_date=now+datetime.timedelta(seconds=i*offset+self.Sampletime/2)
                    JOB=scheduler.getJobInStore(jobId=id)
                    
                    if JOB!=None:
                        scheduler.remove_job(id)
                        
                    callback="DevicesAPP.models:request_callback"
                    kwargs={'datagramId':DG.Identifier}
                    if self.DVT.Connection==LOCAL_CONNECTION: 
                        if DG.isSynchronous() :
                            if DG.Enable:
                                scheduler.add_job(func=callback,trigger='interval',id=id,args=(self,DG,id),kwargs=kwargs,seconds=self.Sampletime,start_date=start_date,
                                          replace_existing=True,max_instances=1,coalesce=True,misfire_grace_time=int(0.5*self.Sampletime))
                        elif DG.isCronned() :
                            if DG.Enable:
                                scheduler.add_cronjob(cronexpression=DG.Cron.getCronExpression(),**{'trigger':'cron','func':callback,'id':id,'args':(self,DG,id),'kwargs':kwargs,
                                          'replace_existing':True,'max_instances':1,'coalesce':True,'misfire_grace_time':20})
                            
                    elif self.DVT.Connection==REMOTE_TCP_CONNECTION:  
                        if DG.isSynchronous() :
                            if DG.Enable: 
                                scheduler.add_job(func=callback,trigger='interval',id=id,args=(self, DG, id),seconds=self.Sampletime,start_date=start_date,
                                          replace_existing=True,max_instances=1,coalesce=True,misfire_grace_time=int(0.5*self.Sampletime))
                        elif DG.isCronned() :
                            if DG.Enable:
                                scheduler.add_cronjob(cronexpression=DG.Cron.getCronExpression(),**{'trigger':'cron','func':callback,'id':id,'args':(self,DG,id),'kwargs':kwargs,
                                          'replace_existing':True,'max_instances':1,'coalesce':True,'misfire_grace_time':20})
                            
                    elif self.DVT.Connection==MEMORY_CONNECTION:
                        if DG.isSynchronous() : 
                            if DG.Enable:
                                scheduler.add_job(func=callback,trigger='interval',id=id,args=(self,DG,id), kwargs=kwargs,seconds=self.Sampletime,start_date=start_date,
                                          replace_existing=True,max_instances=1,coalesce=True,misfire_grace_time=int(0.5*self.Sampletime))
                        elif DG.isCronned() :
                            if DG.Enable:
                                scheduler.add_cronjob(cronexpression=DG.Cron.getCronExpression(),**{'trigger':'cron','func':callback,'id':id,'args':(self,DG,id),'kwargs':kwargs,
                                          'replace_existing':True,'max_instances':1,'coalesce':True,'misfire_grace_time':20})
                            
                    JOB=scheduler.getJobInStore(jobId=id)
                    if JOB!=None: 
                        text=str(_('Polling '))+id+str(_(' for the device '))+self.Name+str(_(' is started with sampletime= ')) + str(self.Sampletime) + str(_(' [s]. Next request at ') + str(JOB.next_run_time))
                        PublishEvent(Severity=0,Text=text,Persistent=True,Code=self.getEventsCode()+str(id))
                    elif DG.Enable:
                        PublishEvent(Severity=4,
                                     Text='Error adding job '+id+ ' to scheduler. Polling for device ' +self.Name+' could not be started' ,
                                     Code=self.getEventsCode()+'100',Persistent=True)
                        #self.State=STOPPED_STATE
                        #self.save()
                    scheduler.wakeup()
            else:        
                self.State=STOPPED_STATE
                self.save()
                text=str(_('Polling for device '))+self.Name+str(_(' could not be started. It has no Datagrams defined '))
                PublishEvent(Severity=3,Text=text,Persistent=True,Code=self.getEventsCode()+'101')
        else:
            if jobIDs != []:
                for job in jobIDs:
                    id=job['id']
                    JOB=scheduler.getJobInStore(jobId=id)
                    if JOB!=None: 
                        try:
                            scheduler.remove_job(id)
                        except:
                            pass
                        JOBs=scheduler.getJobsInStore()
                        if JOB in JOBs:
                            self.State=RUNNING_STATE
                            self.save()
                            text='Polling for the device '+self.Name+' could not be stopped '
                            severity=5
                        else:
                            text='Polling for the device '+self.Name+' is stopped ' 
                            severity=0
                    else:
                        text=str(_('Job ')) + str(id) + str(_(' did not exist. The device ') + self.Name + str(_(' was already stopped.'))) 
                        severity=2  
            else:
                text='Unhandled error on updateRequests for device ' + str(self.Name) 
                severity=5  
                
            PublishEvent(Severity=severity,Text=text,Persistent=True,Code=self.getEventsCode()+'102')
        
    def updatePollingStatus(self,LastUpdated,Error,NextUpdate,DG):
        updateFields=['Error']
        if NextUpdate != None:
            self.NextUpdate=NextUpdate
            updateFields.append('NextUpdate')
        if LastUpdated!= None:
            self.LastUpdated=LastUpdated
            updateFields.append('LastUpdated')
            self.sendNewDataSignals(DG_id=DG.Identifier)
            PublishEvent(Severity=0,Text=str(_('Datagram "'))+str(DG)+str(_('" for device "'))+self.Name+str(_('" updated OK')),Persistent=True,Code=self.getEventsCode()+str(DG.pk))
        self.Error=Error
        if Error!='':
            PublishEvent(Severity=3,Text=self.Name+' '+Error,Persistent=True,Code=self.getEventsCode()+str(DG.pk),Webpush=True)
            
        self.save(update_fields=updateFields)
        
    def setLastUpdated(self,newValue):
        self.LastUpdated=newValue
        self.save(update_fields=['LastUpdated','Error','NextUpdate'])
    
    def getDeviceCommands(self):
        CMDs=DeviceCommands.objects.filter(DVT=self.DVT)
        if len(CMDs)>0:
            return CMDs
        else:
            return []
               
    @staticmethod
    def getNextUpdate(jobID):
        if jobID!=None:
            scheduler=Devices.getScheduler()
            JOB=scheduler.getJobInStore(jobId=jobID)
            if JOB!=None:
                return JOB.next_run_time
        return None
            
    def setNextUpdate(self,jobID):
        next_run_time=Devices.getNextUpdate(jobID=jobID)
        self.NextUpdate=next_run_time
        if next_run_time==None:
            PublishEvent(Severity=3,Text='Next run time for job '+jobID+ ' could not be fetched.',
                         Persistent=True,Code=self.getEventsCode()+'106')
        self.save(update_fields=['NextUpdate',])
        return next_run_time
        
    def setCustomLabels(self):
        DGs=Datagrams.objects.filter(DVT=self.DVT)
        if DGs.count()>0:
            if self.CustomLabels!='':
                CustomLabels=json.loads(self.CustomLabels)
            else:
                CustomLabels={}
            for DG in DGs:
                datagram=DG.getStructure()
                names=datagram['names']
                types=datagram['types']
                if len(names)>0 and (not str(DG.pk) in CustomLabels):
                    CustomLabels[str(DG.pk)]={}
                for name,type in zip(names,types):
                    if not name in CustomLabels[str(DG.pk)]:
                        info=Datagrams.getInfoFromItemName(name=name)
                        ITM=DatagramItems.objects.get(pk=info['itempk'])
                        CustomLabels[str(DG.pk)][name]=ITM.getHumanName()
            self.CustomLabels=json.dumps(CustomLabels)
        else:
            self.CustomLabels=''
        self.save(update_fields=['CustomLabels',])
    
    def getRegistersTables(self,DG=None):
        if DG==None:
            DGs=Datagrams.objects.filter(DVT=self.DVT)
            tables=[]
            if DGs.count()>0:
                for DG in DGs:
                    tables.append(self.getRegistersDBTable(DG=DG))
        else:
            tables=self.getRegistersDBTable(DG=DG)
        return tables
    
    def getLatestData(self,localized=True):
        DGs=Datagrams.objects.filter(DVT=self.DVT)
        if self.CustomLabels=='':
            self.setCustomLabels()
            
        Data={}
        if DGs.count()>0:
            CustomLabels=json.loads(self.CustomLabels)
            for DG in DGs:
                Data[str(DG.pk)]={}
                table=self.getRegistersTables(DG=DG)
                vars='"timestamp"'
                for name in CustomLabels[str(DG.pk)]:
                    vars+=',"'+name+'"'
                sql='SELECT '+vars+' FROM "'+ table +'" ORDER BY timestamp DESC LIMIT 1'
                from utils.BBDD import getRegistersDBInstance
                DB=getRegistersDBInstance()
                row=DB.executeTransaction(SQLstatement=sql)
                if row != []:
                    row=row[0]
                    timestamp=row[0]
                    row=row[1:]
                    if localized and timestamp!=None:
                        from utils.dataMangling import localizeTimestamp
                        timestamp=localizeTimestamp(timestamp) 
                else:
                    timestamp=None
                    row=None
                if CustomLabels!=None:
                    Data[str(DG.pk)]['timestamp']=timestamp
                    for i,name in enumerate(CustomLabels[str(DG.pk)]):
                        info=Datagrams.getInfoFromItemName(name=name)
                        Data[str(DG.pk)][name]={}
                        if row==None:
                            Data[str(DG.pk)][name]['value']=row
                        else:
                            if info['type']!=DTYPE_DIGITAL:
                                Data[str(DG.pk)][name]['value']=row[i]
                                Data[str(DG.pk)][name]['label']=CustomLabels[str(DG.pk)][name]
                            else:
                                from utils.dataMangling import checkBit
                                values={}
                                for k in range(0,8):
                                    if row[i]!=None:
                                        values['bit' + str(k)]=int(checkBit(number=row[i],position=k))
                                    else:
                                        values['bit' + str(k)]=None
                                Data[str(DG.pk)][name]['value']=values
                                Data[str(DG.pk)][name]['label']=CustomLabels[str(DG.pk)][name]
        else:
            Data=None
        return Data
        
    def getDeviceVariables(self):
        DeviceVars=[]
        DGs=Datagrams.objects.filter(DVT=self.DVT)
        if self.CustomLabels=='' or self.CustomLabels==None:
            self.setCustomLabels()
        
        if self.CustomLabels!='' and self.CustomLabels!='{}':
            CustomLabels=json.loads(self.CustomLabels)
                
            for DG in DGs:
                datagram=DG.getStructure()
                names=datagram['names']
                types=datagram['types']
                units=datagram['units']
                table=self.getRegistersTables(DG=DG)
                CustomVars=CustomLabels[str(DG.pk)]
                for name,type,unit in zip(names,types,units):
                    if type==DTYPE_DIGITAL:
                        BitLabels=CustomVars[name].split('$')
                        if len(BitLabels)==8:
                            for i,bitLabel in enumerate(BitLabels):
                                DeviceVars.append({'DG':DG,'label':bitLabel,'name':name,'device':str(self.pk),'table':table,'bit':i,'sample':datagram['sample']*self.Sampletime,'units':None})
                        else:
                            for i in range(0,8):
                                DeviceVars.append({'DG':DG,'label':CustomVars[name]+'_bit'+str(i),'name':name,'device':str(self.pk),'table':table,'bit':i,'sample':datagram['sample']*self.Sampletime,'units':None})
                    else:
                        DeviceVars.append({'DG':DG,'label':CustomVars[name],'name':name,'device':str(self.pk),'table':table,'bit':None,'sample':datagram['sample']*self.Sampletime,'units':unit})
            
        return DeviceVars
    
    def updateAutomationVars(self,setSubsystems=False):
        AutomationVars=MainAPP.models.AutomationVariables.objects.filter(Device=str(self.pk))
        DeviceVars=self.getDeviceVariables()
        SUBSYSTEMs=MainAPP.models.Subsystems.objects.filter(devices=self)
        for dvar in DeviceVars:
            try:
                avar=AutomationVars.get(Tag=dvar['name'],Table=dvar['table'],Device=dvar['device'],BitPos=dvar['bit'])
            except:
                avar=None
                
            if avar==None:
                avar=MainAPP.models.AutomationVariables(Label=dvar['label'],Tag=dvar['name'],Device=dvar['device'],
                                                        Table=dvar['table'],BitPos=dvar['bit'],Sample=dvar['sample'],
                                                        Units=dvar['units'])
            else:
                avar.Label=dvar['label']
                avar.Units=dvar['units']
                
            avar.UserEditable=False
            avar.store2DB()
            
            if setSubsystems:
                if SUBSYSTEMs.count():
                    for SUBS in SUBSYSTEMs:
                        found=avar.checkSubsystem(Name=SUBS.Name)
                        if found==False:
                            avar.createSubsystem(Name=SUBS.Name)
                    
    def deleteAutomationVars(self):
        MainAPP.models.AutomationVariables.objects.filter(Device=self.pk).delete()
            
    @staticmethod
    def parseDeviceConfFile(xmlroot):
        """
        EXTRACTS THE INFORMATION FROM THE CONFIGURATION FILE SENT BY THE DEVICE
        """
        
        node=xmlroot.find('DEVT')
        if node==None:
            raise DevicesAppException('The device responded with an improper Conf.xml file, deviceType tag <DEVT> could not be found: ' + str(xmlroot.text))
        TYPE=node.text
        node=xmlroot.find('DEVC')
        if node==None:
            raise DevicesAppException('The device responded with an improper Conf.xml file, deviceCode tag <DEVC> could not be found: ' + str(xmlroot.text))
        CODE=node.text
        # node=xmlroot.find('DEVIP')
        # if node==None:
            # raise DevicesAppException('The device responded with an improper Conf.xml file, deviceIP tag <DEVIP> could not be found: ' + str(xmlroot.text))
        # DEVICE_IP=node.text.replace(',','.')
        IP=""
        return (TYPE,CODE,IP)   
    
    @staticmethod
    def parseDatagram(xmlroot):
        """
        :callback            datagram=myHttp.buildDatagram(xmlroot)
        :return datagram with structure (DeviceCode,DatagramId,data0,data1...dataN)
        """
        from utils.dataMangling import Bytes2Float32
        datagram=[]
        result=2
        for child in xmlroot:
            if child.tag=='VAR':
                integerValue=int(child.text)
                datagram.append(integerValue)
                #for i in range(0,8):
                    #print('Position ' + str(i) + ':',self.checkBit(integerValue, i))
            elif child.tag=='AV':
                floatValueBytes=[int(i) for i in child.text.split(',')]
                floatValueBin=(floatValueBytes[0]<<24)|(floatValueBytes[1]<<16)|(floatValueBytes[2]<<8)|(floatValueBytes[3])
                floatValue=Bytes2Float32(floatValueBin)
                datagram.append(floatValue)
            elif child.tag=='DEV':  # 
                datagram.insert(0,child.text)
                result-=1
            elif child.tag=='DId':
                datagram.insert(1,child.text)
                result-=1            
        return (result,datagram)
    
    @classmethod
    def scan(cls,FormModel,IP=None):
        if IP==None:
            IP=DEVICES_SUBNET+DEVICES_SCAN_IP4BYTE
        server=DEVICES_PROTOCOL + IP
        #server='http://127.0.0.1'
        (status,root)=cls.requestConfXML(server=server,xmlfile=DEVICES_CONFIG_FILE)
        errors=[]
        
        if status==200:
            (DEVICE_TYPE,DEVICE_CODE,DEVICE_IP) =cls.parseDeviceConfFile(xmlroot=root)
            try:
                Type=DeviceTypes.objects.get(Code=DEVICE_TYPE)
            except DeviceTypes.DoesNotExist: 
                Type=None
                errors.append(_('Unknown Device type: ') + DEVICE_TYPE + str(_('. You should firstly register the Device type.')))
                
            lastRow=Devices.objects.all().count()                     
            DeviceName='Device'+str(lastRow+1)
            DeviceType=DEVICE_TYPE
            DEVICE_CODE=lastRow+1+IP_OFFSET
            DeviceIP=DEVICES_SUBNET+str(DEVICE_CODE)
            payload={'DEVC':str(DEVICE_CODE)}
            (status,r)=cls.requestOrders(serverIP=IP,order='SetConf',payload=payload)
            if status==200 and Type!=None:
                form=FormModel(action='add',initial={'Name':DeviceName,'DVT':Type,'Code':DEVICE_CODE,'IP':DeviceIP})
                state='ConfigOK'
                (status,r)=cls.requestOrders(serverIP=IP,order='reset',payload=None)
                if status!=200:
                    errors.append(_('Device did not responded OK to reset order. Reset it manually to apply the new configuration.'))
            else:
                DEVICE_CODE=0
                DeviceIP=IP
                form=FormModel(action='scan',initial={'Name':DeviceName,'DVT':Type,'Code':DEVICE_CODE,'IP':DeviceIP})
                state='ConfigNoOK'
                if Type!=None:
                    errors.append(_('Device did not acknowledge the "SetConf" order. Revise the Device source code.'))
        else:
            state='Nothing'
            DEVICE_TYPE=None
            form=FormModel(action='scan',initial={'Name':'','Type':'','Code':'','IP':''})
        return {'devicetype':DEVICE_TYPE,'Form':form,'errors':errors}
    
    def uploadFirmware(self,file):
        import requests
        from django.core.files.storage import FileSystemStorage
        __headers = {
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:54.0) Gecko/20100101 Firefox/54.0",
            'Accept':"text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            'Authorization':"Basic ZGl5NGRvdDA6ZGl5NGRvdDA="
            }
        try:
            server=DEVICES_PROTOCOL+str(self.IP)
            r = requests.get(server+'/'+DEVICES_FIRMWARE_WEB,timeout=5,headers=__headers)
            logger.info('Upload GET firmware returned code ' + str(r.status_code))
            if r.status_code==200:
                fs = FileSystemStorage()
                r = requests.post(server+'/'+DEVICES_FIRMWARE_WEB,files={'file':fs.open(file,'rb')},timeout=20,headers=__headers)
            return r.status_code
        except Exception as ex:
            if type(ex) is requests.ConnectTimeout:
                return "Device did not respond to firmware update feature"
            else:
                return "Exception: "+ str(ex)
    
    def getPendingJobs(self):
        if self.DVT.Connection==MEMORY_CONNECTION:
            from .callbacks import PENDING_DB
            PJOBs= PENDING_DB.retrieve_pending_jobs(DV=self) 
            returned=[]
            for PJOB in PJOBs:
                returned.append({'date':PJOB[0].strftime("%Y-%m-%d"),'datagram':PJOB[1]})
            return returned
        else:
            return []
         
    def getFirmwareWeb(self,timeout=1):
        """
        ARDUINO RESPONSE: "<html><body><form method='POST' action='' enctype='multipart/form-data'>
                              <input type='file' name='update'>
                              <input type='submit' value='Update'>
                           </form>
                         </body></html>"
        """
        if self.DVT.Connection==REMOTE_TCP_CONNECTION:
            from .forms import FileUpload
            FORM=FileUpload(DV=self)
            return FORM
        else:
            return ''
        if self.DVT.Connection==REMOTE_TCP_CONNECTION:
            import requests
            import random
            server=DEVICES_PROTOCOL+str(self.IP)
            try:
                r = requests.get(server+'/'+DEVICES_FIRMWARE_WEB+'?t='+str(random.random()),timeout=timeout)
            except Exception as ex:
                if type(ex) is requests.ConnectTimeout:
                    return "Device did not respond to firmware update feature"
            if r.status_code==200:
                return r.text
            else:
                return "No remote firmware update feature is present"
        else:
            return ""
    
    @staticmethod
    def requestOrders(serverIP,order,payload,timeout=1,retries=3):
        """
        :callback       payload = {'key1': 'value1', 'key2': 'value2'}   
                        self.orders_request(server, 'orders', payload) 
        """
        import requests
        import random
        import time
        server=DEVICES_PROTOCOL+str(serverIP)
        #logger.info('Requested order ' + order + ' to IP ' + str(serverIP) + ' with payload ' +str(payload))
        while retries>0: 
            try:
                if payload!=None:
                    r = requests.post(server+'/orders/'+order,params=payload,timeout=timeout)
                else:
                    r = requests.post(server+'/orders/'+order,timeout=timeout)
                
                if r.status_code==200:
                    retries=0
                    return (200,_("Order confirmed by device"))
                else:
                    retries=retries-1
                    if retries==0:
                        return (r.status_code,_("Device responded with HTTP code ") + str(r.status_code))
            except Exception as ex:
                retries=retries-1
                if retries==0:
                    if type(ex) is requests.ConnectTimeout:
                        return (504,_("The device did not respond. Check connections and retry."))
                    else:
                        logger.error("Unexpected error in orders_request:"+ str(sys.exc_info()[1])) 
                        return (100,str(sys.exc_info()[1]))
            time.sleep(1)

        
    @staticmethod
    def requestConfXML(server,xmlfile,timeout=1):
        """
        Requests a xml file from a server
        :param server: 
        :param xmlfile:
        :return: root to the xml. Server error code if error
        :callback:      xmlfile='angles.xml'
                        xmlroot=myHttp.xml_request(server, xmlfile)
        """
        import requests
        import random
        try:
            import xml.etree.ElementTree as ET
            r = requests.get(server+'/'+xmlfile+'?t='+str(random.random()),timeout=timeout)     
            if r.status_code==200:
                root = ET.fromstring(r.text)                
                return (r.status_code,root)
            else:
                return (r.status_code,None)
        except:
            logger.error("Unexpected error in xml_data_request:"+ str(sys.exc_info()[1])) 
            return (100,None)
        
    def getRegistersDBTable(self,DG):
        return str(self.pk)+'_'+str(DG.pk)
    
    def _createRegistersTable(self,DG,Database):
        """
        Creates the table corresponding to the DV and Datagram DG
        """
        TableName=self.getRegistersDBTable(DG=DG)
        datagram=DG.getStructure()
        names=datagram['names']
        datatypes=datagram['datatypes']        
        logger.info('Creating "'+TableName+'" table with:')
        logger.info('   - DeviceType='+str(self.DVT))
        logger.info('   - fieldNames'+str(names)) 
        logger.info('   - fieldTypes'+str(datatypes))  
        fieldNames=names
        fieldTypes=datatypes
        try:
            if len(fieldNames)!=len(fieldTypes):
                logger.error('The length of the lists of names and types does not match in create_datagram_table')
                raise ValueError('The length of the lists of names and types does not match')
            else:
                temp_string=''
                for i in range(0,len(fieldNames)):
                    temp_string+='"'+fieldNames[i] + '" ' + fieldTypes[i] + ','
                sql=self.SQLcreateRegisterTable.replace('*',temp_string).replace('?','"'+TableName+'"')
                result=Database.executeTransactionWithCommit(SQLstatement=sql, arg=[])
                if result==0:
                    logger.info('Succeded in creating the table "'+TableName+'"') 
        except:
            text = str(_("Error in create_datagram_table: ")) + str(sys.exc_info()[1]) 
            raise DevicesAppException(text)
            PublishEvent(Severity=5,Text=text + 'SQL: ' + sql,Persistent=True,Code=self.getEventsCode()+'110')
            #logger.error ("Unexpected error in create_datagram_table:"+ str(sys.exc_info()[1]))
    
    def createRegistersTables(self,Database):
        """
        CREATES ALL REGISTERS TABLE:
        """
        DGs=Datagrams.objects.filter(DVT=self.DVT)
        for DG in DGs:
            self._createRegistersTable(DG=DG,Database=Database)
            
    def getInsertRegisterSQL(self,DatagramId):
        DG = Datagrams.objects.get(DVT=self.DVT,Identifier=DatagramId)
        datagram=DG.getStructure()
        
        names=datagram['names']
        types=datagram['datatypes']
        sql=self.SQLinsertRegister
        #SQLinsertRegister = ''' INSERT INTO %s(*) VALUES($) '''   # the * will be replaced by the column names and the $ by the values  
        temp_string1='?,'
        temp_string2='timestamp,' 
        for i in range(0,len(names)):
            if (names[i].find('$')>=0): # names[i]=STATUS_bits_Alarm0;Alarm1;Alarm2;Alarm3;Alarm4;Alarm5;Alarm6;Alarm7 
                                        #to remove the char ; from the name of the columns
                tempname=names[i].split('_')
                name=tempname[0]
                for component in tempname[1:]:
                    if '$' in component: # found the $ item meaning bit labels
                        break
                    name=name+'_'+component
                name=name
            else:
                name=names[i]
                
            if i<len(names)-1:
                temp_string1+= '?,'
                temp_string2+='"'+name+'"'+ ','
            else:
                temp_string1+='?'
                temp_string2+='"'+name+'"'
                
        sql=sql.replace('*',temp_string2)        
        sql=sql.replace('$',temp_string1).replace('%s','"'+str(self.pk)+'_'+str(datagram['pk'])+'"')
        return {'query':sql,'num_args':len(names)}
    
    
    def checkRegistersDB(self,Database):
        
        rows=Database.retrieve_DB_structure(fields='*')   #('table', 'devices', 'devices', 4, "CREATE TABLE devices...)
        
        required_DGs=[]
            
        DGs=Datagrams.objects.filter(DVT=self.DVT)
        for DG in DGs:
            found=False
            table_to_find=self.getRegistersDBTable(DG=DG)
            for row in rows:
                if (row[1]==table_to_find):   # found the table in the DB
                    found=True
                    datagram=DG.getStructure()
                    Database.checkTableColumns(table=table_to_find,desiredColumns={'names':datagram['names'],'datatypes':datagram['datatypes']})
                    break
            if found is not True:
                required_DGs.append(DG) 
                logger.info('The table '+table_to_find+' was not created.')
            
        for DG in required_DGs:
            self._createRegistersTable(DG=DG,Database=Database)
    
    def insertManyRegisters(self,DatagramId,year,values,NULL=False):
        """
        INSERTS A REGISTER IN THE registersDB INTO THE APPROPIATE TABLE.
        """
        try:                              
            
            query=self.getInsertRegisterSQL(DatagramId=DatagramId)
            sql=query['query']
            num_args=query['num_args']
                    
            from utils.BBDD import getRegistersDBInstance
            DB=getRegistersDBInstance(year=year)
            self.checkRegistersDB(Database=DB)
            result=DB.executeTransactionWithCommit(SQLstatement=sql, arg=values,many=True)
            self.sendUpdateSignals(DG_id=DatagramId,values=values,many=True)
            return result
        except:
            raise DevicesAppException("Unexpected error in insertManyRegisters for device "+str(self)+":" + str(sys.exc_info()[1]))
            
    def insertRegister(self,TimeStamp,DatagramId,year,values,NULL=False):
        """
        INSERTS A REGISTER IN THE registersDB INTO THE APPROPIATE TABLE.
        """
        try:                              
            TimeStamp=TimeStamp.replace(microsecond=0)
            
            query=self.getInsertRegisterSQL(DatagramId=DatagramId)
            sql=query['query']
            num_args=query['num_args']
            roundvalues=[TimeStamp,]
            if NULL==False:
                for i in range(0,num_args): 
                    try:
                        roundvalues.append(round(values[i],DECIMAL_POSITIONS))
                    except:
                        roundvalues.append(values[i])
            else:
                logger.info('Inserted NULL values on device ' + self.Name)  
                for i in range(0,num_args):  
                    roundvalues.append(None)
                    
            from utils.BBDD import getRegistersDBInstance
            DB=getRegistersDBInstance(year=TimeStamp.year)
            self.checkRegistersDB(Database=DB)
            result=DB.executeTransactionWithCommit(SQLstatement=sql, arg=roundvalues)
            self.sendUpdateSignals(DG_id=DatagramId,values=roundvalues)
            return result
        except:
            raise DevicesAppException("Unexpected error in insert_device_register for device "+str(self)+":" + str(sys.exc_info()[1]))
            
    def sendUpdateSignals(self,DG_id,values,many=False):
        DG=Datagrams.objects.get(Identifier=DG_id,DVT=self.DVT)
        datagram=DG.getStructure()
        if not many:
            timestamp=values[0]
            Values=values[1:]
        else:
            timestamp=values[0][0]
            Values=values[0][1:]
            
        SignalVariableValueUpdated.send(sender=self.pk, timestamp=timestamp,
                                                    Tags=datagram['names'],
                                                    Values=Values,Types=datagram['types'],
                                                    DataTypes=datagram['datatypes'])
    
    def sendNewDataSignals(self,DG_id):
        DG=Datagrams.objects.get(Identifier=DG_id,DVT=self.DVT)
        SignalNewDataFromDevice.send(sender=None,DV=self,DG=DG)
            
    def requestDatagram(self,DatagramId,timeout=1,writeToDB=True,resetOrder=True,retries=1):
        """
        Requests a xml file from a server
        :param Name
        :param Code:
        :param DatagramId: DatagramId='angles.xml'
        
        :callback:      

        """
        import xml.etree.ElementTree as ET
        import requests
        import random
        import time
            
        server=DEVICES_PROTOCOL+str(self.IP)
        
        timestamp=timezone.now().replace(microsecond=0) #para hora con info UTC
        
        LastUpdated=None
        out={'values':None,'Error':None,'LastUpdated':None}
        while retries>=0 and out['values']==None:
            try:
                r = requests.get(server+'/'+DatagramId+'.xml?t='+str(random.random()),timeout=timeout)
                if r.status_code==200:
                    root = ET.fromstring(r.text)
                    result,datagram=self.parseDatagram(xmlroot=root)
                    if result==0:
                        deviceCode=datagram[0]
                        if int(deviceCode)==self.Code:
                            del datagram[0:2]
                            Error=''
                            if writeToDB:
                                self.insertRegister(TimeStamp=timestamp, DatagramId=DatagramId, 
                                                                  year=timestamp.year, values=datagram,NULL=False)
                                if resetOrder:
                                    (code,x) = self.requestOrders(serverIP=str(self.IP),order='resetStatics',payload={})
                                    if code==200:
                                        Error=''
                                    else:
                                        Error='The device did not acknowledge the resetStatics order on datagram ' + DatagramId
                            for i,x in enumerate(datagram):
                                try:
                                    x=round(x,DECIMAL_POSITIONS)
                                except:
                                    x=None
                                datagram[i]=x
                            out['values']=datagram
                            out['LastUpdated']=timestamp
                            
                        else:
                            Error='The device responded with a different DeviceCode than the one expected on datagram ' + DatagramId
                            out['values']=None
                            out['LastUpdated']=None
                    else:
                        Error='Error in the format of the datagram received'
                        out['values']=None
                        out['LastUpdated']=None
                else:
                    Error='Error HTTP ' + str(r.status_code)
                    out['values']=None
                    out['LastUpdated']=None
                out['Error']=Error
            except:
                if str(sys.exc_info()[0]).find('Timeout')>=0:
                    if retries>0:
                        Error=self.Name+" did not respond within the timeout margin (default 1 sec)"
                    else:
                        Error="Finished retrying request to " + self.Name
                else:
                    logger.error('Unknown error: ' + str(sys.exc_info()[1]))
                    raise DevicesAppException('Unknown error: ' + str(sys.exc_info()[1]))
                
                if retries==0 and writeToDB:
                    self.insertRegister(TimeStamp=timestamp, DatagramId=DatagramId, 
                                        year=timestamp.year, values=[],NULL=True)
                    
                out['Error']=Error
                out['values']=None
                out['LastUpdated']=None
            retries-=1
            if out['values']==None:
                time.sleep(1)
        return out
    
    def getCharts(self,fromDate,toDate):
        DGs=Datagrams.objects.filter(DVT=self.DVT)
        charts=[]
        if DGs.count()>0:
            i=0
            for DG in DGs:
                datagram_info=DG.getStructure()
                sampletime=datagram_info['sample']*self.Sampletime
                Labeliterable=[]
                if self.CustomLabels=='':
                    self.setCustomLabels()
                
                CustomLabels=json.loads(self.CustomLabels)
                labels=CustomLabels[str(DG.pk)]
                for name in datagram_info['names']:
                    Labeliterable.append(labels[name])
            
                table=self.getRegistersDBTable(DG=DG)
                names=datagram_info['names'][:]
                names.insert(0,'timestamp')
                types=datagram_info['types']
                types.insert(0,'datetime')
                labels=Labeliterable
                labels.insert(0,'timestamp')
                plottypes=datagram_info['plottypes']
                plottypes.insert(0,'timestamp')
                units=datagram_info['units']
                units.insert(0,'timestamp')
                from .charting import generateChart
                chart=generateChart(table=table,fromDate=fromDate,toDate=toDate,names=names,types=types,
                                    labels=labels,plottypes=plottypes,units=units,sampletime=sampletime)  
                 
                charts.append(chart)
        return charts
        
    def deleteRegistersTables(self):
        from utils.BBDD import getRegistersDBInstance
        DGs=Datagrams.objects.filter(DVT=self.DVT)
        DB=getRegistersDBInstance()
        for DG in DGs:
            table=self.getRegistersDBTable(DG=DG)
            DB.dropTable(table=table)

    
        
@receiver(post_save, sender=Devices, dispatch_uid="update_Devices")
def update_Devices(sender, instance, update_fields,**kwargs):
    if kwargs['created']:   # new instance is created
        instance.updateAutomationVars(setSubsystems=True)
               
@receiver(post_delete, sender=Devices, dispatch_uid="delete_Devices")
def delete_Devices(sender, instance,**kwargs):
    instance.deleteAutomationVars()
    logger.info('Se ha eliminado el dispositivo ' + str(instance))

class DevicesBinding(WebsocketBindingWithMembers):

    model = Devices
    stream = "Device_params"
    fields = ["Name","IO","Code","IP","Type","Sampletime","State","LastUpdated","Error"]

    @classmethod
    def group_names(cls, *args, **kwargs):
        return ["Device-models",]

    def has_permission(self, user, action, pk):
        return True
        
        
class DatagramItems(models.Model):
    
    class Meta:
        verbose_name = _('Datagram item')
        verbose_name_plural = _('Datagram items')
        
    Tag = models.CharField(max_length=20,unique=True)
    DataType= models.CharField(max_length=20,choices=DATATYPE_CHOICES)
    PlotType= models.CharField(max_length=10,choices=PLOTTYPE_CHOICES,default=SPLINE_PLOT)
    Units = models.CharField(max_length=10,null=True,blank=True)
    
    def clean(self):
        if self.DataType==DTYPE_DIGITAL:
            self.Units='bits'
            self.PlotType=LINE_PLOT

    def store2DB(self):
        self.full_clean()
        try:
            super().save()
        except OperationalError:
            logger.error("Operational error on Django. System restarted")
            import os
            os.system("sudo reboot")
        
    def __str__(self):
        return self.Tag
    
    def getHumanName4Digital(self,bit):
        name=self.getHumanName().split('$')[bit]
        return name
        
    def getHumanName(self):
        if self.DataType!= DTYPE_DIGITAL:
            return self.Tag+'_'+self.Units
        else:
            kk=''
            for i in range(0,8): 
                kk+='$'+self.Tag+' bit ' + str(i) 
            kk=kk[1:]
            return kk
    
class CronExpressions(models.Model):
    
    class Meta:
        verbose_name = _('Cron expression')
        verbose_name_plural = _('Cron expressions')
    
    Identifier = models.CharField(max_length=50,unique=True)
    
    DayOfWeek = models.CharField(max_length=20,blank=True,default='*',
                           help_text=str(_('Days in the week that it would trigger. '
                                             ' "1-3" would trigger it on Mon., Tue. and Wed. of the week,'
                                             ' "1,3" would trigger it only on Mon. and Wed.,'
                                             ' "*/2" would trigger every two days,'
                                             ' leaving it blank or setting an "*" would trigger it every day.')))
    Month = models.CharField(max_length=20,blank=True,default='*',
                             help_text=str(_('Months that it would trigger. '
                                             ' "1-3" would trigger it on Jan., Febr. and March,'
                                             ' "1,3" would trigger it only on Jan. and March,'
                                             ' "*/2" would trigger every two months,'
                                             ' leaving it blank or setting an "*" would trigger it every month.')))
    DayOfMonth = models.CharField(max_length=20,blank=True,default='*',
                           help_text=str(_('Days that it would trigger. '
                                             ' "1-3" would trigger it on the 1st, 2nd and 3rd day of the month,'
                                             ' "1,3" would trigger it only on 1st and 3rd,'
                                             ' "*/2" would trigger every two days,'
                                             ' leaving it blank or setting an "*" would trigger it every day.')))
    Hours = models.CharField(max_length=20,blank=True,default='0',
                            help_text=str(_('Hours that it would trigger. '
                                             ' "1-3" would trigger it at 1, 2 and 3 a.m.,'
                                             ' "1,3" would trigger it only at 1 and 3 p.m.,'
                                             ' "*/2" would trigger every two hours,'
                                             ' leaving it blank or setting an "*" would trigger it every hour.')))
    Minutes = models.CharField(max_length=20,blank=True,default='0',
                            help_text=str(_('Minutes that it would trigger. '
                                             ' "1-3" would trigger it at minutes 1, 2 and 3,'
                                             ' "1,3" would trigger it only at minutes 1 and 3 ,'
                                             ' "*/2" would trigger every two minutes,'
                                             ' leaving it blank or setting an "*" would trigger it every minute.')))
    Seconds = models.CharField(max_length=20,blank=True,default='0',
                            help_text=str(_('Seconds that it would trigger. '
                                             ' "1-3" would trigger it at seconds 1, 2 and 3,'
                                             ' "1,3" would trigger it only at seconds 1 and 3 ,'
                                             ' "*/2" would trigger every two seconds,'
                                             ' Setting an "*" would trigger it every second.')))
        
    def __str__(self):
        return self.Identifier
    
    def clean(self):
        super().clean()
        if self.Month=='':
            self.Month='*'
        if self.DayOfMonth=='':
            self.DayOfMonth='*'
        if self.DayOfWeek=='':
            self.DayOfWeek='*'
        if self.Hours=='':
            self.Hours='*'
        if self.Minutes=='':
            self.Minutes='*'
        if self.Seconds=='':
            self.Minute='0'
        
    def store2DB(self):
        self.full_clean()
        try:
            super().save()
        except OperationalError:
            logger.error("Operational error on Django. System restarted")
            import os
            os.system("sudo reboot")
    
    def getCronExpression(self):
        return {'seconds':self.Seconds,'minutes':self.Minutes,'hours':self.Hours,'dayofmonth':self.DayOfMonth,'month':self.Month,'dayofweek':self.DayOfWeek}
        
class Datagrams(models.Model):
    
    class Meta:
        verbose_name = _('Datagram')
        verbose_name_plural = _('Datagrams')
        unique_together = (('DVT', 'Identifier'),('DVT', 'Code'))
        
    Identifier = models.CharField(max_length=20)
    Code= models.PositiveSmallIntegerField(help_text='Identifier byte-type code')
    Type= models.PositiveSmallIntegerField(choices=DATAGRAMTYPE_CHOICES)
    Cron = models.ForeignKey(CronExpressions,help_text=str(_('The cron expression that controls the polling. Only applies to cronned datagrams.')),
                            on_delete=models.CASCADE,related_name='datagrams',null=True,blank=True)
    DVT = models.ForeignKey(DeviceTypes,on_delete=models.CASCADE)
    ITMs = models.ManyToManyField(DatagramItems, through='ItemOrdering')
    
    Enable=models.BooleanField(default=True,help_text=str(_('Enables the datagram to be queried')))
    
    def __str__(self):
        return self.Identifier
    
    def serialize(self):
        return {'pk':self.pk,'id':self.Identifier}
    
    def store2DB(self,update_fields=[]):
        self.full_clean()
        try:
            if self.pk:
                super().save(update_fields=update_fields) 
            else:
                super().save() 
        except OperationalError:
            logger.error("Operational error on Django. System restarted")
            import os
            os.system("sudo reboot")
        
    
    def isAsynchronous(self):
        return self.Type==DG_ASYNCHRONOUS
        
    def isSynchronous(self):
        return self.Type==DG_SYNCHRONOUS
    
    def isCronned(self):
        return self.Type==DG_CRONNED
    
    def getDBTypes(self):
        types=[]
        for item in self.itemordering_set.all():
            types.insert(item.Order-1,item.ITM.DataType)
        types.insert(0,'datetime')
        return types
    
    @staticmethod
    def getInfoFromItemName(name):
        info=name.split('_')
        if len(info)==3:
            try:
                IT=DatagramItems.objects.get(pk=int(info[0]))
                return {'itempk':info[0],'numitem':info[1],'datagrampk':info[2],'type':IT.DataType,'units':IT.Units,'human':IT.getHumanName()}
            except:
                raise DevicesAppException(str(_('The datagram item name ')) + str(name) + str(_(' raised exception when getting its info.')))
        else:
            raise DevicesAppException(str(_('The datagram item name ')) + str(name) + str(_(' does not have the proper structure "Item.pk_NumItem_Datagram.pk"')))
            
    def getStructure(self):
        """RETURNS THE STRUCTURE OF A DATAGRAM ASSIGNING THE FOLLOWING NAMES TO THE VARIABLES (COLUMNS IN THE DB)
        THE COLUMN NAME IS THE CONCATENATION OF THE VARIABLE PK + '_'+ NUMBER. THE NUMBER IS A CORRELATIVE NUMBER BETWEEN 1 AND THE NUMBER OF REPETITIONS OF 
        THE VARIABLE IN THE DATAGRAM
        """
        names=[]
        types=[]
        datatypes=[]
        units=[]
        plottypes=[]
        datagramID=self.Identifier
        checkedPK={}
        for ITO in self.itemordering_set.all().order_by('Order'):
            numItems=1
            if not str(ITO.ITM.pk) in checkedPK:
                checkedPK[str(ITO.ITM.pk)]=1
            else:
                numItems=checkedPK[str(ITO.ITM.pk)]+1
                checkedPK[str(ITO.ITM.pk)]+=1
            names.insert(ITO.Order-1,str(ITO.ITM.pk)+'_'+str(numItems)+'_'+str(self.pk))
            units.insert(ITO.Order-1,ITO.ITM.Units)
            plottypes.insert(ITO.Order-1,ITO.ITM.PlotType)
            if ITO.ITM.DataType!= DTYPE_DIGITAL:
                types.insert(ITO.Order-1,ITO.ITM.DataType)
                datatypes.insert(ITO.Order-1,ITO.ITM.DataType)
            else:
                types.insert(ITO.Order-1,ITO.ITM.DataType)
                datatypes.insert(ITO.Order-1,DTYPE_INTEGER)
        if self.isSynchronous():
            sample=1
        else:
            sample=0
        
        return {'pk':self.pk,'ID':datagramID,'names':names,'types':types,'datatypes':datatypes,'units':units,'plottypes':plottypes,'sample':sample}


@receiver(post_save, sender=Datagrams, dispatch_uid="update_Datagrams")
def update_Datagrams(sender, instance, update_fields,**kwargs):
    
    if not kwargs['created']:   # an instance has been modified
        logger.info('Se ha modificado el datagram ' + str(instance.DVT)+"_"+str(instance))
        
    else:
        logger.info('Se ha creado el datagram ' + str(instance.DVT)+"_"+str(instance))
        logger.info('Tiene ' + str(instance.ITMs.count())+' ' + (DatagramItems._meta.verbose_name.title() if (instance.ITMs.count()==1) else DatagramItems._meta.verbose_name_plural.title()))
        for item in instance.ITMs.all():
            logger.info('   - ' + str(item.Tag))


    
class ItemOrdering(models.Model):
    DG = models.ForeignKey(Datagrams, on_delete=models.CASCADE)
    ITM = models.ForeignKey(DatagramItems, on_delete=models.CASCADE,blank=True,null=True)
    Order = models.PositiveSmallIntegerField(help_text='Position in the dataframe 1-based')
    
    def __str__(self):
        return str(self.DG) + ':' +str(self.Order)
        
    class Meta:
        verbose_name = _('Item')
        verbose_name_plural = _('Items')
        ordering = ('Order',)

class ParameterValues(models.Model):
    Command = models.ForeignKey('DevicesAPP.DeviceCommands', on_delete=models.CASCADE)
    Parameter = models.ForeignKey('DevicesAPP.CommandParameters', on_delete=models.CASCADE)
    Value = models.CharField(max_length=20)
    
    def __str__(self):
        return str(self.Command) + ':' +str(self.Parameter)
        
    class Meta:
        verbose_name = _('Parameter')
        verbose_name_plural = _('Parameters') 
        unique_together = ('Parameter', 'Command',)    

class CommandParameters(models.Model):
    Tag = models.CharField(max_length=10)
    def __str__(self):
        return self.Tag
    
class DeviceCommands(models.Model):
    DVT = models.ForeignKey(DeviceTypes,on_delete=models.CASCADE)
    Label = models.CharField(max_length=20,null=True,blank=True)
    Identifier = models.CharField(max_length=20)
    Parameters = models.ManyToManyField(CommandParameters, through='ParameterValues')

    def __str__(self):
        if self.Label:
            return self.Label
        else:
            return self.Identifier
        
    def getPayload(self):
        payload={}
        for PARAM in self.parametervalues_set.all():
            payload[PARAM.Parameter.Tag]=PARAM.Value
        return payload
        
    class Meta:
        verbose_name = _('Command')
        verbose_name_plural = _('Commands')
        
class Beacons(models.Model):
    Identifier = models.CharField(max_length=20,unique=True,error_messages={'unique':_("Invalid Beacon name - This name already exists in the DB.")})
    Latitude = models.FloatField()
    Longitude = models.FloatField()
    WeatherObserver=models.OneToOneField(Devices,on_delete=models.CASCADE,related_name='device2beacon',
                                         null=True,blank=True,limit_choices_to={'DVT__Code': 'OpenWeatherMap'})
    
    def distance_to(self,other):
        from math import sin, cos, sqrt, atan2, radians
        # approximate radius of earth in km
        R = 6373.0
        lat1 = radians(self.Latitude)
        lon1 = radians(self.Longitude)
        lat2 = radians(other.Latitude)
        lon2 = radians(other.Longitude)
        
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        
        a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        
        distance = R * c
        return round(distance,1)
    
    def __str__(self):
        return self.Identifier
    
