#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup as bs
import re

r=requests.get("https://atcoder.jp/contests/")
soup=bs(r.text,"lxml")
#print(soup.body)
content = soup.body.find('div',id='main-div').find('div',id='main-container').find('div',class_='row')
content = content.find('div',class_='col-lg-9 col-md-8')
print(content)
