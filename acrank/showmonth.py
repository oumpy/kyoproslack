#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
import argparse

slack_symbols = [':bamboo:', ':japanese_ogre:', ':dolls:', ':cherry_blossom:',
                 ':flags:',':umbrella_with_rain_drops:', ':tanabata_tree:', ':sparkler:',
                 ':rice_scene:', ':jack_o_lantern:', ':shinto_shrine:', ':christmas_tree:']
month = int(datetime.now().strftime('%m'))

parser = argparse.ArgumentParser()
parser.add_argument('-p', '--prev', help='show previous month',
                    action='store_true')
parser.add_argument('-n', '--next', help='show next month',
                    action='store_true')
parser.add_argument('-s', '--slacksymbol', help='with slack symbol of the month',
                    action='store_true')
parser.add_argument('-a', '--after', help='how many months after now',
                    type=int, default=0)
parser.add_argument('--set_month', help='manually set the month to show.',
                    type=int, default=0)
args = parser.parse_args()

if 1 <= args.set_month <= 12:
    month = args.set_month
if args.prev:
    month -= 1
if args.next:
    month += 1
month += args.after
month %= 12
if month == 0:
    month = 12

if args.slacksymbol:
    output = slack_symbols[month-1] + '%2d' % month
else:
    output = str(month)

print(output)