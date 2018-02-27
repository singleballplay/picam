# Installing Raspbian

Grab the latest Raspbian "lite" image from https://www.raspberrypi.org/downloads/raspbian/. At the momemnt the current version is 2017-11-29-raspbian-stretch-lite.zip. Unzip it locally so you have access to the .img file. Follow the instructions to format the disk with the image so you have a fresh operating system.

Remount the micro sd card and make the following changes:
- Create an empty ssh file in the boot partition to enable ssh access to the pi. You should see two paritions rootfs and boot.

    ```
    $ cd /var/host/media/removeable/boot
    $ touch ssh
    ```

- Change the hostname to something unique for your network. If you're only pi is this one feel free to leave it as 'raspberry' but you probably want to change it. Be careful to edit the relative path etc/ files not your local machine's.

    ```
    $ cd /var/host/media/removeable/rootfs
    $ sudo vi etc/hostname
    $ sudo vi etc/hosts
    ```

- Add your wifi credentials in the wpa_supplicant file.

    ```
    $ sudo etc/wpa_supplicant/wpa_supplication.conf
    ```

- Add a block like this:

    ```
    network={
        ssid="network_ssid_here"
        psk="wifi_password_here"
    }
    ```

Go ahead and put the sd card in the pi and power it on. Use and SSH connection to setup things after the pi is running.

Change the Localisation Options to your locale if you're not in GB. Go to the 'Interfacing Options and enable the camera module. Go to 'Advanced Options and expand the filesystem.

    $ sudo raspi-config

That's it for the basic Raspbian setup you'll need. You might also want too change the password to which you can do in raspi-config as well.

# Installing The Software

Download the latest version of the code here: https://gitlab.com/singleballplay/picam.

Unzip the archive and navigate to the project directory. Run the setup script and you should be good to go. It will probably take a bit to upgrade everything so be patient. Reboot afterwards and you should have the stream(s) available to test.

    $ ./setup
    $ sudo shutdown -r now

## Accessing The Stream

You should be good to go now. The service will run after the device powers up and use whatever cameras are available and should be accessible by the appropriate uri: rtsp://hostname:8554/picam or rtsp://hostname:8554/c920-1 (2,3,4 if you have multiple C920s).

To test the stream on another computer you can run the following gstreamer pipeline and it should display the video:

    $ gst-launch-1.0 rtspsrc location=rtsp://hostname:8554/c920-1 latency=0 ! rtph264depay ! avdec_h264 ! autovideosink

## Adjusting Camera Settings

**In Progress not yet actually available for use**

If you want to change any of the default settings you can edit the picam.py file in the /opt directory. These can also be done after the camera are in use by using the APIs available at http://hostname:8080/settings.

    $ curl -XPOST -d '{"setting": "brightness", "value": "50"}' http://hostname:8080/settings

Unfortunately the settings are camera specific and don't exactly work the same way between the C920 and the Pi Camera Module so this is a bit of a manual process.
