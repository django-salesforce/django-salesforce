#!/usr/bin/env python

"""
A hook into setuptools for Git.
"""

import locale
import os
from subprocess import Popen, PIPE
import sys

if sys.version_info[0] >= 3:
    def u(s, encoding):
        if not isinstance(s, str):
            s = s.decode(encoding)
        return s
else:
    def u(s, encoding):
        return s

def gitlsfiles(dirname=""):
    try:
        p = Popen(['git', 'ls-files', dirname], stdout=PIPE, stderr=PIPE)
        p.stderr.close()
        files = p.stdout.readlines()
    except:
        # Something went terribly wrong but the setuptools doc says we
        # must be strong in the face of danger.  We shall not run away
        # in panic.
        return []
    if p.wait():
        # git chocked
        return []
    encoding = locale.getpreferredencoding()
    return [u(f.strip(), encoding) for f in files]

if __name__ == "__main__":
    import sys
    from pprint import pprint

    if len(sys.argv) != 2:
        print("USAGE: %s DIRNAME" % sys.argv[0])
        sys.exit(1)

    pprint(gitlsfiles(sys.argv[1]))
