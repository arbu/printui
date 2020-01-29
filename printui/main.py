#!/usr/bin/env python

"""
This is a web service to print labels on Brother QL label printers.
"""

import sys
import os
import logging
import random
import json
import configparser
import argparse
import io
import base64

import PIL.ImageFont
import PIL.ImageDraw
import bottle
import fontconfig
import pkg_resources

import brother_ql.conversion
import brother_ql.backends
import brother_ql.raster
import brother_ql.models
import brother_ql.labels

TEMPLATE_DIR = [pkg_resources.resource_filename(__name__, 'views')]

ENDLESS_LABELS = (brother_ql.labels.FormFactor.ENDLESS, )
if hasattr(brother_ql.labels.FormFactor, "PTOUCH_ENDLESS"):
    ENDLESS_LABELS += (brother_ql.labels.FormFactor.PTOUCH_ENDLESS, )

CONFIG_DEFAULTS = {
    'server': {
        },
    'logging': {
        'level': 'WARNING',
        'debug': 'false',
        },
    'fonts': {
        'system_fonts': 'true',
        'additional_paths': '',
        },
    'printer': {
        'device': 'file:///dev/usb/lp1',
        },
    'defaults': {
        'text': '',
        'label_size': '62',
        'orientation': 'portrait',
        'font': 'Minion Pro:Semibold,Linux Libertine:Regular,DejaVu Serif:Book',
        'font_size': '100',
        'align': 'center',
        'margin_top': '24',
        'margin_bottom': '45',
        'margin_left': '35',
        'margin_right': '35',
        'copies': '1',
        'threshold': '70',
        },
    'website': {
        'static_dir': pkg_resources.resource_filename(__name__, 'static'),
        'static_url': '/static',
        },
    }

PARAMETER_TYPES = {
    'text':          str,
    'font_size':     int,
    'font_index':    int,
    'label_size':    str,
    'threshold':     int,
    'align':         str,
    'orientation':   str,
    'copies':        int,
    'margin_top':    float,
    'margin_bottom': float,
    'margin_left':   float,
    'margin_right':  float,
    }

MODELS_MANAGER = brother_ql.models.ModelsManager()
LABELS_MANAGER = brother_ql.labels.LabelsManager()

LOGGER = logging.getLogger(__name__)

@bottle.route('/')
def index():
    bottle.redirect('/designer')

@bottle.route('/static/<filename:path>')
def serve_static(filename):
    return bottle.static_file(filename, root=WEBSITE['static_dir'])

@bottle.route('/designer')
@bottle.jinja2_view('designer', template_lookup=TEMPLATE_DIR)
def labeldesigner():
    font_info = [(index, font[1], font[2]) for index, font in enumerate(FONTS)]
    label_sizes_by_name = [(label.identifier, label.name) for label in brother_ql.labels.ALL_LABELS]
    return {'font_info':    json.dumps(font_info),
            'label_sizes':  label_sizes_by_name,
            'static_url':   WEBSITE['static_url'],
            'defaults':     DEFAULTS,
            }

def render_image(request):
    """ might raise LookupError() """

    param_types = {
        'text':          str,
        'font_size':     int,
        'font_index':    int,
        'label_size':    str,
        'threshold':     int,
        'align':         str,
        'orientation':   str,
        'copies':        int,
        'margin_top':    float,
        'margin_bottom': float,
        'margin_left':   float,
        'margin_right':  float,
        }

    data = request.params.decode() # UTF-8 decoded form data

    context = {}

    for name, datatype in param_types.items():
        context[name] = datatype(data.get(name, DEFAULTS[name]))

    for margin in ('margin_top', 'margin_bottom', 'margin_left', 'margin_right'):
        context[margin] = int(context['font_size'] * (context[margin] / 100.))

    for label in brother_ql.labels.ALL_LABELS:
        if label.identifier == context['label_size']:
            label_type = label
            break
    else: # no label did match
        raise LookupError("Unknown label_size")

    if context['copies'] < 1 or context['copies'] > 20:
        raise ValueError("The number of copies is limited to 20.")

    try:
        font_path = FONTS[context['font_index']][0]
    except KeyError:
        raise LookupError("Couln't find the font")

    im_font = PIL.ImageFont.truetype(font_path, context['font_size'])

    image = PIL.Image.new('L', (20, 20), 'white')
    draw = PIL.ImageDraw.Draw(image)

    # workaround for a bug in multiline_textsize()
    # when there are empty lines in the text:
    lines = []
    for line in context['text'].split('\n'):
        lines.append(line or ' ')
    text = '\n'.join(lines)

    (text_width, text_height) = draw.multiline_textsize(text, font=im_font)

    if context['orientation'] == 'landscape':
        (height, width) = label_type.dots_printable
        if label_type.form_factor in ENDLESS_LABELS:
            width = text_width + context['margin_left'] + context['margin_right']
    elif context['orientation'] == 'portrait':
        (width, height) = label_type.dots_printable
        if label_type.form_factor in ENDLESS_LABELS:
            height = text_height + context['margin_top'] + context['margin_bottom']
    else:
        raise ValueError("Invalid value for parameter 'orientation'. Must " +\
                         "be one of 'portrait' or 'landscape'.")

    vertical_offset = (height - text_height + context['margin_top'] - context['margin_bottom']) // 2
    horizontal_offset = max((width - text_width) // 2, 0)

    if label_type.form_factor in ENDLESS_LABELS:
        if context['orientation'] == 'landscape':
            vertical_offset = context['margin_top']
        else:
            horizontal_offset = context['margin_left']

    context['image'] = PIL.Image.new('L', (width, height), 'white')
    draw = PIL.ImageDraw.Draw(context['image'])
    draw.multiline_text((horizontal_offset, vertical_offset), text, (0), \
                        font=im_font, align=context['align'])

    if label_type.form_factor in ENDLESS_LABELS:
        if context['orientation'] == 'portrait':
            context['rotate'] = 0
        else:
            context['rotate'] = 90
    else:
        context['rotate'] = 'auto'

    return context

@bottle.get('/api/preview/text')
@bottle.post('/api/preview/text')
def get_preview_image():
    context = render_image(bottle.request)

    image_buffer = io.BytesIO()

    context['image'].save(image_buffer, format="PNG")

    image_buffer.seek(0)

    return_format = bottle.request.query.get('return_format', 'png')
    if return_format == 'base64':
        bottle.response.set_header('Content-type', 'text/plain')
        return base64.b64encode(image_buffer.read())
    else:
        bottle.response.set_header('Content-type', 'image/png')
        return image_buffer.read()

@bottle.post('/api/print/text')
@bottle.get('/api/print/text')
def print_text():
    """
    API to print a label

    returns: JSON

    Ideas for additional URL parameters:
    - alignment
    """

    context = render_image(bottle.request)

    raster = brother_ql.raster.BrotherQLRaster(PRINTER['model'])

    brother_ql.conversion.convert(raster, [context['image']] * context['copies'],
            context['label_size'], threshold=context['threshold'], cut=True,
            rotate=context['rotate'])

    try:
        backend = BACKEND_CLASS(PRINTER['device'])
        backend.write(raster.data)
        backend.dispose()
        del backend
    except Exception as e:
        LOGGER.warning('Exception happened: %s', e)
        return {'success': False, 'message': str(e)}

    return {'success': True}

def main():
    global BACKEND_CLASS, FONTS, DEFAULT_FONT, WEBSITE, DEFAULTS, PRINTER

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-c', '--config', default='printui.conf',
                        help="Configuration file to load.")
    parser.add_argument('-d', '--debug', action='store_true',
                        help="Set loglevel to debug and enable additional output.")
    args = parser.parse_args()

    config = configparser.ConfigParser()
    config.read_dict(CONFIG_DEFAULTS)
    with open(args.config) as conf_file:
        config.read_file(conf_file)

    WEBSITE = config['website']

    DEFAULTS = config['defaults']

    PRINTER = config['printer']

    if args.debug:
        loglevel = 'DEBUG'
    else:
        loglevel = config['logging'].get('level', 'WARNING').upper()
    try:
        logging.basicConfig(level=getattr(logging, loglevel))
    except KeyError:
        sys.stderr.write("Unsupported log level: {}\n".format(loglevel))
        sys.exit(2)

    try:
        selected_backend = brother_ql.backends.guess_backend(PRINTER['device'])
    except ValueError:
        parser.error("Couldn't guess the backend to use from the printer string descriptor")

    BACKEND_CLASS = brother_ql.backends.backend_factory(selected_backend)['backend_class']

    if DEFAULTS['label_size'] not in LABELS_MANAGER.iter_identifiers():
        parser.error("Invalid default_size. Please choose on of the " + \
                     "following:\n:" + " ".join(LABELS_MANAGER.iter_identifier()))

    if 'model' not in PRINTER:
        sys.stderr.write("No model specified. Please specify one in the configuration.\n")
        sys.exit(2)

    if PRINTER['model'] not in MODELS_MANAGER.iter_identifiers():
        sys.stderr.write("The specified model is unknown. The following models are available:\n")
        for model in MODELS_MANAGER.iter_identifiers():
            sys.stderr.write("    {}\n".format(model.name))
        sys.exit(2)

    if config['fonts'].getboolean('system_fonts'):
        fc = fontconfig.Config.get_current()
    else:
        fc = fontconfig.Config.create()

    for folder in config['fonts']['additional_paths'].split(','):
        if folder.strip():
            fc.app_font_add_dir(folder)

    props_to_query = (fontconfig.PROP.FILE, fontconfig.PROP.FAMILY, fontconfig.PROP.STYLE)

    FONTS = []
    for font in fc.font_list(fontconfig.Pattern.create(), props_to_query):
        FONTS.append(tuple(font.get(prop, 0)[0] or '' for prop in props_to_query))

    if not FONTS:
        sys.stderr.write("Not a single font was found on your system. Please " + \
                         "install font files to your system or specify " + \
                         "additional font pathes in the configuration.\n")
        sys.exit(2)

    FONTS.sort(key=lambda font: font[1:])

    default_font_index = -1

    for default_font in DEFAULTS['font'].split(','):
        (default_family, default_style) = default_font.split(":")
        for i, (file, family, style) in enumerate(FONTS):
            if default_family == family and default_style == style:
                default_font_index = i
                break
        if default_font_index != -1:
            break
    else: # no default font found
        sys.stderr.write("Could not find any of the default fonts. Choosing a " + \
                         "random one.\n")
        default_font_index = random.randint(0, len(FONTS))
        sys.stderr.write('The default font is now set to: {1} ({2})\n'.format(*FONTS[default_font_index]))

    DEFAULTS["font_index"] = str(default_font_index)


    bottle.run(**config['server'], debug=args.debug or config['logging'].getboolean('debug'))

if __name__ == "__main__":
    main()
