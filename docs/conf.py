#!/usr/bin/env python3
#
# Copyright (c) 2020 Canonical Ltd.
# Copyright (c) 2020 Dave Jones <dave@waveform.org.uk>
#
# This file is part of pibootctl.
#
# pibootctl is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pibootctl is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pibootctl.  If not, see <https://www.gnu.org/licenses/>.

# vim: set et sw=4 sts=4 fileencoding=utf-8:

import sys
import os
from pathlib import Path
from datetime import datetime
from setuptools.config import read_configuration

on_rtd = os.environ.get('READTHEDOCS', None) == 'True'
config = read_configuration(str(Path(__file__).parent / '..' / 'setup.cfg'))
info = config['metadata']

# -- General configuration ------------------------------------------------

extensions = ['sphinx.ext.autodoc', 'sphinx.ext.viewcode', 'sphinx.ext.intersphinx']
if on_rtd:
    needs_sphinx = '1.4.0'
    extensions.append('sphinx.ext.imgmath')
    imgmath_image_format = 'svg'
    tags.add('rtd')
else:
    extensions.append('sphinx.ext.mathjax')
    mathjax_path = '/usr/share/javascript/mathjax/MathJax.js?config=TeX-AMS_HTML'

templates_path = ['_templates']
source_suffix = '.rst'
#source_encoding = 'utf-8-sig'
master_doc = 'index'
project = info['name']
copyright = '2019-{now:%Y} {info[author]}'.format(now=datetime.now(), info=info)
version = info['version']
#release = None
#language = None
#today_fmt = '%B %d, %Y'
exclude_patterns = ['_build']
highlight_language = 'python3'
#default_role = None
#add_function_parentheses = True
#add_module_names = True
#show_authors = False
pygments_style = 'sphinx'
#modindex_common_prefix = []
#keep_warnings = False

# -- Autodoc configuration ------------------------------------------------

autodoc_member_order = 'groupwise'

# -- Intersphinx configuration --------------------------------------------

intersphinx_mapping = {
    'python': ('https://docs.python.org/3.7', None),
}
intersphinx_cache_limit = 7

# -- Options for HTML output ----------------------------------------------

html_theme = 'sphinx_rtd_theme'
pygments_style = 'default'
#html_theme_options = {}
#html_sidebars = {}
html_title = '{info[name]} {info[version]} Documentation'.format(info=info)
#html_theme_path = []
#html_short_title = None
#html_logo = None
#html_favicon = None
html_static_path = ['_static']
#html_extra_path = []
#html_last_updated_fmt = '%b %d, %Y'
#html_use_smartypants = True
#html_additional_pages = {}
#html_domain_indices = True
#html_use_index = True
#html_split_index = False
#html_show_sourcelink = True
#html_show_sphinx = True
#html_show_copyright = True
#html_use_opensearch = ''
#html_file_suffix = None
htmlhelp_basename = '{info[name]}doc'.format(info=info)

# Hack to make wide tables work properly in RTD
# See https://github.com/snide/sphinx_rtd_theme/issues/117 for details
#def setup(app):
#    app.add_stylesheet('style_override.css')

# -- Options for LaTeX output ---------------------------------------------

latex_engine = 'xelatex'

latex_elements = {
    'papersize': 'a4paper',
    'pointsize': '10pt',
    'preamble': r'\def\thempfootnote{\arabic{mpfootnote}}', # workaround sphinx issue #2530
}

latex_documents = [
    (
        'index',           # source start file
        project + '.tex',  # target filename
        html_title,        # title
        info['author'],    # author
        'manual',          # documentclass
        True,              # documents ref'd from toctree only
    ),
]

#latex_logo = None
#latex_use_parts = False
latex_show_pagerefs = True
latex_show_urls = 'footnote'
#latex_appendices = []
#latex_domain_indices = True

# -- Options for epub output ----------------------------------------------

epub_basename = project
#epub_theme = 'epub'
#epub_title = html_title
epub_author = info['author']
epub_identifier = 'https://{info[name]}.readthedocs.io/'.format(info=info)
#epub_tocdepth = 3
epub_show_urls = 'no'
#epub_use_index = True

# -- Options for manual page output ---------------------------------------

man_pages = [
    (info['name'], info['name'],                         '{info[name]} manual'.format(info=info), [info['author']], 1),
    ('help',    '{info[name]}-help'.format(info=info),   '{info[name]} manual'.format(info=info), [info['author']], 1),
    ('status',  '{info[name]}-status'.format(info=info), '{info[name]} manual'.format(info=info), [info['author']], 1),
    ('get',     '{info[name]}-get'.format(info=info),    '{info[name]} manual'.format(info=info), [info['author']], 1),
    ('set',     '{info[name]}-set'.format(info=info),    '{info[name]} manual'.format(info=info), [info['author']], 1),
    ('save',    '{info[name]}-save'.format(info=info),   '{info[name]} manual'.format(info=info), [info['author']], 1),
    ('load',    '{info[name]}-load'.format(info=info),   '{info[name]} manual'.format(info=info), [info['author']], 1),
    ('diff',    '{info[name]}-diff'.format(info=info),   '{info[name]} manual'.format(info=info), [info['author']], 1),
    ('show',    '{info[name]}-show'.format(info=info),   '{info[name]} manual'.format(info=info), [info['author']], 1),
    ('list',    '{info[name]}-list'.format(info=info),   '{info[name]} manual'.format(info=info), [info['author']], 1),
    ('remove',  '{info[name]}-remove'.format(info=info), '{info[name]} manual'.format(info=info), [info['author']], 1),
    ('rename',  '{info[name]}-rename'.format(info=info), '{info[name]} manual'.format(info=info), [info['author']], 1),
]

man_show_urls = True

# -- Options for Texinfo output -------------------------------------------

texinfo_documents = []

#texinfo_appendices = []
#texinfo_domain_indices = True
#texinfo_show_urls = 'footnote'
#texinfo_no_detailmenu = False

# -- Options for linkcheck builder ----------------------------------------

linkcheck_retries = 3
linkcheck_workers = 20
linkcheck_anchors = True
