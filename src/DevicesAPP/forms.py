# coding: utf-8
import datetime

from bootstrap3_datetime.widgets import DateTimePicker
from django import forms
from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.views import generic
from django.forms import ModelForm
from django.urls import reverse
from django.forms import inlineformset_factory

import json
import utils.BBDD
import MainAPP.models
from .constants import APP_TEMPLATE_NAMESPACE,DTYPE_DIGITAL,LOCAL_CONNECTION,REMOTE_TCP_CONNECTION,MEMORY_CONNECTION,REMOTE_RS485_CONNECTION
from . import  models
from .apps import DevicesAppException

from crispy_forms.helper import FormHelper
from crispy_forms.bootstrap import FormActions,AppendedText
from crispy_forms.layout import Layout, Div, Submit, HTML, Button, Row, Field,Fieldset

import logging
logger = logging.getLogger("project")
FORMS_LABEL_CLASS='col-lg-5 col-md-5 col-sm-12 col-xs-12'
FORMS_FIELD_CLASS='col-lg-5 col-md-5 col-sm-12 col-xs-12'

class MainDeviceVarsForm(ModelForm):
    def __init__(self, *args, **kwargs):
        instance=kwargs.get('instance',None)
        try:
            action=kwargs.pop('action')
        except:
            action='add'
            
        super().__init__(*args, **kwargs)
        # If you pass FormHelper constructor a form instance
        # It builds a default layout with all its fields
        self.helper = FormHelper(self)
        self.helper.labels_uppercase = True
        self.helper.label_class = FORMS_LABEL_CLASS
        self.helper.field_class = FORMS_FIELD_CLASS
#         self.helper.form_id = 'id-DeviceForm'
        self.helper.form_class = 'form-horizontal'
        self.helper.form_method = 'post'
        
        if action=='add':
            self.helper.form_action = reverse(APP_TEMPLATE_NAMESPACE+':add',args=['maindevicevars'])
            buttons=FormActions(
                    Submit('save', _('Save')),
                    HTML('<a href="{% url "'+APP_TEMPLATE_NAMESPACE+':home" %}" class="btn btn-secondary">'+str(_('Cancel'))+'</a>')
                )
        elif action=='edit':
            self.helper.form_action = reverse(APP_TEMPLATE_NAMESPACE+':edit',args=['maindevicevars',instance.pk])
            buttons=FormActions(
                    Submit('edit', _('Save changes')),
                    HTML('<a href="{% url "'+APP_TEMPLATE_NAMESPACE+':home" %}" class="btn btn-secondary">'+str(_('Cancel'))+'</a>')
                )
        else:
            raise DevicesAppException(_('The action parameter passed to the form MainDeviceVarsForm is not accepted. Action= ') + str(action))
        
        self.fields['Label'].label = _("Enter the label for the variable")
        self.fields['DataType'].label = _("Set the datatype of the variable")
        self.fields['Value'].label = _("Enter the value for the variable")
        self.fields['Units'].label = _("Set the units of the variable")
        self.fields['PlotType'].label = _("Set the type of plot for the variable")
        self.fields['UserEditable'].label = _("The user can alter the value of the variable")
        
        for field in self.fields:
            help_text = self.fields[field].help_text
            self.fields[field].help_text = None
            if help_text != '':
                self.fields[field].widget.attrs.update({'class':'input-sm has-popover', 'data-content':help_text, 'data-placement':'right', 'data-container':'body'})
            else:
                self.fields[field].widget.attrs.update({'class':'input-sm '})
                
        self.helper.layout = Layout(
            Field('Label'),
            Field('DataType'),
            Field('Value'),
            Field('Units'),
            Field('PlotType'),
            Field('UserEditable'),
            buttons
            )
    
    def save(self, *args, **kwargs):
        instance=super().save(commit=False)
        instance.store2DB()
        return instance
        
    class Meta:
        model = models.MainDeviceVars
        fields=['Label','DataType','Value','Units','PlotType','UserEditable']

                                            

        
class MainGPIOsForm(ModelForm):
    def __init__(self, *args, **kwargs):
        instance=kwargs.get('instance',None)
        try:
            action=kwargs.pop('action')
        except:
            action='add'

        super().__init__(*args, **kwargs)
        # If you pass FormHelper constructor a form instance
        # It builds a default layout with all its fields
        self.helper = FormHelper(self)
        self.helper.labels_uppercase = True
        self.helper.label_class = FORMS_LABEL_CLASS
        self.helper.field_class = FORMS_FIELD_CLASS
#         self.helper.form_id = 'id-DeviceForm'
        self.helper.form_class = 'form-horizontal'
        self.helper.form_method = 'post'
        
        if action=='add':
            self.helper.form_action = reverse(APP_TEMPLATE_NAMESPACE+':add',args=['maingpios'])
            buttons=FormActions(
                    Submit('save', _('Save')),
                    #HTML('<a href="{% url "'+APP_TEMPLATE_NAMESPACE+':home" %}" class="btn btn-secondary">'+str(_('Cancel'))+'</a>')
                )
        elif action=='edit':
            self.helper.form_action = reverse(APP_TEMPLATE_NAMESPACE+':edit',args=['maingpios',instance.pk])
            buttons=FormActions(
                    Submit('edit', _('Save changes')),
                    #HTML('<a href="{% url "'+APP_TEMPLATE_NAMESPACE+':home" %}" class="btn btn-secondary">'+str(_('Cancel'))+'</a>')
                )
        else:
            raise DevicesAppException(_('The action parameter passed to the form MainGPIOsForm is not accepted. Action= ') + str(action))
        
        self.fields['Pin'].label = _("Enter the pin number")
        self.fields['Label'].label = _("Enter a label for the IO")
        self.fields['Direction'].label = _("Set the direction of the IO")
        self.fields['Value'].label = _("Set the current value for the IO")
        self.fields['NotificationTrue'].label = _("Send a notification when value changes to True")
        self.fields['LabelTrue'].label = _("Text for the notification when changes to True")
        self.fields['NotificationFalse'].label = _("Send a notification when value changes to False")
        self.fields['LabelFalse'].label = _("Text for the notification when changes to False")
        
        for field in self.fields:
            help_text = self.fields[field].help_text
            self.fields[field].help_text = None
            if help_text != '':
                self.fields[field].widget.attrs.update({'class':'input-sm has-popover', 'data-content':help_text, 'data-placement':'right', 'data-container':'body'})
            else:
                self.fields[field].widget.attrs.update({'class':'input-sm '})
                
        self.helper.layout = Layout(
            Field('Pin',id='id_pin'),
            Field('Label',id='id_label'),
            Field('Direction'),
            Field('Value'),
            Field('NotificationTrue',id='id_NotificationTrue'),
            Field('LabelTrue'),
            Field('NotificationFalse',id='id_NotificationFalse'),
            Field('LabelFalse'),
            buttons
            )
    
    def save(self, *args, **kwargs):
        instance=super().save(commit=False)
        instance.store2DB()
        return instance
    
    class Meta:
        model = models.MainGPIOs
        fields=['Pin','Label','Direction','Value','NotificationTrue','LabelTrue','NotificationFalse','LabelFalse']
    
    class Media:
        js = ('MainGPIOsFormAnimations.js',)
                                       
class DeviceTypesForm(ModelForm):
    def __init__(self, *args, **kwargs):
        instance=kwargs.get('instance',None)
        try:
            action=kwargs.pop('action')
        except:
            action='add'
        super(DeviceTypesForm, self).__init__(*args, **kwargs)
        # If you pass FormHelper constructor a form instance
        # It builds a default layout with all its fields
        self.helper = FormHelper(self)
        self.helper.labels_uppercase = True
        self.helper.label_class = FORMS_LABEL_CLASS
        self.helper.field_class = FORMS_FIELD_CLASS
#         self.helper.form_id = 'id-DeviceForm'
        self.helper.form_class = 'form-horizontal'
        self.helper.form_method = 'post'
        
        if action=='add':
            self.helper.form_action = reverse(APP_TEMPLATE_NAMESPACE+':add',args=['devicetypes'])
            buttons=FormActions(
                    Submit('save', _('Save')),
                    #HTML('<a href="{% url "'+APP_TEMPLATE_NAMESPACE+':home" %}" class="btn btn-secondary">'+str(_('Cancel'))+'</a>')
                )
        elif action=='edit':
            self.helper.form_action = reverse(APP_TEMPLATE_NAMESPACE+':edit',args=['devicetypes',instance.pk])
            buttons=FormActions(
                    Submit('edit', _('Save changes')),
                    #HTML('<a href="{% url "'+APP_TEMPLATE_NAMESPACE+':home" %}" class="btn btn-secondary">'+str(_('Cancel'))+'</a>')
                )
        else:
            raise DevicesAppException(_('The action parameter passed to the form DevicetypesForm is not accepted. Action= ') + str(action))
        
        self.fields['Connection'].label = _("Set the connection of the device")
        self.fields['Code'].label = _("Enter the type-descriptor of the device")
        self.fields['Description'].label = _("Enter the description of the device")
        self.fields['Description'].widget = forms.Textarea()
        self.fields['MinSampletime'].label = _("Select the minimum sample time for the device")
        self.fields['Picture'].label = _("Upload an image for the DeviceType")
        
        for field in self.fields:
            help_text = self.fields[field].help_text
            self.fields[field].help_text = None
            if help_text != '':
                self.fields[field].widget.attrs.update({'class':'input-sm has-popover', 'data-content':help_text, 'data-placement':'right', 'data-container':'body'})
            else:
                self.fields[field].widget.attrs.update({'class':'input-sm '})
                
        self.helper.layout = Layout(
            Field('Connection'),
            Field('Code'),
            Field('Description'),
            AppendedText('MinSampletime', 's'),
            Field('Picture'),
            buttons
            )
        
    class Meta:
        model = models.DeviceTypes
        fields=['Connection','Code','Description','MinSampletime','Picture']

class DevicesForm(ModelForm):
    def __init__(self, *args, **kwargs):
        initial_arguments = kwargs.get('initial', None)
        updated_initial = {}
        instance=kwargs.get('instance',None)
        try:
            action=kwargs.pop('action')
        except:
            action='add'
        super(DevicesForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.labels_uppercase = True
        self.helper.label_class = FORMS_LABEL_CLASS
        self.helper.field_class = FORMS_FIELD_CLASS
        self.helper.form_class = 'form-horizontal'
        self.helper.form_method = 'post'
        fieldtype=''
        if action=='add+scan':
            self.helper.form_action = reverse(APP_TEMPLATE_NAMESPACE+':add',args=['devices'])
            buttons=FormActions(
                    Submit('save', _('Save')),
                    HTML('<a href="{% url "'+APP_TEMPLATE_NAMESPACE+':scan" "devices" %}" class="btn btn-warning">'+str(_('Scan'))+'</a>'),
                    #HTML('<a href="{% url "'+APP_TEMPLATE_NAMESPACE+':home" %}" class="btn btn-danger">'+str(_('Cancel'))+'</a>')
                )
        elif action=='add':
            self.helper.form_action = reverse(APP_TEMPLATE_NAMESPACE+':add',args=['devices'])
            buttons=FormActions(
                    Submit('save', _('Save')),
                    #HTML('<a href="{% url "'+APP_TEMPLATE_NAMESPACE+':home" %}" class="btn btn-danger">'+str(_('Cancel'))+'</a>')
                )
        elif action=='edit':
            self.helper.form_action = reverse(APP_TEMPLATE_NAMESPACE+':edit',args=['devices',instance.pk])
            buttons=FormActions(
                    Submit('edit', _('Save changes')),
                    #HTML('<a href="{% url "'+APP_TEMPLATE_NAMESPACE+':home" %}" class="btn btn-danger">'+str(_('Cancel'))+'</a>')
                )
        elif action=='scan':
            self.helper.form_action = reverse(APP_TEMPLATE_NAMESPACE+':scan',args=['devices'])
            fieldtype='hidden'
            buttons=FormActions(
                    Submit('scan', _('Scan'),formnovalidate='formnovalidate'),
                    #HTML('<a href="{% url "'+APP_TEMPLATE_NAMESPACE+':home" %}" class="btn btn-danger">'+str(_('Cancel'))+'</a>')
                )
        elif action=='getLabels':
            self.helper.form_method = 'get'
            for field in self.fields:
                self.fields[field].widget.attrs['readonly'] = True
            self.helper.form_action = reverse(APP_TEMPLATE_NAMESPACE+':setCustomLabels',args=[instance.pk])
            buttons=FormActions(
                    Submit('labels', _('Set labels for the data')),
                    #HTML('<a href="{% url "'+APP_TEMPLATE_NAMESPACE+':home" %}" class="btn btn-danger">'+str(_('Cancel'))+'</a>')
                )
        else:
            raise DevicesAppException(_('The action parameter passed to the form DevicesForm is not accepted. Action= ') + str(action))
            
        self.fields['Name'].label = _("Enter the name for the device")
        self.fields['DVT'].label = _("Device type")
        self.fields['DVT'].widget.attrs['readonly'] = True
        #self.fields['Type'].widget.attrs['disabled'] = True
        self.fields['IO'].label = _("Enter the GPIO for the device")
        self.fields['Code'].label = _("Code for the device")
        #self.fields['Code'].widget.attrs['disabled'] = True
        #self.fields['Code'].widget.attrs['readonly'] = True
        self.fields['IP'].label = _("IP address for the device")
        #self.fields['IP'].widget.attrs['readonly'] = True
        #self.fields['IP'].widget.attrs['disabled'] = True
        self.fields['Sampletime'].label = _("Enter the sample time for the device")
        self.fields['RTsampletime'].label = _("Enter the real-time sample time for the device")
        self.fields['State'].label = _("Select the state of the device")
        
        for field in self.fields:
            help_text = self.fields[field].help_text
            self.fields[field].help_text = None
            if help_text != '':
                self.fields[field].widget.attrs.update({'class':'input-sm has-popover', 'data-content':help_text, 'data-placement':'right', 'data-container':'body'})
            else:
                self.fields[field].widget.attrs.update({'class':'input-sm '})
            if initial_arguments!=None:
                try:
                    self.fields[field].initial=initial_arguments[field]
                except:
                    self.fields[field].initial=None
                
        self.helper.layout = Layout(
            Field('Name',type=fieldtype),
            Field('DVT',type=fieldtype),
            Field('IO',type=fieldtype),
            Field('Code',type=fieldtype),
            Field('IP',type=fieldtype),
            AppendedText('Sampletime', 's',type=fieldtype),
            AppendedText('RTsampletime', 's',type=fieldtype),
            Field('State',type=fieldtype),
            Field('Port',type=fieldtype),
            Field('Baudrate',type=fieldtype),
            Field('Parity',type=fieldtype),
            Field('Stopbits',type=fieldtype),
            buttons
            
            )
    
    def clean(self):
        cleaned_data = super(DevicesForm, self).clean()
        DVT = cleaned_data.get('DVT')
        IP = cleaned_data.get('IP')
        Port = cleaned_data.get('Port')
        Baudrate= cleaned_data.get('Baudrate')
        Parity= cleaned_data.get('Parity')
        Stopbits= cleaned_data.get('Stopbits')
        if DVT.Connection==REMOTE_TCP_CONNECTION:
            Code=IP.split('.')[3]
            cleaned_data.update(Code=Code)
        if DVT.Connection !=REMOTE_RS485_CONNECTION:
            cleaned_data.update(Port=None,Baudrate=None,Parity=None,Stopbits=None)
        if DVT.Connection==LOCAL_CONNECTION or DVT.Connection==MEMORY_CONNECTION:
            cleaned_data.update(Code=None)
        return cleaned_data
     
     
    def save(self, *args, **kwargs):
        instance=super().save(commit=False)
        #instance.store2DB()
        return instance
    
    class Meta:
        model = models.Devices
        fields=['Name','DVT','IO','Code','IP','Sampletime','RTsampletime','State','Port','Baudrate','Parity','Stopbits']
        
    class Media:
        js = ('DeviceFormAnimations.js',)

class CronExpressionsForm(ModelForm):
    def __init__(self, *args, **kwargs):
        instance=kwargs.get('instance',None)
        super(CronExpressionsForm, self).__init__(*args, **kwargs)
        # If you pass FormHelper constructor a form instance
        # It builds a default layout with all its fields
        self.helper = FormHelper(self)
        self.helper.labels_uppercase = True
        self.helper.label_class = FORMS_LABEL_CLASS
        self.helper.field_class = FORMS_FIELD_CLASS
#         self.helper.form_id = 'id-DeviceForm'
        self.helper.form_class = 'form-horizontal'
        self.helper.form_method = 'post'
        
        self.fields['Identifier'].label = _("Description")
        self.fields['DayOfWeek'].label = _("Set the days of the week [1=MON, 7=SUN, ?=Ignore]")
        self.fields['Month'].label = _("Set the months [1=JAN, 12=DEC, *=ALL]")
        self.fields['DayOfMonth'].label = _("Set the days of the month [1-31, *=ALL]")
        self.fields['Hours'].label = _("Set the hours of the day [0-23, *=ALL]")
        self.fields['Minutes'].label = _("Set the minutes of the hour [0-59, *=ALL]")
        self.fields['Seconds'].label = _("Set the seconds of the minute [0-59, *=ALL]")
        
        for field in self.fields:
            help_text = self.fields[field].help_text
            self.fields[field].help_text = None
            if help_text != '':
                self.fields[field].widget.attrs.update({'class':'input-sm has-popover', 'data-content':help_text, 'data-placement':'right', 'data-container':'body'})
            else:
                self.fields[field].widget.attrs.update({'class':'input-sm '})
                
        self.helper.layout = Layout(
            Field('Identifier'),
            Field('DayOfWeek'),
            Field('Month'),
            Field('DayOfMonth'),
            Field('Hours'),
            Field('Minutes'),
            Field('Seconds'),
            Submit('submit', _('Submit'),css_class='btn-primary center-block'),
            )
        
    class Meta:
        model = models.CronExpressions
        fields=['Identifier','DayOfWeek','Month','DayOfMonth','Hours','Minutes','Seconds']

class DatagramsForm(ModelForm):
    
    def save(self, commit=True):
        instance = super(DatagramsForm, self).save(commit=False)
        if not instance.pk:
            created=True
        else:
            created=False
        instance.store2DB(update_fields=self.changed_data)
        
        if 'Enable' in self.changed_data or created:
            DVs=models.Devices.objects.filter(DVT=instance.DVT)
            for DV in DVs:
                DV.updateRequests()
        return instance

            
    class Meta:
        model = models.Datagrams
        exclude=[]
        
    class Media:
        js = ('DatagramsFormAnimations.js',)
        
class DatagramCustomLabelsForm(forms.Form):
    def __init__(self, *args, **kwargs):
        DV = kwargs.pop('DV')
        DGs = kwargs.pop('DGs')        
        datagram_info=[]
        self.units=[]
         
        initial_values=self._getInitialValues(DV=DV,DGs=DGs)
        kwargs.update(initial=initial_values)
        
        super(DatagramCustomLabelsForm, self).__init__(*args, **kwargs)

        # If you pass FormHelper constructor a form instance
        # It builds a default layout with all its fields
        self.helper = FormHelper(self)
        self.helper.labels_uppercase = True
        self.helper.label_class = FORMS_LABEL_CLASS
        self.helper.field_class = FORMS_FIELD_CLASS
        self.helper.form_id = 'DatagramCustomLabelsForm'
        self.helper.form_class = 'form-horizontal'
        self.helper.form_method = 'post'
        self.helper.layout = Layout()
        self.helper.form_action = reverse(APP_TEMPLATE_NAMESPACE+':setCustomLabels',args=[DV.pk])
        
        self._setFields(DV=DV,DGs=DGs,initial=initial_values)
        
        self.helper.layout.append(HTML("<h2></h2>"))
        self.helper.layout.append(Submit('submit', _('Save'),css_class='btn-primary'))
         
         
    def _getInitialValues(self,DV,DGs):
        initial_values={}
        if DV.CustomLabels!='':
            CustomLabels=json.loads(DV.CustomLabels)
        else:
            CustomLabels={}
        for DG in DGs:
            HumanNames={}
            try:
                kk=CustomLabels[str(DG.pk)]
            except:
                CustomLabels[str(DG.pk)]=''
                
            if CustomLabels[str(DG.pk)]=='':
                datagram=DG.getStructure()
                for i,name in enumerate(datagram['names']):
                    IT=models.DatagramItems.objects.get(pk=DG.getInfoFromItemName(name=name)['itempk'])
                    if datagram['types'][i]!= DTYPE_DIGITAL:
                        fieldName='analog_variable'+'_'+name
                        initial_values[fieldName]=IT.getHumanName()
                    else:
                        fieldName='digital_variable'+'_'+name
                        for k in range(0,8):
                            initial_values[fieldName+'_bit%s' % k]=IT.getHumanName4Digital(bit=k)
            else:
                HumanNames=CustomLabels[str(DG.pk)]
                for name in HumanNames:
                    type=DG.getInfoFromItemName(name=name)['type']
                    if type != DTYPE_DIGITAL:
                        fieldName='analog_variable'+'_'+name
                        initial_values[fieldName]=HumanNames[name].split('_')[0]
                    else:
                        fieldName='digital_variable'+'_'+name
                        values=HumanNames[name].split('$')
                        if len(values)==8:
                            for k in range(0,8):
                                initial_values[fieldName+'_bit%s' % k]=values[k]
                        else:
                            raise DevicesAppException(str(_('The value in CustomLabels ')) + str(name) + str(_(' is digital but does not have 8 bits separated by "$"')))
        return initial_values
     
    def _setFields(self,DV,DGs,initial):
        self.FieldMapping={}
        for DG in DGs:
            self.FieldMapping[str(DG.pk)]={}
            data=DG.getStructure()
            self.helper.layout.append(HTML("<h3><b>Datagram: "+DG.Identifier+"</b></h3>"))
            for i, field in enumerate(data['names']):
                IT=models.DatagramItems.objects.get(pk=DG.getInfoFromItemName(name=field)['itempk'])
                if data['types'][i]!= DTYPE_DIGITAL:
                    self.units.append(data['units'][i])
                    fieldName='analog_variable'+'_'+field
                    self.FieldMapping[str(DG.pk)][fieldName]=field
                    if fieldName in initial:
                        self.fields[fieldName] = forms.CharField(label=IT.Tag,required=True,initial = initial[fieldName])
                    else:
                        self.fields[fieldName] = forms.CharField(label=IT.Tag,required=True,initial = str(IT))
                    self.helper.layout.append(
                                    AppendedText(fieldName, data['units'][i]))
                else:
                    self.units.append('bits')
                    fieldName='digital_variable'+'_'+field
                    self.helper.layout.append(HTML("<hr>"))                        
                    for k in range(0,8):
                        self.fields[fieldName+'_bit%s' % k] = forms.CharField(label=IT.Tag+ ' bit%s' % k,required=True)
                        self.FieldMapping[str(DG.pk)][fieldName+'_bit%s' % k]=field
                        if (fieldName+'_bit%s' % k) in initial:
                            self.fields[fieldName+'_bit%s' % k].initial = initial[fieldName+'_bit%s' % k]
                        else:
                            self.fields[fieldName+'_bit%s' % k].initial = str(IT)+'_bit%s' % k
                        self.helper.layout.append(fieldName+'_bit%s' % k)
                    self.helper.layout.append(HTML("<hr>"))
            
    def _getItemFromField(self,field):
        # field = digital_variable_7_1_1_bit0
        return field.replace('digital_variable_','').replace('analog_variable_','').split('_bit')[0]
    
    def get_variablesLabels(self):
        CustomLabels={}
        count=0
        field_number=0
        for field in self.fields:
            if field.find('variable')>=0:
                field_value=self.cleaned_data[field]
                Item=self._getItemFromField(field=field)
                info=models.Datagrams.getInfoFromItemName(name=Item)
                identifier=info['datagrampk']  # datagram identifier setup in the field name in HTML
                if not identifier in CustomLabels:
                    CustomLabels[identifier]={}
                if field.find('analog')>=0:
                    CustomLabels[identifier][self.FieldMapping[str(identifier)][field]]=field_value
                    count=0
                    field_number+=1
                else:
                    if count==0:
                        CustomLabels[str(identifier)][self.FieldMapping[str(identifier)][field]]=field_value
                        count=count+1
                    else:
                        CustomLabels[str(identifier)][self.FieldMapping[str(identifier)][field]]+='$'+field_value
                        count=count+1
                
                if count>=8:
                    count=0
                    field_number+=1
        return CustomLabels
                 
class ItemOrderingForm(ModelForm):  
    
    def clean(self):
        cleaned_data=super().clean() # to use the validation of the fields from the model
        Item = cleaned_data['ITM']
        return cleaned_data
    
    class Meta:
        model = models.ItemOrdering
        fields=['Order','ITM']
        
class DeviceGraphs(forms.Form):
    DeviceName = forms.ChoiceField(label=_('Select the device'))
    fromDate=forms.DateTimeField(label=_('From'),widget=forms.widgets.DateTimeInput(attrs={'id': 'datetimepicker11'}))
    toDate=forms.DateTimeField(label=_('To'),widget=forms.widgets.DateTimeInput(attrs={'id': 'datetimepicker12'}))
    
    def __init__(self, *args, **kwargs):
        super(DeviceGraphs, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        #self.helper.form_id = 'id-DeviceGraphs'
        self.helper.form_class = 'form-horizontal'
        self.helper.form_method = 'post'
        self.helper.label_class = FORMS_LABEL_CLASS
        self.helper.field_class = FORMS_FIELD_CLASS
        
        DVs=models.Devices.objects.all()
        device_list=[(1,_('Main Unit'))]
        i=2
        try:
            for DV in DVs:
                device_list.append((i,DV.Name))
                i+=1
        except: 
            pass   
            
        self.fields['DeviceName'].choices=device_list
        now = datetime.datetime.now()
        initfrom=datetime.datetime(now.year,now.month,now.day,0,0,1)
        self.fields['fromDate'].initial=initfrom
        self.fields['toDate'].initial=now
        
        self.helper.layout = Layout(
            Field('DeviceName', autofocus="",css_class='input-sm'),
            Field('fromDate', css_class='input-sm'),
            Field('toDate', css_class='input-sm'),
            Submit('submit', _('Submit'),css_class='btn-primary center-block'),
            )

    def clean_DeviceName(self):# returns the label of the choicefield
        name=self.cleaned_data['DeviceName']
        name = dict(self.fields['DeviceName'].choices)[int(name)]        
        return name
    
    def clean_fromDate(self):
        data = self.cleaned_data['fromDate']
#         now = timezone.localtime(timezone.now())
#         if (now<data):
#             data=now-datetime.timedelta(days=1)
        return data
        
    def clean_toDate(self):
        data = self.cleaned_data['toDate']
#         now = timezone.localtime(timezone.now())
#         if (now<data):
#             data=now
        return data   

class BeaconsForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If you pass FormHelper constructor a form instance
        # It builds a default layout with all its fields
        self.helper = FormHelper()
        self.helper.labels_uppercase = True
        self.helper.label_class = FORMS_LABEL_CLASS
        self.helper.field_class = FORMS_FIELD_CLASS
#         self.helper.form_id = 'id-DeviceForm'
        self.helper.form_class = 'form-horizontal'
        self.helper.form_method = 'post'
         
        self.fields['Identifier'].label = _("Set the unique name for the beacon")
        self.fields['WeatherObserver'].label = _("Select the weather source for the beacon")
        self.fields['Latitude'].label = _("Enter the latitude of the beacon")
        self.fields['Longitude'].label = _("Enter the longitude of the beacon")

        self.helper.layout = Layout(
                Field('Identifier', css_class='input-sm'),
                Field('WeatherObserver', css_class='input-sm'),
                Field('Latitude', css_class='input-sm'),
                Field('Longitude', css_class='input-sm'),
                )
        
    class Meta:
        model = models.Beacons
        fields=['Identifier','WeatherObserver','Latitude','Longitude']
        
    class Media:
        js = ('GoogleMapsLatLong.js',)

class FileUpload(forms.Form):
    file = forms.FileField(label=_('Select the firmware file'))
    
    def __init__(self, *args, **kwargs):
        DV = kwargs.pop('DV')
        super(FileUpload, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_class = 'form-horizontal'
        self.helper.form_method = 'post'
        self.helper.label_class = FORMS_LABEL_CLASS
        self.helper.field_class = FORMS_FIELD_CLASS
        self.helper.form_action = reverse(APP_TEMPLATE_NAMESPACE+':firmwareUpdate',args=[DV.pk,])
        
        self.helper.layout = Layout(
            Field('file', autofocus="",css_class='input-sm',id='firmwareFile'),
            Submit('submit', _('Submit'),css_class='btn-primary center-block'),
            )
    