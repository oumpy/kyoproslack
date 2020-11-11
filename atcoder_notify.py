#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup as bs
import re
import os
import urllib.parse
import sys
import datetime
import locale
import urllib.parse
import pickle
locale.setlocale(locale.LC_TIME, 'ja_JP.UTF-8')

diff_info_filename = 'diff_info.pickle'
rated_only = True

r=requests.get("https://atcoder.jp/contests/")
soup=bs(r.text,"lxml")
#print(soup.body)

content = soup.body.find('div',id='main-div').find('div',id='main-container').find('div',class_='row')
content = content.find('div',class_='col-lg-9 col-md-8')
url_root  = "https://atcoder.jp"

upcoming_contests = content.find('div',id="contest-table-upcoming")
if upcoming_contests == None:#予定されたコンテストが無ければ、終了
    # print("予定されたコンテストはありません。")
    sys.exit()
upcoming_contests = upcoming_contests.find("div",class_ ="panel panel-default").find("tbody")
upcoming_contests = upcoming_contests.find_all("tr")
url_root  = "https://atcoder.jp"

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
        if rated_only and rated.strip() == '-':
            continue
        infos.append((date,duration,name,link,grade,rated))
        infos.sort()
    return infos

def info2post(info):
    date, duration, name, link, grade, rated = info
    start_datetime = datetime.datetime.strptime(date, '%Y-%m-%d %H:%M:%S%z')
    start_str = start_datetime.strftime('%Y-%m-%d(%a) %H:%M')
    duration_hours, duration_minutes = map(int,duration.split(':'))
    end_datetime = (start_datetime + datetime.timedelta(hours=duration_hours, minutes=duration_minutes))
    if start_datetime.date() == end_datetime.date():
        end_str = end_datetime.strftime('%H:%M')
        date_line = '{}-{}'.format(start_str, end_str)
    else:
        end_str = end_datetime.strftime('%Y-%m-%d(%a) %H:%M')
        date_line = '{} - {}'.format(start_str, end_str)
    rated_line = 'rated: {}'.format(rated.strip())

    # if re.match(r'^AtCoder (Beginner|Regular|Grand) Contest', name):
    #     display_name = name
    # else:
    #     display_name = '{} [{}]'.format(name, grade)

    post_message = '\n'.join([name, date_line, link, rated_line])
    return post_message

<<<<<<< HEAD
message = '\n######\n'.join([info2post(info) for info in get_contest_info(upcoming_contests)])
if message:
    print(message)
=======
##これは前回との差分を考慮していないもの
# for info in get_contest_info(upcoming_contests):
#     print(info)

##前回の実行時の予定コンテスト情報をpickleで保存
#前回差分fileがあれば読み込み
##前回との差分をとる
if os.path.isfile(diff_info_filename):
    with open(diff_info_filename, 'rb') as f:
        diff_info = set(pickle.load(f))
else:
    diff_info = set()
upcoming_contests_info = get_contest_info(upcoming_contests)
new_contests_info = [ info for info in upcoming_contests_info if not info in diff_info ]
message = '\n######\n'.join([info2post(info) for info in new_contests_info])
if message:
    print(message)

##現時点での開催予定コンテストを保存
with open(diff_info_filename, 'wb') as f:
    pickle.dump(upcoming_contests_info, f)
>>>>>>> d45d1819d850ce6a1769c5fde855cac16be5b5bb
