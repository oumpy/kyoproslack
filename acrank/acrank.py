#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
from time import sleep
from collections import defaultdict
import os
from datetime import datetime
from slack_sdk import WebClient
from mattermostdriver import Driver
import argparse

# Example:
# python acrank.py week 先週
#

post_to_sns = True
update_link = True
token_file = 'mattermost_token'

team_name = 'main'
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
    'https://kenkoooo.com/atcoder/atcoder-api/v3/user/ac_rank?user={}',
    'https://kenkoooo.com/atcoder/atcoder-api/v3/user/rated_point_sum_rank?user={}',
]
N_ranking = 5
post_format = {
    'post_header_format' : '{1}【{0}のAtCoder ACランキング】{1}', # week, bold-sign
    'post_line_format' : '{0}位：{1}{5}@{2}{6}  ({3}問 {4}点)', # rank, mark, snsid, ac, point, mention-bra, mention-ket
    'post_remain_format' : 'AC1問以上：{}',
    'post_nobody' : '1問も解いた人がいませんでした :scream:',
    'post_footer_format' : '\n{1}優勝{1}は {0}！ :tada:', # winner, bold-sign
    'rank_marks' : [':first_place_medal:',':second_place_medal:',':third_place_medal:'],
    'other_mark' : ':sparkles:',
    'promotion' : '{2}@{0}{3} さんが「{1}」に昇級しました！！\nおめでとうございます！ :laughing::tada:' # username, color, mention-bra, mention-ket
}
post_format_inprogress = {
    'post_header_format' : '{1}【{0}のAtCoder ACランキング（途中経過）】{1}', # week, bold-sign
    'post_nobody' : 'まだ誰も解いていません :hatching_chick:',
    'post_footer_format' : '\n現在、{}がトップです！ :woman-running::man-running:',
    'rank_marks' : ['']*3,
    'other_mark' : '',
}
colors = ['灰色','茶色','緑','水色','青','黄色','橙','赤']
API_interval = 1.0
# maybe 1.0 is a bit too large, since the requests are light.

API_firsttime = True
def API_sleep(t):
    global API_firsttime
    if API_firsttime:
        API_firsttime = False
    else:
        sleep(t)

class Manager(object) :
    def __init__(self):
        pass
    def getChannelId(self, team_name, channel_name) :
        return None
    def getTeamId(self, team_name) :
        return None
    def getMyId(self) :
        return None
    def getTeamMembersData(self, team_id) :
        return list()
    def getChannelMembersData(self, channel_id) :
        return list()
    def getTeamMembers(self, team_id) :
        return list()
    def getChannelMembers(self, channel_id) :
        return list()
    def getIdNameDict(self, channel_id):
        return dict()
    def post(self, channel_id, message, **kwargs):
        return None

class MattermostManager(Manager):
    bold_sign, mention_bra, mention_ket = '**', '', ''

    def __init__(self, token, **kwargs):
        options={
            'token' :   token,
        } | kwargs
        self.mmDriver = Driver(options=options)

    def getChannelId(self, channel_name, team_name) :
        team_id = self.getTeamId(team_name)
        self.mmDriver.login()
        channel_id = self.mmDriver.channels.get_channel_by_name(team_id, channel_name)['id']
        self.mmDriver.logout()
        return channel_id

    def getTeamId(self, team_name):
        self.mmDriver.login()
        if not self.mmDriver.teams.check_team_exists(team_name):
            return None
        team_id = self.mmDriver.teams.get_team_by_name(team_name)['id']
        self.mmDriver.logout()
        return team_id

    def getMyId(self) :
        self.mmDriver.login()
        my_id = self.mmDriver.users.get_user(user_id='me')['id']
        self.mmDriver.logout()
        return my_id

    def getTeamMembersData(self, team_id, per_page=200) :
        # get all users for a team
        # with the max of 200 per page, we need to iterate a bit over the pages
        users_data = []
        pgNo = 0
        def get_users(team_id, pgNo, per_page=per_page):
            self.mmDriver.login()
            users_data = self.mmDriver.users.get_users(params={
                    'in_team'   :   team_id,
                    'page'      :   str(pgNo),
                    'per_page'  :   per_page,
            })
            self.mmDriver.logout()
            return users_data
        teamUsers = get_users(team_id, pgNo)
        while teamUsers:
            users_data += teamUsers
            pgNo += 1
            teamUsers = get_users(team_id, pgNo)
        return users_data

    def getChannelMembersData(self, channel_id, per_page=200) :
        # get all users for a channel
        # with the max of 200 per page, we need to iterate a bit over the pages
        users_data = []
        pgNo = 0
        def get_users(channel_id, pgNo, per_page=per_page):
            self.mmDriver.login()
            users_data = self.mmDriver.users.get_users(params={
                    'in_channel':   channel_id,
                    'page'      :   str(pgNo),
                    'per_page'  :   per_page,
            })
            self.mmDriver.logout()
            return users_data
        channelUsers = get_users(channel_id, pgNo)
        while channelUsers:
            users_data += channelUsers
            pgNo += 1
            channelUsers = get_users(channel_id, pgNo)
        return users_data

    def getChannelMembers(self, channel_id, per_page=200) :
        users_data = self.getChannelMembersData(channel_id, per_page)
        return [user['id'] for user in users_data]

    def getIdNameDict(self, channel_id):
        users_data = self.getChannelMembersData(channel_id)
        return {user['id'] : user['username'] for user in users_data}

    def post(self, channel_id, message, **kwargs):
        self.mmDriver.login()
        param = kwargs | {
            'channel_id':   channel_id,
            'message'   :   message,
            }
        response = self.mmDriver.posts.create_post(options=param)
        self.mmDriver.logout()
        return response

class SlackManager(Manager):
    bold_sign, mention_bra, mention_ket = '*', '<', '>'

    def __init__(self, token):
        self.client = WebClient(token=token)

    def getChannelId(self, channel_name, team_name=None):
        channels = filter(lambda x: x['name']==channel_name , self._get_channel_list())
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

    def _get_channel_list(self, limit=200):
        params = {
            'exclude_archived'  :   'true',
            'types'             :   'public_channel',
            'limit'             :   str(limit),
            }
        channels = self.client.api_call('conversations.list', params=params)
        if channels['ok']:
            return channels['channels']
        else:
            return None

    def getChannelMembersData(self, channel_id):
        return self.client.api_call('conversations.members', params={'channel':channel_id})

    def getMyId(self) :
        return self.client.api_call('auth.test')['user_id']

    def getChannelMembers(self, channel_id, exclude_bot=True) :
        channel_members = self.getChannelMembersData(channel_id)['members']
        return [ member for member in channel_members # if not (bool(member['is_bot']) and exclude_bot) 
            ]

    def getIdNameDict(self, channel_id):
        members_data = self.getChannelMembers(channel_id)
        return {member : member for member in members_data}

    def post(self, channel_id, message, **kwargs):
        params={
            'channel'   :   channel_id,
            'text'      :   message,
        }
        ts_file = kwargs['ts_file']
        os.chdir(kwargs['history_dir'])
        if os.path.isfile(ts_file):
            with open(ts_file, 'r') as f:
                ts = f.readline().rstrip()
                if not kwargs['solopost']:
                    params['thread_ts'] = ts
                    if not kwargs['mute']:
                        params['reply_broadcast'] = 'True'
        else:
            ts = None
        response = self.client.api_call(
            'chat.postMessage',
            params=params
        )
        posted_data = response.data
        if ts is None:
            ts = posted_data['ts']
            with open(ts_file, 'w') as f:
                print(ts, file=f)
        return response


def update_dictionary(dictionary_file=None):
    transpose = dict()
    if dictionary_file:
        with open(dictionary_file) as f:
            for line in f.readlines():
                if line.strip()[0] != '#':
                    a, b = line.split()[:2]
                    transpose[b] = a
    return transpose


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

def get_rating(atcoderid, interval=API_interval):
    urlbase = 'https://atcoder.jp/users/{}/history/json/'
    API_sleep(interval)
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
    parser.add_argument('--system', help='slack or mattermost.',
                        default='mattermost')
    parser.add_argument('--local', help='do not post to mattermost/slack.',
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
    parser.add_argument('-t', '--team', default=team_name,
                        help='team to post.')
    parser.add_argument('-c', '--channel', default=channel_name,
                        help='channel to post.')
    parser.add_argument('--token', default=None,
                        help='bot token.')
    parser.add_argument('--server', default='',
                        help='mattermost server.')
    parser.add_argument('--scheme', default='https',
                        help='mattermost scheme.')
    parser.add_argument('--port', type=int, default=443,
                        help='mattermost port.')
    parser.add_argument('--token-id', default='',
                        help='mattermost token_id.')
    parser.add_argument('--API-interval', type=float, default=API_interval,
                        help='set intervals (sec.) between AtCoder Problems API calls (default={}).'.format(API_interval))
    parser.add_argument('--id-dictionary', default=None,
                        help='Set dictironary file to transpose IDs, to keep the order.')
    args = parser.parse_args()

    API_interval = args.API_interval
    last_rec_file = last_rec_file_format.format(args.cycle)
    if args.local:
        post_to_sns = False
    if args.inprogress:
        update_link = False
        for k, v in post_format_inprogress.items():
            post_format[k] = v
    for k, v in post_format.items():
        globals()[k] = v
    N_ranking = args.nranks
    channel_name = args.channel
    rank_marks += [other_mark]*N_ranking
    ts_file = ts_file_format.format(args.cycle)

    userlist_file_path = base_dir + userlist_file
    last_rec_file_path = rec_dir + last_rec_file
    latest_rec_file_path = rec_dir + latest_rec_file
    token_file_path = base_dir + token_file

    if args.token:
        token = args.token
    else:
        with open(token_file_path, 'r') as f:
            token = f.readline().rstrip()

    if args.system.lower() == 'mattermost':    
        # if os.path.exists(config_file_path):
        #     with open(config_file_path, 'r') as f:
        #         config = yaml.safe_load(f)
        # else:
        config = defaultdict(lambda: None)
        if args.team:
            team_name = args.team
        elif 'team' in config:
            team_name = config['team']
        if args.channel:
            channel_name = args.channel
        elif 'channel' in config:
            channel_name = config['channel']
        config.pop('team', None)
        config.pop('channel', None)
        config.pop('token', None)
        config['url'] = args.server
        config['scheme'] = args.scheme
        config['port'] = args.port
        config['token_id'] = args.token_id
        manager = MattermostManager(token, **config)
    else: # Slack
        team_name = url = None
        if args.channel:
            channel_name = args.channel
        manager = SlackManager(token)

    post_header = post_header_format.format(args.cycle_str, manager.bold_sign)
    channel_id = manager.getChannelId(channel_name, team_name)
    id_name_dict = manager.getIdNameDict(channel_id)
    transpose_dict = update_dictionary(args.id_dictionary)
    id_name_dict = manager.getIdNameDict(channel_id)

    # read member list
    members = manager.getChannelMembers(channel_id)
    member_info = defaultdict(dict)
    with open(userlist_file_path, 'r') as f:
        lines = f.readlines()
        for line in lines:
            nickname, snsid, atcoderid = line.rstrip().split('\t')[:3]
            if snsid in transpose_dict:
                snsid = transpose_dict[snsid]
            if snsid in members:
                member_info[atcoderid]['nickname'] = nickname
                member_info[atcoderid]['snsid'] = snsid
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
    rec_file = rec_file_format.format(datetime.now().strftime(time_format), os.getpid())
    rec_file_path = rec_dir + rec_file
    user_scores = defaultdict(dict)
    for atcoderid in atcoder_ids:
        for s in range(2):
            recname = ['problem_count', 'point_sum'][s]
            API_sleep(API_interval)
            user_data = requests.get(urls[s].format(atcoderid))
            if user_data.status_code // 100 == 2:
                user_data_dic = user_data.json()
                user_scores[atcoderid][recname] = int(user_data_dic['count'])
                if atcoderid in new_members:
                    user_last_scores[atcoderid][recname] = int(user_data_dic['count'])
            else: # status error : the account has been deleted/renamed.
                break
        else:
            if user_last_scores[atcoderid]['rating'] is None:
                user_scores[atcoderid]['rating'] = get_rating(atcoderid, API_interval)
            elif user_scores[atcoderid]['point_sum'] > user_last_scores[atcoderid]['latest_point']:
                user_scores[atcoderid]['rating'] = get_rating(atcoderid, API_interval)
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
    for atcoderid in user_scores.keys() & user_last_scores.keys():
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
            snsid = member_info[atcoderid]['snsid']
            post_lines.append(post_line_format.format(rank, rank_marks[rank-1], id_name_dict[snsid], ac, point, manager.mention_bra, manager.mention_ket))
            if rank == 1:
                winners_str_list.append(rank_marks[0]+'{1}@{0}{2} さん'.format(id_name_dict[snsid], manager.mention_bra, manager.mention_ket))
        if remain_list and args.allsolvers:
            remain_str_list = [ '{1}@{0}{2}'.format(id_name_dict[member_info[x[0]]['snsid']], manager.mention_bra, manager.mention_ket) for x in remain_list ]
            post_lines.append(
                post_remain_format.format('、'.join(remain_str_list))
            )
        post_lines.append(
            post_footer_format.format('、'.join(winners_str_list), manager.bold_sign)
        )
    else:
        post_lines.append(post_nobody)
    message = '\n'.join(post_lines)

    if post_to_sns:
        if len(user_scores) > 0:
            # channel_id = manager.getChannelId(channel_name, team_name)
            os.chdir(rec_dir)
            # if os.path.isfile(ts_file) and (not args.newthread):
            #     with open(ts_file, 'r') as f:
            #         ts = f.readline().rstrip()
            #         params['thread_ts'] = ts
            #         if not args.mute:
            #             params['reply_broadcast'] = 'True'
            # else:
            #     ts = None
            response = manager.post(channel_id, message)
            # posted_data = response.data
            # if ts is None:
            #     ts = posted_data['ts']
            #     with open(ts_file, 'w') as f:
            #         print(ts, file=f)        
    else:
        print(message)

    # update the symlink for last record
    if update_link:
        os.chdir(rec_dir)
        if os.path.islink(last_rec_file):
            os.unlink(last_rec_file)
        os.symlink(rec_file, last_rec_file)

    if args.postpromotion:
        for atcoderid in atcoder_ids:
            cur = user_scores[atcoderid]['rating']
            prev = user_last_scores[atcoderid]['latest_rating']
            if (cur is not None) and (prev is not None):
                cc = cur // 400 if cur > 0 else -1
                pc = prev // 400 if prev > 0 else -1
                if pc < cc < len(colors):
                    message = post_format['promotion'].format(
                        id_name_dict[member_info[atcoderid]['snsid']],
                        colors[cc],
                        manager.mention_bra,
                        manager.mention_ket,
                    )
                    if post_to_sns:
                        manager.post(channel_id, message)
                    else:
                        print(message)

        # update symlink for the latest rating data.
        os.chdir(rec_dir)
        if os.path.islink(latest_rec_file):
            os.unlink(latest_rec_file)
        os.symlink(rec_file, latest_rec_file)
