# coding: utf-8
from itertools import chain
import datetime
from django.utils.translation import ugettext_lazy as _

from django.utils import timezone
import os
import sys
import json

import time
import datetime
import sqlite3

import redis
import redis_lock

import multiprocessing
from multiprocessing import Process, Queue, JoinableQueue, cpu_count

from MainAPP.constants import REGISTERS_DB_PATH

import logging
logger = logging.getLogger("project")

# DEBUG
DEBUGGING=False
# END
# MODULE CONSTANTS
TYPE_TEXT='TEXT'
TYPE_FLOAT='FLOAT'
TYPE_INTEGER='INTEGER'
TYPE_TIMESTAMP='TIMESTAMP'
INTEGRITY_ERROR=-10
COMMITED_OK=0
#END

#from django.conf.settings import REDIS_PORT,REDIS_HOST
REDIS_HOST='localhost'
REDIS_PORT=6379
lock_table = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT)

class RegistersDBException(Exception):
    def __name__(self):
        return 'RegistersDBException'
    pass
        
class Database(object):
    
    def __init__(self,location='',DB_id="commitRegisterDB"):  
        if location != '':
            self.conn = sqlite3.connect(location,detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
            self.DB_id=DB_id
        else:
            self.conn= None
            print ("Incorrect argument, missing location: ", sys.exc_info()[1])            
    
    def getConn(self):
        return self.conn
    
    def _execute(self,SQLstatement,arg,many=False):
        ''' THIS FUNCTION IS REQUIERED TO AVOID INTEGRITY ERROR WHEN TWO GPIOs ARE CHANGED AT THE SAME TIME
        '''
        try:
            cur=self.conn.cursor()
            if not many:
                cur.execute(SQLstatement,arg)
            else:
                cur.executemany(SQLstatement,arg)
                
            self.conn.commit()
            cur.close()
            if DEBUGGING and many: logger.info('The instruction '+ SQLstatement+' executed OK')
            return COMMITED_OK
        except Exception as exc:
            cur.close()
            if type(exc) is sqlite3.IntegrityError:
                return INTEGRITY_ERROR
            else:
                logger.info('Exception executing: ' + SQLstatement + '. Exc: ' + str(exc))
                return INTEGRITY_ERROR
                
    def executeTransactionWithCommit(self,SQLstatement,arg=[],many=False):
        with redis_lock.Lock(lock_table, self.DB_id,expire=10, auto_renewal=True):            
            name = multiprocessing.current_process().name
            if DEBUGGING: logger.info('The process ' + name + ' has the lock.')
            result=self._execute(SQLstatement=SQLstatement,arg=arg,many=many)
            if DEBUGGING:logger.info('The process ' + name + ' executed: ' + SQLstatement + ' with result ' + str(result))
            if DEBUGGING:logger.info('The process ' + name + ' releases the lock.')
            return result
        return -1
        
    
    def executeTransaction(self,SQLstatement,arg=[]):
        cur=self.conn.cursor()
        try:
            cur.execute(SQLstatement,arg)
            rows = cur.fetchall()
        except:
            rows=[]
        cur.close()
        return rows
    
    def retrieve_DB_structure(self, fields):
        sql='SELECT %s FROM sqlite_main WHERE type="table"' % (fields) 
        cur = self.conn.cursor()
        cur.execute(sql)
        info = cur.fetchall()
        cur.close()
        return info
    
    def retrieve_cols_nametype(self,table):
        """
        Retrieve the names of columns in the table
        :param conn: Connection to the SQLite database
        :param table: table to retrieve columns from
        :return: datatypes of columns
        """
        cur = self.conn.cursor()
        sql='PRAGMA TABLE_INFO("%s")'.replace('%s',table)
        cur.execute(sql)      
        info = cur.fetchall()
        #print("\nColumn Info:\nID, Name, Type, NotNull, DefaultVal, PrimaryKey")
        names=[]
        types=[]
        for col in info:
            names.append(col[1])
            types.append(col[2])
        return names,types 
    
    def compact_table(self,table):
        if table.find('"')<0:
            table='"'+table+'"'
            
        sql='VACUUM ' + table
        try:
            cur = self.conn.cursor()
            cur.execute(sql)
            self.conn.commit() 
            cur.close()
            return 0
        except:
            text = str(_("Error in compact_table: ")) + str(sys.exc_info()[1]) 
            #PublishEvent(Severity=5,Text=text + 'SQL: ' + sql,Persistent=True)
            #logger.error("Unexpected error in compact_table: "+ str(sys.exc_info()[1]))
            return -1
    
    def checkTableColumns(self,table,desiredColumns):
        dbNames,dbTypes =self.retrieve_cols_nametype(table)  
        for name,datatype in zip(desiredColumns['names'],desiredColumns['datatypes']): 
            found=False
            equalType=False
            for dbName,dbType in zip(dbNames,dbTypes):
                if dbName==name:
                    found=True
                    if dbType==datatype:
                        equalType=True
                    else:
                        pass# here the type of the column should be changed but SQLITE does not support
            if found==False:
                sql='ALTER TABLE "' + table + '" ADD COLUMN "' + name + '" ' + datatype
                self.executeTransactionWithCommit(SQLstatement=sql, arg=[]) 
                logger.info('The column '+name+' have been added on table ' + table)
                
    def dropTable(self,table):
        table='"'+table+'"'
        sql='DROP TABLE IF EXISTS %s' % table
        return self.executeTransactionWithCommit(SQLstatement=sql,arg=[])
    
    def checkIfColumnExist(self,table,column):
        if self.checkIfTableExist(table):
            names,types =self.retrieve_cols_nametype(table)
            if column in names:
                return True
        return False
        
    def checkIfTableExist(self,table):
        table='"'+table+'"'
        sql="SELECT name FROM sqlite_main WHERE type='table' AND name="+table
        return self.executeTransaction(SQLstatement=sql,arg=[])!=[]

    def getLastRow(table,vars='*',localized=True):
        if vars!='*':
            vars_sql='"timestamp",'
            for var in vars:
                vars_sql+='"'+var+'",'
            vars_sql=vars_sql[:-1]
        else:
            vars_sql='*'
        sql='SELECT '+vars_sql+' FROM "'+ table +'" ORDER BY id DESC LIMIT 1'
        row=self.executeTransaction(SQLstatement=sql)
        if row != []:
            timestamp=row[0]
            values=row[1:]
        else:
            timestamp=None
            values=None
        if localized and timestamp!=None:
            from tzlocal import get_localzone
            local_tz=get_localzone()
            timestamp = local_tz.localize(timestamp)
            timestamp=timestamp+timestamp.utcoffset() 
        return {'timestamp':timestamp,'values':values}
    
def getRegistersDBInstance(year=None):
    if year==None:
        DBPath=REGISTERS_DB_PATH.replace("_XYEARX_",str(timezone.now().year))
    else:
        DBPath=REGISTERS_DB_PATH.replace("_XYEARX_",str(year))
    #logger.debug(DBPath)
    DB=Database(location=DBPath)
    return DB

def backupRegistersDB(year=None):
    if year==None:
        DBPath=REGISTERS_DB_PATH.replace("_XYEARX_",str(timezone.now().year))
    else:
        DBPath=REGISTERS_DB_PATH.replace("_XYEARX_",str(year))
    from shutil import copyfile
    try:
        copyfile(src=DBPath, dst=DBPath+'.bkp')
    except:
        pass

def deleteRegistersDB(year):
    DBPath=REGISTERS_DB_PATH.replace("_XYEARX_",str(year))
    try:
        os.remove(DBPath)
    except OSError:
        pass

def restoreRegistersDB(src=None,year=None):
    if src==None:
        if year==None:
            src=REGISTERS_DB_PATH.replace("_XYEARX_",str(timezone.now().year))+'.bkp'
        else:
            src=REGISTERS_DB_PATH.replace("_XYEARX_",str(year))+'.bkp'
    if year==None:
        dst=REGISTERS_DB_PATH.replace("_XYEARX_",str(timezone.now().year))
    else:
        dst=REGISTERS_DB_PATH.replace("_XYEARX_",str(year))
            
    from shutil import copyfile
    copyfile(src=src, dst=dst)
                
def compactRegistersDB(year=None):
    if year==None:
        DBPath=REGISTERS_DB_PATH.replace("_XYEARX_",str(timezone.now().year))
    else:
        DBPath=REGISTERS_DB_PATH.replace("_XYEARX_",str(year))
    DB=Database(location=DBPath)
    rows=DB.retrieve_DB_structure(fields='*')
    sizep = os.path.getsize(DBPath)
    for row in rows:
        table_name=row[1]
        DB.compact_table(table=table_name)
    size = os.path.getsize(DBPath)
    return {'initial_size':sizep,'final_size':size}

def createTSTDB():
    '''THIS IS VALID FOR DevicesAPP.json fixture
    '''
    sql='CREATE TABLE IF NOT EXISTS "1_1" ( timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "1_1_1" integer, "2_1_1" float, "3_1_1" float, "4_1_1" float, UNIQUE (timestamp) )'
    DB=getRegistersDBInstance()
    DB.executeTransactionWithCommit(SQLstatement=sql)
    sqlIns='INSERT INTO "1_1"(timestamp,"1_1_1","2_1_1","3_1_1","4_1_1") VALUES(?,?,?,?,?)'
    DB.executeTransactionWithCommit(SQLstatement=sqlIns,arg=[datetime.datetime(2018, 2, 4, 20, 58, 31), 7, 3.25, 0.5, 3.5])
    sql='CREATE TABLE IF NOT EXISTS "1_2" ( timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "5_1_2" float, UNIQUE (timestamp) )'
    DB.executeTransactionWithCommit(SQLstatement=sql)
    sqlIns='INSERT INTO "1_2"(timestamp,"5_1_2") VALUES(?,?)'
    DB.executeTransactionWithCommit(SQLstatement=sqlIns,arg=[datetime.datetime(2018, 2, 4, 20, 58, 31), 230.3])