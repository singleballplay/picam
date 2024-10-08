import subprocess

from flask import redirect, render_template, request
from flask.views import MethodView


def get_hostname():
    cat_hostname = subprocess.run(
        ('cat', '/etc/hostname'),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    return cat_hostname.stdout.decode().strip()


def get_current_ssid():
    cmd1 = subprocess.Popen(
        ('sudo', 'cat', '/etc/wpa_supplicant/wpa_supplicant.conf'),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    cmd2 = subprocess.run(
        ('grep', 'ssid'),
        stdin=cmd1.stdout,
        stdout=subprocess.PIPE,
        check=False,
    )
    ssid = ''
    if cmd2.returncode == 0:
        ssid = cmd2.stdout.decode().strip().split('=')[1][1:-1]
    return ssid


def get_current_psk():
    cmd1 = subprocess.Popen(
        ('sudo', 'cat', '/etc/wpa_supplicant/wpa_supplicant.conf'),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    cmd2 = subprocess.run(
        ('grep', 'psk'),
        stdin=cmd1.stdout,
        stdout=subprocess.PIPE,
        check=False,
    )
    psk = ''
    if cmd2.returncode == 0:
        psk = cmd2.stdout.decode().strip().split('=')[1][1:-1]
    return psk


class WifiHandler(MethodView):
    def get(self):
        current_ssid = get_current_ssid()
        cat_hostname = subprocess.run(
            ('cat', '/etc/hostname'),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        current_hostname = cat_hostname.stdout.decode().strip()
        model = {
            'hostname': current_hostname,
            'ssid': current_ssid,
            'psk': '',
            'menu': 'wifi',
        }
        return render_template('config_wifi.html', **model)

    def post(self):
        cat_hostname = subprocess.run(
            ('cat', '/etc/hostname'),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        current_hostname = cat_hostname.stdout.decode().strip()
        hostname = request.form.get('hostname', 'picam')
        if hostname != current_hostname:
            subprocess.run(
                ('update-hostname', current_hostname, hostname),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=True,
            )
        current_ssid = get_current_ssid()
        current_psk = get_current_psk()
        ssid = request.form.get('ssid', None)
        psk = request.form.get('psk', None)
        if ssid and ssid != current_ssid:
            substitution = f's/ssid="{current_ssid}"/ssid="{ssid}"/'
            subprocess.run(
                ('sudo', 'sed', '-i', substitution, '/etc/wpa_supplicant/wpa_supplicant.conf'),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            substitution = f's/psk="{current_psk}"/psk="{psk}"/'
            subprocess.run(
                ('sudo', 'sed', '-i', substitution, '/etc/wpa_supplicant/wpa_supplicant.conf'),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if current_ssid == '':
                wifi_section = 'network={{\n\tssid="{ssid}"\n\tpsk="{psk}"\n}}'.format(
                    ssid=ssid, psk=psk
                )
                ps = subprocess.Popen(
                    ('echo', wifi_section),
                    stdout=subprocess.PIPE,
                )
                subprocess.check_output(
                    ('sudo', 'tee', '-a', '/etc/wpa_supplicant/wpa_supplicant.conf'),
                    stdin=ps.stdout,
                )
                ps.wait()
        return redirect('/admin')
