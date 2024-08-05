from flask import (
    current_app as app,
    render_template,
)
from flask.views import MethodView

from picam.audio import (
    find_audio_devices,
)
from picam.video import (
    find_video_devices,
    get_device_settings,
)


class IndexHandler(MethodView):
    """Dashboard for realtime adjustments of configure devices."""

    def get(self):
        video_devices = {}
        video_configs = app.picam_config.video_devices
        for video_device, device_info in find_video_devices().items():
            serial = device_info['serial']
            device_settings = get_device_settings(video_device)
            if serial in video_configs.keys():
                camera_path = video_configs[serial]['endpoint']
                device_settings.update(
                    {
                        'path': camera_path,
                        'device': video_device,
                        'type': video_configs[serial]['type'],
                        'v4l2_options': device_info['v4l2_options'],
                    }
                )
                video_devices.update({serial: device_settings})

        audio_devices = {}
        audio_configs = app.picam_config.audio_devices
        for serial, device_info in find_audio_devices().items():
            if serial in audio_configs.keys():
                audio_path = audio_configs[serial]['endpoint']
                device_settings = {
                    'path': audio_path,
                    'alsa_idx': device_info['alsa_idx'],
                    'description': device_info['description'],
                    'device_config': audio_configs.get(serial, {}),
                    'rec_level': device_info['rec_level'],
                }
                audio_devices.update({serial: device_settings})

        model = {
            'video_devices': video_devices,
            'audio_devices': audio_devices,
            'menu': 'index',
        }

        return render_template('index.html', **model)
