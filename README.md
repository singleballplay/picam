# Installing Raspbian

Grab the latest Raspbian "lite" image from https://www.raspberrypi.org/downloads/raspbian/. At the moment the current version is 2018-11-13-raspbian-stretch-lite.zip. Unzip it locally so you have access to the .img file. Follow the instructions on the Raspberry Pi website to format the disk with the image so you have a fresh operating system.

The following commands all assume a Linux operating system is being used. If you are on Windows you may need to adjust some of the commands. Feel free to use an editor of your choice instead of vi as well if you aren't familiar with it.

Remount the micro sd card and make the following changes (your path may be different to the boot and rootfs directories). I use Vi as the editor but you can use whatever editor you feel comfortable with. Using nano anywhere you see vi might be a bit easier if you aren't familiar with the program.

- On your host machine create an empty ssh file in the boot partition to enable ssh access to the pi. You should see two paritions rootfs and boot.

    ```
    $ cd /var/host/media/removeable/boot
    $ touch ssh
    ```

- Also change the hostname to something unique for your network. If your only pi is this one feel free to leave it as 'raspberry' but you probably want to change it. Be careful to edit the relative path etc/ files not your local machine's.

    ```
    $ cd /var/host/media/removeable/rootfs
    $ sudo vi etc/hostname
    $ sudo vi etc/hosts
    ```

- Add your wifi credentials in the wpa_supplicant file.

    ```
    $ sudo vi etc/wpa_supplicant/wpa_supplication.conf
    ```

- Add a block like this:

    ```
    network={
        ssid="network_ssid_here"
        psk="wifi_password_here"
    }
    ```

Now go ahead and put the sd card in the pi and power it on. Use an SSH connection to setup things after the pi is running. The default username is probably pi and the password is probably raspberry, you probably will want to change that. You can also connect the Pi to a monitor and keyboard and login normally when it boots up.

    $ ssh pi@yourhostnamehere

Change the Localisation Options to your locale if you're not in GB. Go to the 'Interfacing Options and enable the camera module. Go to 'Advanced Options and expand the filesystem.

    $ sudo raspi-config

That's it for the basic Raspbian setup you'll need. You might also want too change the password to which you can do in raspi-config as well.

# Installing The Software

At this point you'll need to SSH into the Raspberry Pi, or you can hook your Pi up to a monitor and keyboard and login with that.

Clone the latest version of the code here: https://gitlab.com/singleballplay/picam. You might need to install git first.

    $ sudo apt -y install git
    $ git clone https://gitlab.com/singleballplay/picam.git
    $ cd picam

There is a picam.yaml.example file you can copy and name picam.yaml, then add your configuration to it. Replace the spots for the serial numbers with the serials numbers for your camera(s) (directions below).

    $ cp picam.yaml.example picam.yaml

Once you have your configuration ready, run the setup script and you should be good to go. It will probably take a bit to upgrade everything so be patient. Reboot afterwards and you should have the stream(s) available to test. If you need edit the configuration file, you can run the setup again at a later time.

    $ ./setup
    $ sudo shutdown -r now

## Listing Video Devices

To list all of the video devices run the following command and grab the /dev/video0 or other path and enter it in the next command to find the serial number for each camera you want to use.

    $ v4l2-ctl --list-devices

## Finding Webcam Serial

To find the serial number for your video device, run the following command with the path to the device you want to find information about. Unfortunately there's no good way to know which one is which if you have multiple of the same camera so do this for each one and then adjust the configuration endpoint after you know which one is which.

    $ /bin/udevadm info --name=/dev/video0 | grep SERIAL_SHORT

Add that to the configuration file and edit the endpoint if you want something else. Make sure it starts with a / and doesn't have any spaces in it.

## Accessing The Stream

You should be good to go now. The service will run after the device powers up and use whatever cameras are available and should be accessible by the appropriate uri: rtsp://hostname:8554/playfield or rtsp://hostname:8554/backglass, etc. based on how you configured them.

To test the stream on another computer you can run the following gstreamer pipeline and it should display the video:

For H.264 encoding:

    $ gst-launch-1.0 rtspsrc location=rtsp://hostname:8554/playfield latency=100 ! rtph264depay ! queue ! avdec_h264 ! autovideosink

For MJPEG encoding:

    $ gst-launch-1.0 rtspsrc location=rtsp://hostname:8554/playfield latency=100 ! rtpjpegdepay ! queue ! jpegdec ! autovideosink

To add them as sources in OBS, add a new VLC Video Source. Uncheck all of the boxes and leave the stop when not visisble selected in the drop down. The cameras will turn off when not being viewed which saves on power if running on battery. Add a Path/URL to the playlist section and type in the RTSP location of the resource e.g. rtsp://hostname:8554/playfield.

I recommend adding the GStreamer plugin for the best results and configuration. https://obsproject.com/forum/resources/obs-gstreamer.696/

## Adjusting Camera Settings

If you want to change any of the default settings you can edit the picam.py file in the /opt directory. These can also be done after the cameras are in use by visiting a web page on the device at http://hostname:5000/.

## Additional Notes

If using a Logitech Brio/4K Pro, keep the exposure_auto setting at or below 200 to achieve full 60fps, use the gain setting instead to brighten up the image. Brightness and contrast can also do a bit there but don't over do those. On a USB 2.0 system the resolution is limited to 1280x720, if plugging into a USB 3.0+ port you should be able to run higher resolutions. You can use the zoom and pan/tilt settings to get closer if necessary and move the where the center is if zoomed in.

If you are using a C920 for displays, consider bumping the exposure_auto setting to 300 or 400 to reduce the scan line effect and reduce the gain setting to compensate for the additional brightness. Play around with what works best.

Consider running secondary cameras at a lower resolution if you are going to be composing them into a 1080p or 720p feed. That will save on bandwidth and CPU/GPU in the composition software like OBS. Again, play with it depending on the power of the streaming machine.

Sometimes the service on the Pi doesn't start up properly when the device boots up. It fails to set the webcam settings properly. You can see if that's the case by logging into the Pi and running the following command.

    $ sudo systemctl status picam

If you see some text that looks like errors, try restarting the service with the following command.

    $ sudo systemctl restart picam

Normally doing that once should be enough. On rare occassions you may need to do it again. I'm working on a fix.
