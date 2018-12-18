#!/usr/bin/env python3

import logging
import subprocess
import yaml
import re
import gi
gi.require_version('Gst','1.0')
gi.require_version('GstVideo','1.0')
gi.require_version('GstRtspServer','1.0')
from gi.repository import GObject, Gst, GstRtspServer
Gst.init(None)
mainloop = GObject.MainLoop()
server = GstRtspServer.RTSPServer()
mounts = server.get_mount_points()

def adjust_video_settings(device, settings):
    """
    Adjusts the settings for a given webcam

    Args:
        device: the v4l2 device e.g. /dev/video0
        settings: the controls to change
    """
    result = subprocess.run([
        'v4l2-ctl',
        '-d', device,
        '-c', settings
    ])
    if result.returncode != 0:
        logging.error('non-zero return code changing webcam settings')

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

def find_serial(device_name):
    cmd1 = subprocess.Popen(('/bin/udevadm', 'info', '--name={}'.format(device_name)), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    cmd2 = subprocess.run(('grep', 'SERIAL_SHORT'), stdin=cmd1.stdout, stdout=subprocess.PIPE)
    if cmd2.returncode == 0:
        return cmd2.stdout.decode().strip().split('\n')[0].split('=')[1]
    else:
        return ''

settings = None
with open('/opt/picam.yaml', 'r') as settings_file:
    try:
        settings = yaml.safe_load(settings_file)
    except:
        print('failed to parse settings file')

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

# create the camera streams
for video_device, description in find_video_devices():
    if 'bcm2835-v4l2' in description:
        camera_settings = ','.join([
            'rotate=90',
            'iso_sensitivity_auto=0',
            'iso_sensitivity=4',
            'auto_exposure_bias=12',
            'auto_exposure=1',
            'bitrate=10000000'
        ])
        launch=(
            'v4l2src device={} extra-controls="c,{}" '
            '! video/x-h264,width=1280,height=720,framerate=30/1,profile=main'
        ).format(camera_settings, video_device)
        pipeline = '( {} ! h264parse config-interval=2 ! rtph264pay name=pay0 pt=96 )'.format(launch)
        factory = GstRtspServer.RTSPMediaFactory()
        factory.set_launch(pipeline)
        factory.set_shared(True)
        mounts.add_factory('/picam', factory)
    elif 'Cam Link' in description:
        if 'CAMLINK' in settings['video_devices']:
            config_options = settings['video_devices']['CAMLINK']
        else:
            logging.info('camlink not configured')
            continue
        launch = 'v4l2src do-timestamp=true device={}'.format(video_device)
        framerate = config_options.get('framerate', '60')
        width, height = config_options.get('resolution', '1280x720').split('x')
        video_format = (
            "video/x-raw,width={},height={} "
            "! videoscale ! video/x-raw,width=1024,height=576 "
            "! x264enc speed-preset=superfast tune=zerolatency bitrate=5600 key-int-max=120 "
            "! h264parse config-interval=2 "
            "! rtph264pay name=pay0 pt=96"
        ).format(width, height, framerate)
        pipeline = '( {} ! {} )'.format(launch, video_format)
        factory = GstRtspServer.RTSPMediaFactory()
        factory.set_launch(pipeline)
        factory.set_shared(True)
        camera_path = config_options['endpoint']
        mounts.add_factory(camera_path, factory)
    elif 'C920' in description or 'C922' in description or 'BRIO' in description:
        serial = str(find_serial(video_device))
        if serial in settings['video_devices'].keys():
            config_options = settings['video_devices'][serial]
        else:
            logging.info('unknown camera')
            continue
        v4l2_options = {
            'focus_auto': 0,
            'focus_absolute': 0,
            'exposure_auto_priority': 0,
            'exposure_auto': 1,
            'exposure_absolute': 100,
            'brightness': 128,
            'contrast': 128,
            'saturation': 128,
            'sharpness': 128,
            'gain': 96,
            'backlight_compensation': 0,
            'white_balance_temperature_auto': 0,
            'white_balance_temperature': 4400,
            'pan_absolute': 0,
            'tilt_absolute': 0,
            'zoom_absolute': 100
        }
        if 'v4l2' in config_options.keys():
            for k, v in config_options['v4l2'].items():
                v4l2_options.update({k: v})
        camera_settings = ','.join(['{}={}'.format(k, v) for k, v in v4l2_options.items()])
        # tried setting them all at once, but that seems to fail often
        for k, v in v4l2_options.items():
            adjust_video_settings(video_device, '{}={}'.format(k, v))
        launch = 'v4l2src device={}'.format(video_device)
        framerate = config_options.get('framerate', '30')
        width, height = config_options.get('resolution', '1280x720').split('x')
        video_format = (
            "video/x-h264,width={},height={},framerate={}/1,profile=high "
            "! h264parse config-interval=2 "
            "! rtph264pay name=pay0 pt=96 "
        ).format(width, height, framerate)
        if config_options['type'] in ['C922', 'BRIO']:
            if config_options['encoding'] == 'h264':
                keyframe_interval = 2 * framerate
                video_format = (
                    "image/jpeg,width={},height={},framerate={}/1 "
                    "! jpegdec "
                    "! videoscale ! video/x-raw,width=1024,height=576 "
                    "! x264enc bitrate=5600 speed-preset=superfast tune=zerolatency key-int-max={} "
                    "! video/x-h264,profile=high "
                    "! h264parse config-interval=2 "
                    "! rtph264pay name=pay0 pt=96 "
                ).format(width, height, framerate, keyframe_interval)
            if config_options['encoding'] == 'vp8':
                keyframe_interval = 2 * framerate
                video_format = (
                    "image/jpeg,width={},height={},framerate={}/1 "
                    "! jpegdec "
                    "! videoscale ! video/x-raw,width=1024,height=576 "
                    "! vp8enc end-usage=cbr deadline=1 threads=8 keyframe-max-dist={} target-bitrate=4000000 "
                    "! rtpvp8pay name=pay0 pt=96 "
                ).format(width, height, framerate, keyframe_interval)
        if config_options['encoding'] == 'mjpeg':
            video_format = (
                "image/jpeg,width={},height={},framerate={}/1 "
                "! rtpjpegpay name=pay0 pt=26 "
            ).format(width, height, framerate)
        pipeline = '( {} ! {} )'.format(launch, video_format)
        factory = GstRtspServer.RTSPMediaFactory()
        factory.set_launch(pipeline)
        factory.set_shared(True)
        camera_path = config_options['endpoint']
        mounts.add_factory(camera_path, factory)

# creates the audio streams
c920_idx = 0
for alsa_idx, description in find_audio_devices():
    if 'C920' in description:
        for video_device, video_description in find_video_devices():
            s = re.search(r'\(.*\)', video_description)
            if s.group(0)[1:-1] in description:
                serial = find_serial(video_device)
                if serial in settings['video_devices']:
                    camera_path = settings['video_devices'][serial]['endpoint']
                else:
                    c920_idx += 1
                    camera_path = '/c920-{}'.format(c920_idx)
                audio_path = '{}-audio'.format(camera_path)
    elif 'Snowball' in description:
        audio_path = '/snowball-audio'
    else:
        continue
    launch = 'alsasrc device=hw:{} ! queue ! voaacenc ! rtpmp4apay name=pay0 pt=96'.format(alsa_idx)
    pipeline = '( {} )'.format(launch)
    factory = GstRtspServer.RTSPMediaFactory()
    factory.set_launch(pipeline)
    factory.set_shared(True)
    mounts.add_factory(audio_path, factory)

server.attach(None)
mainloop.run()
