#!/usr/bin/env python

"""
This is a web service to print labels on Brother QL label printers.
"""

import math
import sys
import logging
import random
import configparser
import argparse
import io
import base64
import functools
import importlib.resources

import PIL.ImageFont
import PIL.ImageDraw
import bottle
import fontconfig

import brother_ql.conversion
import brother_ql.raster

from .printer import PrinterDevice, PrinterError

TEMPLATE_DIR = [importlib.resources.files(__package__).joinpath('views')]

ENDLESS_LABELS = (brother_ql.labels.FormFactor.ENDLESS, )
if hasattr(brother_ql.labels.FormFactor, "PTOUCH_ENDLESS"):
    ENDLESS_LABELS += (brother_ql.labels.FormFactor.PTOUCH_ENDLESS, )

CONFIG_DEFAULTS = {
    'server': {
        },
    'logging': {
        'level': 'INFO',
        'debug': 'false',
        },
    'fonts': {
        'system_fonts': 'true',
        'additional_paths': '',
        },
    'printer': {
        'discover': 'linux_kernel,pyusb',
        },
    'defaults': {
        'text': '',
        'label_size': 'auto',
        'orientation': 'portrait',
        'font': 'Minion Pro:Semibold,Linux Libertine:Regular,DejaVu Serif:Book',
        'font_size': '100',
        'align': 'center',
        'align_vertical': 'center',
        'margin_top': '24',
        'margin_bottom': '45',
        'margin_left': '35',
        'margin_right': '35',
        'copies': '1',
        'threshold': '70',
        },
    'website': {
        'static_dir': importlib.resources.files(__package__).joinpath('static'),
        'static_url': '/static',
        },
    }

PARAMETER_TYPES = {
    'text':           str,
    'font_size':      int,
    'font_index':     int,
    'label_size':     str,
    'threshold':      int,
    'align':          str,
    'align_vertical': str,
    'orientation':    str,
    'copies':         int,
    'margin_top':     float,
    'margin_bottom':  float,
    'margin_left':    float,
    'margin_right':   float,
}

LOGGER = logging.getLogger(__name__)

def exception_to_json(func):
    """
    Wrapper for all API endpoints that catches exeptions and instead
    returns a dict that will be converted to JSON
    """
    @functools.wraps(func)
    def wrapper_decorator(*args, **kwargs):
        try:
            return func(*args, **kwargs)

        except PrinterError as e:
            messages = [error.description for error in e.errors]
            LOGGER.warning('Printer returned an error: %s', ','.join(messages))
            return {'success': False, 'messages': messages}

        except Exception as e:
            LOGGER.error('Request failed with unhandled exception', exc_info=e)
            if isinstance(e, OSError):
                message = 'Failed to connect to printer.'
            else:
                message = repr(e)
            return {'success': False, 'messages': [message]}
    return wrapper_decorator


@bottle.route('/')
def index():
    bottle.redirect('/designer')

@bottle.route('/static/<filename:path>')
def serve_static(filename):
    return bottle.static_file(filename, root=WEBSITE['static_dir'])

@bottle.route('/designer')
@bottle.jinja2_view('designer', template_lookup=TEMPLATE_DIR)
def labeldesigner():
    return {'static_url': WEBSITE['static_url']}

def render_image(request, printer = None):
    """
    Common function to render a label for preview and printing
    """

    data = request.params.decode() # UTF-8 decoded form data

    context = {}

    for name, datatype in PARAMETER_TYPES.items():
        context[name] = datatype(data.get(name, DEFAULTS[name]))

    for margin in ('margin_top', 'margin_bottom', 'margin_left', 'margin_right'):
        context[margin] = int(context['font_size'] * (context[margin] / 100.))

    if context['label_size'] == 'auto':
        if not printer:
            with PrinterDevice(DEVICE) as printer_instance:
                label = printer_instance.info()[1]
        else:
            label = printer.info()[1]
        if not label:
            context['image'] = PIL.Image.new('L', (1, 1), 'white')
            return context
        context['label_size'] = label.identifier
    else:
        for label_item in brother_ql.labels.ALL_LABELS:
            if label_item.identifier == context['label_size']:
                label = label_item
                break
        else: # no label did match
            raise LookupError("Unknown label_size: {}".format(context['label_size']))

    if context['copies'] < 1 or context['copies'] > 20:
        raise ValueError("The number of copies is limited to 20.")

    try:
        font_path = FONTS[context['font_index']][0]
    except KeyError:
        raise LookupError("Couln't find the font with index {}"\
                .format(context['font_index']))

    im_font = PIL.ImageFont.truetype(font_path, context['font_size'])

    image = PIL.Image.new('L', (20, 20), 'white')
    draw = PIL.ImageDraw.Draw(image)

    # workaround for a bug in multiline_textsize()
    # when there are empty lines in the text:
    lines = []
    for line in context['text'].split('\n'):
        lines.append(line or ' ')
    text = '\n'.join(lines)

    bbox = draw.multiline_textbbox((0, 0), text, font=im_font, align=context['align'])
    text_width, text_height = math.ceil(bbox[2] - bbox[0]), math.ceil(bbox[3] - bbox[1])
    # move anchor to make image start in the top right corner, and add margins
    horizontal_offset = -bbox[0] + context['margin_left']
    vertical_offset = -bbox[1] + context['margin_top']

    # compute image size
    if context['orientation'] == 'landscape':
        (height, width) = label.dots_printable
        if label.form_factor in ENDLESS_LABELS:
            width = text_width + context['margin_left'] + context['margin_right']
    elif context['orientation'] == 'portrait':
        (width, height) = label.dots_printable
        if label.form_factor in ENDLESS_LABELS:
            height = text_height + context['margin_top'] + context['margin_bottom']
    else:
        raise ValueError("Invalid value for parameter 'orientation'. Must " +\
                         "be one of 'portrait' or 'landscape'.")

    # move image to match horizontal alignment (fallback to "center")
    horizontal_space_remaining = width - text_width - context['margin_left'] - context['margin_right']
    if context['align'] == 'right':
        horizontal_offset += horizontal_space_remaining
    elif context['align'] != 'left':
        horizontal_offset += horizontal_space_remaining // 2
    # move image to match vertical alignment (fallback to "center")
    vertical_space_remaining = height - text_height - context['margin_top'] - context['margin_bottom']
    if context['align_vertical'] == 'bottom':
        vertical_offset += vertical_space_remaining
    elif context['align_vertical'] != 'top':
        vertical_offset += vertical_space_remaining // 2

    context['image'] = PIL.Image.new('L', (width, height), 'white')
    draw = PIL.ImageDraw.Draw(context['image'])
    draw.multiline_text((horizontal_offset, vertical_offset), text, (0), \
                        font=im_font, align=context['align'])

    if label.form_factor in ENDLESS_LABELS:
        if context['orientation'] == 'portrait':
            context['rotate'] = 0
        else:
            context['rotate'] = 90
    else:
        context['rotate'] = 'auto'

    return context

@bottle.route('/api/text/preview', method=['GET', 'POST'])
@exception_to_json
def api_text_preview():
    """
    API to generate a preview image

    parameters: text:str             Label text
                font_size:int        Font size in points
                font_index:int       Font index as returned by /api/config
                label_size:str       Label size as returned by /api/config
                threshold:int        Threshold for black and white conversion
                align:str            "left", "center", "right" or "justify"
                align_vertical:str   "top", "center" or "bottom"
                orientation:str      "landscape" or "portrait"
                copies:int           Number of copies to print
                margin_top:float     Text margin in pixels
                margin_bottom:float  Text margin in pixels
                margin_left:float    Text margin in pixels
                margin_right:float   Text margin in pixels
                return_format:str    "png" or "json"

    returns: PNG or JSON depending on return_format parameter
    """
    return_format = bottle.request.query.get('return_format', 'png')

    context = render_image(bottle.request)

    image_buffer = io.BytesIO()

    context['image'].save(image_buffer, format="PNG")

    image_buffer.seek(0)

    if return_format == 'json':
        return {
            'success': True,
            'image': base64.b64encode(image_buffer.read()).decode('utf-8'),
            }
    if return_format == 'png':
        bottle.response.set_header('Content-type', 'image/png')
        return image_buffer.read()

    return {
        'success': False,
        'messages': ['Value for return_format not recognised. Must be one of "png" or "json"'],
        }

@bottle.route('/api/text/print', method=['GET', 'POST'])
@exception_to_json
def api_text_print():
    """
    API to send a print job

    parameters: text:str             Label text
                font_size:int        Font size in points
                font_index:int       Font index as returned by /api/config
                label_size:str       Label size as returned by /api/config
                threshold:int        Threshold for black and white conversion
                align:str            "left", "center", "right" or "justify"
                align_vertical:str   "top", "center" or "bottom"
                orientation:str      "landscape" or "portrait"
                copies:int           Number of copies to print
                margin_top:float     Text margin in pixels
                margin_bottom:float  Text margin in pixels
                margin_left:float    Text margin in pixels
                margin_right:float   Text margin in pixels

    returns: JSON
    """
    with PrinterDevice(DEVICE) as printer:
        context = render_image(bottle.request, printer)

        (model, label) = printer.info()

        if not label:
            return {'success': False, 'messages': ["No label in printer."]}

        if label.identifier != context['label_size']:
            return {'success': False, 'messages': ["Wrong label size."]}

        qlr = brother_ql.raster.BrotherQLRaster(model.identifier)

        # convert will call add_status_information which we don't need
        # overriding this, so it has no effect
        qlr.add_status_information = lambda: None

        brother_ql.conversion.convert(
            qlr=qlr,
            images=[context['image']] * context['copies'],
            label=label.identifier,
            threshold=context['threshold'],
            cut=True,
            rotate=context['rotate'],
            )

        printer.print(qlr)

    return {'success': True}

@bottle.route('/api/config')
@exception_to_json
def api_config():
    """
    API to query the printer server config (fonts, label sizes, default values)

    parameter: none

    returns: JSON
    """
    return {
        'success': True,
        'fonts': [(index, font[1], font[2]) for index, font in enumerate(FONTS)],
        'label_sizes': [(label.identifier, label.name) for label in brother_ql.labels.ALL_LABELS],
        'default_values': dict(DEFAULTS),
        }

@bottle.route('/api/status')
@exception_to_json
def api_status():
    """
    API to query the printer status (label size, errors)

    parameter: none

    returns: JSON
    """
    with PrinterDevice(DEVICE) as printer:
        (model, label) = printer.info()

    return {
        'success': True,
        'model': model.identifier,
        'label': label.identifier if label else None,
        }

def main():
    global FONTS, DEFAULT_FONT, WEBSITE, DEFAULTS, DEVICE

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-c', '--config', nargs='?',
                        help="Configuration file to load.")
    parser.add_argument('-d', '--debug', action='store_true',
                        help="Set loglevel to debug and enable additional output.")
    args = parser.parse_args()

    config = configparser.ConfigParser()
    config.read_dict(CONFIG_DEFAULTS)
    if args.config is not None:
        with open(args.config) as conf_file:
            config.read_file(conf_file)

    if args.debug:
        loglevel = 'DEBUG'
    else:
        loglevel = config['logging'].get('level', 'WARNING').upper()
    try:
        logging.basicConfig(level=getattr(logging, loglevel))
    except KeyError:
        sys.stderr.write("Unsupported log level: {}\n".format(loglevel))
        sys.exit(2)

    WEBSITE = config['website']

    DEFAULTS = config['defaults']

    DEVICE = config['printer'].get('device')

    if not DEVICE:
        devices_found = []
        for backend in config['printer']['discover'].split(','):
            factory = brother_ql.backends.backend_factory(backend.strip())
            devices_found += factory['list_available_devices']()

        if not devices_found:
            LOGGER.critical("No device specified and discovery failed. Exiting!")
            sys.exit(2)

        DEVICE = devices_found[0]['identifier']
        LOGGER.info("No device specified. Selecting %s", DEVICE)

    if config['fonts'].getboolean('system_fonts'):
        fontconfig_instance = fontconfig.Config.get_current()
    else:
        fontconfig_instance = fontconfig.Config.create()

    for folder in config['fonts']['additional_paths'].split(','):
        if folder.strip():
            fontconfig_instance.app_font_add_dir(folder)

    props_to_query = (fontconfig.PROP.FILE, fontconfig.PROP.FAMILY, fontconfig.PROP.STYLE)

    FONTS = []
    for font in fontconfig_instance.font_list(fontconfig.Pattern.create(), props_to_query):
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
        for i, (path, family, style) in enumerate(FONTS):
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
