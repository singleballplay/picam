#!/usr/bin/env python3

from flask import Flask, request, render_template
import subprocess
import logging
import yaml
import json
import html_fields

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.globals["html_fields"] = html_fields

settings = None

with open('/opt/picam.yaml', 'r') as settings_file:
    try:
        settings = yaml.safe_load(settings_file)
    except:
        logging.error('failed to parse settings file')

def find_audio_devices():
    cmd1 = subprocess.run(('cat', '/proc/asound/cards'), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    device_list = cmd1.stdout.decode().strip().split('\n')
    audio_devices = [d.strip() for d in device_list if d]
    devices = {}
    idx = 0
    while idx < len(audio_devices):
        alsa_idx = audio_devices[idx].split(' ')[0]
        devices.update({alsa_idx: audio_devices[idx + 1]})
        idx += 2
    return devices.items()

def get_device_settings(video_device):
    camera_settings = ','.join([
        'focus_auto',
        'focus_absolute',
        'exposure_auto_priority',
        'exposure_auto',
        'exposure_absolute',
        'brightness',
        'contrast',
        'saturation',
        'sharpness',
        'gain',
        'backlight_compensation',
        'white_balance_temperature_auto',
        'white_balance_temperature',
        'pan_absolute',
        'tilt_absolute',
        'zoom_absolute'
    ])
    v4l2_cmd = subprocess.run(('v4l2-ctl', '-d', video_device, '-C', camera_settings), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    settings_list = [val.strip() for val in v4l2_cmd.stdout.decode().split('\n') if val]
    device_settings = {v.split(':')[0].strip(): v.split(':')[1].strip() for v in settings_list}
    return device_settings

def find_serial(device_name):
    cmd1 = subprocess.Popen(('/bin/udevadm', 'info', '--name={}'.format(device_name)), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    cmd2 = subprocess.run(('grep', 'SERIAL_SHORT'), stdin=cmd1.stdout, stdout=subprocess.PIPE)
    if cmd2.returncode == 0:
        return cmd2.stdout.decode().strip().split('\n')[0].split('=')[1]
    else:
        return ''

def find_video_devices():
    """
    fetches devices from v4l2 and creates a dict with the device
    name as the key and the description in value
    """
    device_list = subprocess.run(["v4l2-ctl", "--list-devices"], stdout=subprocess.PIPE).stdout.decode().split('\n')
    video_devices = [d.strip() for d in device_list if d]
    devices = {}
    idx = 0
    while idx < len(video_devices):
        devices.update({video_devices[idx + 1]: video_devices[idx]})
        idx += 2
    return devices.items()

def adjust_mic_volume(device, level):
    """
    Adjust the volume level for a mic device

    Args:
        device: the alsa device id e.g. hw:3
        level: the volume level in from 0-100
    """
    result = subprocess.run([
        'amixer',
        '-D',
        device,
        'sset',
        'Mic',
        '{}%'.format(level)
    ])
    if result.returncode != 0:
        logging.error('non-zero return code setting mic volume')

def adjust_video_settings(device, settings):
    """
    Adjusts the settings for a given webcam

    Args:
        device: the v4l2 device e.g. /dev/video0
        settings: the controls to change
    """
    settings_str = ','.join([
        '{}={}'.format(k, v) for k, v in settings.items()
    ])
    app.logger.info('changing settings to: {}'.format(settings_str))
    result = subprocess.run([
        'v4l2-ctl',
        '-d', device,
        '-c', settings_str
    ])
    if result.returncode != 0:
        logging.error('non-zero return code changing webcam settings')

def adjust_video_setting(device, setting, value):
    """
    Adjusts the setting for a given webcam

    Args:
        device: the v4l2 device e.g. /dev/video0
        setting: the control to change
        value: the value to change it to
    """
    result = subprocess.run([
        'v4l2-ctl',
        '-d', device,
        '-c', '{}={}'.format(setting, value)
    ])
    if result.returncode != 0:
        logging.error('non-zero return code changing webcam setting')

@app.route('/', methods=['GET'])
def index():
    video_devices = {}
    for video_device, description in find_video_devices():
        serial = find_serial(video_device)
        device_settings = get_device_settings(video_device)
        if serial in settings['video_devices']:
            camera_path = settings['video_devices'][serial]['endpoint']
        else:
            camera_path = description
        device_settings.update({'path': camera_path})
        video_devices.update({video_device: device_settings})
    model = {
        'video_devices': video_devices,
        'audio_devices': ['playfield', 'backglass', 'player', 'snowball']
    }
    return render_template('index.html', **model)

@app.route('/audio-devices', methods=['GET'])
def list_audio_devices():
    return 'ok'

@app.route('/audio-device', methods=['POST'])
def adjust_mic():
    device = 'hw:3'
    level = 50
    adjust_mic_volume(device, level)
    return 'ok'

@app.route('/video-devices', methods=['GET'])
def list_video_devices():
    return 'ok'

@app.route('/video-device', methods=['POST'])
def adjust_video():
    data = request.json
    app.logger.info('received data: {}'.format(data))
    adjust_video_settings(data['video_device'], data['settings'])
    return json.dumps('ok')

if __name__ == '__main__':
    app.run(host='0.0.0.0')
