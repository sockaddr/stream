# File name: fillins.py
# Date:      2009/01/19
# Author:    Dave Lehman, Martin Sivak
#
# Copyright (C) Red Hat 2009
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# in a file called COPYING along with this program; if not, write to
# the Free Software Foundation, Inc., 675 Mass Ave, Cambridge, MA
# 02139, USA.

import subprocess
import os, string, stat
import os.path
from errno import *
from tempfile import mkstemp

_ = lambda x: x

## Run an external program and redirect the output to a file.
# @param command The command to run.
# @param argv A list of arguments.
# @param stdin The file descriptor to read stdin from.
# @param stdout The file descriptor to redirect stdout to.
# @param stderr The file descriptor to redirect stderr to.
# @param searchPath Should command be searched for in $PATH?
# @param root The directory to chroot to before running command.
# @return The return code of command.
def execWithRedirect(command, argv, stdin = 0, stdout = 1, stderr = 2,
                     searchPath = 0, root = '/'):
    def chroot ():
        os.chroot(root)

        if not searchPath and not os.access (command, os.X_OK):
            raise RuntimeError, command + " can not be run"

    argv = list(argv)
    if type(stdin) == type("string"):
        if os.access(stdin, os.R_OK):
            stdin = open(stdin)
        else:
            stdin = 0
    if type(stdout) == type("string"):
        stdout = open(stdout, "w")
    if type(stderr) == type("string"):
        stderr = open(stderr, "w")

    if stdout is not None and type(stdout) != int:
        stdout.write("Running... %s\n" %([command] + argv,))

    try:
        proc = subprocess.Popen([command] + argv, stdin=stdin,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                preexec_fn=chroot, cwd=root)

        while True:
            (outStr, errStr) = proc.communicate()
            if outStr:
                stdout.write(outStr)
            if errStr:
                stderr.write(errStr)

            if proc.returncode is not None:
                ret = proc.returncode
                break
    except OSError, (errno, msg):
        raise RuntimeError, errstr

    return ret


def luks_add_key(device,
                 new_passphrase=None, new_key_file=None,
                 passphrase=None, key_file=None):

    params = ["-q"]

    p = os.pipe()
    if passphrase:
        os.write(p[1], "%s\n" % passphrase)
    elif key_file and os.path.isfile(key_file):
        params.extend(["--key-file", key_file])
    else:
        raise ValueError(_("luks_add_key requires either a passphrase or a key file"))

    params.extend(["luksAddKey", device])

    if new_passphrase:
        os.write(p[1], "%s\n" % new_passphrase)
    elif new_key_file and os.path.isfile(new_key_file):
        params.append("%s" % new_key_file)
    else:
        raise ValueError(_("luks_add_key requires either a passphrase or a key file to add"))

    os.close(p[1])

    rc = execWithRedirect("cryptsetup", params,
                                stdin = p[0],
                                stdout = "/dev/null",
                                stderr = "/dev/null",
                                searchPath = 1)

    os.close(p[0])
    if rc:
        raise RuntimeError(_("luks add key failed with errcode %d") % (rc,))

def luks_remove_key(device,
                    del_passphrase=None, del_key_file=None,
                    passphrase=None, key_file=None):

    params = []

    p = os.pipe()
    if del_passphrase: #the first question is about the key we want to remove
        os.write(p[1], "%s\n" % del_passphrase)

    if passphrase:
        os.write(p[1], "%s\n" % passphrase)
    elif key_file and os.path.isfile(key_file):
        params.extend(["--key-file", key_file])
    else:
        raise ValueError(_("luks_remove_key requires either a passphrase or a key file"))

    params.extend(["luksRemoveKey", device])

    if del_passphrase:
        pass
    elif del_key_file and os.path.isfile(del_key_file):
        params.append("%s" % del_key_file)
    else:
        raise ValueError(_("luks_remove_key requires either a passphrase or a key file to remove"))

    os.close(p[1])

    rc = execWithRedirect("cryptsetup", params,
                                stdin = p[0],
                                stdout = "/dev/null",
                                stderr = "/dev/null",
                                searchPath = 1)

    os.close(p[0])
    if rc:
        raise RuntimeError(_("luks_remove_key failed with errcode %d") % (rc,))

def prepare_passphrase_file(phrase):
    """Takes passphrase and returns safe temporary file with this phrase, for use as keyfile in cryptsetup"""
    handle, name = mkstemp(text = False)
    os.write(handle, phrase)
    os.close(handle)
    return name

