#!/bin/sh

coverage run '--omit=/usr/share/*,/usr/lib/python3/*,/usr/local/*,*run_tests*' ./run_tests.py --both
coverage report -m
