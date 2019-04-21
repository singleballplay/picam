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
with open('/home/pi/picam/picam.yaml', 'r') as settings_file:
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
        description = video_devices[idx]
        device = video_devices[idx + 1]
        serial = find_serial(device)
        devices.update({
            device: {
                'serial': serial,
                'description': description
            }
        })
        idx += 2
    return devices.items()


def setup_pi_camera_device():
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
    mount_path = '/picam'
    return (pipeline, mount_path)


def setup_camlink_device():
    if 'CAMLINK' in settings['video_devices']:
        config_options = settings['video_devices']['CAMLINK']
    else:
        logging.info('camlink not configured')
        return (None, None)
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
    mount_path = config_options['endpoint']
    return (pipeline, mount_path)


def setup_logitech_device(serial):
    config_options = settings['video_devices'][serial]
    v4l2_options = {
        'focus_auto': 0,
        'focus_absolute': 0,
        'exposure_auto': 1,
        'exposure_auto_priority': 0,
        'exposure_absolute': 200,
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
        'zoom_absolute': 100,
    }
    v4l2_ctls = [
        'focus_auto',
        'focus_absolute',
        'exposure_auto',
        'exposure_auto_priority',
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
        'zoom_absolute',
    ]
    if 'v4l2' in config_options.keys():
        for k, v in config_options['v4l2'].items():
            v4l2_options.update({k: v})
    #camera_settings = ','.join(['{}={}'.format(k, v) for k, v in v4l2_options.items()])
    # tried setting them all at once, but that seems to fail often, do them
    # in a specific order?
    for ctl in v4l2_ctls:
        adjust_video_settings(video_device, '{}={}'.format(ctl, v4l2_options[ctl]))
    launch = 'v4l2src device={}'.format(video_device)
    framerate = config_options.get('framerate', '30')
    width, height = config_options.get('resolution', '1280x720').split('x')
    video_format = (
        "video/x-h264,width={},height={},framerate={}/1,profile=high "
        "! h264parse config-interval=2 "
        "! rtph264pay name=pay0 pt=96 "
    ).format(width, height, framerate)
    if config_options['type'] in ['C922', 'BRIO']:
        if config_options['encoding'] == 'x264enc':
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
        if config_options['encoding'] == 'vp8enc':
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
    mount_path = config_options['endpoint']
    return (pipeline, mount_path)


# create the camera streams
video_devices = find_video_devices()
for video_device, device_info in video_devices:
    pipeline = None
    mount_path = None
    if 'bcm2835-v4l2' in device_info['description']:
        pipeline, mount_path = setup_pi_camera_device()
    elif 'Cam Link' in device_info['description']:
        pipeline, mount_path = setup_camlink_device()
    elif device_info['serial'] in settings['video_devices'].keys():
        pipeline, mount_path = setup_logitech_device(device_info['serial'])
    if pipeline:
        factory = GstRtspServer.RTSPMediaFactory()
        factory.set_launch(pipeline)
        factory.set_shared(True)
        mounts.add_factory(mount_path, factory)

# creates the audio streams
for alsa_idx, description in find_audio_devices():
    audio_rate = 32000
    audio_path = None
    audio_configs = settings['audio_devices']
    if 'Snowball' in description:
        audio_path = '/snowball-audio'
        audio_rate = 48000
    else:
        for video_device, device_info in video_devices:
            s = re.search(r'(usb[^\)]+)', device_info['description'])
            if s.group(0) in description:
                serial = device_info['serial']
                if serial in audio_configs.keys():
                    audio_path = audio_configs[serial]['endpoint']
                    audio_rate = audio_configs[serial].get('audio_rate', audio_rate)
                    break
    if audio_path:
        launch = (
            'alsasrc device=hw:{alsa_idx} '
            '! audio/x-raw,rate={audio_rate} '
            '! queue ! voaacenc bitrate=160000 '
            '! rtpmp4apay name=pay0 pt=96'
        ).format(
            alsa_idx=alsa_idx,
            audio_rate=audio_rate,
        )
        pipeline = '( {} )'.format(launch)
        factory = GstRtspServer.RTSPMediaFactory()
        factory.set_launch(pipeline)
        factory.set_shared(True)
        mounts.add_factory(audio_path, factory)

server.attach(None)
mainloop.run()
