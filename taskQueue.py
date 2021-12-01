import os, subprocess, sys
import locale
import traceback, platform
from datetime import datetime
import time, json, re
import logging


# --- get encoding
coding = locale.getdefaultlocale()[1].strip()

def get_timestamp():
    return datetime.now().strftime(r"%Y-%m-%d %H:%M:%S")

def excute(cmd, backrun=False):
    logger.debug(f"excute: {cmd}")
    proc = subprocess.Popen(cmd, shell=True, 
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE, bufsize=-1)
    if not backrun:
        try:
            stdout, stderr = proc.communicate(timeout=300)
            return proc.returncode, stdout, stderr
        except subprocess.TimeoutExpired:
            logger.error(f"excute:{cmd} time out")
            FAIL()

def write_fail(logname):
    with open(logname, 'a+') as f:
        mesg = f"[{get_timestamp()}] FAIL | {SN}"
        f.write(mesg + '\n')

def write_pass(logname, myQueueFile):
    with open(logname, 'a+') as f:
        mesg = f"[{get_timestamp()}] PASS | {myQueueFile}"
        f.write(mesg + '\n')

def FAIL():
    logger.info("FAIL")
    sys.exit(1)


def PASS():
    logger.info("PASS")


def count(t):
    for s in range(1,t+1):
        time.sleep(1)
        print(s, end="\r")

def getPythonPids(show=False):
    if platform.system() == "Windows":
        logger.debug(f"Platform: Windows")
        cmd = 'tasklist /SVC /FI "IMAGENAME eq Python.exe"'
        keyWord = "Python.exe"
        pid_index = -2
    elif platform.system() == "Linux":
        logger.debug(f"Platform: Linux")
        cmd = "ps aux | grep python | grep -v color"
        keyWord = "python"
        pid_index = 1
    else:
        logger.error(f"Non Compatible to {platform.system()}")
        FAIL()

    r, o, e = excute(cmd)
    if r != 0:
        logger.error(e.decode(coding))
        FAIL()
    
    procs = o.decode(coding).strip()
    if show:
        logger.debug(procs)
    
    pyPids = []


    for proc in procs.split('\n'):
        if keyWord in proc:
            pyPid = proc.split()[pid_index]
            pyPids.append(pyPid)

    return pyPids


def update_json(jsonFile, jsonInfo):
    logger.info(f"updated {jsonFile}")
    with open(jsonFile, 'w') as json_file:
        json.dump(jsonInfo, json_file, indent = 4, sort_keys=True)

def read_json(jsonFile):
    with open(jsonFile) as f:
        proc_pool = json.load(f)
    return proc_pool


def getQueuePid(fs):

    # single file
    if type(fs) == str:
        found = re.search(r"_\d+.queue$", fs)
        if found:
            found = found.group()   # _654.queue
            return  found[1: ].replace(".queue", "") 

    # muiti queue files
    qPids = []
    for f in fs:
        found = re.search(r"_\d+.queue$", f)
        if found:
            found = found.group()   # _654.queue
            qPids.append( found[1: ].replace(".queue", "") )
    return qPids


def deleteFile(fileName):
    try:
        os.remove(fileName)
        logger.debug(f"{fileName} removed")
    except FileNotFoundError:
        logger.debug(f"{fileName} removed already or fail")

def deleteDir(dirPath):
    ERROR_DIR_NOT_EMPTY = 145
    try:
        os.rmdir(dirPath)
        logger.debug(f"{dirPath} removed")

    except OSError as e:
        if e.winerror != ERROR_DIR_NOT_EMPTY:
               raise
        else:
            logger.debug(f"{dirPath} not empty")

# def getQueueFiles(queueForder):
#     qFiles = os.listdir(queueForder)
#     qFiles = [f"{queueForder}{os.sep}{q}" for q in qFiles]
#     return qFiles

def getPidFiles():
    pidFiles = []
    for fname in os.listdir():
        if re.search(r"\d+.key", fname):
            pidFiles.append(fname)
    return pidFiles

def getQueueFiles(taskQueueName):
    qFiles = []
    fs = os.listdir(taskQueueName)
    for f in fs:
        isQueuefile = re.search(r"\w+.queue$", f)
        if isQueuefile:
            isQueuefile = isQueuefile.group()   # timestamp_pid.queue
            qFiles.append( f )
    return qFiles

def clearDeadProcQFile(taskQueueName):
    # get taskQueueName forder files
    qFiles = getQueueFiles(taskQueueName)

    # get tasklist pids
    taskPids = getPythonPids(show=False)
    logger.debug(f"taskPids: {taskPids}")

    # clear qfile if it not exist in tasklist
    for qfile in qFiles:
        logger.debug(qfile)
        qPid = getQueuePid(qfile)
        if qPid not in taskPids:
            deleteFile(f"{taskQueueName}{os.sep}{qfile}")

def readTaskQueue(queueName):
    logger.info(f"read real task queue from {queueName}")
    
    # get real queue file by comparing with tasklist
    realQueue = []
    qFiles = getQueueFiles(queueName)
    
    # get python proc tasklist pids
    taskPids = getPythonPids(show=False)

    # compare qfile pid with tasklist
    for qfile in qFiles:
        qPid = getQueuePid(qfile)   # get queue file's pid
        if qPid in taskPids:        # check q pid exist in tasklikst?
            realQueue.append(qfile)
        else:
            deleteFile(f"{queueName}{os.sep}{qfile}") # delete dead qFile

    return sorted(realQueue) 

def getPermission(taskQueueName):
    
    myPid = os.getpid()
    logger.info(f'{myPid} try getting {taskQueueName} queue permission..')
    
    # create taskQueueName forder if it not exist
    if not os.path.isdir(taskQueueName):
        os.mkdir(taskQueueName)
        logger.debug(f"create {taskQueueName} forder")

    # clear dead proc's queue file
    clearDeadProcQFile(taskQueueName)
    
    # create my queue file
    myQueueFile = f"{get_timestamp_number()}_{myPid}.queue"
    logger.info(f"create {myQueueFile}")

    with open(f"{taskQueueName}{os.sep}{myQueueFile}", 'w') as f:   pass
    
    while True:

        # read queue files and get task queue (sorted)
        taskQueue = readTaskQueue(taskQueueName)
        logger.debug(f"cur real task queue file:")
        for q in taskQueue: logger.info('\t' + q)

        # is my pid in first queue ?
        logger.info(f"My queue file is {myQueueFile}")
        pidOrder = taskQueue.index(myQueueFile)
        logger.info(f"my pid:{myPid} order is {pidOrder}, sleep {pidOrder}s")

        if pidOrder > 0:
            # sleep order time
            logger.info(f"wait for permission, sleep {pidOrder}")
            time.sleep(pidOrder)
        else:                   # pidOrder == 0 , got permission
            logger.info(f"{myPid} got permission")
            return f"{taskQueueName}{os.sep}{myQueueFile}"

def releasePermission(queueFile):
    logger.info("release permission")
    os.remove(queueFile)
    logger.debug(f"{queueFile} removed")

    # check forder null?
    queueForder = queueFile.split(f"{os.sep}")[0]
    print(queueFile)
    print(queueForder)
    if len( os.listdir(queueForder) ) == 0:
        deleteDir(queueForder)

def get_timestamp_number():
    return str(datetime.now().timestamp()).replace('.','')

def getQueueTimeStamp():
    return str(datetime.now().timestamp()).replace('.','')


def getLogger(logFile=None):

    # create logger 
    log = logging.getLogger(__name__)
    log.setLevel(level=logging.DEBUG)

    # create formatter and add it to the handlers
    formatter = logging.Formatter("%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s")

    if logFile:
        # create file handler for logger.
        fh = logging.FileHandler(logFile)
        fh.setFormatter(formatter)
        fh.setLevel(level=logging.DEBUG)
    
    # reate console handler for logger.
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    ch.setLevel(level=logging.DEBUG)
    
    # add handlers to logger.
    if logFile:
        log.addHandler(fh)

    log.addHandler(ch)

    return log 



if __name__ == '__main__':

    try:
        
        logForder = "logs"
        
        if not os.path.isdir(logForder):
            os.mkdir(logForder)

        # --- create tmp file by timestamp
        SN = str(datetime.now().timestamp()).replace('.','')
        logfile = f"{logForder}{os.sep}{SN}.log"

        # --- init logger ---
        logger = getLogger(logfile)

        # --- get my pid
        
        myPid = os.getpid()
        logger.info(f"SN: {SN}")
        logger.info(f"PID: {myPid}")
        
        permission = getPermission(taskQueueName="writeName")
        # === protected region

        with open("writeName.log", 'a') as f:
            f.write(f"{get_timestamp()} | {SN}\n")
        time.sleep(1)

        # === protected region
        releasePermission(permission)



        permission = getPermission(taskQueueName="sleep3")
        # === protected region
        time.sleep(3)
        # === protected region
        releasePermission(permission)



        PASS()




    except Exception as ex:        
        errMsg = traceback.format_exc()
        logger.error(errMsg)
        FAIL()
        
    finally:
        logger.info("Process END")



