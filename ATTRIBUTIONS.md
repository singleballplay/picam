[pi-gen](https://github.com/RPi-Distro/pi-gen) project is forked to customize the minimal server version of the build.
It adds two additional steps to the normal process to install project specific libraries at the OS level and configure the services that alow the software to run.
The forked project and branch can be found at https://github.com/aaronhanson/pi-gen/tree/picam.

[cameractls](https://github.com/soyersoyer/cameractrls) is cloned into the prebuilt image to provide additional support for Razer webcams(specifically the Kiyo Pro Ultra)  outside of the normal V4L2 abilities. The full source is available in the `/home/pi/cameractrls` directory.
