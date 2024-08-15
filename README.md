# Introduction

Picam allows UVC video and audio (ALSA) devices on a Debian based system, like the Raspberry Pi, to create RTSP streams for use in live streaming application. It was originallly developed as a low cost network camera solution to help live stream pinball. The project is a Python application using the Gstreamer RTSPServer and a Flask web application to manage the configurations as well as provide realtime configuration changes for available controls like recording level or V4L2 options (e.g. brightness, exposure, auto focus, etc).

# Prebuilt Image

For convenience, a prebuilt image is available. It is built using the [pi-gen](https://github.com/aaronhanson/pi-gen/tree/picam) project to build a custom Raspberry Pi OS Lite image which already has the setup procedure completed. It also has SSH enabled and the hostname has been changed to *picam*. If you are using the [Raspberry Pi Imager](https://www.raspberrypi.com/documentation/computers/getting-started.html#raspberry-pi-imager) you can adjust the Wifi settings, hostname, username, etc. After writing the image to a card, plug the device in with a networking cable and give it a moment to boot up and visit [http://picam:5000](http://picam:5000). You can configure the WiFi from there along with all of the other configuration of devices.

Download [picam-v5.0.0.zip](https://drive.google.com/file/d/1edUIBP2RUdX48mVYVPyhLkFI9NXvtqTy/view?usp=sharing)

SHA-256: 81c998901a4fb35e326d617c597d16f075ba7f4bab0b01cee734fbfe9225ae95  picam.img

IMPORTANT!

If you have previously downloaded the Raspbian image from earlier than 2024 (v3.1.0), you will need to download this new image and config the picam again. I'll be working on a more seemless way to upgrade in the future. This version should support the Raspberry Pi 5 now.

# Usage

Visit the UI available at http://hostname or http://hostname:5000. Follow the instructions to configure the available UVC video and audio devices available to the system. To save the configuration visit the 'admin' menu option and click the 'Write Config' button. Then click the 'Restart Picam Service' to make the sources available for use.

## Accessing The Stream

The services will run after the device powers up and use whatever cameras are available and should be accessible by the appropriate uri: rtsp://hostname:8554/playfield or rtsp://hostname:8554/backglass, etc. based on how you configured them.

To test the stream on another computer you can run the following gstreamer pipeline and it should display the video:

Example H.264 encoding:

    $ gst-launch-1.0 rtspsrc location=rtsp://hostname:8554/playfield latency=200 ! rtph264depay ! avdec_h264 ! queue ! autovideosink

Example MJPEG encoding:

    $ gst-launch-1.0 rtspsrc location=rtsp://hostname:8554/playfield latency=200 ! rtpjpegdepay ! jpegdec ! queue ! autovideosink

Example Audio:

    $ gst-launch-1.0 rtspsrc location=rtsp://hostname:8554/mic1 latency=200 ! rtpmp4adepay ! avdec_aac ! audioconvert ! queue ! autoaudiosink

## OBS Sources

To add them as sources in OBS I recommend adding the GStreamer plugin (https://github.com/fzwoch/obs-gstreamer) for the best results and configuration. While you can use the VLC or Media sources, they introduce too much latency to be usable and should be avoided.

### Windows

Download the obs-gstreamer.zip file from the latest release https://github.com/fzwoch/obs-gstreamer/releases and unzip it. Copy the obs-gstreamer.dll file in the windows folder to the plugins directory of OBS.

For Windows installations, the GStreamer MinGW 64-bit runtime is required and can be downloaded from the GStreamer website.
https://gstreamer.freedesktop.org/data/pkg/windows/1.24.6/mingw/gstreamer-1.0-mingw-x86_64-1.24.6.msi

After installing the package, you will need to edit the Windows PATH environment variable for the OBS plugin to be able to find the necessary files. Assuming a default installation you should be able to add c:\gstreamer\1.0\mingw\bin to the user or system PATH variable.


## Additional Notes

### Logitech Brio/4K Pro

If using a Logitech Brio/4K Pro, keep the exposure_auto setting at or below 200 to achieve full 60fps, use the gain setting instead to brighten up the image. Brightness and contrast can also do a bit there but don't over do those. On a USB 2.0 system the resolution is limited to 1280x720, if plugging into a USB 3.0+ port you should be able to run higher resolutions. You can use the zoom and pan/tilt settings to get closer if necessary and move the where the center is if zoomed in.

### Logitech C920/C922

If you are using a C920 for displays, consider bumping the exposure_auto setting to 300 or 400 to reduce the scan line effect and reduce the gain setting to compensate for the additional brightness. Play around with what works best.

### Camlink / Razer Kiyo (Pro/Pro Ultra)

Only one of these (of each model) can be configured at a time as they do not currently have serial numbers to identify them like other UVC devices.

### Razer Kiyo (Pro/Pro Ultra)

The exposure values are a little different from normal. The valid values to get various rough framerates are 10, 20, 39, 78. 39 seems to be very close to 1/120s shutter speed and 78 seems very close to 1/60s shutter. Compensate for exposure using the gain values.

# Install From Scratch

## Install Raspberry Pi OS

Grab the latest Raspberry Pi OS "Lite" image from https://www.raspberrypi.org/downloads/raspbian/. Unzip it locally so you have access to the .img file. Follow the instructions on the Raspberry Pi website to format the disk with the image so you have a fresh operating system.

The following commands all assume a Linux operating system is being used. If you are on Windows you may need to adjust some of the commands. Feel free to use an editor of your choice instead of vi as well if you aren't familiar with it.

Remount the micro sd card and make the following changes (your path may be different to the boot and rootfs directories). Examples are shown using Vi as the editor but you can use whatever editor you feel comfortable with. Using nano anywhere you see vi might be a bit easier if you aren't familiar with the program.

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

Change the Localisation Options to your locale if you're not in GB. Go to the 'Interfacing Options and enable the camera module. Go to 'Advanced Options and expand the filesystem. Also make sure you set the wifi locale.

    $ sudo raspi-config

That's it for the basic Raspbian setup you'll need. You might also want too change the password to which you can do in raspi-config as well.

## Installing The Software

At this point you'll need to SSH into the Raspberry Pi. The setup script will turn off the power to the HDMI output on future reboots by default to save power, this can be toggled from the web admin page but is not persisted between reboots.

Clone the latest version of the code here: https://gitlab.com/singleballplay/picam. You might need to install git first.

    $ sudo apt -y install git
    $ git clone https://gitlab.com/singleballplay/picam.git
    $ cd picam

Run the setup script and you should be good to go. It will probably take a bit to upgrade everything so be patient. Reboot afterwards and you can view the admin website to configure devices that are plugged in.

    $ ./setup
    $ sudo shutdown -r now
