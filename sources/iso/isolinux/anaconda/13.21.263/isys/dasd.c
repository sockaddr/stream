/*
 * dasd.c
 *
 * Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
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
 */

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <linux/fs.h>

#include "isys.h"

#if defined(__s390__) || defined(__s390x__)
#define u8 __u8
#define u16 __u16
#define u32 __u32
#define u64 __u64
#include <s390utils/vtoc.h>
#include <asm/dasd.h>
#endif

#if defined(__s390__) || defined(__s390x__)
/* s390 stuff to detect DASDs */
static int read_vlabel(dasd_information2_t *dasd_info, int fd, int blksize,
                       volume_label_t *vlabel) {
    int rc;
    unsigned long vlabel_start = dasd_info->label_block * blksize;

    memset(vlabel, 0, sizeof(volume_label_t));

    if (lseek(fd, vlabel_start, SEEK_SET) < 0) {
        return 2;
    }

    rc = read(fd, vlabel, sizeof(volume_label_t));
    if (rc != sizeof(volume_label_t)) {
        return 1;
    }

    return 0;
}
#endif

int isLdlDasd(char *device) {
#if !defined(__s390__) && !defined(__s390x__)
    return 0;
#else
    char devname[16];
    int f, ret, blksize;
    dasd_information2_t dasd_info;
    volume_label_t vlabel;

    memset(&dasd_info, 0, sizeof(dasd_info));
    strcpy(devname, "/dev/");
    strcat(devname, device);

    if ((f = open(devname, O_RDONLY)) == -1)
        return 0;

    if (ioctl(f, BLKSSZGET, &blksize) != 0) {
        close(f);
        return 0;
    }

    if (ioctl(f, BIODASDINFO2, &dasd_info) != 0) {
        close(f);
        return 0;
    }

    ret = read_vlabel(&dasd_info, f, blksize, &vlabel);
    close(f);
    if (ret == 2)
        return 0;

    if (strncmp(dasd_info.type, "FBA", 3) == 0)
        return 0;

    if (dasd_info.format == DASD_FORMAT_CDL) /* VOL1, CDL */
        return 0;
    else
        return 1;
#endif
}

char *getDasdPorts() {
#if !defined(__s390__) && !defined(__s390x__)
    return 0;
#else
    char * line, *ports = NULL;
    char devname[7];
    char port[10];
    FILE *fd;
    int ret, sz;

    fd = fopen("/proc/dasd/devices", "r");
    if (!fd)
        return NULL;

    if ((line = (char *)malloc(100 * sizeof(char))) == NULL) {
        fclose(fd);
        return NULL;
    }

    while (fgets(line, 100, fd) != NULL) {
        if ((strstr(line, "unknown") != NULL))
            continue;

        if (strstr(line, "(FBA )") != NULL)
            ret = sscanf(line, "%[A-Za-z.0-9](FBA ) at ( %*d: %*d) is %s : %*s", port, devname);
        else
            ret = sscanf(line, "%[A-Za-z.0-9](ECKD) at ( %*d: %*d) is %s : %*s", port, devname);

        if (ret == 2) {
            if (!ports) {
                sz = strlen(port) + 1;
                if ((ports = (char *) malloc(sz)) == NULL) {
                    fclose(fd);
                    return NULL;
                }

                ports = strcpy(ports, port);
            } else {
                sz = strlen(ports) + strlen(port) + 2;
                if ((ports = (char *) realloc(ports, sz)) == NULL) {
                    fclose(fd);
                    return NULL;
                }

                ports = strcat(ports, ",");
                ports = strcat(ports, port);
            }
        }
    }

    fclose(fd);

    return ports;
#endif
}

/* vim:set shiftwidth=4 softtabstop=4: */
