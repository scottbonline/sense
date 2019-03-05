import sys
from .Senseable import Senseable
from .sense_exceptions import *

if sys.version_info >= (3, 6):
    from .ASyncSenseable import ASyncSenseable

__version__ = "0.6.0"
