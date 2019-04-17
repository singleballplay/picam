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

from picam.device import (
    find_video_devices,
    find_audio_devices,
    get_device_settings,
)


class IndexHandler(MethodView):
    def get(self):
        video_devices = {}
        video_configs = app.picam_config.video_devices
        audio_configs = app.picam_config.audio_devices
        for device_serial, device_info in find_video_devices().items():
            serial = device_info['serial']
            device_settings = get_device_settings(device_serial)
            if serial in video_configs.keys():
                camera_path = video_configs[serial]['endpoint']
                device_settings.update({
                    'path': camera_path,
                    'device': device_serial,
                })
                video_devices.update({serial: device_settings})
        audio_devices = {}
        model = {
            'video_devices': video_devices,
            'audio_devices': audio_devices
        }
        return render_template('index.html', **model)
