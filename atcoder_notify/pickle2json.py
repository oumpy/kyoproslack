#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import json
import pickle

diff_info_basename = sys.argv[1]
with open(diff_info_basename+'.pickle', 'rb') as f:
    diff_info = pickle.load(f)
with open(diff_info_basename + '.json', 'w') as f:
    json.dump({'upcoming': diff_info}, f, indent=4)
