# coding: utf-8

import pandas as pd
import numpy as np
import datetime
import json
import logging
import sys
import pytz
from tzlocal import get_localzone
import itertools

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required,user_passes_test
from django.contrib.auth import login
from django.core.urlresolvers import reverse
from django.http import HttpResponse,HttpResponseNotFound,HttpResponseRedirect
from django.shortcuts import render, render_to_response,get_object_or_404,redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.views import generic
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger("project")

from . import forms
from . import models

from .constants import APP_TEMPLATE_NAMESPACE,LOCAL_CONNECTION,REMOTE_TCP_CONNECTION,REMOTE_RS485_CONNECTION,MEMORY_CONNECTION, \
                        FORM_FIRST_RENDER_MSG,FORM_ISVALID_MSG,FORM_ISNOTVALID_MSG,SCAN_DEVICENOFOUND,SCAN_DEVICEFOUND,TESTS_USER_AGENT,\
                        GPIO_INPUT,GPIO_OUTPUT,GPIO_SENSOR

from MainAPP.models import AutomationVariables

LOGIN_PAGE='accounts:login'
def home(request):
    if request.method == 'POST': # the form has been submited
        return render(request, APP_TEMPLATE_NAMESPACE+'/home.html') 
    else:
        return render(request, APP_TEMPLATE_NAMESPACE+'/home.html') 

def modelSplitter(model):
    if model=='devices':
        Header1 = models.Devices._meta.verbose_name.title()
        Model=models.Devices
        FormModel=forms.DevicesForm
        FormKwargs={'action':'add+scan'}
        message=models.Devices._meta.verbose_name.title()+ str(_(' saved OK'))
        lastAction='getLabels'
    elif model=='devicetypes':
        Header1 = models.DeviceTypes._meta.verbose_name.title()
        Model=models.DeviceTypes
        FormModel=forms.DeviceTypesForm
        FormKwargs={'action':'add'}
        message=models.DeviceTypes._meta.verbose_name.title()+ str(_(' saved OK'))
        lastAction='add'
    elif model=='maingpios':
        Header1 = models.MainGPIOs._meta.verbose_name.title()
        Model=models.MainGPIOs
        FormModel=forms.MainGPIOsForm
        FormKwargs={'action':'add'}
        message=models.MainGPIOs._meta.verbose_name.title()+ str(_(' saved OK'))
        lastAction='add'
    elif model=='maindevicevars':
        Header1 = models.MainDeviceVars._meta.verbose_name.title()
        Model=models.MainDeviceVars
        FormModel=forms.MainDeviceVarsForm
        FormKwargs={'action':'add'}
        message=models.MainDeviceVars._meta.verbose_name.title()+ str(_(' saved OK'))
        lastAction='add'
    elif model=='automationvars':
        Header1 = AutomationVariables._meta.verbose_name.title()
        Model=AutomationVariables
        FormModel=forms.MainDeviceVarsForm
        FormKwargs={'action':'add'}
        message=models.MainDeviceVars._meta.verbose_name.title()+ str(_(' saved OK'))
        lastAction='add'
    else:
        return None
    return {'Header1':Header1,'Model':Model,'FormModel':FormModel,'FormKwargs':FormKwargs,'message':message,'lastAction':lastAction}

def checkUserPermissions(request,action,model):
    # performing some custom type of logic
    if not request.user.has_perm('DevicesAPP.'+action+'_'+model):
        return False
    else:
        return True
    
# VIEWS FOR THE MODELS
def add(request,model):
    
    if not checkUserPermissions(request=request,action='add',model=model):
        return HttpResponseRedirect(reverse(LOGIN_PAGE))
        
    data=modelSplitter(model=model)
    if data==None:
        return HttpResponseNotFound('<h1>No Page Here</h1>') 
    else:
        Header1=str(_('Adding a new ')) +data['Header1']
        Model=data['Model']
        FormModel=data['FormModel']
        FormKwargs=data['FormKwargs']
        message=data['message']
        lastAction=data['lastAction']
    
    if request.method == 'POST': # the form has been submited
        form=FormModel(request.POST,**FormKwargs)
        if form.is_valid():
            instance=form.save()
            if instance.pk==None:
                instance.store2DB()
            if lastAction!='add':
                FormKwargs['action']=lastAction
                ShowForm=True
            else:
                ShowForm=False
            form=FormModel(instance=instance,**FormKwargs)
            
            return render(request, APP_TEMPLATE_NAMESPACE+'/add.html',{'Header1':Header1,
                                                                       'GreenHead':message,
                                                                       'RedMessages':[],
                                                                       'ShowForm':ShowForm,
                                                                       'TestMsg':FORM_ISVALID_MSG,
                                                                       'Form': form
                                                                       })
        else:
            return render(request, APP_TEMPLATE_NAMESPACE+'/add.html',{'Header1':Header1,
                                                                       'GreenMessages':[],
                                                                       'RedMessages':[_('Something is wrong with the data provided'),],
                                                                       'ShowForm':True,
                                                                       'TestMsg':FORM_ISNOTVALID_MSG,
                                                                       'Form': form
                                                                       })
    else:
        form=FormModel(**FormKwargs)
        return render(request, APP_TEMPLATE_NAMESPACE+'/add.html',{'Header1':Header1,
                                                                   'GreenMessages':[],
                                                                   'RedMessages':[],
                                                                   'ShowForm':True,
                                                                   'TestMsg':FORM_FIRST_RENDER_MSG,
                                                                   'Form': form
                                                                   })
    
def setCustomLabels(request,pk):
    Header1=str(_('Setting up the labels for the data from ')) 
    if request.method == 'POST': # the form has been submited
        DV=models.Devices.objects.get(pk=pk)
        DGs=models.Datagrams.objects.filter(DVT=DV.DVT)
        form=forms.DatagramCustomLabelsForm(request.POST,DV=DV,DGs=DGs)
        if form.is_valid():
            CustomLabels=form.get_variablesLabels()
            DV.CustomLabels=json.dumps(CustomLabels)
            DV.save()
            DV.updateAutomationVars()
            message= str(_('Custom labels for device ')) + DV.Name + str(_(' have been set properly.'))
            return render(request, APP_TEMPLATE_NAMESPACE+'/add.html',{'Header1':Header1+ DV.Name,
                                                                   'GreenHead':message,
                                                                   'RedMessages':[],
                                                                   'ShowForm':False,
                                                                   'TestMsg':FORM_ISVALID_MSG,
                                                                   'Form': form
                                                                   })
        else:
            return render(request, APP_TEMPLATE_NAMESPACE+'/add.html',{'Header1':Header1+ DV.Name,
                                                                   'GreenMessages':[],
                                                                   'RedMessages':[],
                                                                   'ShowForm':False,
                                                                   'TestMsg':FORM_ISNOTVALID_MSG,
                                                                   'Form': form
                                                                   })
    else:
        DV=models.Devices.objects.get(pk=pk)
        DGs=models.Datagrams.objects.filter(DVT=DV.DVT)
        form=forms.DatagramCustomLabelsForm(None,DV=DV,DGs=DGs)
        return render(request, APP_TEMPLATE_NAMESPACE+'/add.html',{'Header1':Header1 + DV.Name,
                                                                   'GreenMessages':[],
                                                                   'RedMessages':[],
                                                                   'ShowForm':True,
                                                                   'TestMsg':FORM_FIRST_RENDER_MSG,
                                                                   'Form': form
                                                                   }) 

@user_passes_test(lambda u: u.has_perm('DevicesAPP.scan_devices'))
def scan(request,model):
    data=modelSplitter(model=model)
    if data==None:
        return HttpResponseNotFound('<h1>No Page Here</h1>') 
    else:
        Header1=str(_('Scanning for a new ')) +data['Header1']
        Model=data['Model']
        FormModel=data['FormModel']
        message=data['message']
        lastAction=data['lastAction']
    
    if request.method == 'POST': # the form has been submited
        if 'HTTP_USER_AGENT' in request.META and request.META['HTTP_USER_AGENT']==TESTS_USER_AGENT:
            IP='127.0.0.1'
        else:
            IP=None
        #IP='127.0.0.1'
        scan=Model.scan(FormModel=FormModel,IP=IP)
        RedMessages=[]
        if scan['devicetype']!=None:
            GreenHead=str(_('Found a ')) + scan['devicetype']
            TestMsg=SCAN_DEVICEFOUND
            ShowForm=True
        else:
            RedMessages.append(_('No device was found'))
            GreenHead=''
            TestMsg=SCAN_DEVICENOFOUND
            ShowForm=False
        if scan['errors']!=[]:
            for error in scan['errors']:
                RedMessages.append(error)
            
        return render(request, APP_TEMPLATE_NAMESPACE+'/add.html',{'Header1':Header1,
                                                                   'GreenHead':GreenHead,
                                                                   'GreenMessages':[],
                                                                   'RedMessages':RedMessages,
                                                                   'ShowForm':ShowForm,
                                                                   'TestMsg':TestMsg,
                                                                   'Form': scan['Form']
                                                                   })
    else:
        form=FormModel(action='scan')
        return render(request, APP_TEMPLATE_NAMESPACE+'/add.html',{'Header1':Header1,
                                                                    'TestMsg':FORM_FIRST_RENDER_MSG,
                                                                   'ShowForm':True,
                                                                   'Form': form}) 
                

def viewGraphs(request,model):
    if not checkUserPermissions(request=request,action='view',model=model):
        return HttpResponseRedirect(reverse(LOGIN_PAGE))
    if request.method == 'POST': # the form has been submited
        form = forms.DeviceGraphs(request.POST)
        
        #logger.debug(str(request.POST))
        if form.is_valid():
            DeviceName=form.cleaned_data['DeviceName']
            fromDate=form.cleaned_data['fromDate']
            toDate=form.cleaned_data['toDate']
            
            form_clean = forms.DeviceGraphs({'DeviceName':form['DeviceName'].value(),'fromDate':fromDate,'toDate':toDate})
            
            fromDate=fromDate-fromDate.utcoffset() 
            toDate=toDate-toDate.utcoffset()                 

            try:
                DV=models.Devices.objects.get(Name=DeviceName)
            except models.Devices.DoesNotExist: 
                DV='MainUnit'
            
            charts=[]
            if DV!='MainUnit':  # a device is selected
                #logger.info('The device is a '+str(DV.DVT))
                charts=DV.getCharts(fromDate=fromDate,toDate=toDate)
            else:
                logger.info('The device is the Main Unit')
                charts=models.MainGPIOs.getCharts(fromDate=fromDate,toDate=toDate)
                charts.append(models.MainDeviceVars.getCharts(fromDate=fromDate,toDate=toDate))
            if charts==[]:
                message=_('The device ') + DV.Name + _(' does not have any datagram defined.')+'\n' + \
                        _('Please define a datagram for the device type ') + DV.DVT.Code + _(' and start polling to ') + \
                        _('gather some data to be plotted.')
            else:
                message=''
            return render(request, APP_TEMPLATE_NAMESPACE+'/graph.html', {'DeviceName':DeviceName.replace('_',' '),
                                                                          'chart': json.dumps(charts),
                                                                          'message':message,
                                                                          'Form':form_clean})
        else:
            return render(request, APP_TEMPLATE_NAMESPACE+'/graph.html',{'Form': form})
    else:
        form=forms.DeviceGraphs()
        return render(request, APP_TEMPLATE_NAMESPACE+'/graph.html',{'Form': form})
    
def viewList(request,model):
    if not checkUserPermissions(request=request,action='view',model=model):
        return HttpResponseRedirect(reverse(LOGIN_PAGE))
    
    data=modelSplitter(model=model)
    if data==None:
        return HttpResponseNotFound('<h1>No Page Here</h1>') 
    else:
        Header1=str(_('List of ')) +data['Header1']
        Model=data['Model']
        FormModel=data['FormModel']
        message=data['message']
        lastAction=data['lastAction']
    
    if request.method == 'POST': # the form has been submited
        return HttpResponseNotFound('<h1>No Page Here</h1>') 
    else:
        if Model == models.Devices:
            from django.db.models import Q
            DVs=Model.objects.all()
            remote_DVs=DVs.filter(Q(DVT__Connection=REMOTE_TCP_CONNECTION) | Q(DVT__Connection=REMOTE_RS485_CONNECTION))
            numrows_remote=remote_DVs.count()
            local_DVs=DVs.filter(DVT__Connection=LOCAL_CONNECTION)
            numrows_local=local_DVs.count()
            memory_DVs=DVs.filter(DVT__Connection=MEMORY_CONNECTION)
            numrows_memory=memory_DVs.count()
            return render(request, APP_TEMPLATE_NAMESPACE+'/showDevicesTables.html',{'numrows_table1':numrows_remote,'rows_table1':remote_DVs,
                                                                            'numrows_table2':numrows_local,'rows_table2':local_DVs,
                                                                            'numrows_table3':numrows_memory,'rows_table3':memory_DVs,})
        elif Model == models.DeviceTypes:
            RWs=Model.objects.all()
            numrows=RWs.count()
            message_norows=str(_('There are no ')) + data['Header1'] +str(_(' registered.'))
            return render(request, APP_TEMPLATE_NAMESPACE+'/showDeviceTypeTable.html',{'Header1':Header1,
                                                                            'numrows_table1':numrows,
                                                                            'message_norows1':message_norows,
                                                                            'rows_table1':RWs
                                                                            })
        elif Model == models.MainGPIOs:
            IOs=Model.objects.all()
            OUTs=IOs.filter(Direction=GPIO_OUTPUT)
            numrows_out=OUTs.count()
            INs=IOs.filter(Direction=GPIO_INPUT)
            numrows_in=INs.count()
            SENSORs=IOs.filter(Direction=GPIO_SENSOR)
            numrows_sensor=SENSORs.count()
            return render(request, APP_TEMPLATE_NAMESPACE+'/showGPIOsTables.html',{'numrows_table1':numrows_out,'rows_table1':OUTs,'cols_table1':4,
                                                                               'numrows_table2':numrows_in,'rows_table2':INs,'cols_table2':3,
                                                                               'numrows_table3':numrows_sensor,'rows_table3':SENSORs,'cols_table3':3,
                                                                                    })
        elif Model == models.MainDeviceVars:
            RWs=Model.objects.all()
            numrows=RWs.count()
            message_norows=str(_('There are no ')) + data['Header1'] +str(_(' registered.'))
            return render(request, APP_TEMPLATE_NAMESPACE+'/showMainDeviceVarsTable.html',{'Header1':Header1,
                                                                            'numrows_table1':numrows,
                                                                            'message_norows1':message_norows,
                                                                            'rows_table1':RWs
                                                                            })
        else:
            return HttpResponseNotFound('<h1>No Page Here for Model '+str(model)+'</h1>') 

def edit(request,model,pk):
    if not checkUserPermissions(request=request,action='change',model=model):
        return HttpResponseRedirect(reverse(LOGIN_PAGE))
    
    data=modelSplitter(model=model)
    if data==None:
        return HttpResponseNotFound('<h1>No Page Here</h1>') 
    else:
        Header1=str(_('Editing a ')) +data['Header1']
        Model=data['Model']
        FormModel=data['FormModel']
        FormKwargs=data['FormKwargs']
        message=data['message']
        lastAction=data['lastAction']
    
    Instance = get_object_or_404(Model, pk=pk)
    
    if request.method == 'POST': # the form has been submited
        form=FormModel(request.POST,action='edit',instance=Instance)
        if form.is_valid():
            instance=form.save()
            if lastAction!='add':
                FormKwargs['action']=lastAction
                ShowForm=True
            else:
                ShowForm=False
            form=FormModel(instance=instance,**FormKwargs)
            return render(request, APP_TEMPLATE_NAMESPACE+'/add.html',{'Header1':Header1+' ' + str(Instance),
                                                                       'GreenHead':message,
                                                                       'RedMessages':[],
                                                                       'ShowForm':ShowForm,
                                                                       'TestMsg':FORM_ISVALID_MSG,
                                                                       'Form': form
                                                                       }) 
        else:
            return render(request, APP_TEMPLATE_NAMESPACE+'/add.html',{'Header1':Header1+' ' + str(Instance),
                                                                       'GreenMessages':[],
                                                                       'RedMessages':[_('Something is wrong with the data provided'),],
                                                                       'ShowForm':True,
                                                                       'TestMsg':FORM_ISNOTVALID_MSG,
                                                                       'Form': form
                                                                       }) 
    else:
        form=FormModel(action='edit',instance=Instance)

        return render(request, APP_TEMPLATE_NAMESPACE+'/add.html',{'Header1':Header1+' ' + str(Instance),
                                                                   'GreenMessages':[],
                                                                   'RedMessages':[],
                                                                   'ShowForm':True,
                                                                   'TestMsg':FORM_FIRST_RENDER_MSG,
                                                                   'Form': form
                                                                   })  

def toggle(request,model,pk):
    if not checkUserPermissions(request=request,action='toggle',model=model):
        return HttpResponseRedirect(reverse(LOGIN_PAGE))
    
    data=modelSplitter(model=model)
    Model=data['Model']
    Instance = get_object_or_404(Model, pk=pk)
    
    if request.method == 'GET':
        if model=='devices':
            Instance.togglePolling()
            messages.info(request, 'accordion1')
        elif model=='maingpios':
            Instance.toggle()
            messages.info(request, 'accordion4')
        elif model=='maindevicevars':
            Instance.toggle()
            messages.info(request, 'accordion2')
        else:
            return HttpResponseNotFound('<h1>No Page Here for Model '+str(model)+'</h1>') 
        
    return redirect(request.META['HTTP_REFERER'])
    
@login_required
@user_passes_test(lambda u: u.has_perm('DevicesAPP.view_devices'))
def AdvancedDevicePage(request,pk):
    import datetime
    import json
    DV=models.Devices.objects.get(pk=pk)
    pendingJobs=DV.getPendingJobs()
    firmware=DV.getFirmwareWeb()
    LatestData=DV.getLatestData()
    COMMANDS=models.DeviceCommands.objects.filter(DVT=DV.DVT)
    from django.contrib.messages import get_messages
    storage = get_messages(request)
    firmware_data=None
    for message in storage:
        if 'Firmware updated OK' == message.message or 'Firmware update FAILED'== message.message:
            firmware_data=message.message
    Order={}
    DGs=[]
    if LatestData:
        for datagram in LatestData:
            DG=models.Datagrams.objects.get(pk=datagram)
            DGs.append(DG.serialize())
            Order[datagram]=DG.getStructure()['names']
            for element in LatestData[datagram]:
                if isinstance(LatestData[datagram][element],datetime.datetime):
                    LatestData[datagram][element]=LatestData[datagram][element].timestamp()
    return render(request, APP_TEMPLATE_NAMESPACE + '/'+DV.DVT.Code+'.html',
                                                        {'Device':DV,'Latest':json.dumps(LatestData),'Order':json.dumps(Order),
                                                         'Commands':COMMANDS,'Firmware':firmware,'DGs':json.dumps(DGs),
                                                         'pendingJobs':pendingJobs,'firmware_data':firmware_data})

def handle_uploaded_file(f):
    import os
    path=os.path.join(settings.MEDIA_ROOT,f.name)
    with open(path, 'wb+') as destination:
        for chunk in f.chunks():
            destination.write(chunk)
    return path
            
@login_required
@user_passes_test(lambda u: u.has_perm('DevicesAPP.view_devices'))
def firmwareUpdate(request,devicePK):
    DV=get_object_or_404(models.Devices,pk=int(devicePK))
    if request.method == 'POST' and request.FILES['file']:
        from django.core.files.storage import FileSystemStorage
        firmwareFile = request.FILES['file']
        filepath=handle_uploaded_file(f=firmwareFile)
        logger.info('Upload firmware stored at ' + str(filepath))
        status= DV.uploadFirmware(file=filepath)
        logger.info('Upload firmware returned code ' + str(status))
        if status==200:
            messages.info(request, 'Firmware updated OK')
        else:
            messages.info(request, 'Firmware update FAILED')
            
    return redirect(request.META['HTTP_REFERER'])
            
    
# @login_required
# @user_passes_test(lambda u: u.has_perm('DevicesAPP.view_devices'))
# def sendCMD(request,CMD,DV,payload=''):
#     import datetime
#     import json
#     DV=models.Devices.objects.get(pk=DV)
#     COMMAND=models.DeviceCommands.objects.get(pk=CMD)
#     DV.requestCMD(server=DV.IP,order=COMMAND.Identifier,payload=payload,timeout=1)
#     #print("Sent command " + str(COMMAND)+ " to the device " + str(DV))
#     return HttpResponse(status=204)
    
# END

@csrf_exempt
def asynchronous_datagram(request):
    import xml.etree.ElementTree as ET
    from utils.BBDD import getRegistersDBInstance
    from .models import Devices,Datagrams
    if request.method == 'POST':
        DB=getRegistersDBInstance()
        xmltext=str(request.body,'utf-8').replace("'","")
        root = ET.fromstring(xmltext)
        (result,datagram)=Devices.parseDatagram(xmlroot=root)
        logger.info('Async Request: Datagram ' + str(datagram))
        if result==0:
            timestamp=timezone.now()  
            deviceCode=datagram[0]
            datagramCode=datagram[1]
            DV=Devices.objects.get(Code=deviceCode)
            DG=Datagrams.objects.get(DVT=DV.DVT,Code=int(datagramCode))
            del datagram[0:2]
            if DV!=None and DG!=None:
                DV.insertRegister(TimeStamp=timestamp, DatagramId=DG.Identifier, year=timestamp.year, values=datagram)

        else:
            print('The datagram received was not properly formatted: ' + datagram)
        
    else: #GET
        logger.info('Asynchronous Request with GET format. No longer supported.')

    return HttpResponse(status=204) #The server successfully processed the request and is not returning any content

@login_required
def ajax_get_data_for_devicetype(request,devicetypePK):
    if request.is_ajax():
        DVT=models.DeviceTypes.objects.get(pk=devicetypePK)
        info={'Connection':DVT.Connection}
        return HttpResponse(json.dumps(info))
    else:
        return HttpResponse(json.dumps([]))

@login_required
def ajax_get_orders_for_device(request,devicePK):
    if request.is_ajax():
        DV=models.Devices.objects.get(pk=devicePK)
        orders=models.DeviceCommands.objects.filter(DVT=DV.DVT)
        info=[]
        if len(orders)>0:
            for order in orders:
                info.append({'Identifier':order.Identifier,'HumanTag':order.Label})
                
        return HttpResponse(json.dumps(info))
    else:
        return HttpResponse(json.dumps([]))
    