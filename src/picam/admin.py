import os
import subprocess
import re
from functools import lru_cache

import yaml

from flask import (
    url_for,
    redirect,
    render_template,
    current_app as app,
)
from flask.views import MethodView


def noop(self, *args, **kw):  # pylint: disable=unused-argument
    pass


yaml.emitter.Emitter.process_tag = noop


@lru_cache(maxsize=None)
def is_raspberry_pi():
    cpu_info = subprocess.run(
        ('grep', 'Raspberry Pi', '/proc/cpuinfo'),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    return cpu_info.returncode == 0


def render_yaml(yaml_data):
    resp = app.make_response(
        yaml.dump(
            yaml_data,
            default_flow_style=False,
            allow_unicode=True,
            encoding=None,
        )
    )
    resp.headers['Content-type'] = 'application/yaml'
    return resp


def check_for_new_version():
    cmd = subprocess.run(
        'git fetch origin'.split(' '),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    script_dir = os.path.dirname(__file__)
    cmd = subprocess.run(
        f'git diff master origin/master {script_dir}/../../version.txt'.split(' '),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    r = re.search(r'\+(\d\.\d\.\d)', cmd.stdout.decode())
    if r:
        app.logger.info(r.group(1))
    else:
        app.logger.info('no matching group')
    return r.group(1) if r else ''


def get_version():
    script_dir = os.path.dirname(__file__)
    cmd = subprocess.run(
        f'cat {script_dir}/../../version.txt'.split(' '),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    return cmd.stdout.decode().strip()


def get_wifi_power():
    wifi_power_setting = ''
    if is_raspberry_pi():
        cmd1 = subprocess.run(
            ('iwconfig', 'wlan0'),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        wifi_power = re.findall('Power Management:(.*)\n', cmd1.stdout.decode().strip())
        wifi_power_setting = wifi_power[0] if wifi_power else ''
    return wifi_power_setting


def get_cpu_governor():
    governor = ''
    if is_raspberry_pi():
        cmd1 = subprocess.run(
            ('cat', '/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        governor = cmd1.stdout.decode().strip()
    return governor


class AdminHandler(MethodView):
    def get(self):
        model = {
            'new_version_available': check_for_new_version(),
            'version': get_version(),
            'wifi_power': get_wifi_power(),
            'scaling_governor': get_cpu_governor(),
            'menu': 'admin',
        }
        return render_template('admin.html', **model)


class ScalingGovernorHandler(MethodView):
    def post(self):
        if is_raspberry_pi():
            subprocess.run(
                ('toggle-performance'),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        return redirect(url_for('admin'))


class UpdatePicamHandler(MethodView):
    def post(self):
        subprocess.run(
            ('update-picam'),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return redirect(url_for('admin'))


class RestartPicamHandler(MethodView):
    def post(self):
        subprocess.run(
            ('restart-picam-service'),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return redirect(url_for('admin'))


class WifiPowerHandler(MethodView):
    def post(self):
        if is_raspberry_pi():
            subprocess.run(
                ('sudo', 'iwconfig', 'wlan0', 'power', 'off'),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        return redirect(url_for('admin'))


class HdmiHandler(MethodView):
    def post(self):
        if is_raspberry_pi():
            subprocess.run(
                ('toggle-hdmi-power'),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        return redirect(url_for('admin'))


class RebootHandler(MethodView):
    def post(self):
        subprocess.run(
            ('sudo', 'shutdown', '-r'),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return redirect(url_for('admin'))


class ShutdownHandler(MethodView):
    def post(self):
        subprocess.run(
            ('sudo', 'shutdown', '-h'),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return redirect('admin')


class WriteConfigHandler(MethodView):
    def post(self):
        app.picam_config.write_config()
        return redirect(url_for('admin'))


class ReloadConfigHandler(MethodView):
    def post(self):
        app.picam_config.load_config()
        return redirect(url_for('admin'))


class DownloadConfigHandler(MethodView):
    def get(self):
        return render_yaml(app.picam_config)
