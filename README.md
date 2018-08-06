# Installing Raspbian

Grab the latest Raspbian "lite" image from https://www.raspberrypi.org/downloads/raspbian/. At the momemnt the current version is 2017-11-29-raspbian-stretch-lite.zip. Unzip it locally so you have access to the .img file. Follow the instructions to format the disk with the image so you have a fresh operating system.

Remount the micro sd card and make the following changes (your path may be different to the boot and rootfs directories):

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

Unzip the archive and navigate to the project directory. There is a picam.yaml.example file to add your configuration to. Replace the spots for the serial numbers with the serials numbers for your camera(s) (directions below).

Run the setup script and you should be good to go. It will probably take a bit to upgrade everything so be patient. Reboot afterwards and you should have the stream(s) available to test.

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

    $ gst-launch-1.0 rtspsrc location=rtsp://hostname:8554/playfield latency=0 ! rtph264depay ! avdec_h264 ! autovideosink

To add them as sources in OBS, add a new 'Media Source' and uncheck all of the boxes. Then, in the 'Input' field enter the rtsp uri for the webcam and in the 'Input Format' box enter flv_live.

## Adjusting Camera Settings

If you want to change any of the default settings you can edit the picam.py file in the /opt directory. These can also be done after the cameras are in use by visiting a web page on the device at http://hostname:5000/.
