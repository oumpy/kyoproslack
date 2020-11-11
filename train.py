#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup as bs
import re
import os
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
##これは前回との差分を考慮していないもの
for info in get_contest_info(upcoming_contests):
    print(info)

import pickle
##前回の実行時の予定コンテスト情報をpickleで保存
#前回差分fileがあれば読み込み
##前回との差分をとる
if os.path.isfile('diff_info.pickle'):
    with open('diff_info.pickle', 'rb') as f:
        diff_info = pickle.load(f)
    upcoming_contests_info = list(set(get_contest_info(upcoming_contests))-set(diff_info))
    if len(upcoming_contests_info)==0:
        print("前回から新規に生えたコンテストはありません")
    for info_ in upcoming_contests_info:
        print("new!!!!",info_)

##現時点での開催予定コンテストを保存

with open('diff_info.pickle', 'wb') as f:
    pickle.dump(get_contest_info(upcoming_contests), f)





