#!/usr/bin/env python3
import subprocess
import gi
gi.require_version('Gst','1.0')
gi.require_version('GstVideo','1.0')
gi.require_version('GstRtspServer','1.0')
from gi.repository import GObject, Gst, GstRtspServer
Gst.init(None)
mainloop = GObject.MainLoop()
server = GstRtspServer.RTSPServer()
mounts = server.get_mount_points()

# fetch the devices from v4l2
video_devices = [d.strip() for d in subprocess.run(["v4l2-ctl", "--list-devices"], stdout=subprocess.PIPE).stdout.decode().split('\n') if d]
devices = {}
idx = 0
while idx < len(video_devices):
    devices.update({video_devices[idx]: video_devices[idx + 1]})
    idx += 2

# create the camera streams
# assumes one of each camera possibly
c920_idx = 0
for k, v in devices.items():
    cam_device = v
    if 'bcm2835-v4l2' in k:
        launch=(
            'v4l2src device={} extra-controls="c,rotate=90,iso_sensitivity_auto=0,iso_sensitivity=4,auto_exposure_bias=12,auto_exposure=1,bitrate=10000000" '
            '! video/x-h264,width=1280,height=720,framerate=30/1,profile=main'
        ).format(cam_device)
        pipeline = '( {} ! h264parse config-interval=2 ! rtph264pay name=pay0 pt=96 )'.format(launch)
        factory = GstRtspServer.RTSPMediaFactory()
        factory.set_launch(pipeline)
        factory.set_shared(True)
        mounts.add_factory('/picam', factory)
    else:
        c920_idx += 1
        launch = 'v4l2src device={} extra-controls="c,focus_auto=0,exposure_auto_priority=0,exposure_auto=1,exposure_absolute=400,gain=96,saturation=128,contrast=128,brightness=128"'.format(cam_device)
        pipeline = '( {} ! h264parse config-interval=2 ! video/x-h264,width=1280,height=720,framerate=30/1,profile=main ! rtph264pay name=pay0 pt=96 )'.format(launch)
        factory = GstRtspServer.RTSPMediaFactory()
        factory.set_launch(pipeline)
        factory.set_shared(True)
        mounts.add_factory('/c920-{}'.format(c920_idx), factory)

server.attach(None)
mainloop.run()
