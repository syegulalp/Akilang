# Stolen shamelessly from https://stackoverflow.com/a/35304921
# with some modifications

from contextlib import contextmanager

import ctypes
import io
import os
import sys
import tempfile
import platform
import colorama

system = platform.system()

if system == "Linux":

    libc = ctypes.CDLL(None)
    c_stdout = ctypes.c_void_p.in_dll(libc, 'stdout')

elif system == "Windows":

    libc = ucrtbase = ctypes.CDLL("ucrtbase")
    iob_func = ucrtbase.__acrt_iob_func
    iob_func.restype = ctypes.c_void_p
    iob_func.argtypes = [ctypes.c_int]

    s_stdin = iob_func(0)
    c_stdout = iob_func(1)
    c_stdout = ctypes.c_void_p(c_stdout)


@contextmanager
def stdout_redirector(stream):
    colorama.deinit()

    # The original fd stdout points to. Usually 1 on POSIX systems.
    original_stdout_fd = sys.stdout.fileno()

    def _redirect_stdout(to_fd):
        """Redirect stdout to the given file descriptor."""

        # Flush the C-level buffer stdout
        libc.fflush(c_stdout)

        # Flush and close sys.stdout - also closes the file descriptor (fd)
        sys.stdout.close()

        # Make original_stdout_fd point to the same file as to_fd
        os.dup2(to_fd, original_stdout_fd)
        # Create a new sys.stdout that points to the redirected fd
        sys.stdout = io.TextIOWrapper(os.fdopen(original_stdout_fd, 'wb'))

    # Save a copy of the original stdout fd in saved_stdout_fd
    saved_stdout_fd = os.dup(original_stdout_fd)

    try:
        # Create a temporary file and redirect stdout to it
        tfile = tempfile.TemporaryFile(mode='w+b')
        _redirect_stdout(tfile.fileno())

        # Yield to caller, then redirect stdout back to the saved fd
        yield
        _redirect_stdout(saved_stdout_fd)

        # Copy contents of temporary file to the given stream
        # (not used here)

        tfile.flush()
        #tfile.seek(0, io.SEEK_SET)
        # stream.write(tfile.read())

    finally:
        tfile.close()
        os.close(saved_stdout_fd)

    colorama.init()
