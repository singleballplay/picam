import json

from flask import make_response


def render_json(json_data):
    resp = make_response(json.dumps(json_data))
    resp.headers['Content-type'] = 'application/json'
    return resp
