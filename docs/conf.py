#!/usr/bin/env python3
# vim: set et sw=4 sts=4 fileencoding=utf-8:

import sys
import os
import pkginfo
from datetime import datetime

on_rtd = os.environ.get('READTHEDOCS', None) == 'True'
info = pkginfo.Installed('pictl')

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
project = info.package_name
copyright = '2019-%s %s' % (datetime.now().year, info.author)
version = info.version
release = info.version
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
    'python': ('https://docs.python.org/3.5', None),
}
intersphinx_cache_limit = 7

# -- Options for HTML output ----------------------------------------------

if on_rtd:
    html_theme = 'sphinx_rtd_theme'
    pygments_style = 'default'
    #html_theme_options = {}
    #html_sidebars = {}
else:
    html_theme = 'default'
    #html_theme_options = {}
    #html_sidebars = {}
html_title = '%s %s Documentation' % (project, version)
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
htmlhelp_basename = '%sdoc' % info.package_name

# Hack to make wide tables work properly in RTD
# See https://github.com/snide/sphinx_rtd_theme/issues/117 for details
def setup(app):
    app.add_stylesheet('style_override.css')

# -- Options for LaTeX output ---------------------------------------------

#latex_engine = 'pdflatex'

latex_elements = {
    'papersize': 'a4paper',
    'pointsize': '10pt',
    'preamble': r'\def\thempfootnote{\arabic{mpfootnote}}', # workaround sphinx issue #2530
}

latex_documents = [
    (
        'index',                       # source start file
        '%s.tex' % project,            # target filename
        '%s %s Documentation' % (project, version), # title
        info.author,                   # author
        'manual',                      # documentclass
        True,                          # documents ref'd from toctree only
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
epub_author = info.author
epub_identifier = 'https://pictl.readthedocs.io/'
#epub_tocdepth = 3
epub_show_urls = 'no'
#epub_use_index = True

# -- Options for manual page output ---------------------------------------

man_pages = [
    ('pictl',  'pictl',        'pictl manual', [info.author], 1),
    ('help',   'pictl-help',   'pictl manual', [info.author], 1),
    ('status', 'pictl-status', 'pictl manual', [info.author], 1),
    ('get',    'pictl-get',    'pictl manual', [info.author], 1),
    ('set',    'pictl-set',    'pictl manual', [info.author], 1),
    ('save',   'pictl-save',   'pictl manual', [info.author], 1),
    ('load',   'pictl-load',   'pictl manual', [info.author], 1),
    ('diff',   'pictl-diff',   'pictl manual', [info.author], 1),
    ('show',   'pictl-show',   'pictl manual', [info.author], 1),
    ('list',   'pictl-list',   'pictl manual', [info.author], 1),
    ('remove', 'pictl-remove', 'pictl manual', [info.author], 1),
    ('rename', 'pictl-rename', 'pictl manual', [info.author], 1),
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
