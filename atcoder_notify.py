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

def get_contest_info(upcoming_contests):#soupの一部を渡すと、(date,duration,name,link,grade,rated)のlistを返す。
    infos =[]
    for i in upcoming_contests:
        date = i.find("td",class_ = "text-center").find("a").text
        #print(date)
        duration = i.find_all("td")[2].text
        #print(duration)
        contest_color = str(i.find_all("td")[1].find("span")).split('"')[1]
        if 'red' in contest_color:
            grade = 'AGC-grade'
        elif 'orange' in contest_color:
            grade = 'ARC-grade'
        elif 'blue' in contest_color:
            grade = 'ABC-grade'
        else:
            grade = 'unrated'
        #print(grade)
        name = i.find_all("td")[1].find("a").text
        #print(name)
        link = i.find_all("td")[1].find("a").get("href")
        link = urllib.parse.urljoin(url_root,link)
        #print(link)
        rated = i.find_all("td")[3].text
        #print(rated)
        infos.append((date,duration,name,link,grade,rated))
    return infos

for info in get_contest_info(upcoming_contests):
    print(info)

recent_contests = content.find('div',id='contest-table-recent').find("div",class_ ="panel panel-default").find("tbody")
recent_contests = recent_contests.find_all("tr")
