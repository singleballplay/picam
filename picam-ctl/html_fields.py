from jinja2 import Markup, escape

def label(for_elem, data):
    return Markup('<label for="{}">{}</label>'.format(
        for_elem,
        escape(data)
    ))

def text_input():
    pass

def range_input():
    pass

def checkbox_input():
    pass

def video_control(input_type, device_name, options=None):
    if input_type == 'range':
        pass
    elif input_type == 'text':
        pass
    elif input_type == 'checkbox':
        pass
    markup = (
        '<div class="video-control">'
        '\t<label for="{0}-{1}">{1}</label>'
        '\t<input type="range" min="0" max="255" value="" name="{0}-{1}" id="{0}-{1}"/>'
        '\t<span id="{0}-{1}_value" class="settings-value"></span>'
        '</div>'
    ).format(
        device_name,
        input_type
    )
    return Markup(markup)
