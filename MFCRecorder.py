import time, datetime, os, threading, sys, asyncio, configparser, subprocess
from livestreamer import Livestreamer
from queue import Queue
from mfcauto import Client, Model, FCTYPE, STATE


Config = configparser.ConfigParser()
Config.read(sys.path[0] + "/config.conf")
save_directory = Config.get('paths', 'save_directory')
wishlist = Config.get('paths', 'wishlist')
interval = int(Config.get('settings', 'checkInterval'))
directory_structure = Config.get('paths', 'directory_structure').lower()
postProcessingCommand = Config.get('settings', 'postProcessingCommand')
try:
    postProcessingThreads = int(Config.get('settings', 'postProcessingThreads'))
except ValueError:
    pass
completed_directory = Config.get('paths', 'completed_directory').lower()

online = []
if not os.path.exists("{path}".format(path=save_directory)):
    os.makedirs("{path}".format(path=save_directory))

recording = []
recordingNames = []

def getOnlineModels():
    wanted = []
    with open(wishlist) as f:
        models = list(set(f.readlines()))
        for theModel in models:
            wanted.append(int(theModel))
    f.close()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = Client(loop)

    def query():
        try:
            MFConline = Model.find_models(lambda m: m.bestsession["vs"] == STATE.FreeChat.value)
            for model in MFConline:
                if model.bestsession['uid'] in wanted and model.bestsession['uid'] not in recording:
                    thread = threading.Thread(target=startRecording, args=(model.bestsession,))
                    thread.start()
            client.disconnect()
        except:
            client.disconnect()
            pass

    client.on(FCTYPE.CLIENT_MODELSLOADED, query)
    try:
        loop.run_until_complete(client.connect())
        loop.run_forever()
    except:
        pass
    loop.close()

def startRecording(model):
    try:
        session = Livestreamer()
        streams = session.streams("hlsvariant://http://video{srv}.myfreecams.com:1935/NxServer/ngrp:mfc_{id}.f4v_mobile/playlist.m3u8"
          .format(id=(int(model['uid']) + 100000000),
            srv=(int(model['camserv']) - 500)))
        stream = streams["best"]
        fd = stream.open()
        now = datetime.datetime.now()
        filePath = directory_structure.format(path=save_directory, model=model['nm'], uid=model['uid'],
                                              seconds=now.strftime("%S"), day=now.strftime("%d"),
                                              minutes=now.strftime("%M"), hour=now.strftime("%H"),
                                              month=now.strftime("%m"), year=now.strftime("%Y"))
        directory = filePath.rsplit('/', 1)[0]+'/'
        if not os.path.exists(directory):
            os.makedirs(directory)
        with open(filePath, 'wb') as f:
            recording.append(model['uid'])
            recordingNames.append(model['nm'])
            while True:
                try:
                    data = fd.read(1024)
                    f.write(data)
                except:
                    f.close()
                    recording.remove(model['uid'])
                    recordingNames.remove(model['nm'])
                    if postProcessingCommand != "":
                        processingQueue.put({'model':model['nm'], 'path': filePath, 'uid':model['uid']})
                    elif completed_directory != "":
                        finishedDir = completed_directory.format(path=save_directory, model=model, uid=model['uid'],
                                                                 seconds=now.strftime("%S"), minutes=now.strftime("%M"),
                                                                 hour=now.strftime("%H"), day=now.strftime("%d"),
                                                                 month=now.strftime("%m"), year=now.strftime("%Y"))
                        if not os.path.exists(finishedDir):
                            os.makedirs(finishedDir)
                        os.rename(filePath, finishedDir+'/'+filePath.rsplit['/', 1][0])
                    return

        if model in recording:
            recording.remove(model['uid'])
            recordingNames.remove(model['nm'])
    except:
        if model in recording:
            recording.remove(model['uid'])
            recordingNames.remove(model['nm'])

def postProcess():
    global processingQueue
    global postProcessingCommand
    while True:
        while processingQueue.empty():
            time.sleep(1)
        parameters = processingQueue.get()
        print("got parameters")
        model = parameters['model']
        path = parameters['path']
        filename = path.rsplit('/', 1)[1]
        uid = str(parameters['uid'])
        directory = path.rsplit('/', 1)[0]+'/'
        print(postProcessingCommand.split() + [path, filename, directory, model, uid])
        subprocess.call(postProcessingCommand.split() + [path, filename, directory, model, uid])


if __name__ == '__main__':
    if postProcessingCommand != "":
        processingQueue = Queue()
        postprocessingWorkers = []
        for i in range(0, postProcessingThreads):
            t = threading.Thread(target=postProcess)
            postprocessingWorkers.append(t)
            t.start()
    print("____________________Connection Status____________________")
    while True:
        getOnlineModels()
        sys.stdout.write("\033[F")
        sys.stdout.write("\033[K")
        sys.stdout.write("\033[F")
        sys.stdout.write("\033[K")
        sys.stdout.write("\033[F")
        sys.stdout.write("\033[F")
        print()
        print()
        print("Disconnected:")
        print("Waiting for next check")
        print("____________________Recording Status_____________________")
        for i in range(20, 0, -1):
            sys.stdout.write("\033[K")
            print("{} model(s) are being recorded. Next check in {} seconds".format(len(recording), i))
            sys.stdout.write("\033[K")
            print("the following models are being recorded: {}".format(recordingNames), end="\r")
            time.sleep(1)
            sys.stdout.write("\033[F")
        sys.stdout.write("\033[F")
        sys.stdout.write("\033[F")
        sys.stdout.write("\033[F")