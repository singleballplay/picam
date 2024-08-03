#!/usr/bin/env python3

import logging
import subprocess
import yaml
import re
import os

import gi
gi.require_version('Gst','1.0')
gi.require_version('GstVideo','1.0')
gi.require_version('GstRtspServer','1.0')
from gi.repository import GObject, Gst, GstRtspServer

Gst.init(None)
mainloop = GObject.MainLoop()

server = GstRtspServer.RTSPServer()
mounts = server.get_mount_points()

logging.basicConfig(level=logging.INFO)

settings = None
script_dir = os.path.dirname(__file__)
with open(f'{script_dir}/picam.yaml', 'r') as settings_file:
    try:
        settings = yaml.safe_load(settings_file)
    except:
        logging.info('failed to parse settings file')


def adjust_video_settings(device, settings):
    """
    Adjusts the settings for a given webcam

    Args:
        device: the v4l2 device e.g. /dev/video0
        settings: the controls to change
    """
    logging.info('adjusting %s for %s', device, settings)
    result = subprocess.run([
        'v4l2-ctl',
        '-d', device,
        '-c', settings
    ])
    if result.returncode != 0:
        logging.error('non-zero return code changing webcam settings')


def find_audio_devices():
    """
    Look at all of the usb sound devices available and create a dict with the alsa index based
    on the card id found and the serial if available.

    Special cases can be handled here for devices like Snowballs and such that do not have serials
    and only support one of that type connected to the Pi.
    """
    logging.info('finding audio devices available')
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
        if card_idx:
            devices.update({card_idx: serial})
    logging.info(f'found {len(devices.keys())} audio devices')
    return devices


def find_serial(device_name):
    """
    Look for a serial in the info for the device. Not all devices report serials.

    Args:
        device: the v4l2 device e.g. /dev/video0
    """
    cmd1 = subprocess.Popen(
        ('/bin/udevadm', 'info', '--name={}'.format(device_name)),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    cmd2 = subprocess.run(('grep', 'SERIAL_SHORT'), stdin=cmd1.stdout, stdout=subprocess.PIPE)
    if cmd2.returncode == 0:
        return cmd2.stdout.decode().strip().split('\n')[0].split('=')[1]
    else:
        return ''


def find_video_devices():
    """
    fetches devices from v4l2 and creates a dict with the device
    name as the key and the description in value
    """
    logging.info('finding video devices available')
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
        devices.update({
            device: {
                'serial': serial,
                'description': description
            }
        })
        while device != '' and len(video_devices):
            device = video_devices.pop(0)
        if len(video_devices) == 1:
            break
    logging.info(f'found {len(devices.keys())} video devices')
    return devices.items()


def setup_pi_camera_device(video_device):
    """
    Creates a gstreamer pipeline for the built in pi camera module.
    Uses the built in encoder; limited to 60fps.

    Args:
        video_device: the v4l2 device e.g. /dev/video0
    """
    logging.info(f'setting up pi camera module')
    camera_settings = ','.join([
        'rotate=90',
        'iso_sensitivity_auto=0',
        'iso_sensitivity=4',
        'auto_exposure_bias=12',
        'auto_exposure=1',
        'bitrate=10000000'
    ])
    launch=(
        'v4l2src device={} do-timestamp=1 extra-controls="c,{}" '
        '! video/x-h264,width=1280,height=720,framerate=30/1,profile=main'
    ).format(video_device, camera_settings)
    pipeline = '( {} ! h264parse config-interval=2 ! rtph264pay name=pay0 pt=96 )'.format(launch)
    mount_path = '/picam'
    return (pipeline, mount_path)


def setup_uvc_device(serial, video_device, config_options):
    """
    Creates gstreamer pipeline for the video device.

    Args:
        serial: the serial of the device
        video_device: the v4l2 device e.g. /dev/video0
        config_options: the device config options which include the v4l2 configs
    """
    logging.info(f'setting up video device {video_device}')
    # run through all of the options and set the "auto" flags first
    # errors can happen if setting "absolute" values if corresponding "auto" isn't set properly
    if serial not in ['KIYOPRO', 'KIYOPROULTRA']:
        for ctl, val in config_options.get('v4l2', {}).items():
            if ctl.endswith('_auto'):
                adjust_video_settings(video_device, '{}={}'.format(ctl, val))
        for ctl, val in config_options.get('v4l2', {}).items():
            if ctl.endswith('_auto'):
                # we already handled these first
                continue
            if ctl in ('exposure_absolute', 'focus_absolute', 'white_balance_temperature'):
                if ctl == 'exposure_absolute' and config_options['v4l2'].get('auto_exposure', 3) != 1:
                    continue
                if ctl == 'exposure_absolute' and config_options['v4l2'].get('exposure_auto', 3) != 1:
                    continue
                elif ctl == 'focus_absolute' and config_options['v4l2'].get('focus_auto', 0):
                    continue
                elif ctl == 'focus_absolute' and config_options['v4l2'].get('focus_automatic_continuous', 0):
                    continue
                elif ctl == 'white_balance_temperature' and config_options['v4l2'].get('white_balance_temperature_auto', 0):
                    continue
                elif ctl == 'white_balance_temperature' and config_options['v4l2'].get('white_balance_automatic', 0):
                    continue
            adjust_video_settings(video_device, '{}={}'.format(ctl, val))
    framerate = config_options.get('framerate', '30')
    width, height = config_options.get('resolution', '1280x720').split('x')
    launch = 'v4l2src device={} io-mode=4 do-timestamp=1'.format(video_device)
    if config_options['encoding'] == 'h264':
        if serial not in ['KIYOPRO', 'KIYOPROULTRA']:
            # better control over the iframe period, default is way too many seconds
            launch = 'uvch264src device={} initial-bitrate=5000000 average-bitrate=5000000 auto-start=true iframe-period=2000 name=src0 fixed-framerate=true src0.vidsrc'.format(video_device)
    video_format = (
        "video/x-h264,width={},height={},framerate={}/1,profile=main "
        "! h264parse config-interval=1 "
        "! rtph264pay name=pay0 pt=96 "
    ).format(width, height, framerate)
    if config_options['encoding'] == 'mjpeg':
        video_format = (
            "image/jpeg,width={},height={},framerate={}/1 "
            "! queue leaky=downstream "
            "! jpegparse "
            "! rtpjpegpay name=pay0 pt=26 "
        ).format(width, height, framerate)
    elif config_options['encoding'] == 'jpegenc':
        # scale video down to get enough performance out of the software encoder
        # slight quality hit at the expense of latency
        if framerate not in (60, 48, 30, 24):
            # 59.940
            framerate = '7013/117'
        else:
            framerate = f'{framerate}/1'
        video_format = (
            "video/x-raw,width={width},height={height},framerate={framerate} "
            "! videoscale ! video/x-raw,width=1280,height=720 "
            "! queue max-size-buffers=2 leaky=downstream "
            "! jpegenc "
            "! rtpjpegpay name=pay0 pt=96"
        ).format(
            width=width,
            height=height,
            framerate=framerate,
        )
    elif config_options['encoding'] == 'v4l2h264enc':
        keyframe_interval = 2 * framerate
        if framerate not in (60, 48, 30, 24):
            # 59.940
            framerate = '7013/117'
        else:
            framerate = f'{framerate}/1'
        video_format = (
            "video/x-raw,width={width},height={height},framerate={framerate} "
            "! videoscale ! video/x-raw,width=1280,height=720 "
            "! videoconvert ! video/x-raw,format=I420 "
            "! v4l2h264enc extra-controls=encode,h264_level=13,h264_profile=4,video_bitrate=10000000 "
            "! h264parse config-interval=2 "
            "! rtph264pay name=pay0 pt=96 "
        ).format(
            width=width,
            height=height,
            framerate=framerate,
            keyframe_interval=keyframe_interval,
        )
    elif config_options['encoding'] == 'x264enc':
        # scale video down to get enough performance out of the software encoder
        # slight quality hit at the expense of latency
        keyframe_interval = 2 * framerate
        if framerate not in (60, 48, 30, 24):
            # 59.940
            framerate = '7013/117'
        else:
            framerate = f'{framerate}/1'
        video_format = (
            "video/x-raw,width={width},height={height},framerate={framerate} "
            "! videoscale ! video/x-raw,width=1024,height=576 "
            "! videoconvert ! video/x-raw,format=I420 "
            "! queue max-size-buffers=4 leaky=downstream "
            "! x264enc bitrate=5600 speed-preset=superfast tune=zerolatency key-int-max={keyframe_interval} "
            "! video/x-h264,profile=high "
            "! h264parse config-interval=2 "
            "! rtph264pay name=pay0 pt=96 "
        ).format(
            width=width,
            height=height,
            framerate=framerate,
            keyframe_interval=keyframe_interval,
        )
    elif config_options['encoding'] == 'vp8enc':
        keyframe_interval = 2 * framerate
        if framerate not in (60, 48, 30, 24):
            # 59.940
            framerate = '7013/117'
        else:
            framerate = f'{framerate}/1'
        video_format = (
            "video/x-raw,width={width},height={height},framerate={framerate} "
            "! videoscale ! video/x-raw,width=1024,height=576 "
            "! videoconvert ! video/x-raw,width={width},height={height},framerate={framerate},format=I420 "
            "! vp8enc end-usage=cbr deadline=1 threads=8 keyframe-max-dist={keyframe_interval} target-bitrate=4000000 "
            "! rtpvp8pay name=pay0 pt=96 "
        ).format(
            width=width,
            height=height,
            framerate=framerate,
            keyframe_interval=keyframe_interval,
        )
    pipeline = '( {} ! {} )'.format(launch, video_format)
    mount_path = config_options['endpoint']
    return (pipeline, mount_path)


def main():
    # create the camera streams
    video_devices = find_video_devices()
    for video_device, device_info in video_devices:
        pipeline = None
        mount_path = None
        logging.info(device_info['description'])
        if 'bcm2835-v4l2' in device_info['description']:
            pipeline, mount_path = setup_pi_camera_device(video_device)
        elif 'Cam Link' in device_info['description']:
            serial = 'CAMLINK'
            config_options = settings['video_devices'][serial]
            pipeline, mount_path = setup_uvc_device(serial, video_device, config_options)
        elif 'Kiyo Pro Ultra' in device_info['description'] and 'KIYOPROULTRA' in settings['video_devices'].keys():
            serial = 'KIYOPROULTRA'
            config_options = settings['video_devices'][serial]
            pipeline, mount_path = setup_uvc_device(serial, video_device, config_options)
        elif 'Kiyo Pro' in device_info['description'] and 'KIYOPRO' in settings['video_devices'].keys():
            serial = 'KIYOPRO'
            config_options = settings['video_devices'][serial]
            pipeline, mount_path = setup_uvc_device(serial, video_device, config_options)
        elif device_info['serial'] in settings['video_devices'].keys():
            serial = device_info['serial']
            config_options = settings['video_devices'][serial]
            pipeline, mount_path = setup_uvc_device(serial, video_device, config_options)
        if pipeline:
            logging.info(pipeline)
            factory = GstRtspServer.RTSPMediaFactory()
            factory.set_launch(pipeline)
            factory.set_shared(True)
            logging.info(factory.get_protocols())
            mounts.add_factory(mount_path, factory)

    # creates the audio streams
    for alsa_idx, serial in find_audio_devices().items():
        audio_rate = 32000
        audio_path = None
        audio_configs = settings['audio_devices']
        if serial in audio_configs.keys():
            audio_path = audio_configs[serial]['endpoint']
            audio_rate = audio_configs[serial].get('audio_rate', audio_rate)
        if audio_path:
            launch = (
                'alsasrc device=hw:{alsa_idx} do-timestamp=1 '
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


main()
