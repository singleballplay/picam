#!/usr/bin/env python3
import logging
import yaml

from flask import Flask

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.secret_key = 'picamsecret'


class PicamConfig:
    """
    Holds Picam configuration structure
    """

    def __init__(self, *args, **kwargs):
        self.load_config()

    def load_config(self):
        with open('/home/pi/picam/picam.yaml', 'r') as settings_file:
            try:
                settings = yaml.safe_load(settings_file)
                self.video_devices = settings['video_devices']
                self.audio_devices = settings['audio_devices']
            except:
                logging.error('failed to parse settings file')

    def write_config(self):
        data = dict(
            video_devices=self.video_devices,
            audio_devices=self.audio_devices,
        )
        with open('/home/pi/picam/picam.yaml', 'w') as settings_file:
            yaml.dump(data, settings_file, default_flow_style=False)


app.picam_config = PicamConfig()

from picam import (
    index,
    admin,
    device,
    wifi,
)

app.add_url_rule(
    '/', view_func=index.IndexHandler.as_view('index')
)
app.add_url_rule(
    '/admin', view_func=admin.AdminHandler.as_view('admin')
)
app.add_url_rule(
    '/wifi', view_func=wifi.WifiHandler.as_view('wifi')
)
app.add_url_rule(
    '/devices', view_func=device.DevicesHandler.as_view('devices')
)
app.add_url_rule(
    '/config-video-device/<serial>',
    view_func=device.VideoDeviceHandler.as_view('config-video-device'),
    methods=['GET', 'POST', 'DELETE',]
)
app.add_url_rule(
    '/config-audio-device/<serial>',
    view_func=device.AudioDeviceHandler.as_view('config-audio-device'),
    methods=['GET', 'POST', 'DELETE',]
)
app.add_url_rule(
    '/api/video-device/<serial>',
    view_func=device.VideoDeviceApiHandler.as_view('api-video-device'),
    methods=['POST']
)
app.add_url_rule(
    '/scaling-governor',
    view_func=admin.ScalingGovernorHandler.as_view('scaling-governor')
)
app.add_url_rule(
    '/reboot',
    view_func=admin.RebootHandler.as_view('reboot')
)
app.add_url_rule(
    '/shutdown',
    view_func=admin.ShutdownHandler.as_view('shutdown')
)
app.add_url_rule(
    '/write-config',
    view_func=admin.WriteConfigHandler.as_view('write-config')
)
app.add_url_rule(
    '/reload-config',
    view_func=admin.ReloadConfigHandler.as_view('reload-config')
)
app.add_url_rule(
    '/download-config',
    view_func=admin.DownloadConfigHandler.as_view('download-config')
)
app.add_url_rule(
    '/restart-picam',
    view_func=admin.RestartPicamHandler.as_view('restart-picam')
)
app.add_url_rule(
    '/update-picam',
    view_func=admin.UpdatePicamHandler.as_view('update-picam')
)
app.add_url_rule(
    '/hdmi',
    view_func=admin.HdmiHandler.as_view('hdmi')
)
app.add_url_rule(
    '/wifi-power',
    view_func=admin.WifiPowerHandler.as_view('wifi-power')
)

if __name__ == '__main__':
    app.run(host='0.0.0.0', threaded=True)
