#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
from collections import defaultdict
import os
from datetime import datetime
from slack_sdk import WebClient
import argparse

# Example:
# python acrank.py week 先週
#

post_to_slack = True
update_link = True
slacktoken_file = 'slack_token'

channel_name = 'competition'
base_dir = os.environ['HOME'] + '/var/acrank/'
rec_dir = base_dir + 'record/'
userlist_file = 'memberlist.tsv'
userlist_file_path = base_dir + userlist_file
last_rec_file_format = 'record-{}'
latest_rec_file = 'latest'
ts_file_format = 'ts-{}'
time_format = '%Y%m%d%H%M%S'
rec_file_format = 'record-{}-{}.txt' # time, pid
urls = [
    'https://kenkoooo.com/atcoder/resources/ac.json',
    'https://kenkoooo.com/atcoder/resources/sums.json',
]
N_ranking = 5
post_format = {
    'post_header_format' : '*【{}のAtCoder ACランキング】*',
    'post_line_format' : '{}位：{}<@{}>  ({}問 {}点)', # rank, mark, slackid, ac, point
    'post_remain_format' : 'AC1問以上：{}',
    'post_nobody' : '1問も解いた人がいませんでした :scream:',
    'post_footer_format' : '\n＊優勝＊は {}！ :tada:', # winner
    'rank_marks' : [':first_place_medal:',':second_place_medal:',':third_place_medal:'],
    'other_mark' : ':sparkles:',
    'promotion' : '<@{}> さんが「{}」に昇級しました！！\nおめでとうございます！ :laughing::tada:'
}
post_format_inprogress = {
    'post_header_format' : '*【{}のAtCoder ACランキング（途中経過）】*',
    'post_nobody' : 'まだ誰も解いていません :hatching_chick:',
    'post_footer_format' : '\n現在、{}がトップです！ :woman-running::man-running:',
    'rank_marks' : ['']*3,
    'other_mark' : '',
}
colors = ['灰色','茶色','緑','水色','青','黄色','橙','赤']

def get_channel_list(client, limit=200):
    params = {
        'exclude_archived': 'true',
        'types': 'public_channel',
        'limit': str(limit),
        }
    channels = client.api_call('conversations.list', params=params)
    if bool(channels['ok']):
        return channels['channels']
    else:
        return None

def get_channel_id(client, channel_name):
    channels = filter(lambda x: x['name']==channel_name , get_channel_list(client))
    target = None
    for c in channels:
        if target is not None:
            break
        else:
            target = c
    if target is None:
        return None
    else:
        return target['id']

def get_rating(atcoderid):
    urlbase = 'https://atcoder.jp/users/{}/history/json/'
    contest_record = requests.get(urlbase.format(atcoderid)).json()
    if contest_record:
        return contest_record[-1]['NewRating']
    else:
        return 0

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('cycle') # e.g. 'week'
    parser.add_argument('cycle_str') # e.g. '先週'
    parser.add_argument('--inprogress', help='show the status in progress, without updating the record.',
                        action='store_true')
    parser.add_argument('--noslack', help='do not post to slack.',
                        action='store_true')
    parser.add_argument('--mute', help='post in thread without showing on channel.',
                        action='store_true')
    parser.add_argument('-a', '--allsolvers',
                        help='show everyone who solved one or more.',
                        action='store_true')
    parser.add_argument('-p', '--postpromotion',
                        help='make a post when someone is promoted.',
                        action='store_true')
    parser.add_argument('--newthread',
                        help='finish the previous thread and make a new one.',
                        action='store_true')
    parser.add_argument('-n', '--nranks', type=int, default=N_ranking,
                        help='how many rankers?')
    parser.add_argument('-s', '--sufficiency', type=int, default=0,
                        help='set sufficient ACs to show in the ranking.')
    parser.add_argument('-c', '--channel', default=channel_name,
                        help='slack channel to post.')
    parser.add_argument('--slacktoken', default=None,
                        help='slack bot token.')
    args = parser.parse_args()

    last_rec_file = last_rec_file_format.format(args.cycle)
    if args.noslack:
        post_to_slack = False
    if args.inprogress:
        update_link = False
        for k, v in post_format_inprogress.items():
            post_format[k] = v
    for k, v in post_format.items():
        globals()[k] = v
    N_ranking = args.nranks
    channel_name = args.channel
    rank_marks += [other_mark]*N_ranking
    post_header = post_header_format.format(args.cycle_str)
    ts_file = ts_file_format.format(args.cycle)

    userlist_file_path = base_dir + userlist_file
    last_rec_file_path = rec_dir + last_rec_file
    latest_rec_file_path = rec_dir + latest_rec_file
    slacktoken_file_path = base_dir + slacktoken_file

    if args.slacktoken:
        token = args.slacktoken
    else:
        with open(slacktoken_file_path, 'r') as f:
            token = f.readline().rstrip()
    web_client = WebClient(token=token)

    # read member list
    slack_members = set([ member['id'] for member in web_client.api_call('users.list')['members'] if not member['deleted']])
    member_info = defaultdict(dict)
    with open(userlist_file_path, 'r') as f:
        lines = f.readlines()
        for line in lines:
            nickname, slackid, atcoderid = line.rstrip().split('\t')[:3]
            if slackid in slack_members:
                member_info[atcoderid]['nickname'] = nickname
                member_info[atcoderid]['slackid'] = slackid
    atcoder_ids = set(member_info.keys())

    # read the previous record
    user_last_scores = defaultdict(lambda: defaultdict(lambda: None))
    new_members = set()
    if os.path.isfile(last_rec_file_path):
        with open(last_rec_file_path, 'r') as f:
            lines = f.readlines()
            for line in lines:
                atcoderid, ac, point = line.rstrip().split()[:3]
                user_last_scores[atcoderid]['problem_count'] = int(ac)
                user_last_scores[atcoderid]['point_sum'] = int(point)
        new_members = atcoder_ids - set(user_last_scores.keys())
    if os.path.isfile(latest_rec_file_path):
        with open(latest_rec_file_path, 'r') as f:
            lines = f.readlines()
            for line in lines:
                atcoderid, latest_ac, latest_point, latest_rating = (line.rstrip().split()+[None])[:4]
                if atcoderid in user_last_scores:
                    user_last_scores[atcoderid]['latest_point'] = int(latest_point)
                    if not latest_rating in [None, '']:
                        user_last_scores[atcoderid]['latest_rating'] = int(latest_rating)

    # get the new status from atcoder problems
    datasets = [requests.get(urls[s]).json() for s in range(2)]
    rec_file = rec_file_format.format(datetime.now().strftime(time_format), os.getpid())
    rec_file_path = rec_dir + rec_file
    user_scores = defaultdict(dict)
    for s in range(2):
        data = datasets[s]
        recname = ['problem_count', 'point_sum'][s]
        L = len(data)
        for i in range(L):
            atcoderid = data[i]['user_id']
            if atcoderid in atcoder_ids:
                user_scores[atcoderid][recname] = int(data[i][recname])
            if atcoderid in new_members:
                user_last_scores[atcoderid][recname] = int(data[i][recname])
    del data, datasets
    for atcoderid in atcoder_ids:
        if user_last_scores[atcoderid]['rating'] is None:
            user_scores[atcoderid]['rating'] = get_rating(atcoderid)
        elif user_scores[atcoderid]['point_sum'] > user_last_scores[atcoderid]['latest_point']:
            user_scores[atcoderid]['rating'] = get_rating(atcoderid)
        else:
            user_scores[atcoderid]['rating'] = user_last_scores[atcoderid]['latest_rating']
        if user_scores[atcoderid]['rating'] is None:
            user_scores[atcoderid]['rating_str'] = ''
        else:
            user_scores[atcoderid]['rating_str'] = str(user_scores[atcoderid]['rating'])
    # write the new status
    with open(rec_file_path, 'w') as f:
        for atcoderid in user_scores.keys():
            print(atcoderid, user_scores[atcoderid]['problem_count'], user_scores[atcoderid]['point_sum'], user_scores[atcoderid]['rating_str'],sep='\t', file=f)
    # back-record new members' status
    if new_members:
        with open(last_rec_file_path, 'a') as f:
            for atcoderid in new_members:
                print(atcoderid, user_scores[atcoderid]['problem_count'], user_scores[atcoderid]['point_sum'], user_scores[atcoderid]['rating_str'], sep='\t', file=f)
    # print(user_last_scores)
    # print(user_scores)
    
    # compute differences from last time
    accomp_list = []
    for atcoderid in user_scores.keys():
        if user_scores[atcoderid]['problem_count'] > user_last_scores[atcoderid]['problem_count']:
            accomp_list.append([
                atcoderid,
                user_scores[atcoderid]['problem_count'] - user_last_scores[atcoderid]['problem_count'],
                user_scores[atcoderid]['point_sum'] - user_last_scores[atcoderid]['point_sum'],
            ])
    accomp_list.sort(key=lambda x: (-x[1],-x[2]))
    N=len(accomp_list)
    rank = 1
    for i in range(N):
        if accomp_list[i][1:] == accomp_list[i-1][1:-1]:
            accomp_list[i].append(rank)
        elif i >= N_ranking and (args.sufficiency <= 0 or accomp_list[i][1] < args.sufficiency):
            ranking_list = accomp_list[:i]
            remain_list = accomp_list[i:]
            break
        else:
            rank = i+1
            accomp_list[i].append(rank)
    else:
        ranking_list = accomp_list
        remain_list = []

    post_lines = [post_header]
    winners_str_list = []
    if N > 0:
        for atcoderid, ac, point, rank in ranking_list:
            slackid = member_info[atcoderid]['slackid']
            post_lines.append(post_line_format.format(rank, rank_marks[rank-1], slackid, ac, point))
            if rank == 1:
                winners_str_list.append(rank_marks[0]+'<@{}> さん'.format(slackid))
        if remain_list and args.allsolvers:
            remain_str_list = [ '<@{}>'.format(member_info[x[0]]['slackid']) for x in remain_list ]
            post_lines.append(
                post_remain_format.format('、'.join(remain_str_list))
            )
        post_lines.append(
            post_footer_format.format('、'.join(winners_str_list))
        )
    else:
        post_lines.append(post_nobody)
    message = '\n'.join(post_lines)

    if post_to_slack:
        if len(user_scores) > 0:
            channel_id = get_channel_id(web_client, channel_name)
            params={
                'channel': channel_id,
                'text': message,
                #'thread_ts': thread_ts,
                #'reply_broadcast': reply_broadcast,
            }
            os.chdir(rec_dir)
            if os.path.isfile(ts_file) and (not args.newthread):
                with open(ts_file, 'r') as f:
                    ts = f.readline().rstrip()
                    params['thread_ts'] = ts
                    if not args.mute:
                        params['reply_broadcast'] = 'True'
            else:
                ts = None
            response = web_client.api_call(
                'chat.postMessage',
                params=params
            )
            posted_data = response.data
            if ts is None:
                ts = posted_data['ts']
                with open(ts_file, 'w') as f:
                    print(ts, file=f)        
    else:
        print(message)

    if args.postpromotion:
        for atcoderid in atcoder_ids:
            cur = user_scores[atcoderid]['rating']
            prev = user_last_scores[atcoderid]['latest_rating']
            if (cur is not None) and (prev is not None):
                cc = cur // 400
                pc = prev // 400
                if max(pc,0) < cc < len(colors):
                    message = post_format['promotion'].format(
                        member_info[atcoderid]['slackid'],
                        colors[cc],
                    )
                    if post_to_slack:
                        web_client.api_call('chat.postMessage', params={
                            'channel': channel_id,
                            'text': message,
                        })
                    else:
                        print(message)

    # update the symlink for last record
    if update_link:
        os.chdir(rec_dir)
        if os.path.islink(last_rec_file):
            os.unlink(last_rec_file)
        os.symlink(rec_file, last_rec_file)
    if args.postpromotion:
        os.chdir(rec_dir)
        if os.path.islink(latest_rec_file):
            os.unlink(latest_rec_file)
        os.symlink(rec_file, latest_rec_file)
