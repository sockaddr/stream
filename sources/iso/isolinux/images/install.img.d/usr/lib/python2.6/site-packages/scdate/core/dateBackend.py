# -*- coding: utf-8 -*-
#
# dateBackend.py - provides the backend for system date calls
#
# Copyright © 2001-2010 Red Hat, Inc.
# Copyright © 2001-2003 Brent Fox <bfox@redhat.com>
#                       Tammy Fox <tfox@redhat.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# Authors:
# Brent Fox <bfox@redhat.com>
# Tammy Fox <tfox@redhat.com>
# Nils Philippsen <nphilipp@redhat.com>

import os
import sys
import time
import shlex

from slip.util.files import overwrite_safely

class dateBackend(object):

    def __init__(self):
        self.ntpFile = None
        self.ntpServers = None
        self.ntpBroadcastClient = False
        self.ntpLocalTimeSource = False
        self.readNtpConf()
        self.getNtpServers()
        pass

    def getDate (self):
        times = time.localtime(time.time())
        return times

    def writeDateConfig (self, sysDate, sysTime):
        year, month, day = sysDate
        hour, min, sec = sysTime

        #--cal.get_date starts counting months at 0 for Jan.  We need to start counting at 1
        month = month + 1
        cmd = '/bin/date -s %d/%d/%d\ %s:%s:%s' % (year, month, day, hour, min, sec)
        fd = os.popen(cmd, 'r')
        lines = fd.readlines()
        return not fd.close()

    def syncHardwareClock(self):
        # sync hardware clock.  Will use either localtime or utc
        # according to value in /etc/adjtime (recorded last time hwclock
        # was run).
        if os.access("/sbin/hwclock", os.F_OK) == 1:
            #The S390 has no hwclock binary, so don't try to run it if it isn't there
            return not os.system("/sbin/hwclock --systohc")
        return True

    def writeNtpConfig (self, ntpServers, ntpBroadcastClient, ntpLocalTimeSource, ntpIburst):
        broadcastclientFound = False
        ntpFileList = []

        servers = []
        for server in ntpServers:
            if server not in servers:
                servers.append (server)
        if ntpLocalTimeSource and "127.127.1.0" not in servers:
            servers.append ("127.127.1.0")

        serversfound = []

        # Write /etc/ntp.conf file, default to template if it was missing or
        # empty
        if self.ntpFile and len (self.ntpFile) > 0:
            lines = self.ntpFile
        else:
            fd = open("/usr/share/system-config-date/ntp.conf.template", "r")
            lines = fd.readlines()
            fd.close ()

        for line in lines:
            tokens = line.split ()
            if len (tokens) == 0 or tokens[0][0] == "#":
                # empty line or comment, copy verbatim
                ntpFileList.append (line)

            elif tokens[0] == "server":
                # server line
                if len(tokens) > 1:
                    host = tokens[1]
                    if host in servers:
                        line = self.addRemoveIburst(line, ntpIburst)
                        ntpFileList.append (line)
                        serversfound.append (host)
                else:
                    # What do we do here? server without an address isn't
                    # described in the documentation. Barring any problems
                    # we'll leave the line as it is.
                    ntpFileList.append (line)
            elif tokens[0] in ("broadcastclient", "#broadcastclient") or len (tokens) > 1 and tokens[0] == "#" and tokens[1] == "broadcastclient":
                # if 'broadcastclient' is found in the line
                if not broadcastclientFound:
                    if not ntpBroadcastClient:
                        ntpFileList.append("#")
                    ntpFileList.append ("broadcastclient\n")
                    broadcastclientFound = 1
                else:
                    ntpFileList.append(line)
            else:
                #This is not the server line, so just add it to the list
                ntpFileList.append(line)

        for server in servers:
            if not server in serversfound:
                if ntpIburst:
                    ntpFileList.append ("server %s iburst\n" % (server))
                else:
                    ntpFileList.append ("server %s\n" % (server))

        if not broadcastclientFound and ntpBroadcastClient:
            ntpFileList.append("broadcastclient\n")

        #Now that we've got the list of data, open the file and write it out
        try:
            overwrite_safely("/etc/ntp.conf", "".join(ntpFileList))
        except Exception, e:
            print >>sys.stderr, e
            return

        self.ntpFile = ntpFileList

        # Add or remove iburst to NTPSERVERARGS in /etc/sysconfig/network
        try:
            f = open("/etc/sysconfig/network", "r")
            lines = f.readlines()
            f.close()
        except:
            return

        lines_new = []
        found = False
        for line in lines:
            # parsing shell is hard
            start, x, end = line.partition("=")
            if start.lstrip() == "NTPSERVERARGS" and end == end.lstrip() and \
                    len(end) > 0:
                end_tokens = shlex.split(end)
                tokens = end_tokens[0].split()
                if "iburst" in tokens:
                    found = True
                    if not ntpIburst:
                        # rebuild changed NTPSERVERARGS line, not optimal
                        tokens = filter(lambda x: x != "iburst", tokens)
                        if len(tokens) > 0:
                            if len(tokens) > 1:
                                end_tokens[0] = "\"%s\"" % (" ".join(tokens))
                            elif len(tokens) == 1:
                                end_tokens[0] = tokens[0]
                            line = start + x + " ".join(end_tokens) + "\n"
                        else:
                            line = ""

            lines_new.append(line)
        if ntpIburst and not found:
            lines_new.append("NTPSERVERARGS=iburst\n")

        try:
            overwrite_safely("/etc/sysconfig/network", "".join(lines_new))
        except Exception, e:
            print e
            return

        return 0

    def startNtpService (self, wait):
        if self.isNtpRunning() == 1:
            fullPath = '/sbin/service ntpd restart > /dev/null'
        else:
            fullPath = '/sbin/service ntpd start > /dev/null'
        path = "/sbin/service"
        args = [path, "ntpd", "restart"]

        retval = os.system(fullPath)
        return retval

    def chkconfigOn(self):
        path = ('/sbin/chkconfig --level 2345 ntpd on')
        os.system (path)

    def chkconfigOff(self):
        path = ('/sbin/chkconfig --level 2345 ntpd off')
        os.system (path)

    def stopNtpService (self):
        if self.isNtpRunning() == 1:
            path = ('/sbin/service ntpd stop > /dev/null')
            os.system (path)
            self.chkconfigOff ()

    def isNtpRunning (self):
        if not os.access("/etc/ntp.conf", os.R_OK):
            #The file doesn't exist, so return
            return 0

        command = ('/sbin/service ntpd status > /dev/null')

        result = os.system(command)

        try:
            if result == 0:
                #ntpd is running
                return 1
            else:
                #ntpd is stopped
                return 0
        except:
            #we cannot parse the output of the initscript
            #the initscript is busted, so disable ntp
            return None

    def getNtpServers (self):
        self.ntpServers = []
        self.ntpLocalTimeSource = False

        if self.ntpFile:
            for line in self.ntpFile:
                tokens = line.split ()

                if len (tokens) == 0:
                    continue

                elif tokens[0] == "server":
                    try:
                        server = tokens[1]
                        if server == "127.127.1.0":
                            self.ntpLocalTimeSource = True
                        else:
                            self.ntpServers.append (server)
                    except IndexError:
                        # They have a server line in /etc/ntp.conf with no
                        # server specified
                        pass

        return (self.ntpServers, self.ntpLocalTimeSource)

    def getNtpBroadcastClient(self):
        broadcastclient = False

        if self.ntpFile:
            for line in self.ntpFile:
                location = line.find ('broadcastclient')
                if location == 0:
                    tokens = line.split ()

                    if tokens[0][0] != "#" and tokens[0] == "broadcastclient":
                        broadcastclient = True

        self.ntpBroadcastClient = broadcastclient

        return broadcastclient

    def getIburst(self):
        for line in self.ntpFile:
            directive, hash, comment = line.partition("#")
            tokens = directive.split()
            if len(tokens) > 0 and tokens[0] == "server" and "iburst" in tokens:
                return True
        return False

    def readNtpConf(self):
        try:
            fd = open('/etc/ntp.conf', 'r')
            self.ntpFile = fd.readlines()
            fd.close()
        except:
            return

    def addRemoveIburst(self, line, addIburst):
        precomment, x, comment = line.rstrip("\n").partition("#")

        tokens = precomment.split()

        if "iburst" in tokens:
            if not addIburst:
                tokens.remove("iburst")
                return " ".join(tokens) + x + comment + "\n"
        else:
            if addIburst:
                tokens.append("iburst")
                return " ".join(tokens) + x + comment + "\n"

        # unchanged
        return line

# vim: et ts=4
