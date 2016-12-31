#!/usr/bin/python

from __future__ import print_function

import re
import argparse
from ConfigParser import SafeConfigParser
import sys
import ast
import os
import io
import copy
import subprocess
import collections

import cairo
import math

try:
  import pango
  import pangocairo
  use_pygobject = False
except ImportError:
  from gi.repository import Pango as pango
  from gi.repository import PangoCairo as pangocairo
  use_pygobject = True

try:
  import webcolors
  have_webcolors = True
except ImportError:
  have_webcolors = False


__version__ = '0.9.1'

def cairo_font(tk_font):
  family, size, weight = tk_font
  return pango.FontDescription('{} {} {}'.format(family, weight, size))

def cairo_text_bbox(text, font_params):
  surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 8, 8)
  ctx = cairo.Context(surf)
  font = cairo_font(font_params)

  if use_pygobject:
    layout = pangocairo.create_layout(ctx)
    pctx = layout.get_context()
    fo = cairo.FontOptions()
    fo.set_antialias(cairo.ANTIALIAS_SUBPIXEL)
    pangocairo.context_set_font_options(pctx, fo)
    layout.set_font_description(font)
    layout.set_text(text, len(text))
    re = layout.get_pixel_extents()[1]
    extents = (re.x, re.y, re.x + re.width, re.y + re.height)

  else: # pyGtk
    pctx = pangocairo.CairoContext(ctx)
    pctx.set_antialias(cairo.ANTIALIAS_SUBPIXEL)
    layout = pctx.create_layout()
    layout.set_font_description(font)
    layout.set_text(text)

    #print('@@ EXTENTS:', layout.get_pixel_extents()[1])
    extents = layout.get_pixel_extents()[1]
  w = extents[2] - extents[0]
  h = extents[3] - extents[1]
  x0 = - w // 2.0
  y0 = - h // 2.0
  return [x0,y0, x0+w,y0+h]



class NodeStyle(object):
  def __init__(self, name, node_style=None):
    self.name = name
    self.pattern = '.'
    self.shape = 'bubble'
    self.text_mod = None
    self.text_mod_func = None
    self.font = ['Helvetica', 14, 'bold']
    self.text_color = (0,0,0)
    self.fill = (144,164,174)

    if node_style is None:
      node_style = {}

    for k,v in node_style.iteritems():
      if hasattr(self, k):
        # Check for color styles
        if k.endswith('fill') or k.endswith('color'):
          v = convert_color(v)
        setattr(self, k, v)

    if self.text_mod is not None:
      self.text_mod_func = eval(self.text_mod) # WARNING: eval() on user input

  def __repr__(self):
    keys = (
      'pattern',
      'shape',
      'text_mod',
      'font',
      'text_color',
      'fill')

    ini_keys = ['{} = {}'.format(k, repr(getattr(self, k))) for k in keys]
    return '[{}]\n{}\n'.format(self.name, '\n'.join(ini_keys))


class DrawStyle(object):
  def __init__(self, styles=None, node_styles=[]):
    # Set defaults
    self.line_width = 2
    self.line_color = (0,0,0)
    self.outline_width = 2
    self.padding = 5
    self.max_radius = 9
    self.h_sep = 17
    self.v_sep = 9
    self.arrows = True
    self.title_pos = 'tl'
    self.bullet_fill = (255,255,255)
    self.text_color = (0,0,0)
    self.shadow = True
    self.shadow_fill = (0,0,0, 127)
    self.title_font = ('Helvetica', 22, 'bold')

    # Load any styles
    if styles is None:
      styles = {}

    for k,v in styles.iteritems():
      if hasattr(self, k):
        # Check for color styles
        if k.endswith('_fill') or k.endswith('_color'):
          v = convert_color(v)

        setattr(self, k, v)

    # Set node style defaults
    if len(node_styles) == 0:
      node_styles = [
        ('bubble', {'shape':'bubble', 'pattern':'^\w', 'font':('Helvetica', 14, 'bold'), 'fill':(179, 229, 252)}),
        ('box', {'shape':'box', 'pattern':'^/', 'font':('Times', 14, 'italic'),
                'fill':(144, 164, 174), 'text_mod':'lambda txt: txt[1:]'}),
        ('token', {'shape':'bubble', 'pattern':'.', 'font':('Helvetica', 16, 'bold'), 'fill':(179, 229, 252)}),
      ]

    for _, ns in node_styles:
      if 'text_color' not in ns:
        ns['text_color'] = self.text_color

    # Init node styles
    self.node_styles = [NodeStyle(name, ns) for name,ns in node_styles]

  def __repr__(self):
    keys = ('line_width',
      'outline_width',
      'padding',
      'line_color',
      'max_radius',
      'h_sep',
      'v_sep',
      'arrows',
      'title_pos',
      'bullet_fill',
      'text_color',
      'shadow',
      'shadow_fill',
      'title_font')

    ini_keys = ['{} = {}'.format(k, repr(getattr(self, k))) for k in keys]

    return '[style]\n{}\n'.format('\n'.join(ini_keys))


def convert_color(c):
  rgb = c

  # Check for hex string
  try:
    rgb = hex_to_rgb(rgb)
  except (TypeError, ValueError):
    pass

  # Check for named color
  if have_webcolors:
    try:
      rgb = webcolors.name_to_rgb(rgb)
    except AttributeError:
      pass

  # Restrict to valid range
  rgb = tuple(0 if c < 0 else 255 if c > 255 else c for c in rgb)
  return rgb

def rgb_to_hex(rgb):
  return '#{:02X}{:02X}{:02X}'.format(*rgb[:3])

def hex_to_rgb(hex_color):
  v = int(hex_color[1:], 16)
  b = v & 0xFF
  g = (v >> 8) & 0xFF
  r = (v >> 16) & 0xFF
  return (r,g,b)

def rgb_to_cairo(rgb):
  if len(rgb) == 4:
    r,g,b,a = rgb
    return (r / 255.0, g / 255.0, b / 255.0, a / 255.0)

  else:
    r,g,b = rgb
    return (r / 255.0, g / 255.0, b / 255.0, 1.0)

def parse_style_config(fname):
  if os.path.exists(fname):
    print('Reading styles from "{}"'.format(fname))

  cp = SafeConfigParser()
  cp.read(fname)

  styles = {}

  # Extract all sections into a dictionary
  sd = collections.OrderedDict()
  for sname in cp.sections():
    opts = {}
    for opt in cp.options(sname):
      opts[opt] = ast.literal_eval(cp.get(sname, opt))
    sd[sname] = opts

  # Style section is main set of style settings
  if 'style' in sd:
    styles = sd['style']

  # All remaining sections are node styles
  node_styles = [(k,v) for k,v in sd.iteritems() if k != 'style']

  # Simplify title position
  if 'title_pos' in styles:
    pos = styles['title_pos'].lower()
    pos = pos.replace('top', 't')
    pos = pos.replace('bottom', 'b')
    pos = pos.replace('left', 'l')
    pos = pos.replace('right', 'r')
    pos = pos.replace('center', 'c')
    pos = pos.replace('-', '')
    pos = pos.replace(' ', '')
    styles['title_pos'] = pos

  return DrawStyle(styles, node_styles)

class BaseShape(object):
  def __init__(self):
    self.options = {}
    self._bbox = [0,0,1,1]
    self.tags = set()

  @property
  def points(self):
    return tuple(self._bbox)

  @property
  def bbox(self):
    if 'width' in self.options:
      w = self.options['width'] / 2
    else:
      w = 1

    x0 = self._bbox[0] - w
    y0 = self._bbox[1] - w
    x1 = self._bbox[2] + w
    y1 = self._bbox[3] + w
    return (x0,y0,x1,y1)

  def is_tagged(self, item):
    return item in self.tags

  def update_tags(self):
    if 'tags' in self.options:
      self.tags = self.tags.union(self.options['tags'])
      del self.options['tags']

  def move(self, dx, dy):
    self._bbox[0] += dx
    self._bbox[1] += dy
    self._bbox[2] += dx
    self._bbox[3] += dy

  def dtag(self, tag=None):
    if tag is None:
      self.tags.clear()
    else:
      self.tags.discard(tag)

  def addtag(self, tag=None):
    if tag is not None:
      self.tags.add(tag)

  def draw(self, c):
    pass


class LineShape(BaseShape):
  def __init__(self, x0, y0, x1, y1, options):
    BaseShape.__init__(self)
    self.options = options
    self._bbox = [x0, y0, x1, y1]
    self.update_tags()

class RectShape(BaseShape):
  def __init__(self, x0, y0, x1, y1, options):
    BaseShape.__init__(self)
    self.options = options
    self._bbox = [x0, y0, x1, y1]
    self.update_tags()


class OvalShape(BaseShape):
  def __init__(self, x0, y0, x1, y1, options):
    BaseShape.__init__(self)
    self.options = options
    self._bbox = [x0, y0, x1, y1]
    self.update_tags()

class ArcShape(BaseShape):
  def __init__(self, x0, y0, x1, y1, options):
    BaseShape.__init__(self)
    self.options = options
    self._bbox = [x0, y0, x1, y1]
    self.update_tags()

  @property
  def bbox(self):
    if 'width' in self.options:
      w = self.options['width'] / 2
    else:
      w = 1

    # Calculate bounding box for arc segment
    x0, y0, x1, y1 = self.points
    xc = (x0 + x1) / 2
    yc = (y0 + y1) / 2
    rad = (x1 - x0) / 2
    rad += w

    start = self.options['start'] % 360
    extent = self.options['extent']
    stop = (start + extent) % 360

    if extent < 0:
      start, stop = stop, start  # Swap points so we can rotate CCW

    if stop < start:
      stop += 360 # Make stop greater than start

    angles = [start, stop]

    # Find the extrema of the circle included in the arc
    ortho = (start // 90) * 90 + 90
    while ortho < stop:
      angles.append(ortho)
      ortho += 90 # Rotate CCW


    # Convert all extrema points to cartesian
    points = [(rad * math.cos(a*math.pi / 180), rad * math.sin(a*math.pi / 180)) for a in angles]

    points = zip(*points)
    bx0 = min(points[0]) + xc
    by0 = min(points[1]) + yc
    bx1 = max(points[0]) + xc
    by1 = max(points[1]) + yc

    #print('@@ ARC BB:', (bx0,by0,bx1,by1), rad, angles, start, extent)
    return (bx0,by0,bx1,by1)



class TextShape(BaseShape):
  text_id = 1
  def __init__(self, x0, y0, text_bbox, options):
    BaseShape.__init__(self)
    self.options = options

    if 'anchor' in options:
      anchor = options['anchor'].lower()
    else:
      anchor = 'l'

    bx0,by0, bx1,by1 = text_bbox(options['text'], options['font'])
    w = bx1 - bx0
    h = by1 - by0

    if anchor == 'c':
      x0 -= w//2
      y0 -= h//2

    self._bbox = [x0, y0, x0+w, y0+h]
    #self._bbox = text_bbox(options['text'], options['font'])
    self.update_tags()
    #print('## NEW TEXT:', x0, y0, self._bbox, anchor)

class BubbleShape(BaseShape):
  def __init__(self, x0, y0, x1, y1, options):
    BaseShape.__init__(self)
    self.options = options
    self._bbox = [x0, y0, x1, y1]
    self.update_tags()

class BoxBubbleShape(BaseShape):
  def __init__(self, x0, y0, x1, y1, options):
    BaseShape.__init__(self)
    self.options = options
    self._bbox = [x0, y0, x1, y1]
    self.update_tags()

class HexBubbleShape(BaseShape):
  def __init__(self, x0, y0, x1, y1, options):
    BaseShape.__init__(self)
    self.options = options
    self._bbox = [x0, y0, x1, y1]
    self.update_tags()


def cairo_draw_arrow(head, tail, fill, c):
  width = c.get_line_width()
  c.save()
  dy = head[1] - tail[1]
  dx = head[0] - tail[0]
  angle = math.atan2(dy,dx)
  c.translate(head[0],head[1])
  c.rotate(angle)
  c.scale(width, width)

  # Now positioned to draw arrow at 0,0 with point facing right
  apath = [(-4,0), (-4.5,2), (0,0)]

  mirror = [(x,-y) for x, y in reversed(apath[1:-1])] # Mirror central points
  apath.extend(mirror)

  c.move_to(*apath[0])
  for p in apath[1:]:
    c.line_to(*p)
  c.close_path()

  c.set_source_rgba(*fill)
  c.fill()

  c.restore()

def cairo_draw_text(x, y, text, font, text_color, c):
  c.save()
  #print('## TEXT COLOR:', text_color)
  c.set_source_rgba(*rgb_to_cairo(text_color))
  font = cairo_font(font)

  c.translate(x, y)

  if use_pygobject:
    layout = pangocairo.create_layout(c)
    pctx = layout.get_context()
    fo = cairo.FontOptions()
    fo.set_antialias(cairo.ANTIALIAS_SUBPIXEL)
    pangocairo.context_set_font_options(pctx, fo)
    layout.set_font_description(font)
    layout.set_text(text, len(text))
    pangocairo.update_layout(c, layout)
    pangocairo.show_layout(c, layout)

  else: # pyGtk
    pctx = pangocairo.CairoContext(c)
    pctx.set_antialias(cairo.ANTIALIAS_SUBPIXEL)
    layout = pctx.create_layout()
    layout.set_font_description(font)
    layout.set_text(text)
    pctx.update_layout(layout)
    pctx.show_layout(layout)

  c.restore()


def cairo_draw_shape(shape, c, styles):
  default_pen = rgb_to_cairo(styles.line_color)
  c.set_source_rgba(*default_pen)

  if 'width' in shape.options:
    width = shape.options['width']
  else:
    width = 2.0

  c.set_line_width(width)

  text_color = shape.options['text_color'] if 'text_color' in shape.options \
    else styles.text_color


  if isinstance(shape, TextShape):
    x0, y0, x1, y1 = shape.points
    cairo_draw_text(x0, y0, shape.options['text'], shape.options['font'], text_color, c)

  elif isinstance(shape, LineShape):
    x0, y0, x1, y1 = shape.points

    if 'arrow' not in shape.options:
      c.move_to(x0,y0)
      c.line_to(x1,y1)
      c.stroke()

    else: # Draw line with arrowhead
      if shape.options['arrow'] == 'first':
        head = x0, y0
        tail = x1, y1
      else: # Last
        head = x1, y1
        tail = x0, y0

      # Adjust head point to show gaps between lines
      length = math.sqrt(abs(x1 - x0)**2 + abs(y1 - y0)**2)
      length -= 3
      angle = math.atan2(head[1] - tail[1], head[0] - tail[0])
      #print('# LEN:', length, angle * 180 / math.pi)

      c.save()
      c.translate(*tail)
      c.rotate(angle)
      c.move_to(0,0)
      c.line_to(length,0)
      c.stroke()
      c.restore()

      cairo_draw_arrow(head, tail, default_pen, c)

  elif isinstance(shape, RectShape):
    x0, y0, x1, y1 = shape.points
    c.rectangle(x0,y0, x1-x0,y1-y0)

    stroke = True if shape.options['width'] > 0 else False

    #print('%% RECT:', stroke, shape.options)
    if 'fill' in shape.options:
      c.set_source_rgba(*rgb_to_cairo(shape.options['fill']))
      if stroke:
        c.fill_preserve()
      else:
        c.fill()

    if stroke:
      c.set_source_rgba(*default_pen)
      c.stroke()

  elif isinstance(shape, BubbleShape):
    x0, y0, x1, y1 = shape.points

    stroke = True if shape.options['width'] > 0 else False

    #print('%% BUBBLE:', stroke, shape.points, shape.options)

    rad = (y1 - y0) / 2.0
    left = x0 + rad
    right = x1 - rad

    xc = (x0 + x1) / 2
    yc = (y0 + y1) / 2.0

    if abs(right - left) <= 1: # Circular bubble
      c.arc(xc,yc, rad, 0, 2 * math.pi)
    else: # Rounded box
      c.move_to(xc, y1)
      c.line_to(right, y1)
      c.arc_negative(right,yc, rad, math.pi / 2, -math.pi / 2)
      c.line_to(left, y0)
      c.arc_negative(left,yc, rad, -math.pi / 2, math.pi / 2)
      c.close_path()

    if 'fill' in shape.options:
      c.set_source_rgba(*rgb_to_cairo(shape.options['fill']))
      if stroke:
        c.fill_preserve()
      else:
        c.fill()

    if stroke:
      c.set_source_rgba(*default_pen)
      c.stroke()

#    # Add text bounding box
#    w = x1-x0
#    h = y1-y0
#    bx0, by0, bx1, by1 = cairo_text_bbox(shape.options['text'], shape.options['font'])
#    bw = abs(bx1-bx0)
#    bh = abs(by1-by0)
#    c.rectangle(x0 + (w - bw)//2, y0 + (h - bh)//2, bw, bh)
#    c.set_source_rgba(*default_pen)
#    c.stroke()

    # Add the text
    if 'text' in shape.options:
      x, y = shape.options['text_pos']
      x += (x0 + x1) / 2
      y += (y0 + y1) / 2
      cairo_draw_text(x, y, shape.options['text'], shape.options['font'], text_color, c)

  elif isinstance(shape, HexBubbleShape):
    x0, y0, x1, y1 = shape.points

    stroke = True if shape.options['width'] > 0 else False

    #print('%% HEXBUBBLE:', stroke, shape.points, shape.options)

    rad = (y1 - y0) / 2.0
    left = x0 + rad
    right = x1 - rad
    rpad = rad * 0.5

    xc = (x0 + x1) / 2
    yc = (y0 + y1) / 2.0

    if abs(right - left) <= 1: # Round hex
      left = xc
      right = xc

    c.move_to(xc, y1)
    c.line_to(right+rpad, y1)
    c.line_to(right+rad, yc) # Right point
    c.line_to(right+rpad, y0)
    c.line_to(left-rpad, y0)
    c.line_to(left-rad, yc) # Left point
    c.line_to(left-rpad, y1)
    c.close_path()

    if 'fill' in shape.options:
      c.set_source_rgba(*rgb_to_cairo(shape.options['fill']))
      if stroke:
        c.fill_preserve()
      else:
        c.fill()

    if stroke:
      c.set_source_rgba(*default_pen)
      c.stroke()

#    # Add text bounding box
#    w = x1-x0
#    h = y1-y0
#    bx0, by0, bx1, by1 = cairo_text_bbox(shape.options['text'], shape.options['font'])
#    bw = abs(bx1-bx0)
#    bh = abs(by1-by0)
#    c.rectangle(x0 + (w - bw)//2, y0 + (h - bh)//2, bw, bh)
#    c.set_source_rgba(*default_pen)
#    c.stroke()

    # Add the text
    if 'text' in shape.options:
      x, y = shape.options['text_pos']
      x += (x0 + x1) / 2
      y += (y0 + y1) / 2
      cairo_draw_text(x, y, shape.options['text'], shape.options['font'], text_color, c)


  elif isinstance(shape, BoxBubbleShape):
    x0, y0, x1, y1 = shape.points
    w = x1-x0
    h = y1-y0
    c.rectangle(x0,y0, w,h)

    stroke = True if shape.options['width'] > 0 else False

    #print('%% BOXBUBBLE:', stroke, shape.options)
    if 'fill' in shape.options:
      c.set_source_rgba(*rgb_to_cairo(shape.options['fill']))
      if stroke:
        c.fill_preserve()
      else:
        c.fill()

    if stroke:
      c.set_source_rgba(*default_pen)
      c.stroke()

#    # Add text bounding box
#    bx0, by0, bx1, by1 = cairo_text_bbox(shape.options['text'], shape.options['font'])
#    bw = abs(bx1-bx0)
#    bh = abs(by1-by0)
#    c.rectangle(x0 + (w - bw)//2, y0 + (h - bh)//2, bw, bh)
#    c.set_source_rgba(*default_pen)
#    c.stroke()

    # Add the text
    if 'text' in shape.options:
      x, y = shape.options['text_pos']
      x += (x0 + x1) / 2
      y += (y0 + y1) / 2
      cairo_draw_text(x, y, shape.options['text'], shape.options['font'], text_color, c)

  elif isinstance(shape, OvalShape):
    x0, y0, x1, y1 = shape.points
    xc = (x0 + x1) / 2
    yc = (y0 + y1) / 2
    rad = (x1 - x0) / 2

    c.arc(xc,yc, rad, 0, 2 * math.pi)

    stroke = True if shape.options['width'] > 0 else False

    if 'fill' in shape.options:
      c.set_source_rgba(*rgb_to_cairo(shape.options['fill']))
      if stroke:
        c.fill_preserve()
      else:
        c.fill()

    if stroke:
      c.set_source_rgba(*default_pen)
      c.stroke()


  elif isinstance(shape, ArcShape):
    x0, y0, x1, y1 = shape.points
    xc = (x0 + x1) / 2
    yc = (y0 + y1) / 2
    rad = (x1 - x0) / 2

    start = shape.options['start']
    extent = shape.options['extent']

    # Start and end angles
    sa = -start * math.pi / 180.0
    ea = -(start + extent) * math.pi / 180.0

    # Tk has opposite angle convention from Cairo
    #   Positive extent is a negative rotation in Cairo
    #   Negative extent is a positive rotation in Cairo

    # Arc fill
    if 'fill' in shape.options:
      c.move_to(xc,yc)
      if extent >= 0:
        c.arc_negative(xc,yc, rad, sa, ea)
      else:
        c.arc(xc,yc, rad, sa, ea)
      c.set_source_rgba(*rgb_to_cairo(shape.options['fill']))
      c.fill()

    # Stroke arc segment
    c.new_sub_path()
    if extent >= 0:
      c.arc_negative(xc,yc, rad, sa, ea)
    else:
      c.arc(xc,yc, rad, sa, ea)

    c.set_source_rgba(*default_pen)
    c.stroke()

    #print('%% ARC:', xc, yc, rad, start, extent)


def xml_escape(txt):
    txt = txt.replace('&', '&amp;')
    txt = txt.replace('<', '&lt;')
    txt = txt.replace('>', '&gt;')
    txt = txt.replace('"', '&quot;')
    return txt


def svg_draw_shape(shape, fh, styles):
  default_pen = rgb_to_hex(styles.line_color)

  if 'width' in shape.options:
    width = shape.options['width']
  else:
    width = 2.0

  attrs = {
    'stroke': 'none',
    'fill': '#fff'
  }

  if width > 0:
    attrs['stroke-width'] = width
    attrs['stroke'] = default_pen

  if 'fill' in shape.options:
    attrs['fill'] = rgb_to_hex(shape.options['fill'])

    if len(shape.options['fill']) == 4:
      attrs['fill-opacity'] = shape.options['fill'][3] / 255.0


  if isinstance(shape, TextShape):
    x0, y0, x1, y1 = shape.points
    x = (x0 + x1) / 2 # Center text
    y = y1 - 10 # FIXME: Adjust for baseline offset

    font_name = shape.options['font_name']
    fh.write(u'<text class="{}" x="{}" y="{}">{}</text>\n'.format(font_name, x, y,
      xml_escape(shape.options['text'])))

  elif isinstance(shape, LineShape):
    x0, y0, x1, y1 = shape.points

    # We don't need a fill attribute for lines
    del attrs['fill']

    attributes = ' '.join(['{}="{}"'.format(k,v) for k,v in attrs.iteritems()])

    if 'arrow' not in shape.options:
      fh.write(u'<line x1="{}" y1="{}" x2="{}" y2="{}" {} />\n'.format(
        x0,y0,x1,y1, attributes))
    else: # Draw line with arrowhead
      attributes += ' marker-end="url(#arrow)"'

      if shape.options['arrow'] == 'first':
        head = x0, y0
        tail = x1, y1
      else: # Last
        head = x1, y1
        tail = x0, y0

      # Move end point back to account for arrow marker
      length = math.sqrt(abs(x1 - x0)**2 + abs(y1 - y0)**2)
      length -= 4
      angle = math.atan2(head[1] - tail[1], head[0] - tail[0])

      head = (tail[0] + length * math.cos(angle), tail[1] + length * math.sin(angle))

      fh.write(u'<line x1="{}" y1="{}" x2="{}" y2="{}" {} />\n'.format(
        tail[0],tail[1],head[0],head[1], attributes))


  elif isinstance(shape, RectShape):
    x0, y0, x1, y1 = shape.points
    #c.rectangle(x0,y0, x1-x0,y1-y0)

    attributes = ' '.join(['{}="{}"'.format(k,v) for k,v in attrs.iteritems()])

    fh.write(u'<rect x="{}" y="{}" width="{}" height="{}" {}/>\n'.format(
      x0,y0, x1-x0, y1-y0, attributes))


  elif isinstance(shape, BubbleShape):
    x0, y0, x1, y1 = shape.points

    attributes = ' '.join(['{}="{}"'.format(k,v) for k,v in attrs.iteritems()])

    rad = (y1 - y0) / 2.0
    left = x0 + rad
    right = x1 - rad

    xc = (x0 + x1) / 2
    yc = (y0 + y1) / 2.0

    if abs(right - left) <= 1: # Circular bubble
      fh.write(u'<circle cx="{}" cy="{}" r="{}" {}/>\n'.format(xc, yc, rad, attributes))
    else: # Rounded box
      fh.write(u'<path d="M{},{} A{},{} 0 0,1 {},{} H{} A{},{} 0 0,1 {},{} z" {}/>\n'.format(left,y1, rad,rad,left,y0, right, rad,rad,right,y1,  attributes))

    # Add the text
    if 'text' in shape.options:
      x, y = shape.options['text_pos']
      th = abs(y)
  #    y += (y0 + y1) / 2
      x = (x0 + x1) / 2 # Center in bubble
      y = ((y0 + y1) / 2) + th / 2

      txt = xml_escape(shape.options['text'])
      font_name = shape.options['font_name']
      if 'href' in shape.options and shape.options['href'] is not None: # Hyperlink
        href = shape.options['href']
        fh.write(u'<a xlink:href="{}" target="_parent">\n  <text class="{} link" x="{}" y="{}">{}</text></a>\n'.format(href, font_name, x, y, txt))
      else:
        fh.write(u'<text class="{}" x="{}" y="{}">{}</text>\n'.format(font_name, x, y, txt))

  elif isinstance(shape, HexBubbleShape):
    x0, y0, x1, y1 = shape.points

    attributes = ' '.join(['{}="{}"'.format(k,v) for k,v in attrs.iteritems()])

    rad = (y1 - y0) / 2.0
    left = x0 + rad
    right = x1 - rad
    rpad = rad * 0.5

    xc = (x0 + x1) / 2
    yc = (y0 + y1) / 2.0

    if abs(right - left) <= 1: # Round hex
      left = xc
      right = xc

    fh.write(u'<path d="M{},{} H{} L{},{} L{},{} H{} L{},{} z" {}/>\n'.format(left-rpad,y1,
    right+rpad, right+rad,yc, right+rpad,y0, left-rpad, left-rad,yc,  attributes))

    # Add the text
    if 'text' in shape.options:
      x, y = shape.options['text_pos']
      th = abs(y)
  #    y += (y0 + y1) / 2
      x = (x0 + x1) / 2 # Center in bubble
      y = ((y0 + y1) / 2) + th / 2

      txt = xml_escape(shape.options['text'])
      font_name = shape.options['font_name']
      if 'href' in shape.options and shape.options['href'] is not None: # Hyperlink
        href = shape.options['href']
        fh.write(u'<a xlink:href="{}" target="_parent">\n  <text class="{} link" x="{}" y="{}">{}</text></a>\n'.format(href, font_name, x, y, txt))
      else:
        fh.write(u'<text class="{}" x="{}" y="{}">{}</text>\n'.format(font_name, x, y, txt))


  elif isinstance(shape, BoxBubbleShape):
    x0, y0, x1, y1 = shape.points

    attributes = ' '.join(['{}="{}"'.format(k,v) for k,v in attrs.iteritems()])

    fh.write(u'<rect x="{}" y="{}" width="{}" height="{}" {}/>\n'.format(
      x0,y0, x1-x0, y1-y0, attributes))

    # Add the text
    if 'text' in shape.options:
      x, y = shape.options['text_pos']
      th = abs(y)
      #y += (y0 + y1) / 2
      x = (x0 + x1) / 2 # Center in bubble
      y = ((y0 + y1) / 2) + th / 2

      txt = xml_escape(shape.options['text'])
      font_name = shape.options['font_name']
      if 'href' in shape.options and shape.options['href'] is not None: # Hyperlink
        fh.write(u'<a xlink:href="{}" target="_parent">\n  <text class="{} link" x="{}" y="{}">{}</text></a>\n'.format(shape.options['href'], font_name, x, y, txt))
      else:
        fh.write(u'<text class="{}" x="{}" y="{}">{}</text>\n'.format(font_name, x, y, txt))

  elif isinstance(shape, OvalShape):
    x0, y0, x1, y1 = shape.points
    xc = (x0 + x1) / 2
    yc = (y0 + y1) / 2
    rad = (x1 - x0) / 2

    attributes = ' '.join(['{}="{}"'.format(k,v) for k,v in attrs.iteritems()])

    fh.write(u'<circle cx="{}" cy="{}" r="{}" {}/>\n'.format(xc, yc, rad, attributes))


  elif isinstance(shape, ArcShape):
    x0, y0, x1, y1 = shape.points
    xc = (x0 + x1) / 2
    yc = (y0 + y1) / 2
    rad = (x1 - x0) / 2

    start = shape.options['start'] % 360
    extent = shape.options['extent']
    stop = (start + extent) % 360

    if extent < 0:
      start, stop = stop, start  # Swap points so we can rotate CCW


    # Start and end angles
    sa = start * math.pi / 180.0
    ea = stop * math.pi / 180.0

    attrs['fill'] = 'none'

    attributes = ' '.join(['{}="{}"'.format(k,v) for k,v in attrs.iteritems()])

    xs = xc + rad * math.cos(sa)
    ys = yc - rad * math.sin(sa)
    xe = xc + rad * math.cos(ea)
    ye = yc - rad * math.sin(ea)

    fh.write(u'<path d="M{},{} A{},{} 0 0,0 {},{}" {}/>\n'.format(xs,ys, rad,rad, xe,ye, attributes))



class RailCanvas(object):
  '''This is a clone of the Tk canvas subset used by the original Tcl
     It implements an abstracted canvas that can render objects to different
     backends other than just a Tk canvas widget.
  '''
  def __init__(self, text_bbox=cairo_text_bbox):
    self.text_bbox = text_bbox
    self.shapes = []


  def _get_shapes(self, item=None):
    # Filter shapes
    if item is None or item == 'all':
      shapes = self.shapes
    else:
      shapes = [s for s in self.shapes if s.is_tagged(item)]
    return shapes

  def create_arc(self, x0, y0, x1, y1, **options):
    shape = ArcShape(x0, y0, x1, y1, options)
    self.shapes.append(shape)

  def create_line(self, x0, y0, x1, y1, **options):
    shape = LineShape(x0, y0, x1, y1, options)
    self.shapes.append(shape)

  def create_oval(self, x0, y0, x1, y1, **options):
    shape = OvalShape(x0, y0, x1, y1, options)
    self.shapes.append(shape)

  def create_rectangle(self, x0, y0, x1, y1, **options):
    shape = RectShape(x0, y0, x1, y1, options)
    self.shapes.append(shape)

  def create_bubble(self, x0, y0, x1, y1, **options):
    shape = BubbleShape(x0, y0, x1, y1, options)
    self.shapes.append(shape)

  def create_boxbubble(self, x0, y0, x1, y1, **options):
    shape = BoxBubbleShape(x0, y0, x1, y1, options)
    self.shapes.append(shape)

  def create_hexbubble(self, x0, y0, x1, y1, **options):
    shape = HexBubbleShape(x0, y0, x1, y1, options)
    self.shapes.append(shape)

  def create_text(self, x0, y0, **options):
    shape = TextShape(x0, y0, self.text_bbox, options)
    self.shapes.append(shape)

    # Add a unique tag to serve as an ID
    id_tag = 'id' + str(TextShape.text_id)
    TextShape.text_id += 1
    shape.tags.add(id_tag)
    return id_tag

  def bbox(self, item=None):
    bx0 = 0
    bx1 = 0
    by0 = 0
    by1 = 0

    boxes = [s.bbox for s in self._get_shapes(item)]
    boxes = zip(*boxes)
    if len(boxes) > 0:
      bx0 = min(boxes[0])
      by0 = min(boxes[1])
      bx1 = max(boxes[2])
      by1 = max(boxes[3])

    #print('## BBB', (bx0, by0, bx1, by1), boxes)
    return (bx0, by0, bx1, by1)

  def move(self, item, dx, dy):
    #print('## MOVE 1', item, dx, dy, 'Shapes:', len(self._get_shapes(item)))
    for s in self._get_shapes(item):
      s.move(dx, dy)

  def tag_raise(self, item):
    to_raise = self._get_shapes(item)
    for s in to_raise:
      self.shapes.remove(s)
    self.shapes.extend(to_raise)

  def addtag_withtag(self, tag, item):
    for s in self._get_shapes(item):
      s.addtag(tag)


  def dtag(self, item, tag=None):
    for s in self._get_shapes(item):
      s.dtag(tag)

  def draw(self, c):
    '''Draw all shapes on the canvas'''
    for s in self.shapes:
      tk_draw_shape(s, c)

  def delete(self, item):
    for s in self._get_shapes(item):
      self.shapes.remove(s)



class RailroadLayout(object):
  def __init__(self, canvas, style, url_map=None):
    self.canvas = canvas
    self.tagcnt = 0
    self.style = style
    
    if url_map is None:
      url_map = {}
    self.url_map = url_map

  def get_tag(self, prefix='x', suffix=''):
    self.tagcnt += 1
    return '{}{}{}'.format(prefix, self.tagcnt, suffix)

  def draw_right_turnback(self, tag, x, y0, y1, flow='down'):
    c = self.canvas
    s = self.style

    # Ensure y0 < y1
    y0, y1 = (min(y0,y1), max(y0,y1))

    #if y0 + 2*s.max_radius < y1:  # Two bends
    #print('## RT:', y1, y0, y1-y0, 5*s.max_radius)
    if y1 - y0 > 3*s.max_radius: # Two bends
      xr0 = x - s.max_radius
      xr1 = x + s.max_radius
      # Top curve
      c.create_arc(xr0,y0,xr1,y0+2*s.max_radius, width=s.line_width, start=90, extent=-90, tags=(tag,), style='arc')
      yr0 = y0 + s.max_radius
      yr1 = y1 - s.max_radius
      if abs(yr1-yr0) > s.max_radius*2: # Two line segments with arrow in middle
        half_y = (yr1 + yr0) / 2
        if flow == 'down':
          c.create_line(xr1,yr0,xr1,half_y, width=s.line_width, tags=(tag,), arrow='last')
          c.create_line(xr1,half_y,xr1,yr1, width=s.line_width, tags=(tag,))
        else: # Up
          c.create_line(xr1,yr1,xr1,half_y, width=s.line_width, tags=(tag,), arrow='last')
          c.create_line(xr1,half_y,xr1,yr0, width=s.line_width, tags=(tag,))

      else: # No arrow
        c.create_line(xr1,yr0,xr1,yr1, width=s.line_width, tags=(tag,))
      # Bottom curve
      c.create_arc(xr0,y1-2*s.max_radius,xr1,y1, width=s.line_width, start=0, extent=-90, tags=(tag,), style='arc')
    else: # Single arc turnback
      r = (y1 - y0) / 2
      x0 = x - r
      x1 = x + r
      c.create_arc(x0,y0,x1,y1, width=s.line_width, start=90, extent=-180, tags=(tag,), style='arc')
    
  def draw_left_turnback(self, tag, x, y0, y1, flow='up'):
    c = self.canvas
    s = self.style

    # Ensure y0 < y1
    y0, y1 = (min(y0,y1), max(y0,y1))
    
    #if y0 + 2*s.max_radius < y1: # Two bends
    if y1 - y0 > 3*s.max_radius: # Two bends
      xr0 = x - s.max_radius
      xr1 = x + s.max_radius
      # Top curve
      c.create_arc(xr0,y0,xr1,y0+2*s.max_radius, width=s.line_width, start=90, extent=90, tags=(tag,), style='arc')
      yr0 = y0 + s.max_radius
      yr1 = y1 - s.max_radius
      if abs(yr1-yr0) > s.max_radius*2:
        half_y = (yr1 + yr0) / 2
        if flow == 'down':
          c.create_line(xr0,yr0,xr0,half_y, width=s.line_width, tags=(tag,), arrow='last')
          c.create_line(xr0,half_y,xr0,yr1, width=s.line_width, tags=(tag,))
        else: # Up
          c.create_line(xr0,yr1,xr0,half_y, width=s.line_width, tags=(tag,), arrow='last')
          c.create_line(xr0,half_y,xr0,yr0, width=s.line_width, tags=(tag,))
      else:
        c.create_line(xr0,yr0,xr0,yr1, width=s.line_width, tags=(tag,))
        
      # Bottom curve
      c.create_arc(xr0,y1-2*s.max_radius,xr1,y1, width=s.line_width, start=180, extent=90, tags=(tag,), style='arc')
    else: # Single arc turnback
      r = (y1 - y0) / 2
      x0 = x - r
      x1 = x + r
      c.create_arc(x0,y0,x1,y1, width=s.line_width, start=90, extent=180, tags=(tag,), style='arc')

  def format_text(self, txt):
    s = self.style

    # Default to first node style
    node_style = s.node_styles[0]

    # Check each node pattern for a match
    for ns in s.node_styles:
      if re.match(ns.pattern, txt):
        node_style = ns
        break

    # Apply any text transformation for this style
    if ns.text_mod_func:
      txt = ns.text_mod_func(txt)

    return (txt, node_style)

  def draw_bubble(self, txt):
    tag = self.get_tag()
    c = self.canvas
    s = self.style
    
    if txt is None: # Line for skipped options
      c.create_line(0,0,1,0, width=s.outline_width, tags=(tag,))
      return [tag, 1, 0]
    elif txt == 'bullet': # Small bullet
      w = s.outline_width
      r = w+1
      c.create_oval(0,-r,2*r,r, width=s.outline_width, tags=(tag,), fill=s.bullet_fill)
      return [tag, 2*r, 0]
    else: # Bubble with text inside
      txt, node_style = self.format_text(txt)

      font = node_style.font
      font_name = node_style.name + '_font'
      fill = node_style.fill
      text_color = node_style.text_color

      if txt in self.url_map:
        href = self.url_map[txt]
      else:
        href = None

      id1 = c.create_text(0,0, anchor='c', text=txt, font=font, font_name=font_name,
                        text_color=text_color, tags=(tag,))
      x0, y0, x1, y1 = c.bbox(id1)
      
      #print('## TEXT BBOX', x0,y0,x1,y1, txt)

      h = y1 - y0 + 2

      rad = (h+1) // 2 # Round up
      #rad = h / 2.0
      #top = y0 - 2    # KPT: Not sure why "top" is derived from y0
      btm = y1
      top = btm - 2*rad
#      fudge = int(3*istoken + len(txt)*1.4)
#      left = x0 + fudge
#      right = x1 - fudge
      left = x0
      right = x1
      if node_style.shape in ('bubble', 'hex'):
        left += rad // 2 - 2
        right -= rad // 2 - 2
      else: # Add fixed padding
        left -= 5
        right += 5

      if left > right: # Too mutch fudge: Create a circle from two arcs
        left = (x0 + x1) / 2 # Left and right both at midpoint of text bbox
        right = left
        
      tag2 = self.get_tag(suffix='-box')
      tags = [tag, tag2]

      if node_style.shape == 'bubble': # Rounded bubble
        c.delete(id1)
        c.create_bubble(left-rad, top, right+rad, btm, text=txt, text_pos=(x0,y0),
          font=font, font_name=font_name, text_color=text_color, width=s.outline_width, tags=tags, fill=fill, href=href)

      elif node_style.shape == 'hex': # Hex bubble
        c.delete(id1)
        c.create_hexbubble(left-rad, top, right+rad, btm, text=txt, text_pos=(x0,y0),
          font=font, font_name=font_name, text_color=text_color, width=s.outline_width, tags=tags, fill=fill, href=href)

      else: # Box bubble
        c.delete(id1)
        c.create_boxbubble(left, top, right, btm, text=txt, text_pos=(x0,y0),
          font=font, font_name=font_name, text_color=text_color, width=s.outline_width, tags=tags, fill=fill, href=href)
        
      x0, y0, x1,y1 = c.bbox(tag2)
      #print('## BUBBLE BBOX:', x0, y0, x1, y1)
      width = x1 - x0
      c.move(tag, -x0, 2)
      
      c.tag_raise(id1) # Bring text above any filled bubbles
      
      #print('## BUBBLE EXIT: ({})'.format(txt), width, x0, y0, x1, y1)
      return [tag, width, 0]


  def draw_line(self, lx):
    '''Draw a series of elements from left to right'''
    tag = self.get_tag()
    c = self.canvas
    s = self.style
    
    sep = s.h_sep
    exx = 0
    exy = 0
    
    for term in lx:
      t, texx, texy = self.draw_diagram(term) # Draw each element
      if exx > 0: # Second element onward
        xn = exx + sep # Add space between elements
        c.move(t, xn, exy) # Shift last element forward
        c.create_line(exx-1, exy, xn, exy, tags=(tag,), width=s.line_width, arrow='last') # Connecting line (NOTE: -1 fudge)
        exx = xn + texx # Start at end of this element
      else: # First element
        exx = texx # Start at end of this element
      
      exy = texy
      
      c.addtag_withtag(tag, t) # Retag this element
      c.dtag(t, t) # Drop old tags
    
    if exx == 0: # Nothing drawn, Add a line segment with an arrow in the middle
      exx = sep * 2    
      c.create_line(0,0,sep,0, width=s.line_width, tags=(tag,), arrow='last')
      c.create_line(sep, 0,exx,0, width=s.line_width, tags=(tag,))
      exx = sep
      
    return [tag, exx, exy] # Exit point
    
    
  def draw_backwards_line(self, lx):
    tag = self.get_tag()
    c = self.canvas
    s = self.style
    
    sep = s.h_sep
    exx = 0 # Prev element end point
    exy = 0
    
    lb = reversed(lx) # Reverse so we can draw left to right
    
    for term in lb:
      t, texx, texy = self.draw_diagram(term) # Draw each element
      #tx0, ty0, tx1, ty1 = c.bbox(t)
      #w = tx1 - tx0
      if exx > 0: # Second element onward
        xn = exx + sep # Add space between elements
        c.move(t, xn, 0) # Shift last element forward
        c.create_line(exx,exy,xn,exy, tags=(tag,), width=s.line_width, arrow='first') # Connecting line
        exx = xn + texx # Start at end of this element
      else: # First element
        exx = texx # Start at end of this element

      exy = texy
      c.addtag_withtag(tag, t) # Retag this element
      c.dtag(t, t) # Drop old tags

    if exx == 0: # Nothing drawn, Add a line segment with an arrow in the middle
      c.create_line(0,0,sep,0, width=s.line_width, tags=(tag,))
      exx = sep
      
    return [tag, exx, exy] # Exit point


  def draw_stack(self, indent, lx):
    tag = self.get_tag()
    c = self.canvas
    s = self.style
    
    sep = s.v_sep * 2
    btm = 0
    n = len(lx)
    i = 0
    next_bypass_y = 0
    
    for term in lx:
      bypass_y = next_bypass_y
      if i > 0 and i < n and len(term) > 1 and indent >= 0 and \
        (term[0] == 'opt' or term[0] == 'optx'):
        bypass = 1
        term = ['line', term[1:]]
      else:
        bypass = 0
        next_bypass_y = 0
        
      t, exx, exy = self.draw_diagram(term)
      tx0, ty0, tx1, ty1 = c.bbox(t)
      
      if i == 0:
        btm = ty1
        exit_y = exy
        exit_x = exx
      else:
        enter_y = btm - ty0 + sep*2 + 2
        if bypass:
          next_bypass_y = enter_y - s.max_radius
        if indent < 0: # rightstack
          w = tx1 - tx0
          enter_x = exit_x - w + sep*indent
          ex2 = sep*2 - indent
          if ex2 > enter_x:
            enter_x = ex2
        else: # stack & indentstack
          enter_x = sep*2 + indent
      
        back_y = btm + sep + 1
        
        if bypass_y > 0:
          mid_y = (bypass_y + s.max_radius + back_y) / 2
          c.create_line(bypass_x, bypass_y, bypass_x, mid_y, \
            width=s.line_width, tags=(tag,), arrow='last')
          c.create_line(bypass_x, mid_y, bypass_x, back_y+s.max_radius, \
            width=s.line_width, tags=(tag,))
            
        c.move(t, enter_x, enter_y)
        e2 = exit_x + sep
        c.create_line(exit_x, exit_y, e2, exit_y, \
          width=s.line_width, tags=(tag,))
        self.draw_right_turnback(tag, e2, exit_y, back_y)
        e3 = enter_x - sep
        bypass_x = e3 - s.max_radius
        emid = (e2+e3)/2
        c.create_line(e2, back_y, emid, back_y, \
          width=s.line_width, tags=(tag,), arrow='last')
        c.create_line(emid, back_y, e3, back_y, \
          width=s.line_width, tags=(tag,))
        #r2 = (enter_y - back_y) / 2 # FIXME: unused
        self.draw_left_turnback(tag, e3, back_y, enter_y, 'down')
        c.create_line(e3, enter_y, enter_x, enter_y, \
          width=s.line_width, tags=(tag,), arrow='last')
        exit_x = enter_x + exx
        exit_y = enter_y + exy
          
      c.addtag_withtag(tag, t)
      c.dtag(t, t)
      btm = c.bbox(tag)[3]
      i += 1

    if bypass:
      fwd_y = btm + sep + 1
      mid_y = (next_bypass_y + s.max_radius + fwd_y) / 2
      descender_x = exit_x + s.max_radius
      c.create_line(bypass_x, next_bypass_y, bypass_x, mid_y, \
        width=s.line_width, tags=(tag,), arrow='last')
      c.create_line(bypass_x, mid_y, bypass_x, fwd_y-s.max_radius, \
        width=s.line_width, tags=(tag,))
      c.create_arc(bypass_x, fwd_y - 2*s.max_radius, bypass_x + 2*s.max_radius, fwd_y, \
        width=s.line_width, start=180, extent=90, tags=(tag,), style='arc')
      c.create_arc(exit_x - s.max_radius, exit_y, descender_x, exit_y + 2*s.max_radius, \
        width=s.line_width, start=90, extent=-90, tags=(tag,), style='arc')
      c.create_arc(descender_x, fwd_y - 2*s.max_radius, descender_x + 2*s.max_radius, fwd_y, \
        width=s.line_width, start=180, extent=90, tags=(tag,), style='arc')
      exit_x = exit_x + 2*s.max_radius
      half_x = (exit_x + indent) / 2
      c.create_line(bypass_x + s.max_radius, fwd_y, half_x, fwd_y, \
        width=s.line_width, tags=(tag,), arrow='last')
      c.create_line(halfx_, fwd_y, exit_x, fwd_y, \
        width=s.line_width, tags=(tag,))
      c.create_line(descender_x, exit_y+s.max_radius, descender_x, fwd_y-s.max_radius, \
        width=s.line_width, tags=(tag,), arrow='last')
      exit_y = fwd_y      
      
    width = c.bbox(tag)[2]
    return [tag, exit_x, exit_y]


  def draw_loop(self, forward, back):
    tag = self.get_tag()
    c = self.canvas
    s = self.style
    
    sep = s.h_sep
    vsep = s.v_sep
    

    if isinstance(back, basestring) or back is None:
      back = [back]

    if back[0] == 'line':
      back = back[1:]

    if len(back) == 1:
      if back[0] == ',': # Tight space when loop back is single comma
        vsep = 0
      elif back[0] is None: # Tighten spacing when loop back is just a line
        vsep /= 2

    # Forward section
    ft, fexx, fexy = self.draw_diagram(forward)
    fx0, fy0, fx1, fy1 = c.bbox(ft)
    fw = fx1 - fx0 # Fwd width

    # Backward section
    bt, bexx, bexy = self.draw_backwards_line(back)
    bx0, by0, bx1, by1 = c.bbox(bt)
    bw = bx1 - bx0 # Back width
    dy = fy1 - by0 + vsep # Amount to shift backward objects
    #print('## LOOP:', dy, fy1, by0, vsep)
    c.move(bt, 0, dy) # Move backward objects up above fwd
    # Recompute input and exit points
    biny = dy
    bexy = dy + bexy
    by0 = dy + by0
    by1 = dy + by1

    mxx = 0

    if fw > bw: # Forward is longer
      if fexx < fw and fexx >= bw: # Fwd exit point is left of the right side of fwd
        dx = (fexx - bw) / 2 # Shift backward objects no further than exit point
        c.move(bt, dx, 0)
        bexx = dx + bexx
        # Add extension lines to each side of backward
        c.create_line(0,biny,dx,biny, width=s.line_width, tags=(bt,))
        c.create_line(bexx,bexy,fexx,bexy, width=s.line_width, tags=(bt,), arrow='first')
        mxx = fexx
      else: # Fwd exit is aligned with fwd
        dx = (fw - bw) / 2
        c.move(bt, dx, 0) # Shift backward objects to middle of fwd
        bexx = dx + bexx
        # Add extension lines to each side of backward
        c.create_line(0,biny,dx,biny, width=s.line_width, tags=(bt,))
        c.create_line(bexx,bexy,fx1,bexy, width=s.line_width, tags=(bt,), arrow='first')
        mxx = fexx
      
    elif bw > fw: # Backward is longer
      dx = (bw - fw) / 2
      c.move(ft, dx, 0) # Shift fwd objects to middle of backward
      fexx = dx + fexx
      # Add extension lines to each side of fwd
      c.create_line(0,0,dx,fexy, width=s.line_width, tags=(ft,), arrow='last')
      c.create_line(fexx,fexy,bx1,fexy, width=s.line_width, tags=(ft,))
      mxx = bexx
    
    c.addtag_withtag(tag, bt) # Retag
    c.addtag_withtag(tag, ft)
    c.dtag(bt, bt) # Drop old tags
    c.dtag(ft, ft)
    c.move(tag, sep, 0) # Make space for left turnback
    mxx = mxx + sep
    c.create_line(0,0,sep,0, width=s.line_width, tags=(tag,)) # Feed in line meeting above left turnback
    self.draw_left_turnback(tag, sep, 0, biny, 'up')
    self.draw_right_turnback(tag, mxx, fexy, bexy, 'down')
    #x0, y0, x1, y1 = c.bbox(tag) # Bounds for the entire loop
    exit_x = mxx + s.max_radius # Add radius of right turnback to get full width
    c.create_line(mxx,fexy,exit_x,fexy, width=s.line_width, tags=(tag,)) # Feed out line above right turnback
    
    return [tag, exit_x, fexy]

  def draw_toploop(self, forward, back):
    tag = self.get_tag()
    c = self.canvas
    s = self.style
    
    sep = s.v_sep
    vsep = sep / 2 # Tighten spacing for top loops

    if isinstance(back, basestring) or back is None:
      back = [back]

    if back[0] == 'line':
      back = back[1:]

    ft, fexx, fexy = self.draw_diagram(forward)
    fx0, fy0, fx1, fy1 = c.bbox(ft)
    fw = fx1 - fx0
    bt, bexx, bexy = self.draw_backwards_line(back)
    bx0, by0, bx1, by1 = c.bbox(bt)
    bw = bx1 - bx0
    dy = -(by1 - fy0 + vsep)
    #print('## TLOOP:', dy, by1, fy0, vsep)
    c.move(bt, 0, dy)
    biny = dy
    bexy = dy + bexy
    by0 = dy + by0
    by1 = dy + by1

    mxx = 0

    if fw > bw: # Forward is longer
      dx = (fw - bw) / 2
      c.move(bt, dx, 0) # Shift backward objects to middle of fwd
      bexx = dx + bexx
      # Add extension lines to each side of backward
      c.create_line(0,biny,dx,biny, width=s.line_width, tags=(bt,))
      c.create_line(bexx,bexy,fx1,bexy, width=s.line_width, tags=(bt,), arrow='first')
      mxx = fexx
    elif bw > fw: # Backward is longer
      dx = (bw - fw) / 2
      c.move(ft, dx, 0) # Shift fwd objects to middle of backward
      fexx = dx + fexx
      # Add extension lines to each side of fwd
      c.create_line(0,0,dx,fexy, width=s.line_width, tags=(ft,))
      c.create_line(fexx,fexy,bx1,fexy, width=s.line_width, tags=(ft,))
      mxx = bexx

    c.addtag_withtag(tag, bt) # Retag
    c.addtag_withtag(tag, ft)
    c.dtag(bt, bt) # Drop old tags
    c.dtag(ft, ft)
    c.move(tag, sep, 0) # Make space for left turnback
    mxx = mxx + sep
    c.create_line(0,0,sep,0, width=s.line_width, tags=(tag,)) # Feed in line meeting below left turnback
    self.draw_left_turnback(tag, sep, 0, biny, 'down')
    self.draw_right_turnback(tag, mxx, fexy, bexy, 'up')
    x0, y0, x1, y1 = c.bbox(tag)
    c.create_line(mxx,fexy,x1,fexy, width=s.line_width, tags=(tag,)) # Feed out line below right turnback
    
    return [tag, x1, fexy]


  def draw_or(self, lx):
    tag = self.get_tag()
    c = self.canvas
    s = self.style

    sep = s.v_sep
    vsep = sep / 2
    
    n = len(lx)
    m = {}
    mxw = 0
    
    for i, term in enumerate(lx):
      m[i] = mx = self.draw_diagram(term)
      tx = mx[0]
      x0, y0, x1, y1 = c.bbox(tx)
      w = x1 - x0
      if i > 0:
        w += 20 # Extra space for arrowheads
      if w > mxw:
        mxw = w

    x0 = 0
    x1 = sep
    x2 = sep * 2
    xc = mxw / 2
    x3 = mxw + x2
    x4 = x3 + sep
    x5 = x4 + sep
    
    for i in xrange(len(lx)):
      t, texx, texy = m[i]
      tx0, ty0, tx1, ty1 = c.bbox(t)
      w = tx1 - tx0
      dx = (mxw - w) / 2 + x2
      if w > 10 and dx > x2 + 10:
        dx = x2 + 10
      c.move(t, dx, 0)
      texx = texx + dx
      m[i] = [t, texx, texy]
      tx0, ty0, tx1, ty1 = c.bbox(t)
      if i == 0:
        ax = 'last' if dx > x2 else 'none'
        c.create_line(0,0,dx,0, width=s.line_width, tags=(tag,), arrow=ax)
        c.create_line(texx,texy,x5+1,texy, width=s.line_width, tags=(tag,))
        exy = texy
        c.create_arc(-sep,0,sep,sep*2, width=s.line_width, start=90, extent=-90, tags=(tag,), style='arc')
        btm = ty1
        
      else:
        dy = btm - ty0 + vsep
        if dy < 2*sep:
          dy = 2*sep
        c.move(t, 0, dy)
        texy = texy + dy
        if dx > x2:
          c.create_line(x2,dy,dx,dy, width=s.line_width, tags=(tag,), arrow='last')
          ax = 'last' if dx < xc-2 else 'none'
          c.create_line(texx,texy,x3,texy, width=s.line_width, tags=(tag,), arrow=ax)
        y1 = dy - 2*sep
        c.create_arc(x1,y1,x1+2*sep,dy, width=s.line_width, start=180, extent=90, style='arc', tags=(tag,))
        y2 = texy - 2*sep
        c.create_arc(x3-sep,y2,x4,texy, width=s.line_width, start=270, extent=90, style='arc', tags=(tag,))
        if i == len(lx)-1:
          c.create_arc(x4,exy,x4+2*sep,exy+2*sep, width=s.line_width, start=180, extent=-90, style='arc', tags=(tag,))
          c.create_line(x1,dy-sep,x1,sep, width=s.line_width, tags=(tag,))
          c.create_line(x4,texy-sep,x4,exy+sep, width=s.line_width, tags=(tag,))
        btm = ty1 + dy
        
      c.addtag_withtag(tag, t)
      c.dtag(t, t)
      
    return [tag, x5, exy]

    
  def draw_diagram(self, spec):
    if isinstance(spec, basestring):
      spec = [spec]
  
    if spec is None:
      return self.draw_bubble(spec)
    if len(spec) == 1:
      return self.draw_bubble(spec[0])
    elif len(spec) == 0:
      return self.draw_bubble(None)
    else:
      if spec[0] == 'line':
        return self.draw_line(spec[1:])
      elif spec[0] == 'stack':
        return self.draw_stack(0, spec[1:])
      elif spec[0] == 'indentstack':
        hsep = self.style.h_sep * spec[1]
        return self.draw_stack(hsep, spec[2:])
      elif spec[0] == 'rightstack':
        return self.draw_stack(-1, spec[1:])
      elif spec[0] == 'loop':
        return self.draw_loop(spec[1], spec[2])
      elif spec[0] == 'toploop':
        return self.draw_toploop(spec[1], spec[2])
      elif spec[0] == 'or':
        return self.draw_or(spec[1:])
      elif spec[0] == 'opt':
        args = spec[1:]
        if len(args) == 1:
          return self.draw_or([None, args])
        else: # All args on one line
          return self.draw_or([None, ['line'] + args])
      elif spec[0] == 'optx': # opt with pass through on bottom
        args = spec[1:]
        if len(args) == 1:
          return self.draw_or([args, None])
        else: # All args on one line
          return self.draw_or([['line'] + args, None])

      elif spec[0] == 'optloop': # opt with all args in a loop
        args = spec[1:]
        return self.draw_or([None, ['loop'] + args])
        
      elif spec[0] == 'tailbranch':
        # NOTE: The original Tcl had a draw_tail_branch proc that was unused here
        return self.draw_or(spec[1:])
      else:
        raise ValueError('Unrecognized diagram element: "{}"'.format(spec[0]))
        
    return None


svg_header = u'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!-- Created by Syntax-Trax http://kevinpt.github.io/syntax-trax -->
<svg xmlns="http://www.w3.org/2000/svg"
xmlns:xlink="http://www.w3.org/1999/xlink"
xml:space="preserve"
width="{}" height="{}" version="1.1">
<style type="text/css">
<![CDATA[
{}
.label {{fill:#000;
  text-anchor:middle;
  font-size:16pt; font-weight:bold; font-family:Sans;}}
.link {{fill: #0D47A1;}}
.link:hover {{fill: #0D47A1; text-decoration:underline;}}
.link:visited {{fill: #4A148C;}}
]]>
</style>
<defs>
  <marker id="arrow" markerWidth="5" markerHeight="4" refX="2.5" refY="2" orient="auto" markerUnits="strokeWidth">
    <path d="M0,0 L0.5,2 L0,4 L4.5,2 z" fill="{}" />
  </marker>
</defs>
'''

def render_railroad(spec, title, url_map, out_file, backend, styles, scale, transparent):
  print('Rendering to {} using {} backend'.format(out_file, backend))
  rc = RailCanvas(cairo_text_bbox)

  layout = RailroadLayout(rc, styles, url_map)
  layout.draw_diagram(spec)

  if title is not None: # Add title
    pos = styles.title_pos

    x0,y0,x1,y1 = rc.bbox('all')
    
    tid = rc.create_text(0, 0, anchor='l', text=title, font=styles.title_font,
      font_name='title_font')

    tx0, ty0, tx1, ty1 = rc.bbox(tid)
    h = ty1 - ty0
    w = tx1 - tx0
    
    mx = x0 if 'l' in pos else (x1 + x0 - w) / 2  if 'c' in pos else x0 + x1 - w
    my = (y0 - h - styles.padding) if 't' in pos else (y1 - y0 - styles.padding)

    rc.move(tid, mx, my)

  x0,y0,x1,y1 = rc.bbox('all')

  W = int((x1 - x0 + 2*styles.padding) * scale)
  H = int((y1 - y0 + 2*styles.padding) * scale)

  if not styles.arrows: # Remove arrow heads
    for s in rc.shapes:
      if 'arrow' in s.options:
        del s.options['arrow']

  if styles.shadow: # Draw shadows first
    bubs = [copy.deepcopy(s) for s in rc.shapes
      if isinstance(s, BoxBubbleShape) or isinstance(s, BubbleShape) or isinstance(s, HexBubbleShape)]

    # Remove all text and offset shadow
    for s in bubs:
      del s.options['text']
      s.options['fill'] = styles.shadow_fill
      w = s.options['width']
      s.options['width'] = 0
      s.move(w+1,w+1)

    # Put rest of shapes after the shadows
    bubs.extend(rc.shapes)
    rc.shapes = bubs


  if backend == 'svg':

    # Reposition all shapes in the viewport
    for s in rc.shapes:
      s.move(-x0 + styles.padding, -y0 + styles.padding)

    # Generate CSS for fonts
    text_color = rgb_to_hex(styles.text_color)
    css = []

    fonts = {}
    # Collect fonts from common styles
    for f in [k for k in dir(styles) if k.endswith('_font')]:
      fonts[f] = (getattr(styles, f), text_color)
    # Collect node style fonts
    for ns in styles.node_styles:
      fonts[ns.name + '_font'] = (ns.font, rgb_to_hex(ns.text_color))

    for f, fs in fonts.iteritems():
      family, size, weight = fs[0]
      text_color = fs[1]

      if weight == 'italic':
        style = 'italic'
        weight = 'normal'
      else:
        style = 'normal'

      css.append('''.{} {{fill:{}; text-anchor:middle;
    font-family:{}; font-size:{}pt; font-weight:{}; font-style:{};}}'''.format(f,
      text_color, family, size, weight, style))


    font_styles = '\n'.join(css)
    line_color = rgb_to_hex(styles.line_color)

    with io.open(out_file, 'w', encoding='utf-8') as fh:
      fh.write(svg_header.format(W,H, font_styles, line_color))
      if not transparent:
        fh.write(u'<rect width="100%" height="100%" fill="white"/>')
      for s in rc.shapes:
        svg_draw_shape(s, fh, styles)
      fh.write(u'</svg>')

  else: # Cairo backend
    ext = os.path.splitext(out_file)[1].lower()

    if ext == '.svg':
      surf = cairo.SVGSurface(out_file, W, H)
    elif ext == '.pdf':
      surf = cairo.PDFSurface(out_file, W, H)
    elif ext in ('.ps', '.eps'):
      surf = cairo.PSSurface(out_file, W, H)
      if ext == '.eps':
        surf.set_eps(True)
    else: # Bitmap
      surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)

    ctx = cairo.Context(surf)

    if not transparent:
      # Fill background
      ctx.rectangle(0,0, W,H)
      ctx.set_source_rgba(1.0,1.0,1.0)
      ctx.fill()

    ctx.scale(scale, scale)
    ctx.translate(-x0 + styles.padding, -y0 + styles.padding)

    for s in rc.shapes:
      cairo_draw_shape(s, ctx, styles)

    if ext in ('.svg', '.pdf', '.ps', '.eps'):
      surf.show_page()
    else:
      surf.write_to_png(out_file)



def line(*args):
  return ['line'] + list(args)

def loop(fwd, back):
  return ['loop', fwd, back]

def toploop(fwd, back):
  return ['toploop', fwd, back]

def choice(*args):
  return ['or'] + list(args)

def opt(*args):
  return ['opt'] + list(args)

def optx(*args):
  return ['optx'] + list(args)

def optloop(fwd, back):
  return ['optloop', fwd, [back]]


def stack(*args):
  return ['stack'] + list(args)

def rightstack(*args):
  return ['rightstack'] + list(args)

def indentstack(indent, *args):
  return ['indentstack', indent] + list(args)


url_map_re = re.compile(r'^\s*url_map\s*=\s*')

def parse_spec_file(fname):
  # Read input diagram
  with io.open(fname, 'r', encoding='utf-8') as fh:
    spec_lines = fh.readlines()

  map_line = -1
  # Split off any url_map
  for i,l in enumerate(spec_lines):
    if url_map_re.match(l):
      map_line = i
      break

  if map_line >= 0:
    spec = ''.join(spec_lines[:map_line])
    url_map = ''.join(spec_lines[map_line:])
    # Strip off assignment
    url_map = url_map_re.sub('', url_map)
  else: # No URL map
    spec = ''.join(spec_lines)
    url_map = '{}'


  # Parse the spec into an object
  spec = eval(spec) # FIXME: Unsafe

  # Add start and end bullets
  spec = ['line', 'bullet', spec, 'bullet']

  url_map = ast.literal_eval(url_map)

  return spec, url_map

def dump_style_ini(ini_file):
  keys= ('line_width',
    'outline_width',
    'padding',
    'line_color',
    'max_radius',
    'h_sep',
    'v_sep',
    'arrows',
    'title_pos',
    'bullet_fill',
    'text_color',
    'shadow',
    'shadow_fill',
    'title_font')

  defaults = DrawStyle()

  if os.path.exists(ini_file):
    print('Ini file "{}" exists'.format(ini_file))
    return

  print('Creating ini with default styles in "{}"'.format(ini_file))
  with open(ini_file, 'w') as fh:
    fh.write(str(defaults))
    for ns in defaults.node_styles:
      fh.write('\n')
      fh.write(str(ns))

def parse_args():
  parser = argparse.ArgumentParser(description='Railroad diagram generator')
  parser.add_argument('-i', '--input', dest='input', action='store', help='Diagram spec file')
  parser.add_argument('-o', '--output', dest='output', action='store', help='Output file')
  parser.add_argument('-s', '--style', dest='styles', action='store', default='syntrax.ini', help='Style config file')
  parser.add_argument('--title', dest='title', action='store', help='Diagram title')
  parser.add_argument('-t', '--transparent', dest='transparent', action='store_true',
    default=False, help='Transparent background')
  parser.add_argument('--scale', dest='scale', action='store', default='1', help='Scale image')
  parser.add_argument('-v', '--version', dest='version', action='store_true', default=False, help='Syntrax version')
  parser.add_argument('--get-style', dest='get_style', action='store_true', default=False,
    help='Create default style .ini')


  args, unparsed = parser.parse_known_args()
  
  if args.version:
    print('Syntrax {}'.format(__version__))
    sys.exit(0)

  if args.get_style:
    dump_style_ini('syntrax.ini')
    sys.exit(0)

  # Allow file to be passed in without -i
  if args.input is None and len(unparsed) > 0:
    args.input = unparsed[0]

  if args.input is None:
    print('Error: input file is required')
    sys.exit(1)
    
  if args.output is None: # Default to png
    args.output = os.path.splitext(args.input)[0] + '.png'

  if args.output.lower() in ('png', 'svg', 'pdf', 'ps', 'eps'):
    args.output = os.path.splitext(args.input)[0] + '.' + args.output.lower()

  args.scale = float(args.scale)
  
  return args


def main():  
  args = parse_args()
  
  # Process styles
  styles = parse_style_config(args.styles)

  spec, url_map = parse_spec_file(args.input)

  #print('## spec', spec)

  # Force SVG backend for SVG output
  backend = 'cairo'
  if os.path.splitext(args.output)[1].lower() == '.svg':
    backend = 'svg'
  
  #title = 'JSON syntax number'
  #title = None

  render_railroad(spec, args.title, url_map, args.output, backend, styles, args.scale, args.transparent)
  

if __name__ == '__main__':
  main()

