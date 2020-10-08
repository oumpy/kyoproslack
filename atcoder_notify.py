#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup as bs
import re
import urllib.parse
import sys
r=requests.get("https://atcoder.jp/contests/")
soup=bs(r.text,"lxml")
#print(soup.body)

content = soup.body.find('div',id='main-div').find('div',id='main-container').find('div',class_='row')
content = content.find('div',class_='col-lg-9 col-md-8')
url_root  = "https://atcoder.jp"

upcoming_contests = content.find('div',id="contest-table-upcoming")
if upcoming_contests == None:#予定されたコンテストが無ければ、終了
    print("予定されたコンテストはありません。")
    sys.exit()
upcoming_contests = upcoming_contests.find("div",class_ ="panel panel-default").find("tbody")
upcoming_contests = upcoming_contests.find_all("tr")
url_root  = "https://atcoder.jp"
import urllib.parse

def get_contest_info(upcoming_contests):#soupの一部を渡すと、(date,name,link)のlistを返す。
    infos =[]
    for i in upcoming_contests:
        date = i.find("td",class_ = "text-center").find("a").text
        #print(date)
        name = i.find_all("td")[1].find("a").text
        #print(name)
        link = i.find_all("td")[1].find("a").get("href")
        link = urllib.parse.urljoin(url_root,link)
        #print(link)
        infos.append((date,name,link))
    return infos

for info in get_contest_info(upcoming_contests):
    print(info)

recent_contests = content.find('div',id='contest-table-recent').find("div",class_ ="panel panel-default").find("tbody")
recent_contests = recent_contests.find_all("tr")
print(len(recent_contests))
for i in recent_contests:
    #print(i)
    #print("ここで区切り")
    date = i.find("td",class_ = "text-center").find("a").text
    print(date)
    print("~~~~~~~~~~~~~~~~~~~~~~~")
    name = i.find_all("td")[1].find("a").text
    print(name)
    link = i.find_all("td")[1].find("a").get("href")
    link = urllib.parse.urljoin(url_root,link)
    print("~~~~~~~~~~~~~~~~~~~~~~~")

    print(link)
    break
