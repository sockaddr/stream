/*
 * totalmemory.c - Report total system memory
 *
 * Copyright (C) 1999-2014  Red Hat, Inc.  All rights reserved.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Author(s): Erik Troan <ewt@redhat.com>
 *            Matt Wilson <msw@redhat.com>
 *            Michael Fulbright <msf@redhat.com>
 *            Jeremy Katz <katzj@redhat.com>
 *            David Cantrell <dcantrell@redhat.com>
 */

#include <errno.h>
#include <stdlib.h>
#include <glib.h>

#include "log.h"
#include "totalmemory.h"

/* report total system memory in kB (given to us by /proc/meminfo) */
guint64 totalMemory(void) {
    int i = 0, len = 0;
    guint64 total = 0;
    gchar *contents = NULL;
    gchar **lines = NULL, **fields = NULL;
    GError *fileErr = NULL;

    if (!g_file_get_contents(MEMINFO, &contents, NULL, &fileErr)) {
        logMessage(ERROR, "error reading %s: %s", MEMINFO, fileErr->message);
        g_error_free(fileErr);
        return total;
    }

    lines = g_strsplit(contents, "\n", 0);
    g_free(contents);

    for (i = 0; i < g_strv_length(lines); i++) {
        if (g_str_has_prefix(lines[i], "MemTotal:")) {
            fields = g_strsplit(lines[i], " ", 0);
            len = g_strv_length(fields);

            if (len < 3) {
                logMessage(ERROR, "unknown format for MemTotal line in %s", MEMINFO);
                g_strfreev(fields);
                g_strfreev(lines);
                return total;
            }

            errno = 0;
            total = g_ascii_strtoull(fields[len - 2], NULL, 10);

            if ((errno == ERANGE && total == G_MAXUINT64) ||
                (errno == EINVAL && total == 0)) {
                logMessage(ERROR, "%s: %d: %m", __func__, __LINE__);
                abort();
            }

            g_strfreev(fields);
            break;
        }
    }

    g_strfreev(lines);
    return total;
}
