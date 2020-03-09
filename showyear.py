#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
import argparse

year = int(datetime.now().strftime('%Y'))

parser = argparse.ArgumentParser()
parser.add_argument('-p', '--prev', help='show previous year',
                    action='store_true')
parser.add_argument('-n', '--next', help='show next year',
                    action='store_true')
parser.add_argument('-a', '--after', help='how many years after now',
                    type=int, default=0)
parser.add_argument('--set_year', help='manually set the year to show.',
                    type=int, default=0)
args = parser.parse_args()

if args.set_year > 0:
    year = args.set_year
if args.prev:
    year -= 1
if args.next:
    year += 1
year += args.after

print(year)
