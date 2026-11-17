"""Muralis's version, in its own module.

Kept apart from ``muralis/__init__.py`` so that modules imported *by* the
package initialiser can read the version without depending on the package being
fully initialised — which is how import cycles start.
"""

__version__ = "0.5.0"
