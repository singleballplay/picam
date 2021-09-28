# Prebuilt Image

For convenience, a prebuilt image is available. It is built using the pi-gen project to build a custom Raspbian Buster lite image which already has the setup procedure completed. It also has SSH enabled and the hostname has been changed to *picam*. After writing the image to a card, plug the device in with a networking cable and give it a moment to boot up and visit [http://picam:5000](http://picam:5000). You can configure the WiFi from there along with all of the other configuration of devices.

Download [picam-v2.1.zip](https://drive.google.com/file/d/19fXkvyqRLcE_RVAXHOYaQtvDsRTa3AyP/view?usp=sharing)

SHA-256: b1c2b4b4a384f0fbc625d851149df3e1dd0320cd8ee05b26d9de247b352384fd  2020-04-09-Raspbian-picam.img

It is a good idea to visit the admin page in the website and run the 'Update Picam' to get the latest changes. The downloaded image will periodically be updated but not as frequently as the code. Restart after updating. Future versions will check for updates but that feature is not currently implemented.

IMPORTANT!

If you have previously downloaded the Raspbian Stretch image, from about a year ago, you will need to download this new image and config the picam again. I'll be working on a more seemless way to upgrade in the future. This version should support the Raspberry Pi 4 now.


# OBS Sources

To add them as sources in OBS I recommend adding the GStreamer plugin (https://github.com/fzwoch/obs-gstreamer) for the best results and configuration. While you can use the VLC or Media sources, they introduce too much latency to be usable and should be avoided.

## Windows

Download the obs-gstreamer.zip file from the latest release https://github.com/fzwoch/obs-gstreamer/releases and unzip it. Copy the obs-gstreamer.dll file in the windows folder to the plugins directory of OBS.

For Windows installations, the GStreamer MinGW 64-bit runtime is required and can be downloaded from the GStreamer website. https://gstreamer.freedesktop.org/data/pkg/windows/1.18.5/mingw/gstreamer-1.0-mingw-x86_64-1.18.5.msi

After installing the package, you will need to edit the Windows PATH environment variable for the OBS plugin to be able to find the necessary files. Assuming a default installation you should be able to add c:\gstreamer\1.0\mingw\bin to the user or system PATH variable.


## Additional Notes

If using a Logitech Brio/4K Pro, keep the exposure_auto setting at or below 200 to achieve full 60fps, use the gain setting instead to brighten up the image. Brightness and contrast can also do a bit there but don't over do those. On a USB 2.0 system the resolution is limited to 1280x720, if plugging into a USB 3.0+ port you should be able to run higher resolutions. You can use the zoom and pan/tilt settings to get closer if necessary and move the where the center is if zoomed in.

If you are using a C920 for displays, consider bumping the exposure_auto setting to 300 or 400 to reduce the scan line effect and reduce the gain setting to compensate for the additional brightness. Play around with what works best.

Consider running secondary cameras at a lower resolution if you are going to be composing them into a 1080p or 720p feed. That will save on bandwidth and CPU/GPU in the composition software like OBS. Again, play with it depending on the power of the streaming machine.


# Install From Scratch

## Install Raspbian

Grab the latest Raspbian "lite" image from https://www.raspberrypi.org/downloads/raspbian/. At the moment the current version is 2020-02-13-raspbian-buster-lite.zip. Unzip it locally so you have access to the .img file. Follow the instructions on the Raspberry Pi website to format the disk with the image so you have a fresh operating system.

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

## Accessing The Stream

You should be good to go now. The service will run after the device powers up and use whatever cameras are available and should be accessible by the appropriate uri: rtsp://hostname:8554/playfield or rtsp://hostname:8554/backglass, etc. based on how you configured them.

To test the stream on another computer you can run the following gstreamer pipeline and it should display the video:

For H.264 encoding:

    $ gst-launch-1.0 rtspsrc location=rtsp://hostname:8554/playfield latency=100 ! queue ! rtph264depay ! avdec_h264 ! autovideosink

For MJPEG encoding:

    $ gst-launch-1.0 rtspsrc location=rtsp://hostname:8554/playfield latency=100 ! queue ! rtpjpegdepay ! jpegdec ! autovideosink
