import logging
import subprocess
import yaml
import json
import re

from flask import request, flash, url_for, redirect, Response, render_template, current_app as app
from flask.views import MethodView

def noop(self, *args, **kw):
    pass

yaml.emitter.Emitter.process_tag = noop

def render_yaml(yaml_data):
    resp = app.make_response(
        yaml.dump(
            yaml_data,
            default_flow_style=False,
            allow_unicode=True,
            encoding=None
        )
    )
    resp.headers['Content-type'] = 'application/yaml'
    return resp


def get_cpu_governor():
    cmd1 = subprocess.run(
        ('cat', '/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL
    )
    return cmd1.stdout.decode().strip()


class AdminHandler(MethodView):
    def get(self):
        model = {
            'scaling_governor': get_cpu_governor(),
        }
        return render_template('admin.html', **model)


class ScalingGovernorHandler(MethodView):
    def post(self):
        governor_cmd = subprocess.run(('toggle-performance'), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        return redirect(url_for('admin'))


class UpdatePicamHandler(MethodView):
    def post(self):
        cmd1 = subprocess.run(('update-picam'), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        return redirect(url_for('admin'))


class RestartPicamHandler(MethodView):
    def post(self):
        cmd1 = subprocess.run(('restart-picam-service'), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        return redirect(url_for('admin'))


class WifiPowerHandler(MethodView):
    def post(self):
        cmd1 = subprocess.run(('sudo', 'iwconfig', 'wlan0', 'power', 'off'), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        return redirect(url_for('admin'))


class HdmiHandler(MethodView):
    def post(self):
        cmd1 = subprocess.run(('toggle-hdmi-power'), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        return redirect(url_for('admin'))


class RebootHandler(MethodView):
    def post(self):
        cmd1 = subprocess.run(('sudo', 'shutdown', '-r'), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        return redirect(url_for('admin'))


class ShutdownHandler(MethodView):
    def post(self):
        cmd1 = subprocess.run(('sudo', 'shutdown', '-h'), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
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
