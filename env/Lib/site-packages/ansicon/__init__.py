# -*- coding: utf-8 -*-
# Copyright 2019 Avram Lubkin, All Rights Reserved

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
**ANSICON Python module**
A Python wrapper for loading Jason Hood's ANSICON

ANSICON can be found at https://github.com/adoxa/ansicon
"""

import ctypes
from ctypes import wintypes
import os
import sys

KERNEL32 = ctypes.windll.kernel32
KERNEL32.FreeLibrary.argtypes = (wintypes.HANDLE,)
KERNEL32.FreeLibrary.restype = wintypes.BOOL


def _get_dll_path():
    """
    Determines the path of the ANSICON DLL
    """

    directory = os.path.dirname(os.path.abspath(__file__))
    dll = 'ANSI64.dll' if sys.maxsize > 2**31 else 'ANSI32.dll'
    return os.path.join(directory, dll)


class _Loader(object):
    """
    DLL Loader
    Keeps track of DLL handle for unloading
    """

    def __init__(self):
        self.dll = None

    def load(self):
        """
        Load the DLL
        Does nothing if the DLL is already loaded.
        Will raise an exception, most likely WindowsError, if it fails.
        """

        if self.dll is None:
            self.dll = ctypes.WinDLL(_get_dll_path(), use_last_error=True)

    def unload(self):
        """
        Unload the DLL
        Does nothing if the DLL has not been loaded.
        Will raise a WindowsError exception if it fails.
        """

        if self.dll is None:
            return

        if not KERNEL32.FreeLibrary(self.dll._handle):  # pylint: disable=protected-access
            raise ctypes.WinError(ctypes.get_last_error())
        self.dll = None

    def loaded(self):
        """
        Returns True if the the DLL was previously loaded
        """

        return self.dll is not None


_ANSICON = _Loader()
load = _ANSICON.load  # pylint: disable=invalid-name
unload = _ANSICON.unload  # pylint: disable=invalid-name
loaded = _ANSICON.loaded  # pylint: disable=invalid-name
