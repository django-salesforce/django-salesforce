# -*- coding: utf-8 -*-
"""winpty wrapper tests."""

# Standard library imports
import os
import time

# Third party imports
from winpty import PTY, WinptyError
from winpty.enums import Backend
from winpty.ptyprocess import which
import pytest


CMD = bytes(which('cmd').lower(), 'utf-8')


def pty_factory(backend):
    @pytest.fixture(scope='function')
    def pty_fixture():
        pty = PTY(80, 20, backend=backend)
        loc = bytes(os.getcwd(), 'utf8')
        assert pty.spawn(CMD)
        time.sleep(0.3)
        return pty
    return pty_fixture


conpty_provider = pty_factory(Backend.ConPTY)
winpty_provider = pty_factory(Backend.WinPTY)


@pytest.fixture(scope='function', params=[
    pytest.lazy_fixture('conpty_provider'),
    pytest.lazy_fixture('winpty_provider')])
def pty_fixture(request):
    pty = request.param
    return pty


def test_read(pty_fixture, capsys):
    pty = pty_fixture
    loc = os.getcwd()
    readline = ''

    with capsys.disabled():
        start_time = time.time()
        while loc not in readline:
            if time.time() - start_time > 5:
                break
            readline += pty.read().decode('utf-8')
    assert loc in readline


def test_write(pty_fixture):
    pty = pty_fixture
    line = pty.read()

    str_text = 'Eggs, ham and spam ünicode'
    text = bytes(str_text, 'utf-8')
    num_bytes = pty.write(text)

    line = ''
    start_time = time.time()
    while str_text not in line:
        if time.time() - start_time > 5:
            break
        line += pty.read().decode('utf-8')

    assert str_text in line


def test_isalive(pty_fixture):
    pty = pty_fixture
    pty.write(b'exit\r\n')

    text = 'exit'
    line = ''
    while text not in line:
        line += pty.read().decode('utf-8')

    while pty.isalive():
        pty.read()
        continue

    assert not pty.isalive()


def test_agent_spawn_fail(pty_fixture):
    pty = pty_fixture
    try:
        pty.spawn(CMD)
        assert False
    except WinptyError:
        pass


@pytest.mark.parametrize(
    'backend_name,backend',
    [("ConPTY", Backend.ConPTY), ('WinPTY', Backend.WinPTY)])
def test_pty_create_size_fail(backend_name, backend):
    try:
        PTY(80, -25, backend=backend)
        assert False
    except WinptyError:
        pass


def test_agent_resize_fail(pty_fixture):
    pty = pty_fixture
    try:
        pty.set_size(-80, 70)
        assert False
    except WinptyError:
        pass


def test_agent_resize(pty_fixture):
    pty = pty_fixture
    pty.set_size(80, 70)

