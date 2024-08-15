from flask import current_app as app
from flask import render_template
from flask.views import MethodView

from picam.audio import find_audio_devices
from picam.utils import render_json
from picam.video import find_video_devices
from picam.wifi import get_hostname


def _load_video_devices():
    video_devices = []
    video_configs = app.picam_config.video_devices
    video_device_serials = {}
    for video_device, device_info in find_video_devices().items():
        serial = device_info['serial']
        video_device_serials.update({serial: serial})
        video_devices.append(
            {
                'device': video_device,
                'description': device_info['description'],
                'serial': serial,
                'device_config': video_configs.get(serial, {}),
            }
        )
    return video_devices


def _load_audio_devices():
    audio_devices = []
    audio_configs = app.picam_config.audio_devices
    for serial, device_info in find_audio_devices(with_rates=False).items():
        audio_devices.append(
            {
                'serial': serial,
                'alsa_idx': device_info['alsa_idx'],
                'description': device_info['description'],
                'device_config': audio_configs.get(serial, {}),
            }
        )
    return audio_devices


class DevicesHandler(MethodView):
    """Handles controller logic for listing available devices and returns the
    config settings if available."""

    def get(self):
        model = {
            'video_devices': _load_video_devices(),
            'audio_devices': _load_audio_devices(),
            'hostname': get_hostname(),
            'menu': 'devices',
        }
        return render_template('devices.html', **model)


class DevicesApiHander(MethodView):
    def get(self):
        model = {
            'video_devices': _load_video_devices(),
            'audio_devices': _load_audio_devices(),
            'hostname': get_hostname(),
        }
        return render_json(
            {
                'status': 'ok',
                'data': model,
            }
        )
