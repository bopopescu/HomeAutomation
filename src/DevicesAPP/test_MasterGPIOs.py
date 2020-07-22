from .test_utils import *

print('############################################')
print('# TESTING OF MainGPIOs MODEL FUNCTIONS #')
print('############################################')

@tag('maingpios')
class MainGPIOsModelTests(TestCase):
    def setUp(self):
        from utils.BBDD import getRegistersDBInstance
        self.DB=getRegistersDBInstance()
        self.DB.dropTable(table='inputs')
        self.DB.dropTable(table='outputs')
        self.signal_was_called = False
        self.signaltimestamp=None
        self.signalTag=None
        self.signalValue=None
        def handler(sender, **kwargs):
            self.signal_was_called = True
            self.signaltimestamp=kwargs['timestamp']
            self.signalTag=kwargs['Tags'][0]
            self.signalValue=kwargs['Values'][0]
        
        self.handler=handler
  
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
         
          
# INDIVIDUAL FUNCTIONS TESTING
    def test_store2DB(self):
        '''
        storeDB: method provided to perform the foloowing steps:
            - Validate the input data for the GPIO
            - Saves the instance into the DB
            - Introduces a first register into the registers DB with the current value reading it for Inputs, and forcing it in Outputs
        '''
        print('## TESTING THE OPERATION OF THE store2DB METHOD ##')
        instance=MainGPIOs(**MainGPIODict)
        now=timezone.now().replace(microsecond=0).replace(tzinfo=None)
        instance.store2DB()
        # checks that store2DB creates the corresponding table in the registers DB and introduces a first record with the current value
        self.assertEqual(instance.Value,GPIO_HIGH)
        self.assertTrue(self.DB.checkIfTableExist(table=instance.getRegistersDBTable()))
        latest=instance.getLatestData(localized=False)
        self.assertAlmostEqual(latest[instance.getRegistersDBTag()]['timestamp'],now,delta=datetime.timedelta(seconds=1))# latest value is dated now
        self.assertEqual(latest[instance.getRegistersDBTag()]['value'],GPIO_HIGH)# latest value is high
        self.DB.dropTable(table=instance.getRegistersDBTable())
          
    def test_updateValue(self):
        '''
        updateValue: method that handles the creation of registers DB rows. It has several alternative operational paths:
            - The standard one is when the pre-initialized parameters are defaulted. In this situation, it checks if newValue is different from the previous one
            and in case so, it introduces a row with the previous value, and a second one with the newValue. Both these rows are separated 1 second in the timestamps
            to provide step-like plots.
            - If a timestamp is provided, only one row is created with the passed timestamp if and only if newValue is different from the previous one.
            - If force=True, it generates the row independently of the newValue.
            Independently of the operational path followed, this method also sets up the value of the GPIO in case it is an output.
        '''
        print('## TESTING THE OPERATION OF THE updateValue METHOD ##')
        instance=MainGPIOs(**MainGPIODict)
        instance.save() # to avoid the creation of the DB tables and insertion of the first row that function store2DB does...
        print('    -> Tested standard path')
        now=timezone.now().replace(microsecond=0).replace(tzinfo=None)
        SignalVariableValueUpdated.connect(self.handler)
        instance.updateValue(newValue=GPIO_LOW,timestamp=None,writeDB=True,force=False)
        SignalVariableValueUpdated.disconnect(self.handler)
        # checks values from the signal
        self.assertAlmostEqual(self.signaltimestamp,timezone.now().replace(microsecond=0),delta=datetime.timedelta(seconds=1))# signal timestamp value is dated now
        self.assertEqual(self.signalValue,instance.Value)
        self.assertEqual(self.signalTag,str(instance.pk))
        
        
        table=instance.getRegistersDBTable()
        vars='"timestamp","'+instance.getRegistersDBTag()+'"'
        sql='SELECT '+vars+' FROM "'+ table +'" ORDER BY timestamp DESC LIMIT 2'
        rows=self.DB.executeTransaction(SQLstatement=sql)
        self.assertEqual(rows[1][1],GPIO_HIGH)# previous to latest value equals the previous Value
        self.assertEqual(rows[0][1],GPIO_LOW) # latest value equals the newValue
        self.assertEqual(rows[0][0]-rows[1][0],datetime.timedelta(seconds=1))# checks that it inserts two rows with 1 second difference
        self.assertAlmostEqual(rows[0][0],now,delta=datetime.timedelta(seconds=1))# checks that the latest value is dated now
          
        print('    -> Tested update with timestamp')
        now=timezone.now().replace(microsecond=0).replace(tzinfo=None)+datetime.timedelta(seconds=10)
        instance.updateValue(newValue=GPIO_HIGH,timestamp=now,writeDB=True,force=False)
        latest=instance.getLatestData(localized=False)
        self.assertEqual(latest[instance.getRegistersDBTag()]['timestamp'],now)# latest value is dated now
        self.assertEqual(latest[instance.getRegistersDBTag()]['value'],GPIO_HIGH)# latest value is dated now
          
        self.DB.dropTable(table=instance.getRegistersDBTable())
     
    def test_setHigh(self):
        '''
        Method that sets the value of an output to high and updates the value in the registers DB.
        '''
        print('## TESTING THE OPERATION OF THE setHigh METHOD ##')
        newDict=editDict(keys=['Value',], newValues=[GPIO_LOW,], Dictionary=MainGPIODict)
        instance=MainGPIOs(**newDict)
        instance.store2DB()
        instance.setHigh()
        self.assertEqual(instance.Value,GPIO_HIGH)# current value equals High
        latest=instance.getLatestData(localized=False)
        self.assertEqual(latest[instance.getRegistersDBTag()]['value'],GPIO_HIGH)# last value on DB equals High
        self.DB.dropTable(table=instance.getRegistersDBTable())
      
    def test_setLow(self):
        '''
        Method that sets the value of an output to low and updates the value in the registers DB.
        '''
        print('## TESTING THE OPERATION OF THE setLow METHOD ##')
        newDict=editDict(keys=['Value',], newValues=[GPIO_HIGH,], Dictionary=MainGPIODict)
        instance=MainGPIOs(**newDict)
        instance.store2DB()
        instance.setLow()
        self.assertEqual(instance.Value,GPIO_LOW)# current value equals Low
        latest=instance.getLatestData(localized=False)
        self.assertEqual(latest[instance.getRegistersDBTag()]['value'],GPIO_LOW)# last value on DB equals Low
        self.DB.dropTable(table=instance.getRegistersDBTable())
         
    def test_IntegrityError(self):
        '''
        This tests checks that in case of two semi-simultaneous GPIO queries to registers DB, no error occurs. In fact, the 
        DB driver handles it by delaying in time the conflicting row up to when there is no more integrity error.
        '''
        import time
        print('## TESTING THE OPERATION OF THE registers DB Integrity Error handler METHOD ##')
        instance=MainGPIOs(**MainGPIODict)
        instance.store2DB()
        newDict=editDict(keys=['Pin','Label'], newValues=[15,'Test Output 2'], Dictionary=MainGPIODict)
        instance2=MainGPIOs(**newDict)
        time.sleep(1)
        instance2.store2DB()
          
        instance.setLow()
        instance2.setLow()
        table=instance.getRegistersDBTable()
        vars='"timestamp","'+instance.getRegistersDBTag()+'"'+ ',"'+instance2.getRegistersDBTag()+'"'
        sql='SELECT '+vars+' FROM "'+ table +'" ORDER BY timestamp ASC'
        rows=self.DB.executeTransaction(SQLstatement=sql)
        # initialization
        self.assertEqual(rows[0][1],GPIO_HIGH) # initial value of instance
        self.assertEqual(rows[0][2],None) # instance2 not yet created
        self.assertEqual(rows[1][2],GPIO_HIGH) # initial value of instance2
        # instance setLow
        self.assertEqual(rows[2][1],GPIO_HIGH) # previous value of instance
        self.assertEqual(rows[3][1],GPIO_LOW) # new value of instance
        self.assertEqual(rows[2][2],GPIO_HIGH) # initial value of instance2
        self.assertEqual(rows[3][2],GPIO_HIGH) # initial value of instance2
        # instance2 setLow
        self.assertEqual(rows[4][1],GPIO_LOW) # value of instance
        self.assertEqual(rows[5][1],GPIO_LOW) # value of instance
        self.assertEqual(rows[4][2],GPIO_HIGH) # previous value of instance2
        self.assertEqual(rows[5][2],GPIO_LOW) # new value of instance2
        # time span
        for i in range(2,4):
            self.assertEqual(rows[i+1][0]-rows[i][0],datetime.timedelta(seconds=1))# checks that it inserts two rows with 1 second difference
 
        self.DB.dropTable(table=instance.getRegistersDBTable())
        self.DB.dropTable(table=instance2.getRegistersDBTable())
          
    def test_str(self):        
        print('## TESTING THE OPERATION OF THE str METHOD ##')
        instance=MainGPIOs(**MainGPIODict)
        instance.store2DB()
        self.assertEqual(str(instance),instance.Label + ' on pin ' + str(instance.Pin) )
        self.DB.dropTable(table=instance.getRegistersDBTable())
      
    def test_initializeIOs(self):
        print('## TESTING THE OPERATION OF THE initializeIOs METHOD ##')
        instance=MainGPIOs(**MainGPIODict)
        instance.store2DB()
        newDict=editDict(keys=['Pin','Label','Direction','Value'], newValues=[15,'Test Input 1',GPIO_INPUT,GPIO_LOW], Dictionary=MainGPIODict)
        instance2=MainGPIOs(**newDict)
        instance2.store2DB()
          
        print('    -> Tested declareInputEvent=True')
        MainGPIOs.initializeIOs(declareInputEvent=True)
        print('    -> Tested declareInputEvent=False')
        MainGPIOs.initializeIOs(declareInputEvent=False)
         
        self.DB.dropTable(table=instance.getRegistersDBTable())
        self.DB.dropTable(table=instance2.getRegistersDBTable())
    
    def test_InputChangeEvent(self):
        print('## TESTING THE OPERATION OF THE InputChangeEvent METHOD ##')
        newDict=editDict(keys=['Pin','Label','Direction','Value'], newValues=[15,'Test Input 1',GPIO_INPUT,GPIO_HIGH], Dictionary=MainGPIODict)
        instance=MainGPIOs(**newDict)
        instance.save()
        
        instance.InputChangeEvent()
        
        table=instance.getRegistersDBTable()
        vars='"timestamp","'+instance.getRegistersDBTag()+'"'
        sql='SELECT '+vars+' FROM "'+ table +'" ORDER BY timestamp ASC'
        rows=self.DB.executeTransaction(SQLstatement=sql)
        # initialization
        self.assertEqual(rows[0][1],GPIO_HIGH) # initial value of instance
        self.assertEqual(rows[1][1],GPIO_LOW) # final value of instance
        
        self.DB.dropTable(table=instance.getRegistersDBTable())
    
    def test_updateLabel(self):
        print('## TESTING THE OPERATION OF THE updateLabel METHOD ##')
        newDict=editDict(keys=['Pin','Label','Direction','Value'], newValues=[15,'Test Input 1',GPIO_INPUT,GPIO_HIGH], Dictionary=MainGPIODict)
        instance=MainGPIOs(**newDict)
        instance.save()
        
        SUBSYSTEMs=MainAPP.models.Subsystems.objects.filter(gpios=instance)
        self.assertQuerysetEqual(SUBSYSTEMs,[]) # no subsystem assigned
        subsystem=MainAPP.models.Subsystems(Name=0,content_object=instance)
        subsystem.save()
        SUBSYSTEMs=MainAPP.models.Subsystems.objects.filter(gpios=instance)
        self.assertEqual(list(SUBSYSTEMs),[subsystem,]) # a subsystem returned
        
        newLabel='New label for you'
        instance.updateLabel(newLabel=newLabel)
        AVAR=MainAPP.models.AutomationVariables.objects.get(Device='MainGPIOs',Tag=instance.getRegistersDBTag())
        self.assertEqual(AVAR.Label,newLabel) # an AVAR is now created
        avar_subsystem=MainAPP.models.Subsystems.objects.filter(automationvariables=AVAR)
        self.assertEqual(avar_subsystem[0].Name,subsystem.Name) # the same subsystem is assigned to corresponding AVAR
        
    def test_getCharts(self):
        '''
        getCharts: method that retrieves the chart structured in a dictionary with the following keys:
            - title : the table name
            - cols : a list with the first element being a list of dictionaries describing data of each of the columns in the graph
                . label : human readable label for the variable (a list of 8 elements in case of digital variables)
                . name : the name of the variable
                . type : the type (digital, analog, datetime) of the variable
                . plottype : the type of plot desired for the variable
            - rows : a list of the row values of the graph. Each row is a list with the first element being a unix timestamp and the following ones are the values of the variables.
            - statistics: a dictionary with teh following keys:
                . number : the number of the statistic indicators
                . num_rows : the number of rows of the graph
                . mean : a list with the mean values of each of the columns. A None value is introduced for digital variables
                . max : a list with the max values of each of the columns.
                . min : a list with the min values of each of the columns.
                . on_time : a list with the amount of seconds being at value==1 of each of the columns (for digital variables only, None else)
                . off_time : a list with the amount of seconds being at value==0 of each of the columns (for digital variables only, None else)
        In case no values are in the DB in the time span required, it returns two rows with date dateIni and dateEnd respectively with the rows
        being:
            - the last values present in the DB if there are any.
            - None in case no register can be found at all.
        '''
         
        print('## TESTING THE OPERATION OF THE getCharts METHOD ##')
        import time
        print('    -> Tested with valid records in the DB')
        local_tz=get_localzone()
          
        dateIni=(timezone.now()-datetime.timedelta(seconds=1)).replace(microsecond=0)
        outDict=editDict(keys=['Value',], newValues=[GPIO_LOW,], Dictionary=MainGPIODict)
        instance=MainGPIOs(**outDict)
        instance.store2DB()
          
        inDict=editDict(keys=['Pin','Label','Direction','Value'], newValues=[15,'Test Input 1',GPIO_INPUT,GPIO_LOW], Dictionary=MainGPIODict)
        instance2=MainGPIOs(**inDict)
        instance2.store2DB()
        instance.updateValue(newValue=GPIO_HIGH,timestamp=None,writeDB=True,force=False)
        instance2.updateValue(newValue=GPIO_HIGH,timestamp=None,writeDB=True,force=False)
        time.sleep(4)
        instance.updateValue(newValue=GPIO_LOW,timestamp=None,writeDB=True,force=False)
        instance2.updateValue(newValue=GPIO_LOW,timestamp=None,writeDB=True,force=False)
          
        dateEnd=timezone.now().replace(microsecond=0)
          
        charts=MainGPIOs.getCharts(fromDate=dateIni,toDate=dateEnd)
        for chart in charts:
            title=chart['title']
            self.assertTrue(title in 'inputs outputs')
            self.assertTrue(chart['cols'][0][0]['label']=='timestamp') # first column is timestamp
            if title=='inputs':
                self.assertTrue(chart['cols'][0][1]['label'][0]==inDict['Label']) # second column is the GPIO
            else:
                self.assertTrue(chart['cols'][0][1]['label'][0]==outDict['Label']) # second column is the GPIO
            self.assertEqual(len(chart['rows']),5) # there are 5 rows with data
            self.assertTrue(chart['rows'][0][1][0]==0)
            self.assertTrue(chart['rows'][1][1][0]==0)
            self.assertTrue(chart['rows'][2][1][0]==1)
            self.assertTrue(chart['rows'][3][1][0]==1)
            self.assertTrue(chart['rows'][4][1][0]==0)
          
        print('    -> Tested with no records in the solicited timespan but yes in the DB')
        ''' creates two registers dated in dateIni and dateEnd with the last value from the registers DB
        '''
        dateIni=(timezone.now()+datetime.timedelta(seconds=1)).replace(microsecond=0)
        dateEnd=(dateIni+datetime.timedelta(seconds=10)).replace(microsecond=0)
        charts=MainGPIOs.getCharts(fromDate=dateIni,toDate=dateEnd)
        for chart in charts:
            title=chart['title']
            self.assertTrue(len(chart['rows'])==2) # there are 2 rows with data dated at dateIni and dateEnd resp.
            self.assertEqual(chart['rows'][0][1][0], chart['rows'][1][1][0]) # checks both rows have the same value
            self.assertAlmostEqual(datetime.datetime.fromtimestamp(chart['rows'][0][0]/1000,tz=local_tz),dateIni,delta=datetime.timedelta(seconds=1))# checks that the first row is dated as dateIni
            self.assertAlmostEqual(datetime.datetime.fromtimestamp(chart['rows'][1][0]/1000,tz=local_tz),dateEnd,delta=datetime.timedelta(seconds=1))# checks that the second row is dated as dateEnd
              
        self.DB.dropTable(table=instance.getRegistersDBTable())
        self.DB.dropTable(table=instance2.getRegistersDBTable())
        print('    -> Tested with no table in the DB')
        instance.delete()
        instance2.delete()
        instance=MainGPIOs(**outDict)
        instance.save()
        instance2=MainGPIOs(**inDict)
        instance2.save()
        charts=MainGPIOs.getCharts(fromDate=dateIni,toDate=dateEnd)
        for chart in charts:
            title=chart['title']
            self.assertAlmostEqual(datetime.datetime.fromtimestamp(chart['rows'][0][0]/1000,tz=local_tz),dateIni,delta=datetime.timedelta(seconds=1))# checks that the first row is dated as dateIni
            self.assertAlmostEqual(datetime.datetime.fromtimestamp(chart['rows'][1][0]/1000,tz=local_tz),dateEnd,delta=datetime.timedelta(seconds=1))# checks that the second row is dated as dateEnd
            for i,col in enumerate(chart['cols'][0]):
                if col['type']==DTYPE_DIGITAL:
                    self.assertEqual(chart['rows'][0][i],[None,None,None,None,None,None,None,None]) # all None values
                elif col['type']!='datetime':
                    self.assertEqual(chart['rows'][0][i],None) # all None values
                     
        print('    -> Tested with empty table in the DB')
        instance.checkRegistersDB(Database=self.DB)
        instance2.checkRegistersDB(Database=self.DB)
        self.assertTrue(self.DB.checkIfTableExist(instance.getRegistersDBTable()))
        self.assertTrue(self.DB.checkIfTableExist(instance2.getRegistersDBTable()))
        charts=MainGPIOs.getCharts(fromDate=dateIni,toDate=dateEnd)
        for chart in charts:
            title=chart['title']
            self.assertTrue(len(chart['rows'])==2) # there are 2 rows with data dated at dateIni and dateEnd resp.
            self.assertAlmostEqual(datetime.datetime.fromtimestamp(chart['rows'][0][0]/1000,tz=local_tz),dateIni,delta=datetime.timedelta(seconds=1))# checks that the first row is dated as dateIni
            self.assertAlmostEqual(datetime.datetime.fromtimestamp(chart['rows'][1][0]/1000,tz=local_tz),dateEnd,delta=datetime.timedelta(seconds=1))# checks that the second row is dated as dateEnd
            for i,col in enumerate(chart['cols'][0]):
                if col['type']==DTYPE_DIGITAL:
                    self.assertEqual(chart['rows'][0][i],[None,None,None,None,None,None,None,None]) # all None values
                elif col['type']!='datetime':
                    self.assertEqual(chart['rows'][0][i],None) # all None values
              
        self.DB.dropTable(table=instance.getRegistersDBTable())
        self.DB.dropTable(table=instance2.getRegistersDBTable())
         
print('###########################################')
print('# TESTING OF MainGPIOsForm FUNCTIONS #')
print('###########################################')

@tag('maingpios')
class MainGPIOsForm(TestCase):
    remoteDVT=None
    localDVT=None
    memoryDVT=None
          
    def setUp(self):
        pass
                  
    def test_valid_data(self):
        '''
        Checks that the form is valid with good data and when saved, creates the instance and its associated automationvar
        '''
        print('## TESTING THE CREATION OF INSTANCE THROUGH FORM ##')
        
#         outDict=editDict(keys=['Value','Label'], newValues=[GPIO_LOW,'test'], Dictionary=MainGPIODict)
#         form = MainGPIOsForm(outDict)
#         self.assertTrue(form.is_valid())
#         instance = form.save()
#         AVARs=MainAPP.models.AutomationVariables.objects.filter(Device='MainGPIOs').filter(Tag=instance.getRegistersDBTag())
#         self.assertEqual(1,AVARs.count()) # one automationvar is returned