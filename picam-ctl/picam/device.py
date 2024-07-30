import subprocess

from flask import (
    current_app as app,
    render_template,
)
from flask.views import MethodView

from .audio import find_audio_devices
from .video import find_video_devices


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
        cat_hostname = subprocess.run(
            ('cat', '/etc/hostname'),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        hostname = cat_hostname.stdout.decode().strip()
        model = {
            'video_devices': video_devices,
            'audio_devices': audio_devices,
            'hostname': hostname,
            'menu': 'devices',
        }
        return render_template('devices.html', **model)
