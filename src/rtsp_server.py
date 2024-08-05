#!/usr/bin/env python3

import logging
import subprocess
import os

import gi
import yaml

from picam import (
    audio,
    video,
)

gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
gi.require_version('GstRtspServer', '1.0')

# pylint: disable=wrong-import-position,wrong-import-order
from gi.repository import (
    GLib,
    Gst,
    GstRtspServer,
)

Gst.init(None)
mainloop = GLib.MainLoop()

server = GstRtspServer.RTSPServer()
mounts = server.get_mount_points()

logging.basicConfig(level=logging.INFO)


def load_configs():
    configs = None
    script_dir = os.path.dirname(__file__)
    with open(f'{script_dir}/picam.yaml', 'r', encoding='UTF-8') as settings_file:
        try:
            configs = yaml.safe_load(settings_file)
        except Exception:  # pylint: disable=broad-exception-caught
            logging.info('failed to parse settings file')
    return configs


def adjust_video_settings(device, settings):
    """
    Adjusts the settings for a given webcam

    Args:
        device: the v4l2 device e.g. /dev/video0
        settings: the controls to change
    """
    logging.info('adjusting %s for %s', device, settings)
    result = subprocess.run(
        [
            'v4l2-ctl',
            '-d',
            device,
            '-c',
            settings,
        ],
    )
    if result.returncode != 0:
        logging.error('non-zero return code changing webcam settings')


def setup_pi_camera_device(video_device):
    """
    Creates a gstreamer pipeline for the built in pi camera module.
    Uses the built in encoder; limited to 60fps.

    Args:
        video_device: the v4l2 device e.g. /dev/video0
    """
    logging.info('setting up pi camera module')
    camera_settings = ','.join(
        [
            'rotate=90',
            'iso_sensitivity_auto=0',
            'iso_sensitivity=4',
            'auto_exposure_bias=12',
            'auto_exposure=1',
            'bitrate=10000000',
        ]
    )
    launch = (
        'v4l2src device={} do-timestamp=1 extra-controls="c,{}" '
        '! video/x-h264,width=1280,height=720,framerate=30/1,profile=main'
    ).format(video_device, camera_settings)
    pipeline = '( {} ! h264parse config-interval=2 ! rtph264pay name=pay0 pt=96 )'.format(launch)
    mount_path = '/picam'
    return (pipeline, mount_path)


def set_v4l2_controls(video_device, v4l2_options):
    # run through all of the options and set the "auto" flags first
    # errors can happen if setting "absolute" values if corresponding "auto" isn't set properly
    for ctl, val in v4l2_options.items():
        if ctl.endswith('_auto'):
            adjust_video_settings(video_device, '{}={}'.format(ctl, val))
    for ctl, val in v4l2_options.items():
        if ctl.endswith('_auto'):
            # we already handled these first
            continue

        if ctl == 'exposure_absolute' and (
            v4l2_options.get('auto_exposure', 3) != 1 or v4l2_options.get('exposure_auto', 3) != 1
        ):
            continue

        if ctl == 'focus_absolute' and (
            v4l2_options.get('focus_auto', 0) or v4l2_options.get('focus_automatic_continuous', 0)
        ):
            continue

        if ctl == 'white_balance_temperature' and (
            v4l2_options.get('white_balance_temperature_auto', 0)
            or v4l2_options.get('white_balance_automatic', 0)
        ):
            continue

        adjust_video_settings(video_device, '{}={}'.format(ctl, val))


def setup_vp8enc_pipeline(width, height, framerate):
    keyframe_interval = 2 * framerate
    return (
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


def setup_mjpeg_pipeline(width, height, framerate):
    return (
        "image/jpeg,width={},height={},framerate={}/1 "
        "! queue leaky=downstream "
        "! jpegparse "
        "! rtpjpegpay name=pay0 pt=26 "
    ).format(width, height, framerate)


def setup_x264enc_pipeline(width, height, framerate):
    # scale video down to get enough performance out of the software encoder
    # slight quality hit at the expense of latency
    keyframe_interval = 2 * framerate
    return (
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


def setup_jpegenc_pipeline(width, height, framerate):
    # scale video down to get enough performance out of the software encoder
    # slight quality hit at the expense of latency
    return (
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


def setup_v4l2h264enc_pipeline(width, height, framerate):
    return (
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
    )


def setup_uvc_device(serial, video_device, config_options):
    """
    Creates gstreamer pipeline for the video device.

    Args:
        serial: the serial of the device
        video_device: the v4l2 device e.g. /dev/video0
        config_options: the device config options which include the v4l2 configs
    """
    logging.info('setting up video device %s', video_device)

    if serial not in ['KIYOPRO', 'KIYOPROULTRA']:
        # kiyo webcams maintain configurations so don't require presetting each time
        set_v4l2_controls(
            video_device,
            config_options.get('v4l2', {}),
        )

    framerate = config_options.get('framerate', '30')
    if framerate not in (60, 48, 30, 24):
        # 59.940
        framerate = '7013/117'
    else:
        framerate = f'{framerate}/1'

    width, height = config_options.get('resolution', '1280x720').split('x')

    launch = 'v4l2src device={} io-mode=4 do-timestamp=1'.format(video_device)

    # default to the built-in h264 encoding if possible
    encoding = config_options['encoding']
    if encoding == 'h264':
        if serial not in ['KIYOPRO', 'KIYOPROULTRA']:
            # better control over the iframe period, default is way too many seconds
            # kiyos do not support the module unfortunately but do better anyways
            # pylint: disable=line-too-long
            launch = 'uvch264src device={} initial-bitrate=5000000 average-bitrate=5000000 auto-start=true iframe-period=2000 name=src0 fixed-framerate=true src0.vidsrc'.format(
                video_device
            )
    video_format = (
        "video/x-h264,width={},height={},framerate={}/1,profile=main "
        "! h264parse config-interval=1 "
        "! rtph264pay name=pay0 pt=96 "
    ).format(width, height, framerate)

    if encoding == 'mjpeg':
        video_format = setup_mjpeg_pipeline(width, height, framerate)
    elif encoding == 'jpegenc':
        video_format = setup_jpegenc_pipeline(width, height, framerate)
    elif encoding == 'v4l2h264enc':
        video_format = setup_v4l2h264enc_pipeline(width, height, framerate)
    elif encoding == 'x264enc':
        video_format = setup_x264enc_pipeline(width, height, framerate)
    elif encoding == 'vp8enc':
        video_format = setup_vp8enc_pipeline(width, height, framerate)

    pipeline = '( {} ! {} )'.format(launch, video_format)
    mount_path = config_options['endpoint']
    return (pipeline, mount_path)


def main():
    configs = load_configs()

    # create the camera streams
    for video_device, device_info in video.find_video_devices().items():
        pipeline = None
        mount_path = None
        logging.info(device_info['description'])
        if 'bcm2835-v4l2' in device_info['description']:
            pipeline, mount_path = setup_pi_camera_device(video_device)
        elif 'Cam Link' in device_info['description']:
            serial = 'CAMLINK'
            config_options = configs['video_devices'][serial]
            pipeline, mount_path = setup_uvc_device(serial, video_device, config_options)
        elif (
            'Kiyo Pro Ultra' in device_info['description']
            and 'KIYOPROULTRA' in configs['video_devices'].keys()
        ):
            serial = 'KIYOPROULTRA'
            config_options = configs['video_devices'][serial]
            pipeline, mount_path = setup_uvc_device(serial, video_device, config_options)
        elif (
            'Kiyo Pro' in device_info['description']
            and 'KIYOPRO' in configs['video_devices'].keys()
        ):
            serial = 'KIYOPRO'
            config_options = configs['video_devices'][serial]
            pipeline, mount_path = setup_uvc_device(serial, video_device, config_options)
        elif device_info['serial'] in configs['video_devices'].keys():
            serial = device_info['serial']
            config_options = configs['video_devices'][serial]
            pipeline, mount_path = setup_uvc_device(serial, video_device, config_options)
        if pipeline:
            logging.info(pipeline)
            factory = GstRtspServer.RTSPMediaFactory()
            factory.set_launch(pipeline)
            factory.set_shared(True)
            mounts.add_factory(mount_path, factory)

    # creates the audio streams
    for alsa_idx, serial in audio.find_audio_devices().items():
        audio_rate = 32000
        audio_path = None
        audio_configs = configs['audio_devices']
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
