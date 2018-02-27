#!/usr/bin/env python3

from flask import Flask, request
import subprocess
import logging

app = Flask(__name__)

def adjust_setting(device, setting, value):
    result = subprocess.run([
        'v4l2-ctl',
        '-d', device,
        '-c', '{}={}'.format(setting, value)
    ])
    if result.returncode != 0:
        logging.error('non-zero return code')

@app.route('/settings', methods=['POST'])
def update_setting():
    data = request.json
    device = '/dev/video0'
    adjust_setting(
        device,
        setting = data['setting'],
        value = data['value']
    )
    return 'ok'

if __name__ == '__main__':
    app.run()
