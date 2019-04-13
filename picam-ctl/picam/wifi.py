import logging
import subprocess

from flask import (
    current_app as app,
    request,
    flash,
    redirect,
    render_template,
)
from flask.views import MethodView


class WifiHandler(MethodView):
    def get(self):
        current_ssid = self.get_current_ssid()
        cat_hostname = subprocess.run(('cat', '/etc/hostname'), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        current_hostname = cat_hostname.stdout.decode().strip()
        model = {
            'hostname': current_hostname,
            'ssid': current_ssid,
            'psk': '',
        }
        return render_template('config_wifi.html', **model)

    def post(self):
        cat_hostname = subprocess.run(('cat', '/etc/hostname'), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        current_hostname = cat_hostname.stdout.decode().strip()
        hostname = request.form.get('hostname', 'picam')
        if hostname != current_hostname:
            subprocess.run(
                ('update-hostname', current_hostname, hostname),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )

        current_ssid = self.get_current_ssid()
        current_psk = self.get_current_psk()
        ssid = request.form.get('ssid', None)
        psk = request.form.get('psk', None)
        if ssid and ssid != current_ssid:
            substitution = "s/ssid=\"{}\"/ssid=\"{}\"/".format(current_ssid, ssid)
            print(substitution)
            cmd1 = subprocess.run(
                ('sudo', 'sed', '-i', substitution, '/etc/wpa_supplicant/wpa_supplicant.conf'),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            substitution = "s/psk=\"{}\"/psk=\"{}\"/".format(current_psk, psk)
            print(substitution)
            cmd1 = subprocess.run(
                ('sudo', 'sed', '-i', substitution, '/etc/wpa_supplicant/wpa_supplicant.conf'),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            if current_ssid == '':
                wifi_section = 'network={{\n\tssid="{ssid}"\n\tpsk="{psk}"}}'.format(ssid=ssid, psk=psk)

        return redirect('/admin')

    def get_current_ssid(self):
        cmd1 = subprocess.Popen(
            ('sudo', 'cat', '/etc/wpa_supplicant/wpa_supplicant.conf'),
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        cmd2 = subprocess.run(
            ('grep', 'ssid'),
            stdin=cmd1.stdout, stdout=subprocess.PIPE
        )
        if cmd2.returncode == 0:
            return cmd2.stdout.decode().strip().split('=')[1][1:-1]
        else:
            return ''

    def get_current_psk(self):
        cmd1 = subprocess.Popen(
            ('sudo', 'cat', '/etc/wpa_supplicant/wpa_supplicant.conf'),
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        cmd2 = subprocess.run(
            ('grep', 'psk'),
            stdin=cmd1.stdout, stdout=subprocess.PIPE
        )
        if cmd2.returncode == 0:
            return cmd2.stdout.decode().strip().split('=')[1][1:-1]
        else:
            return ''
