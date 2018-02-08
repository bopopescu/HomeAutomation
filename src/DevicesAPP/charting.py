import pandas as pd
import numpy as np
import datetime
from utils.BBDD import getRegistersDBInstance
from .constants import DTYPE_DIGITAL

def generateChart(table,fromDate,toDate,names,types,labels,plottypes,sampletime):
    
    DB=getRegistersDBInstance()
    
    chart={}
    chart['title']=table
    chart['cols']=[]
    i=0
    tempname=[]
    tempnameEmpty=[]
    vars=''
    tempStats={'number':5,'num_rows':[],'mean':[],'max':[],'min':[],'on_time':[],'off_time':[]}
    for name,type,label,plottype in zip(names,types,labels,plottypes):
        if DB.checkIfColumnExist(table=table,column=name):
            vars+='"'+str(name)+'"'+','
            if type!=DTYPE_DIGITAL:
                tempname.append({'name':name,'label':label,'type':type,'plottype':plottype})
            else:
                labels=label.split('$')
                tempname.append({'name':name,'label':labels,'type':type,'plottype':plottype})
            
        else:
            if type!=DTYPE_DIGITAL:
                tempnameEmpty.append({'name':name,'label':label,'type':type,'plottype':plottype})
            else:
                labels=label.split('$')
                tempnameEmpty.append({'name':name,'label':labels,'type':type,'plottype':plottype})

    if vars!='' and vars!='"timestamp",':
        vars=vars[:-1]
        chart['cols'].append(tempname)    
        
        limit=10000
        sql='SELECT '+vars+' FROM "'+ table +'" WHERE timestamp BETWEEN "' + str(fromDate).split('+')[0]+'" AND "'+str(toDate).split('+')[0] + '" ORDER BY timestamp ASC LIMIT ' + str(limit)
        #logger.info('SQL:' + sql)
        
        df=pd.read_sql_query(sql=sql,con=DB.getConn(),index_col='timestamp')
        
        if not df.empty:
            
            # TO FORCE THAT THE INITIAL ROW CONTAINS THE INITIAL DATE
            addedtime=pd.to_datetime(arg=df.index.values[0])-fromDate.replace(tzinfo=None)
            if addedtime>datetime.timedelta(minutes=1):
                ts = pd.to_datetime(fromDate.replace(tzinfo=None))
                new_row = pd.DataFrame([df.iloc[0].values], columns = df.columns, index=[ts])
                df=pd.concat([pd.DataFrame(new_row),df], ignore_index=False)
                
            # TO FORCE THAT THE LAST ROW CONTAINS THE END DATE
            addedtime=toDate.replace(tzinfo=None)-pd.to_datetime(arg=df.index.values[-1])
            if addedtime>datetime.timedelta(minutes=1):
                ts = pd.to_datetime(toDate.replace(tzinfo=None))
                new_row = pd.DataFrame([df.iloc[-1].values], columns = df.columns, index=[ts])
                df=pd.concat([df,pd.DataFrame(new_row)], ignore_index=False)
            
            # RESAMPLING DATA TO 1 MINUTE RESOLUTION AND INTERPOLATING VALUES
            df_res=df.resample('1T').mean()
            df_int=df_res.interpolate(method='zero')
        else:
            sql='SELECT '+vars+' FROM "'+ table +'" ORDER BY timestamp DESC LIMIT 1'
            df=pd.read_sql_query(sql=sql,con=DB.getConn(),index_col='timestamp')
            if not df.empty:
                values=np.concatenate([df.values,df.values])
            else:
                values=[]
                for col in chart['cols'][1:]:
                    values.append([None,None])
            # TO FORCE THAT THE INITIAL ROW CONTAINS THE INITIAL DATE
            ts_ini = pd.to_datetime(fromDate.replace(tzinfo=None))
            ts_end = pd.to_datetime(toDate.replace(tzinfo=None))
            df = pd.DataFrame(data=values,index=[ts_ini,ts_end],columns=df.columns)
            df_int=df
                
        tempStats={'number':5,'num_rows':df.count(numeric_only=True).tolist(),'mean':[],'max':df.max(numeric_only=True).tolist(),'min':df.min(numeric_only=True).tolist(),'on_time':[],'off_time':[]}
        
        for col in chart['cols'][0][1:]:
            if col['type']==DTYPE_DIGITAL:
                from utils.dataMangling import dec2bin
                        
                try:
                    df[col['name']]=df[col['name']].apply(func=dec2bin)
#                     from MainAPP.models import AdditionalCalculations
#                     kk=pd.DataFrame(df[col['name']])
#                     CALC=AdditionalCalculations(df=kk,key=col['name'])
#                     tempStats['on_time'].append(CALC.duty(level=True,absoluteValue=True))
#                     tempStats['off_time'].append(CALC.duty(level=False,absoluteValue=True))
                except KeyError:
                    tempStats['on_time'].append(None)
                    tempStats['off_time'].append(None)
                tempStats['mean'].append(None)
            else:
                try:
                    # AN ERROR CAN OCCUR IF THE VARIABLE HAS NO VALUE ALONG THE TIMESPAN
                    tempStats['mean'].append(df_int[str(col['name'])].mean())
                except KeyError:
                    tempStats['mean'].append(None)
                tempStats['on_time'].append(None)
                tempStats['off_time'].append(None)
        
        tempX2 = [x / 1000000 for x in df.index.values.tolist()]
        # TRANSFORMING THE NANs TO NONEs TO AVOID JSON ENCODING ISSUES
        tempData=df.where(pd.notnull(df), None).values.tolist()
        
        for row,timestamp in zip(tempData,tempX2):
            row.insert(0,timestamp)   
             
        chart['rows']=tempData
        chart['statistics']=tempStats
    else:
        chart['cols'].append(tempnameEmpty)
        chart['rows']=[]
        row=[]
        for timestamp in (fromDate,toDate):
            row.append(timestamp.timestamp()*1000)  # this is to equalize the timestamp output to ms as above by pandas
            for col in chart['cols'][0][1:]:
                if col['type']==DTYPE_DIGITAL:
                    row.append([None,None,None,None,None,None,None,None])
                    tempStats['on_time'].append([None,None,None,None,None,None,None,None])
                    tempStats['off_time'].append([None,None,None,None,None,None,None,None])
                else:
                    row.append(None)
                    tempStats['on_time'].append(None)
                    tempStats['off_time'].append(None)
                tempStats['mean'].append(None)
                tempStats['max'].append(None)
                tempStats['min'].append(None)
                tempStats['num_rows'].append(2)
            chart['rows'].append(row)
            chart['statistics']=tempStats
            row=[]
    return chart