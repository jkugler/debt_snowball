#!/bin/sh

coverage3 run '--omit=/usr/share/*,/usr/lib/python3/*,/usr/local/*,*run_tests*' ./run_tests.py --both
coverage3 report -m
