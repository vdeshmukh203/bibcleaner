"""
bibcleaner – BibTeX deduplication and normalisation tool.

The installed package uses a flat-module layout (``bibcleaner.py`` at the
project root, declared via ``py-modules`` in ``pyproject.toml``).  This
``src/bibcleaner/`` directory is kept for development reference; it is *not*
included in the built distribution.

All public symbols are available by importing the top-level module::

    import bibcleaner as bc
    entries = bc.parse_bibtex(text)
"""

__version__ = "0.1.0"
__author__ = "Vaibhav Deshmukh"
__license__ = "MIT"
