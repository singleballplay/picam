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


def find_audio_devices(with_rates=False):
    """
    Look at all of the usb sound devices available and create a dict with the alsa index based
    on the card id found and the serial if available.

    Special cases can be handled here for devices like Snowballs and such that do not have serials
    and only support one of that type connected to the Pi.
    """
    devices = {}
    snd_cmd = subprocess.run(
        ('ls', '-1', '/dev/snd/by-id'),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    usb_devices = snd_cmd.stdout.decode().strip().split('\n')
    card_idx_pattern = re.compile('/sound/card(\d+)/')
    for usb_device in usb_devices:
        serial = None
        card_idx = None
        model = ''
        cmd1 = subprocess.run(
            ('/bin/udevadm', 'info', '--name=/dev/snd/by-id/{}'.format(usb_device)),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        lines = cmd1.stdout.decode().strip().split('\n')
        for line in lines:
            if 'DEVPATH=' in line:
                m = re.search(card_idx_pattern, line)
                if m:
                    card_idx = m.group(1)
            elif 'SERIAL_SHORT=' in line:
                serial = line.strip().split('=')[1]
            elif 'ID_MODEL=' in line:
                model = line.strip().split('=')[1]
                model = model.replace('_', ' ')
        if card_idx and serial:
            sample_rates = []
            if with_rates:
                for sample_rate in [32000, 44100, 48000]:
                    cmd = subprocess.run(
                        f'gst-launch-1.0 alsasrc device=hw:{card_idx} num-buffers=10 ! audio/x-raw,rate={sample_rate} ! fakesink'.split(),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    if cmd.returncode == 0:
                        sample_rates.append(sample_rate)
            if len(sample_rates) > 0 or with_rates == False:
                devices.update({
                    serial: {
                        'alsa_idx': card_idx,
                        'description': model,
                        'sample_rates': sample_rates,
                    }
                })
    return devices


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


def get_v4l2_settings(device):
    v4l2_options_raw = subprocess.run(
        ('v4l2-ctl', '--device={}'.format(device), '-l'),
        stdout=subprocess.PIPE,
    ).stdout.decode().split('\n')
    v4l2_settings = {}
    for line in v4l2_options_raw:
        elems = line.strip().split(' ')
        v4l2_option = elems[0]
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
        v4l2_options = get_v4l2_settings(device)
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
        for serial, device_info in find_audio_devices(with_rates=False).items():
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
            'menu': 'devices',
        }
        return render_template('devices.html', **model)


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
                if 'YUYV' in encodings:
                    resolutions = list(video_options['YUYV'].keys())
                    if resolution not in resolutions:
                        resolution = resolutions[0]
                        device_config.update({'resolution': resolutions[0]})
                    framerates = video_options['YUYV'][resolution]
                    if str(framerate) not in [str(f) for f in framerates]:
                        framerate = framerates[0]
                        device_config.update({'framerate': framerate})
                if 'H264' in encodings:
                    encoding = 'h264'
                    resolutions = video_options['H264'].keys()
                    framerates = video_options['H264'][resolution]
                elif 'MJPG' in encodings:
                    encoding = 'mjpeg'
                    resolutions = video_options['MJPG'].keys()
                    framerates = video_options['MJPG'][resolution]
                if str(60) in [str(f) for f in framerates]:
                    framerate = 60
                device_config.update({
                    'resolution': resolution,
                    'framerate': framerate,
                    'encoding': encoding,
                })
                v4l2_settings.update({k: v['default'] for k, v in v4l2_options.items()})
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
                    if v4l2_ctl == 'exposure_auto':
                        ctl_val = 3
                    else:
                        ctl_val = 1
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
        sample_rates = []
        for device_serial, device_info in find_audio_devices(with_rates=True).items():
            if device_serial == serial:
                device_config = audio_configs.get(device_serial, {})
                description = device_info['description']
                sample_rates = device_info['sample_rates']
                break
        model = {
            'description': description,
            'serial': serial,
            'audio_device': serial,
            'device_config': device_config,
            'sample_rates': sample_rates,
            'menu': 'devices',
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
