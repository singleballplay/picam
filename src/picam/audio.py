import subprocess
import json
import re

from flask import (
    current_app as app,
    request,
    redirect,
    render_template,
)
from flask.views import MethodView


def render_json(json_data):
    resp = app.make_response(json.dumps(json_data))
    resp.headers['Content-type'] = 'application/json'
    return resp


def get_current_recording_level(card_idx):
    cmd = subprocess.run(
        ('amixer', '-c', card_idx, 'sget', 'Mic'),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    rec_level = '0'
    if cmd.returncode == 0:
        for line in cmd.stdout.decode().strip().split('\n'):
            if line.strip().startswith('Mono:'):
                matches = re.findall(r'(-?\d+)%', line)
                rec_level = matches[0] if matches else '0'
    return rec_level


def adjust_audio_volume(card_idx, level):
    """Use amixer to change the volumne level of the audio device

    Args:
        card_idx: the alsa device id e.g. 0 for /proc/asound/card0
        level: the volume level for the device in percentage
    """
    subprocess.run(
        ('amixer', '-c', card_idx, 'set', 'Mic', f'{level}%'),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )


def get_asound_devices(recordable_devices):
    cmd1 = subprocess.run(
        ('cat', '/proc/asound/cards'),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    device_list = cmd1.stdout.decode().strip().split('\n')
    audio_devices = [d.strip() for d in device_list if d]
    devices = {}
    idx = 0
    while idx < len(audio_devices):
        alsa_idx = audio_devices[idx].split(' ')[0]
        if alsa_idx in recordable_devices.keys():
            devices.update({alsa_idx: audio_devices[idx + 1]})
        idx += 2
    return devices


def get_recordable_devices():
    cmd1 = subprocess.run(
        ('arecord', '--list-devices'),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
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


def find_audio_devices(with_rates=False):  # pylint: disable=too-many-locals
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
    card_idx_pattern = re.compile(r'/sound/card(\d+)/')
    for usb_device in usb_devices:
        serial = None
        card_idx = None
        model = ''
        cmd1 = subprocess.run(
            ('/bin/udevadm', 'info', f'--name=/dev/snd/by-id/{usb_device}'),
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
                    # test available audio rates checking with caps from gstreamer
                    pipeline = (
                        'gst-launch-1.0 alsasrc device=hw:{card_idx} num-buffers=10 '
                        '! audio/x-raw,rate={sample_rate} '
                        '! fakesink'
                    ).format(card_idx=card_idx, sample_rate=sample_rate)
                    cmd = subprocess.run(
                        pipeline.split(),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    if cmd.returncode == 0:
                        sample_rates.append(sample_rate)
            rec_level = get_current_recording_level(card_idx)
            devices.update(
                {
                    serial: {
                        'alsa_idx': card_idx,
                        'description': model,
                        'rec_level': rec_level,
                        'sample_rates': sample_rates,
                    }
                }
            )
    return devices


class AudioDeviceHandler(MethodView):
    def get(self, serial):
        audio_configs = app.picam_config.audio_devices
        audio_devices = find_audio_devices(with_rates=True)
        device_info = audio_devices.get(serial)
        device_config = audio_configs.get(serial, {})
        device_config.update({'rec_level': device_info['rec_level']})
        model = {
            'alsa_idx': device_info['alsa_idx'],
            'description': device_info['description'],
            'serial': serial,
            'audio_device': serial,
            'rec_level': device_info['rec_level'],
            'device_config': device_config,
            'sample_rates': device_info['sample_rates'],
            'menu': 'devices',
        }
        return render_template('config_audio_device.html', **model)

    def post(self, serial):
        if request.form.get('delete', None):
            del app.picam_config.audio_devices[serial]
            return redirect('/devices')

        if not app.picam_config.audio_devices.get(serial):
            app.picam_config.audio_devices[serial] = {}

        endpoint_url = request.form.get(f'{serial}-endpoint')
        if endpoint_url and not endpoint_url.startswith('/'):
            endpoint_url = '/' + endpoint_url
        app.picam_config.audio_devices[serial]['endpoint'] = endpoint_url

        audio_rate = request.form.get(f'{serial}-audio_rate')
        if audio_rate:
            app.picam_config.audio_devices[serial]['audio_rate'] = int(audio_rate)

        rec_level = request.form.get('{}-rec_level'.format(serial))
        if rec_level:
            alsa_idx = request.form.get('{}-alsa_idx'.format(serial))
            adjust_audio_volume(str(alsa_idx), str(rec_level))
            app.picam_config.audio_devices[serial]['rec_level'] = int(rec_level)

        for config_option in ['type']:
            app.picam_config.audio_devices[serial][config_option] = request.form.get(
                '{}-{}'.format(serial, config_option)
            )

        return redirect('/devices')

    def delete(self, serial):
        del app.picam_config.video_devices[serial]
        return redirect('/devices')


class AudioDeviceApiHandler(MethodView):
    def post(self, serial):
        app.logger('updating audio level for %s', serial)
        data = request.json
        adjust_audio_volume(data['alsa_idx'], data['rec_level'])
        return render_json({'status': 'ok'})
