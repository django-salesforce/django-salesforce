import os
import time
from collections import namedtuple

from django.core.files.storage import (
    get_storage_class as _get_storage_class
)
from paramiko import SFTPServerInterface, SFTPServer, SFTPAttributes
from paramiko.common import DEBUG
from paramiko.sftp import Message, SFTP_OK


from django_sftp.handler import StubSFTPHandle

PseudoStat = namedtuple(
    'PseudoStat',
    [
        'st_size', 'st_mtime', 'st_nlink', 'st_mode', 'st_uid', 'st_gid',
        'st_dev', 'st_ino', 'st_atime'
    ])


class StubSFTPServer(SFTPServer):

    def start_subsystem(self, name, transport, channel):
        self.sock = channel
        self._log(DEBUG, 'Started sftp server on channel %s' % repr(channel))
        self._send_server_version()
        self.server.session_started()
        while True:
            try:
                t, data = self._read_packet()
            except EOFError:
                return
            except Exception:
                return
            msg = Message(data)
            request_number = msg.get_int()
            try:
                self._process(t, request_number, msg)
            except Exception:
                # send some kind of failure message, at least
                try:
                    self._send_status(request_number, SFTP_OK)
                except:
                    pass


class StubSFTPServerInterface(SFTPServerInterface):
    # assume current folder is a fine root
    # (the tests always create and eventualy delete a subfolder, so there shouldn't be any mess)
    ROOT = '/'  # os.getcwd()
    storage_class = None
    server_interface = None

    def __init__(self, server, *largs, **kwargs):
        """
        Create a new SFTPServerInterface object.  This method does nothing by
        default and is meant to be overridden by subclasses.

        :param .ServerInterface server:
            the server object associated with this channel and SFTP subsystem
        """
        super(StubSFTPServerInterface, self).__init__(server, *largs, **kwargs)
        self.storage = self.get_storage()
        self.server_interface = server
        self.ROOT = self.server_interface.get_home_dir()

    def session_started(self):
        """
        The SFTP server session has just started.  This method is meant to be
        overridden to perform any necessary setup before handling callbacks
        from SFTP operations.
        """
        pass

    def session_ended(self):
        """
        The SFTP server session has just ended, either cleanly or via an
        exception.  This method is meant to be overridden to perform any
        necessary cleanup before this `.SFTPServerInterface` object is
        destroyed.
        """
        pass

    def get_storage_class(self):
        if self.storage_class is None:
            return _get_storage_class()
        return self.storage_class

    def get_storage(self):
        storage_class = self.get_storage_class()
        return storage_class()

    def _realpath(self, path):
        root = self.ROOT
        if self.ROOT.endswith('/'):
            root = self.ROOT[:-1]
        return root + self.canonicalize(path)

    def list_folder(self, path):
        path = self._realpath(path)
        out = []
        directories, files = self.storage.listdir(path)
        flist = [name + '/' for name in directories if name] + [name for name in files if name]
        for fname in flist:
            attr = SFTPAttributes.from_stat(self.stat(os.path.join(path, fname)))
            attr.filename = fname.replace('/', '')
            out.append(attr)
        return out

    def stat(self, path):
        if self.isfile(path):
            st_mode = 0o0100770
        else:
            # directory
            st_mode = 0o0040770
        st_time = int(self.getmtime(path))
        return PseudoStat(
            st_size=self.getsize(path),
            st_mtime=st_time,
            st_atime=st_time,
            st_nlink=1,
            st_mode=st_mode,
            st_uid=1000,
            st_gid=1000,
            st_dev=0,
            st_ino=0,
        )

    lstat = stat

    def _exists(self, path):
        if path.endswith('/'):
            return True
        return self.storage.exists(path)

    def isfile(self, path):

        return self._exists(path) and not path.endswith('/')

    def islink(self, path):
        return False

    def isdir(self, path):
        return not self.isfile(path)

    def getmtime(self, path):
        if self.isdir(path):
            return 0
        return self._origin_getmtime(path)

    def getsize(self, path):
        if self.isdir(path):
            return 0
        return self.storage.size(path)

    def _origin_getmtime(self, path):
        t = time.mktime(self.storage.get_modified_time(path).timetuple())
        return t

    def open(self, path, flags, attr):
        path = self._realpath(path)
        if flags:
            f = self.storage.open(path, 'wb')
            self.server_interface.add_log('uploaded: {}'.format(path))
        else:
            f = self.storage.open(path, 'rb')
            self.server_interface.add_log('downloaded: {}'.format(path))
        print(flags)
        fobj = StubSFTPHandle(flags)
        fobj.filename = path
        fobj.readfile = f
        fobj.writefile = f
        return fobj

    def remove(self, path):
        path = self._realpath(path)
        self.server_interface.add_log('removed: {}'.format(path))
        try:
            self.storage.delete(path)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK

    def rename(self, oldpath, newpath):
        # oldpath = self._realpath(oldpath)
        # newpath = self._realpath(newpath)
        # try:
        #     os.rename(oldpath, newpath)
        # except OSError as e:
        #     return SFTPServer.convert_errno(e.errno)
        return SFTP_OK

    def readlink(self, path):
        return SFTP_OK

    def symlink(self, target_path, path):
        return SFTP_OK

    def mkdir(self, path, attr):
        return SFTP_OK

    def rmdir(self, path):
        return SFTP_OK

    def chattr(self, path, attr):
        return SFTP_OK
