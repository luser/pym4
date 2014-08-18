#!/bin/sh
/usr/bin/m4 -I/usr/share/autoconf2.13 --reload autoconf.m4f configure.in > /tmp/configure

awk '
/__oline__/ { printf "%d:", NR + 1 }
           { print }
' /tmp/configure | sed '
/__oline__/s/^\([0-9][0-9]*\):\(.*\)__oline__/\2\1/
' >/tmp/configure2
