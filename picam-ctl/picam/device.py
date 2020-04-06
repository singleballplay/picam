import logging
import subprocess
import yaml
import json
import re

from flask import (
    current_app as app,
    request,
    flash,
    redirect,
    Response,
    render_template,
)
from flask.views import MethodView

V4L2_DEFAULTS = {
    'focus_auto': 0,
    'focus_absolute': 0,
    'exposure_auto_priority': 0,
    'exposure_auto': 1,
    'exposure_absolute': 200,
    'brightness': 128,
    'contrast': 128,
    'saturation': 128,
    'sharpness': 128,
    'gain': 32,
    'backlight_compensation': 0,
    'white_balance_temperature_auto': 0,
    'white_balance_temperature': 4400,
    'pan_absolute': 0,
    'tilt_absolute': 0,
    'zoom_absolute': 100
}

LOGITECH_WEBCAM_OPTIONS = [
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
]


def render_json(json_data):
    resp = app.make_response(json.dumps(json_data))
    resp.headers['Content-type'] = 'application/json'
    return resp


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


def get_snd_devices():
    cmd1 = subprocess.run(
        ('ls', '-1', '/dev/snd/by-id'),
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )
    return cmd1.stdout.decode().strip().split('\n')

def get_asound_devices(recordable_devices):
    cmd1 = subprocess.run(
        ('cat', '/proc/asound/cards'),
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )
    device_list = cmd1.stdout.decode().strip().split('\n')
    audio_devices = [d.strip() for d in device_list if d]
    devices = {}
    idx = 0
    while idx < len(audio_devices):
        alsa_idx = audio_devices[idx].split(' ')[0]
        if alsa_idx in recordable_devices.keys():
            devices.update({alsa_idx: audio_devices[idx +1]})
        idx += 2
    return devices


def get_recordable_devices():
    cmd1 = subprocess.run(
        ('arecord', '--list-devices'),
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )
    device_list = cmd1.stdout.decode().strip().split('\n')
    audio_devices = [d.strip() for d in device_list if d]
    devices = {}
    idx = 1
    while idx < len(audio_devices):
        summary_line = audio_devices[idx]
        alsa_idx = re.search(r'^card (\d+):', summary_line).groups()[0]
        description = re.search(r'^card \d: [^[]+ \[([^,]+)\]', summary_line).groups()[0]
        serial = 'UNKNOWN'
        devices.update(
            {
                alsa_idx: {
                    'serial': serial,
                    'description': description,
                    'summary_line': summary_line,
                }
            }
        )
        idx += 3
    return devices


def find_serial(device_name):
    cmd1 = subprocess.Popen(('/bin/udevadm', 'info', '--name={}'.format(device_name)), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    cmd2 = subprocess.run(('grep', 'SERIAL_SHORT'), stdin=cmd1.stdout, stdout=subprocess.PIPE)
    if cmd2.returncode == 0:
        return cmd2.stdout.decode().strip().split('\n')[0].split('=')[1]
    else:
        return ''


def find_audio_devices():
    video_devices = {}
    for video_device, device_info in find_video_devices().items():
        s = re.search(r'(usb[^\)]+)', device_info['description'])
        if s:
            video_devices.update({
                device_info['serial']: {
                    'usb_description': s.group(0),
                    'description': device_info['description'],
                    'video_device': video_device,
                }
            })
    sound_devices = {}
    for snd_device in get_snd_devices():
        cmd1 = subprocess.Popen(
            ('/bin/udevadm', 'info', '--name=/dev/snd/by-id/{}'.format(snd_device)),
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        cmd2 = subprocess.run(
            ('grep', 'SERIAL_SHORT'),
            stdin=cmd1.stdout, stdout=subprocess.PIPE
        )
        dev_serial_short = ''
        if cmd2.returncode == 0:
            dev_serial_short = cmd2.stdout.decode().strip().split('\n')[0].split('=')[1]
        cmd1 = subprocess.Popen(
            ('/bin/udevadm', 'info', '--name=/dev/snd/by-id/{}'.format(snd_device)),
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        cmd2 = subprocess.run(
            ('grep', 'SERIAL'),
            stdin=cmd1.stdout, stdout=subprocess.PIPE
        )
        dev_serial = ''
        if cmd2.returncode == 0:
            dev_serial = cmd2.stdout.decode().strip().split('\n')[0].split('=')[1]

        if dev_serial_short:
            sound_devices.update({
                dev_serial_short: {
                    'alsa_idx': '',
                    'snd_device': snd_device,
                    'description': dev_serial,
                }
            })
    #recordable_devices = get_recordable_devices()
    #asound_devices = get_asound_devices(recordable_devices)
    return sound_devices


def get_device_settings(video_device, webcam_type=None):
    camera_settings = ','.join(LOGITECH_WEBCAM_OPTIONS)
    v4l2_cmd = subprocess.run(
        ('v4l2-ctl', '-d', video_device, '-C', camera_settings),
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )
    settings_list = [
        val.strip()
        for val in v4l2_cmd.stdout.decode().split('\n') if val
    ]
    device_settings = {
        v.split(':')[0].strip(): v.split(':')[1].strip()
        for v in settings_list
    }
    return device_settings


def find_video_serial(device_name):
    cmd1 = subprocess.Popen(
        ('/bin/udevadm', 'info', '--name={}'.format(device_name)),
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )
    cmd2 = subprocess.run(
        ('grep', 'SERIAL_SHORT'),
        stdin=cmd1.stdout, stdout=subprocess.PIPE
    )
    if cmd2.returncode == 0:
        return cmd2.stdout.decode().strip().split('\n')[0].split('=')[1]
    else:
        return ''


def find_video_devices():
    """
    fetches devices from v4l2 and creates a dict with the device
    name as the key and the description in value
    """
    device_list = subprocess.run(
        ["v4l2-ctl", "--list-devices"],
        stdout=subprocess.PIPE
    ).stdout.decode().split('\n')
    video_devices = [d.strip() for d in device_list]
    devices = {}
    while len(video_devices):
        description = video_devices.pop(0)
        device = video_devices.pop(0)
        serial = find_serial(device)
        if 'Cam Link' in description:
            serial = 'CAMLINK'
        devices.update({
            device: {
                'serial': serial,
                'description': description
            }
        })
        while device != '' and len(video_devices):
            device = video_devices.pop(0)
        if len(video_devices) == 1:
            break
    return devices


class DevicesHandler(MethodView):
    def get(self):
        video_devices = []
        video_configs = app.picam_config.video_devices
        video_device_serials = {}
        for video_device, device_info in find_video_devices().items():
            serial = device_info['serial']
            video_device_serials.update({serial: serial})
            video_devices.append({
                'device': video_device,
                'description': device_info['description'],
                'serial': serial,
                'device_config': video_configs.get(serial, {}),
            })
        audio_devices = []
        audio_configs = app.picam_config.audio_devices
        for serial, device_info in find_audio_devices().items():
            audio_devices.append({
                'serial': serial,
                'alsa_idx': device_info['alsa_idx'],
                'description': device_info['description'],
                'device_config': audio_configs.get(serial, {}),
            })
        cat_hostname = subprocess.run(('cat', '/etc/hostname'), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        hostname = cat_hostname.stdout.decode().strip()
        model = {
            'video_devices': video_devices,
            'audio_devices': audio_devices,
            'hostname': hostname,
        }
        return render_template('devices.html', **model)


class VideoDeviceApiHandler(MethodView):
    def post(self, serial):
        data = request.json
        adjust_video_settings(data['video_device'], data['settings'])
        return render_json({'status': 'ok'})


class VideoDeviceHandler(MethodView):
    def get(self, serial):
        v4l2_settings = V4L2_DEFAULTS.copy()
        description = ''
        if request.method == 'GET':
            device_config = None
            video_configs = app.picam_config.video_devices
            for video_device, device_info in find_video_devices().items():
                if serial == device_info['serial']:
                    description = device_info['description']
                    device_config = video_configs.get(serial, {})
                    v4l2_settings.update(device_config.get('v4l2', {})),
            model = {
                'serial': serial,
                'video_device': serial,
                'description': description,
                'device_config': device_config,
                'v4l2': v4l2_settings,
                'message': '',
            }
            return render_template('config_video_device.html', **model)

    def post(self, serial):
        v4l2_settings = V4L2_DEFAULTS.copy()
        if request.form.get('delete', None):
            del app.picam_config.video_devices[serial]
            return redirect('/devices')
        if not app.picam_config.video_devices.get(serial):
            app.picam_config.video_devices[serial] = dict()
        if not app.picam_config.video_devices.get('v4l2'):
            app.picam_config.video_devices[serial]['v4l2'] = dict()
        endpoint_url = request.form.get('{}-endpoint'.format(serial))
        if endpoint_url and not endpoint_url.startswith('/'):
            endpoint_url = '/' + endpoint_url
        app.picam_config.video_devices[serial]['endpoint'] = endpoint_url
        framerate = request.form.get('{}-framerate'.format(serial))
        if framerate:
            app.picam_config.video_devices[serial]['framerate'] = int(framerate)
        for config_option in ['resolution', 'type', 'encoding']:
            app.picam_config.video_devices[serial][config_option] = request.form.get('{}-{}'.format(serial, config_option))
        for v4l2_ctl in LOGITECH_WEBCAM_OPTIONS:
            ctl_val = request.form.get('{}-{}'.format(serial, v4l2_ctl))
            if ctl_val is not None:
                v4l2_settings[v4l2_ctl] = int(ctl_val)
        app.picam_config.video_devices[serial]['v4l2'].update(v4l2_settings)
        return redirect('/devices')

    def delete(self, serial):
        del app.picam_config.video_devices[serial]
        return render_json({"status": "ok"})


class AudioDeviceHandler(MethodView):
    def get(self, serial):
        audio_configs = app.picam_config.audio_devices
        device_config = None
        description = ''
        for device_serial, device_info in find_audio_devices().items():
            if device_serial == serial:
                device_config = audio_configs.get(device_serial, {})
                description = device_info['description']
                break
        model = {
            'description': description,
            'serial': serial,
            'audio_device': serial,
            'device_config': device_config,
        }
        return render_template('config_audio_device.html', **model)

    def post(self, serial):
        if request.form.get('delete', None):
            del app.picam_config.audio_devices[serial]
            return redirect('/devices')
        if not app.picam_config.audio_devices.get(serial):
            app.picam_config.audio_devices[serial] = dict()
        endpoint_url = request.form.get('{}-endpoint'.format(serial))
        if endpoint_url and not endpoint_url.startswith('/'):
            endpoint_url = '/' + endpoint_url
        app.picam_config.audio_devices[serial]['endpoint'] = endpoint_url
        audio_rate = request.form.get('{}-audio_rate'.format(serial))
        if audio_rate:
            app.picam_config.audio_devices[serial]['audio_rate'] = int(audio_rate)
        for config_option in ['type']:
            app.picam_config.audio_devices[serial][config_option] = request.form.get('{}-{}'.format(serial, config_option))
        return redirect('/devices')

    def delete(self, serial):
        del app.picam_config.video_devices[serial]
        return redirect('/devices')
