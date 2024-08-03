import logging
import subprocess
import yaml
import json
import re

from flask import (
    current_app as app,
    request,
    redirect,
    Response,
    render_template,
)
from flask.views import MethodView


def render_json(json_data):
    resp = app.make_response(json.dumps(json_data))
    resp.headers['Content-type'] = 'application/json'
    return resp


def find_resolutions(device):
    formats = subprocess.run(
        ('v4l2-ctl', '-d', device, '--list-formats-ext'),
        stdout=subprocess.PIPE,
    )
    lines = formats.stdout.decode().split('\n')
    options = {}
    format_re = re.compile('\[\d+\]:')
    current_format = None
    current_resolution = None
    for line in lines:
        m = format_re.search(line)
        if m:
            if 'YUYV' in line:
                current_format = 'YUYV'
                options.update({current_format: {}})
            if 'MJPG' in line:
                current_format = 'MJPG'
                options.update({current_format: {}})
            if 'H264' in line:
                current_format = 'H264'
                options.update({current_format: {}})
            if 'NV12' in line:
                current_format = 'NV12'
                options.update({current_format: {}})
        else:
            if 'Size' in line and current_format is not None:
                resolution = line.split(' ')[-1]
                options[current_format].update({resolution: []})
                current_resolution = resolution
            if 'Interval' in line and current_resolution is not None:
                framerate_str = line.split(' ')[-2][1:]
                if framerate_str == '59.940':
                    framerate = framerate_str
                else:
                    framerate = int(float(framerate_str))
                options[current_format][current_resolution].append(framerate)
    return options


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


def find_serial(device_name):
    cmd1 = subprocess.Popen(('/bin/udevadm', 'info', '--name={}'.format(device_name)), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    cmd2 = subprocess.run(('grep', 'SERIAL_SHORT'), stdin=cmd1.stdout, stdout=subprocess.PIPE)
    if cmd2.returncode == 0:
        serial = cmd2.stdout.decode().strip().split('\n')[0].split('=')[1]
    else:
        serial = ''
    return serial


def get_device_settings(video_device, webcam_type=None):
    v4l2_settings = get_v4l2_settings(video_device)
    camera_settings = ','.join(v4l2_settings.keys())
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


def get_v4l2_settings(device):
    v4l2_options_raw = subprocess.run(
        ('v4l2-ctl', '--device={}'.format(device), '-l'),
        stdout=subprocess.PIPE,
    ).stdout.decode().split('\n')
    v4l2_settings = {}
    for line in v4l2_options_raw:
        elems = line.strip().split(' ')
        v4l2_option = elems[0]
        # exclude 'User Controls' and 'Camera Controls' lines
        if v4l2_option and v4l2_option != 'User' and v4l2_option != 'Camera':
            _min = re.findall('min=(-?\d+)', line)
            _max = re.findall('max=(-?\d+)', line)
            _default = re.findall('default=(-?\d+)', line)
            _step = re.findall('step=(-?\d+)', line)
            _value = re.findall('value=(-?\d+)', line)
            v4l2_settings.update({
                v4l2_option: {
                    'min': _min[0] if _min else None,
                    'max': _max[0] if _max else None,
                    'step': _step[0] if _step else None,
                    'default': _default[0] if _default else None,
                    'value': _value[0] if _value else None,
                }
            })
    return v4l2_settings


def v4l2h264enc_available():
    cmd = subprocess.run(
        'gst-inspect-1.0 v4l2h264enc'.split(' '),
        stdout=subprocess.PIPE
    )
    return cmd.returncode == 0


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
        if serial == '' and 'Cam Link' in description:
            # cam link does not report unique serial so set one
            serial = 'CAMLINK'
        if serial == '' and 'Kiyo Pro Ultra' in description:
            # cam link does not report unique serial so set one
            serial = 'KIYOPROULTRA'
        elif serial == '' and 'Kiyo Pro' in description:
            # cam link does not report unique serial so set one
            serial = 'KIYOPRO'
        v4l2_options = get_v4l2_settings(device)
        if serial in ('KIYOPRO', 'KIYOPROULTRA'):
            v4l2_options.update({'exposure_time_absolute': {'min': 10}})
            v4l2_options.update({'exposure_time_absolute': {'max': 156}})
        devices.update({
            device: {
                'serial': serial,
                'description': description,
                'v4l2_options': v4l2_options,
                'video_options': find_resolutions(device),
            }
        })
        # probably a better way to handle this but seems to work for now
        # loop until a blank line
        while device != '' and len(video_devices):
            device = video_devices.pop(0)
        if len(video_devices) == 1:
            break
    return devices


class VideoDeviceApiHandler(MethodView):
    def post(self, serial):
        data = request.json
        adjust_video_settings(data['video_device'], data['settings'])
        return render_json({'status': 'ok'})


class VideoDeviceHandler(MethodView):
    def get(self, serial):
        v4l2_settings = {}
        description = ''
        if request.method == 'GET':
            device_config = None
            video_configs = app.picam_config.video_devices
            v4l2_options = {}
            video_options = None
            for video_device, device_info in find_video_devices().items():
                if serial == device_info['serial']:
                    description = device_info['description']
                    device_config = video_configs.get(serial, {})
                    v4l2_options = device_info.get('v4l2_options', {})
                    v4l2_settings = {
                        setting: value['default']
                        for setting, value in v4l2_options.items()
                        if value.get('default', None) is not None
                    }
                    v4l2_settings.update(device_config.get('v4l2', {}))
                    video_options = device_info.get('video_options', None)
                    break
            encodings = video_options.keys()
            resolutions = []
            framerates = []
            resolution = device_config.get('resolution', '1920x1080')
            framerate = device_config.get('framerate', 30)
            encoding = device_config.get('encoding', 'jpegenc')
            if not device_config:
                if 'H264' in encodings:
                    encoding = 'h264'
                    resolutions = list(video_options['H264'].keys())
                    if resolution not in resolutions:
                        resolution = resolutions[0]
                        device_config.update({'resolution': resolutions[0]})
                    framerates = video_options['H264'][resolution]
                    if str(framerate) not in [str(f) for f in framerates]:
                        framerate = framerates[0]
                        device_config.update({'framerate': framerate})
                elif 'MJPG' in encodings:
                    encoding = 'mjpeg'
                    resolutions = list(video_options['MJPG'].keys())
                    if resolution not in resolutions:
                        resolution = resolutions[0]
                        device_config.update({'resolution': resolutions[0]})
                    framerates = video_options['MJPG'][resolution]
                    if str(framerate) not in [str(f) for f in framerates]:
                        framerate = framerates[0]
                        device_config.update({'framerate': framerate})
                elif 'YUYV' in encodings:
                    resolutions = list(video_options['YUYV'].keys())
                    if resolution not in resolutions:
                        resolution = resolutions[0]
                        device_config.update({'resolution': resolutions[0]})
                    framerates = video_options['YUYV'][resolution]
                    if str(framerate) not in [str(f) for f in framerates]:
                        framerate = framerates[0]
                        device_config.update({'framerate': framerate})
                if str(60) in [str(f) for f in framerates]:
                    framerate = 60
                device_config.update({
                    'resolution': resolution,
                    'framerate': framerate,
                    'encoding': encoding,
                })
                v4l2_settings.update({k: v.get('default', None) for k, v in v4l2_options.items()})
            else:
                if encoding == 'h264':
                    resolutions = video_options['H264'].keys()
                    framerates = video_options['H264'][resolution]
                elif encoding == 'mjpeg':
                    resolutions = video_options['MJPG'].keys()
                    framerates = video_options['MJPG'][resolution]
                else:
                    resolutions = list(video_options['YUYV'].keys())
                    if resolution not in resolutions:
                        resolution = resolutions[0]
                        device_config['resolution'] = resolutions[0]
                    framerates = video_options['YUYV'][resolution]
                    if str(framerate) not in [str(f) for f in framerates]:
                        framerate = framerates[0]
                        device_config.update({'framerate': framerate})
            model = {
                'serial': serial,
                'video_device': serial,
                'description': description,
                'device_config': device_config,
                'v4l2_options': v4l2_options,
                'v4l2': v4l2_settings,
                'video_options': video_options,
                'resolutions': resolutions,
                'framerates': [str(f) for f in framerates],
                'message': '',
                'menu': 'devices',
                'v4l2h264enc_available': v4l2h264enc_available(),
            }
            return render_template('config_video_device.html', **model)

    def post(self, serial):
        if request.form.get('delete', None):
            del app.picam_config.video_devices[serial]
            return redirect('/devices')
        video_devices = find_video_devices()
        v4l2_options = {}
        for _, device_info in video_devices.items():
            if device_info['serial'] == serial:
                v4l2_options = device_info['v4l2_options']
                break
        v4l2_settings = {}
        # prune out the settings that aren't available
        keys = list(v4l2_settings.keys())
        for k in keys:
            if k not in v4l2_options:
                del v4l2_settings[k]
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
            if framerate != '59.940':
                framerate = int(framerate)
            app.picam_config.video_devices[serial]['framerate'] = framerate
        for config_option in ['resolution', 'type', 'encoding']:
            app.picam_config.video_devices[serial][config_option] = request.form.get('{}-{}'.format(serial, config_option))
        for v4l2_ctl in v4l2_options.keys():
            ctl_val = request.form.get('{}-{}'.format(serial, v4l2_ctl))
            if ctl_val is not None:
                if ctl_val == 'on':
                    # not quite the best way to handle this generically
                    if v4l2_ctl == 'auto_exposure':
                        ctl_val = 3
                    else:
                        ctl_val = 1

                    # deprecated property?
                    if v4l2_ctl == 'exposure_auto':
                        ctl_val = 3
                    else:
                        ctl_val = 1
                v4l2_settings[v4l2_ctl] = int(ctl_val)
            else:
                # handle missing values as 'off' or 'manual'
                auto_properties = (
                    'focus_auto',
                    'focus_automatic_continuous',
                    'white_balance_auto',
                    'white_balance_automatic',
                    'backlight_compensation',
                    'exposure_auto_priority',
                    'exposure_dynamic_framerate',
                )
                if v4l2_ctl in auto_properties:
                    v4l2_settings[v4l2_ctl] = 0

                if v4l2_ctl == 'auto_exposure':
                    # manual mode
                    v4l2_settings[v4l2_ctl] = 1

                # deprecated property?
                if v4l2_ctl == 'exposure_auto':
                    # manual mode
                    v4l2_settings[v4l2_ctl] = 1
        app.picam_config.video_devices[serial]['v4l2'].update(v4l2_settings)
        return redirect('/devices')

    def delete(self, serial):
        del app.picam_config.video_devices[serial]
        return render_json({"status": "ok"})
