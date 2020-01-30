
# =============================================================================='
# sividl.devices
# ==============================================================================
# This module contains phidl wrapper classes used for quick generation of
# nanophotonic structures for e-beam lithography.
#
# Implemented devices are so far:
#   - Write field with alignment marker
#   - Etch slabs
#   - Generator of rectangular labelled parameter sweeps
#   - Representation of images as pixel array
#
# Note that all dimensions are in micrometer.
# ==============================================================================

from __future__ import absolute_import, division, print_function

import itertools as it
import string

import gdspy
from matplotlib.font_manager import FontProperties
import numpy as np
from phidl import Device
import phidl.geometry as pg
from sividl.sividl_utils import image_to_binary_bitmap, render_text


class SividdleDevice(Device):
    """Global device class holding all common class functions.

    Parameters
    ----------
    name: string
        Name of top-level cell.
    """

    def __init__(self, name):
        Device.__init__(self, name=name)

    def invert(self, layer):
        """Inverts a pattern from positive to negative or vice versa.

        Parameters
        ----------
        layer: string
            Layer of new, inverted device.
        """
        bounding_box = Device('interim_bounding_box')
        bounding_box.add_polygon([(self.xmin, self.ymin),
                                  (self.xmin, self.ymax),
                                  (self.xmax, self.ymax),
                                  (self.xmax, self.ymin)], layer=layer)

        # perform substraction for positive e-beam resist
        inverse = pg.boolean(
            A=bounding_box,
            B=self,
            operation='A-B',
            layer=layer
        )

        return inverse

    def add_label(self, params):
        """Adding a label to device.

        Parameters
        ----------
        params: dict
            Dictionary containing the settings.
        params['orientation']: string
            Indicators 'r', 'l', 't', 'b' to indicate
            label position with reference to device
            (right, left, top, bottom).
        params['layer']: int
            Layer of text.
        params['text']: string
            Text to render.
        params['style']: string
            Font style,
            from here:
            https://matplotlib.org/3.1.1/gallery/text_labels_and_annotations/fonts_demo.html
        params['distance']: float
            Distance between label and device.
        """
        assert params['orientation'] in ['r', 'l', 't', 'b'], \
            "Orientation must be one of the following: ['r', 'l', 't', 'b']"

        # Add text
        params['name'] = 'label_{}'.format(params['text'])
        text_device = RenderedText(params)

        # Shift center of bounding box to origin,
        # text center should now overlapp with center of device.
        text_device.center = [0, 0]

        # Move text.
        if params['orientation'] == 'l':
            text_device.movex(
                -(text_device.xsize + self.xsize) / 2 - params['distance']
            )
        elif params['orientation'] == 'r':
            text_device.movex(
                (text_device.xsize + self.xsize) / 2 + params['distance']
            )
        elif params['orientation'] == 't':
            text_device.movey(
                (text_device.ysize + self.ysize) / 2 + params['distance']
            )
        elif params['orientation'] == 'b':
            text_device.movey(
                -(text_device.ysize + self.ysize) / 2 - params['distance']
            )

        self << text_device


class BoundingBox(SividdleDevice):
    """Contains a writefield and all plot functions.

    Parameters
    ----------
    layer: int
        Layer of bounding box.
    wf_size: int
        Write filed size in um.
    """

    def __init__(self, layer, wf_size):
        # Properly instantiate Device
        SividdleDevice.__init__(self, name='writefield_boundingbox')
        self.add_polygon([(-wf_size * 0.5, -wf_size * 0.5),
                          (-wf_size * 0.5, wf_size * 0.5),
                          (wf_size * 0.5, wf_size * 0.5),
                          (wf_size * 0.5, -wf_size * 0.5)], layer=layer)


class CrossAligmentMark(SividdleDevice):
    """Write alignment marker.

    Parameters
    ----------
    positive (Boolean): Positive tone resist if true
    layer: int
        Layer of aligment mark.
    d_small: int
        Width of small rectangle.
    d_large:  int
        Width of large rectangle.
    sep: int
        Gap between rectangles.
    """

    def __init__(self, layer, d_small=1.75, d_large=1.975, sep=0.275):
        SividdleDevice.__init__(self, name='aligment_mark')
        self << pg.rectangle(size=(d_large, d_large), layer=layer)
        self << pg.rectangle(size=(d_small, d_small), layer=layer)\
            .movex(d_large + sep)
        self << pg.rectangle(size=(d_small, d_small), layer=layer)\
            .movey(d_large + sep)
        self << pg.rectangle(size=(d_large, d_large), layer=layer)\
            .move([d_small + sep, d_small + sep])


class WriteFieldCrossAligmentMark(SividdleDevice):
    """Writefiled with four cross-type alignment markers.

    Parameters
    ----------
    params: dict
        Contains the writefield parameters:
    params['bounding_box_size']: float
        Dimension of write field.
    params['positive']: boolean
        If True, pattern for positive tone resist is created.
    params['bounding_box_layer']: int
        Layer of bounding box.
    params['alignment_layer']: int:
        Layer of alignment markers.
    params['alignment_offset_dx']: int
        Offset of alignment markers
        from edge of writefield in x-direction.
    params['alignment_offset_dy']: int
        Offset of alignment markers
        from edge of writefield in x-direction.
    """

    def __init__(self, params):

        SividdleDevice.__init__(self, name='writefield')

        # make bounding box
        bounding_box = BoundingBox(
            params['bounding_box_layer'], params['bounding_box_size']
        )

        self << bounding_box

        # make alignment marks
        alignment_mark = CrossAligmentMark(params['alignment_layer'])

        if params['positive']:
            alignment_mark = alignment_mark.invert(params['alignment_layer'])

        # Position alignment marks on writefield
        delta_x = params['alignment_offset_dx']
        delta_y = params['alignment_offset_dy']

        self << pg.copy(alignment_mark).move(
            (
                bounding_box.xsize * 0.5 - delta_x,
                bounding_box.ysize * 0.5 - delta_y
            )
        )
        self << pg.copy(alignment_mark).move(
            (
                bounding_box.xsize * 0.5 - delta_x,
                -(bounding_box.ysize * 0.5 - delta_y)
            )
        )
        self << pg.copy(alignment_mark).move(
            (
                -(bounding_box.xsize * 0.5 - delta_x),
                bounding_box.ysize * 0.5 - delta_y
            )
        )
        self << pg.copy(alignment_mark).move(
            (
                -(bounding_box.xsize * 0.5 - delta_x),
                -(bounding_box.ysize * 0.5 - delta_y)
            )
        )

        # Shift center of bounding box to origin
        self.center = [0, 0]


class EtchSlap(SividdleDevice):
    """Generate two etching strip for isotropic etching tests.

    Parameters
    ----------
    params: dict
        Dictionary containing the following parameters:

    params['expose_layer']: int
        Layer for exposed regions.
    params['id_string']: string
        Identifier of device, will be printed
        in label layer.
    params['label_layer']: int
        Layer for labelling which details
        slit/slap dimensions.
    params['length_slab']: float
        Length of the slits and the resulting slab.
    params['width_slit']: float
        Width of the two slits.
    params['width_slab']: float:
        Separation of two slits which will result
        in width of slab.
    """

    def __init__(self, params):

        SividdleDevice.__init__(self, name='etchslab')

        # retrieve parameters
        self.id_string = params['id_string']
        self.expose_layer = params['expose_layer']
        self.label_layer = params['label_layer']
        self.length_slab = params['length_slab']
        self.width_slit = params['width_slit']
        self.width_slab = params['width_slab']

        slit = pg.rectangle(
            size=(self.width_slit, self.length_slab),
            layer=self.expose_layer
        ).rotate(90)

        self << pg.copy(slit).movey((self.width_slit + self.width_slab) * 0.5)
        self << pg.copy(slit).movey(-(self.width_slit + self.width_slab) * 0.5)
        self.label(
            text='{} \n slab_width = {:.2f} \
                \n slit_width = {:.2f} \
                \n slab_length = {:.2f}'.format(
                self.id_string,
                self.width_slab,
                self.width_slit,
                self.length_slab
            ),
            position=(self.xmin, self.ymax),
            layer=self.label_layer
        )

        # Shift center of bounding box to origin.
        self.center = [0, 0]


class WaveGuide(SividdleDevice):
    """Device describing a rectangular waveguide.

    This device will hace two ports associated with the axis defined
    by the 'height' dimension, which are named ''wgport1' and 'wgport2'.

    Parameters
    ----------
    layer: int
        Layer of waveguide.
    length: float
        length of waveguide.
    height: float
        Height of waveguide.
    """

    def __init__(self, layer, length, height):

        SividdleDevice.__init__(self, name='waveguide')

        self.add_polygon(
            [(0, 0), (length, 0), (length, height), (0, height)],
            layer=layer
        )
        self.add_port(
            name='wgport1',
            midpoint=[0, height / 2],
            width=height,
            orientation=180
        )

        self.add_port(
            name='wgport2',
            midpoint=[length, height / 2],
            width=height,
            orientation=0
        )

        # Shift center of bounding box to origin.
        self.center = [0, 0]


class Taper(SividdleDevice):
    """Device describing a tapering section of a waveguide.

    This device will hace two ports associated left and right ends
    of the tapered sections, named 'tpport1' and 'tpport2'.

    Parameters
    ----------
    layer: int
        Layer of waveguide.
    length: float
        length of taper.
    dy_min: float
        Minimum height of taper.
    dy_max: float
        MAximum height of taper.
    """

    def __init__(self, layer, length, dy_min, dy_max):

        SividdleDevice.__init__(self, name='taper')

        self.add_polygon(
            [
                (0, 0),
                (0, dy_min),
                (length, (dy_max - dy_min) / 2 + dy_min),
                (length, -(dy_max - dy_min) / 2)
            ],
            layer=2
        )

        self.add_port(
            name='tpport1',
            midpoint=[0, dy_min / 2],
            width=dy_min,
            orientation=180
        )

        self.add_port(
            name='tpport2',
            midpoint=[length, dy_min / 2],
            width=dy_max,
            orientation=0
        )


class EquidistantRectangularSweep(SividdleDevice):
    """Lays out equidistant grid of devices generated using different parameters.

    Parameters
    ----------
    sweep_params: dict
        Dictionary containing the settings of sweep,
        with the following keys.
    sweep_params['params']: dict
        Setting dictionary for device class to be used.
    sweep_params['device_name']: string
        Name used for gds cell.
    sweep_params['device_class']: SividdleDevice
        Sividdle device to be replicated
        and for which the params dictionary is furnished.
    sweep_params['varsx']: array
        Array of values to be changed in x-direction,
        will replace params at key 'keyx'.
    sweep_params['keyx']: string
        Dictionary key of entry in params for which
        varsx furnishes the new variables.
    sweep_params['varxz'] /  sweep_params['keyy']: array / string
        Same for y-direction.
    sweep_params['pitchx'] / sweep_params['pitchy']: float
        Separation of bounding boxes of different
        devices in x-direction / y-direction.
    sweep_params['grid_label']: boolean
        If True, label grid by assigning each
        device a coordinate 'A0', 'A1', etc.
    sweep_params['grid_label_params']: dict
        Parameters of grid label.
    sweep_params['grid_label_params']['label_layer']: int
        Layer of grid label to be exposed.
    sweep_params['grid_label_params']['textsize']: int
        Textsize of label.
    sweep_params['grid_label_params']['font']: string
        Font style,
        from here:
        https://matplotlib.org/3.1.1/gallery/text_labels_and_annotations/fonts_demo.html
    sweep_params['grid_label_params']['label_dist']: float
        Distance between label and device.
    sweep_params['grid_label_params']['revert_numbers']: boolean
        Revert ordering of numbers
        (sometimes usefull if same sweep
        is replicated in mirrored way).
    sweep_params['grid_label_params']['revert_letters']: boolean
        Revert odering of letters.
    """

    def __init__(self, sweep_params):

        # Shorten
        sp = sweep_params

        SividdleDevice.__init__(self, name=sp['sweep_name'])

        num_iter_x = len(sp['varsx'])
        num_iter_y = len(sp['varsy'])

        # keep track of necessary paddings
        padding_x = np.zeros([num_iter_x, num_iter_y])
        padding_y = np.zeros_like(padding_x)

        # Stores dimensions of devices
        device_dimensions = np.zeros([num_iter_x, num_iter_y, 2])

        # Generate labels
        letter_label = list(string.ascii_uppercase)[0:num_iter_x]
        number_label = [str(i) for i in range(num_iter_y)]

        if sp['grid_label_params']['revert_numbers']:
            number_label = number_label[::-1]

        if sp['grid_label_params']['revert_letters']:
            letter_label = letter_label[::-1]

        # make devices
        # TODO: Adjust for non quadratic grid
        for i, j in it.product(range(num_iter_x), repeat=2):
            sp['device_params'][sp['keyx']] = sp['varsx'][i]
            sp['device_params'][sp['keyy']] = sp['varsy'][j]
            sp['device_params']['id_string'] = '{}{}'.format(
                letter_label[i],
                number_label[j]
            )

            device = sp['device_class'](sp['device_params'])
            device_dimensions[i, j, 0] = device.xsize
            device_dimensions[i, j, 1] = device.ysize

        for i, j in it.product(range(num_iter_x), repeat=2):
            sp['device_params'][sp['keyx']] = sp['varsx'][i]
            sp['device_params'][sp['keyy']] = sp['varsy'][j]
            sp['device_params']['id_string'] = '{}{}'.format(
                letter_label[i],
                number_label[j]
            )

            new_device = sp['device_class'](sp['device_params'])

            if j < num_iter_x - 1:
                # One to the right, takes into account xsize.
                current_xsize = device_dimensions[i, j, 0]
                right_xsize = device_dimensions[i, j + 1, 0]
                padding_x[i, j + 1] = padding_x[i, j] + \
                    (current_xsize + right_xsize) * 0.5 + sp['pitchx']

            if i < num_iter_y - 1:
                current_ysize = device_dimensions[i, j, 1]
                top_ysize = device_dimensions[i + 1, j, 1]
                padding_y[i + 1, j] = padding_y[i, j] + \
                    (current_ysize + top_ysize) * 0.5 + sp['pitchy']

            # Add grid labels.
            if sp['grid_label']:

                if i == 0 or i == num_iter_y - 1:
                    sp['grid_label_params']['text'] = number_label[j]
                    if i == 0:
                        sp['grid_label_params']['orientation'] = 'b'
                    else:
                        sp['grid_label_params']['orientation'] = 't'

                    new_device.add_label(sp['grid_label_params'])
                if j == 0 or j == num_iter_x - 1:
                    sp['grid_label_params']['text'] = letter_label[i]
                    if j == 0:
                        sp['grid_label_params']['orientation'] = 'l'
                    else:
                        sp['grid_label_params']['orientation'] = 'r'

                    new_device.add_label(sp['grid_label_params'])

            self << new_device.move([padding_x[i, j], padding_y[i, j]])

        # Shift center of bounding box to origin.
        self.center = [0, 0]


class ImageArray(SividdleDevice):
    """Transforms a color image to BW array and generates an according pattern.

    Parameters
    ----------
    params: dict
        Dictionary containing setting
    params['name']: string
        Name of GDS cell.
    params['image']: string
        Path to image
    params['threshold']: int
        Threshold from 0 - 255 separating black from white
    params['pixel_size']: int
        Physical size of one pixel on the design in um.
    params['layer']: int
        Layer where picture will be displayed.
    """

    def __init__(self, params):

        SividdleDevice.__init__(self, name=params['name'])

        # Generate binary bitmap out of image
        bitmap = image_to_binary_bitmap(params['image'], params['threshold'])
        x_image = bitmap.shape[0]
        y_image = bitmap.shape[1]

        # Define pixel polygon
        pixel = pg.rectangle(
            size=(
                params['pixel_size'],
                params['pixel_size']
            ),
            layer=params['layer']
        )

        for x in range(x_image):
            for y in range(y_image):
                if bitmap[x, y] == 1:
                    self << pg.copy(pixel).move(
                        (
                            x * params['pixel_size'],
                            y * params['pixel_size']
                        )
                    )

        # Shift center of bounding box to origin.
        self.center = [0, 0]


class RenderedText(SividdleDevice):
    """Device containing rendered text.

    Parameters
    ----------
    params: dict
        Dictionary containing all settings
    params['name']: string
        Name of gds cell.
    params['text']: string
        Text to render.
    params['style']: string
        Font style,
        from here:
        https://matplotlib.org/3.1.1/gallery/text_labels_and_annotations/fonts_demo.html
    params['fontsize']: float
        Font size to render.
    params['layer']:
        Layer of rendered text.
    """

    def __init__(self, params):

        SividdleDevice.__init__(self, name=params['name'])

        font_prop = FontProperties(style=params['style'])

        text = gdspy.PolygonSet(
            render_text(
                params['text'],
                params['fontsize'],
                font_prop=font_prop
            ),
            layer=params['layer']
        )

        self.add(text)

        # Shift center of bounding box to origin.
        self.center = [0, 0]
