import os
import glob
import subprocess

# Functions to find and access USB drive
#  from http://stackoverflow.com/questions/22615750/how-can-the-directory-of-a-usb-drive-connected-to-a-system-be-obtained

DEBUG = False

def debugprint(x):
    if DEBUG:
        print(x)

def get_usb_devices():
    sdb_devices = map(os.path.realpath, glob.glob('/dev/sd*'))
    usb_devices = [d for d in sdb_devices if len(d) > 0]
    debugprint('{} {}'.format(list(sdb_devices), list(usb_devices)))
    return dict((os.path.basename(dev), dev) for dev in usb_devices)

def get_usb_path():
    devices = get_usb_devices()
    output = subprocess.check_output(['mount']).splitlines()
    is_usb = lambda path: any(dev in path.decode('utf8') for dev in devices)
    usb_info = (line for line in output if is_usb(line.split()[0]))
    fullInfo = []
    for info in usb_info:
        mountURI = info.split()[0]
        usbURI = info.split()[2]
        for x in range(3, info.split().__sizeof__()):
            if info.split()[x].__eq__("type"):
                for m in range(3, x):
                    usbURI += " "+info.split()[m]
                break
        fullInfo.append([mountURI.decode('utf8'), usbURI.decode('utf8')])
    debugprint('devices {}'.format(devices))
    debugprint('usb_info {}'.format(list(usb_info)))
    debugprint('fullInfo {}'.format(fullInfo))
    if not fullInfo:
        return None
    for dev in fullInfo[0]:
        if 'media' in dev:
            return dev
    return None

def usb_inserted():
    path = get_usb_path()
    return path is not None
    
if __name__ == '__main__':
    print('get_usb_path() returns', get_usb_path())
