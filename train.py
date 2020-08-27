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
recent_contests = content.find('div',id='contest-table-recent').find("div",class_ ="panel panel-default").find("tbody")
recent_contests = recent_contests.find_all("tr")
print(len(recent_contests))
for i in recent_contests:
    #print(i)
    #print("ここで区切り")
    date = i.find("td",class_ = "text-center").find("a").text
    print(date)
    name = i.find_all("td")[1].find("a").text
    print(name)
    break
