#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
from time import sleep
import time
import sys
import re
import logging
import traceback
from collections import defaultdict
import os
from datetime import datetime
from urllib.parse import quote
from slack_sdk import WebClient
try:
    from mattermostautodriver import TypedDriver as Driver # mattermostautodriver >= 10
except ImportError:
    from mattermostautodriver import Driver # mattermostautodriver 2.x
import httpx
import argparse
from typing import List, Dict, Optional, Union, Any

# Example:
# python acrank.py week 先週
#

post_to_sns = True
update_link = True
token_file = 'mattermost_token'

team_name = 'main'
channel_name = 'competition'
base_dir = os.environ['HOME'] + '/.acrank/'
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
    'promotion' : '{2}@{0}{3} さんが「{1}」に昇級しました！！\nおめでとうございます！ :laughing::tada:', # username, color, mention-bra, mention-ket
    'relegation' : '{2}@{0}{3} さんが「{1}」に降級しました。\nまたがんばりましょう！ :sob:', # username, color, mention-bra, mention-ket
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

MM_timeout = 60.0       # seconds per Mattermost API request (None = wait forever)
MM_retries = 8          # retries of a Mattermost API call on transient errors (5,10,20,40,60,60,... s)
HTTP_timeout = (10, 30) # (connect, read) seconds for AtCoder / AtCoder Problems
HTTP_retries = 3        # retries of an AtCoder / AtCoder Problems request on transient errors
transient_status = {429, 500, 502, 503, 504}
unprocessed_status = {429, 503} # transient statuses meaning that the request was surely not processed
post_lookback_ms = 5 * 60 * 1000 # how far back to look for an already-created post (allows for clock skew)
post_settle_s = 90  # after a failure that the server may still be processing, wait this long before re-posting
post_recheck_s = 120 # after such a re-post, check again for a late duplicate this long afterwards (at the end of the run)

# mattermostautodriver logs every HTTP error body (e.g. whole nginx error pages) to stderr;
# keep the log quiet: warn() shows the error id / page title instead (see describe_error).
logging.getLogger('mattermostautodriver').addHandler(logging.NullHandler())

API_firsttime = True
def API_sleep(t):
    global API_firsttime
    if API_firsttime:
        API_firsttime = False
    else:
        sleep(t)

def warn(message):
    print('[{}] acrank: {}'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), message),
          file=sys.stderr, flush=True)

def retry_wait(n):
    # n-th retry (0-origin): 5, 10, 20, 40, 60, 60, ... seconds
    return min(60, 5 * 2 ** n)

def error_status(e):
    # HTTP status of a Mattermost API error, or None (e.g. network errors).
    # mattermostautodriver 2.x and 10.11: httpx.HTTPStatusError for 429 and 5xx other than 501
    # (other 4xx raise exceptions without the status);
    # >= 11.1: MattermostError / InvalidMattermostError with status_code for every error status.
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code
    status = getattr(e, 'status_code', None)
    return status if isinstance(status, int) else None

def describe_error(e):
    status = error_status(e)
    if status is not None:
        return 'HTTP {}{}'.format(status, _error_excerpt(e))
    if '<html' in _safe_str(e).lower(): # e.g. an nginx 4xx page with mattermostautodriver 2.x
        return '{}{}'.format(type(e).__name__, _error_excerpt(e))
    return '{}: {}'.format(type(e).__name__, _safe_str(e))

def _safe_str(e):
    try:
        return str(e)
    except Exception:
        return '<unprintable {}>'.format(type(e).__name__)

def _error_excerpt(e, limit=120):
    # the server's error id/message (JSON), or the title of an HTML error page (nginx)
    if isinstance(e, httpx.HTTPStatusError):
        try:
            data = e.response.json()
            if isinstance(data, dict) and (data.get('id') or data.get('message')):
                return ' ({})'.format(str(data.get('id') or data.get('message'))[:limit])
        except Exception:
            pass
        try:
            text = e.response.text
        except Exception:
            return ''
    elif getattr(e, 'error_id', None):
        return ' ({})'.format(str(e.error_id)[:limit])
    else:
        text = _safe_str(e)
    text = ' '.join(text.split())
    m = re.search(r'<title>(.*?)</title>', text, re.IGNORECASE)
    if m:
        text = m.group(1)
    return ' ({})'.format(text[:limit]) if text else ''

class FetchError(Exception):
    pass

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
    def finish(self):
        pass

class MattermostManager(Manager):
    bold_sign, mention_bra, mention_ket = '**', '', ''

    def __init__(self, **config):
        self.retries = config.pop('retries', MM_retries)
        config.setdefault('max_retries', 0) # mattermostautodriver >= 11.10 has its own retries; we retry by ourselves
        self.mmDriver = Driver(options=config)
        self.logged_in = False
        self.members_cache = dict()
        self.duplicate_checks = [] # (due time, channel_id, user_id, message, since)

    @staticmethod
    def _is_transient(e):
        # network errors, timeouts, and 429/5xx (incl. nginx 502 while Mattermost is stalled).
        if isinstance(e, (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)):
            return True
        return error_status(e) in transient_status

    @staticmethod
    def _maybe_processed(e):
        # True if the failed request may have reached Mattermost and may still be (or have been) processed,
        # e.g. a read timeout, a dropped connection, 500/502/504.
        if isinstance(e, (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)):
            return False
        return error_status(e) not in unprocessed_status

    def _with_retry(self, description, func, *args, **kwargs):
        for n in range(self.retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if n >= self.retries or not self._is_transient(e):
                    raise
                wait = retry_wait(n)
                warn('{} failed ({}); retrying in {} s ({}/{})'.format(
                    description, describe_error(e), wait, n + 1, self.retries))
                sleep(wait)

    def _login(self):
        # With a personal access token, login() only sets the token and fetches the own user.
        # We do it once per run and never log out: logging out (as this script used to do after
        # every call) only revokes the server-side session that other bots with the same token share.
        if not self.logged_in:
            self._with_retry('login', self.mmDriver.login)
            self.logged_in = True

    def _call(self, description, func, *args, **kwargs):
        self._login()
        return self._with_retry(description, func, *args, **kwargs)

    # The API is called through the driver's HTTP client (client.get/post/delete), whose interface is
    # the same in mattermostautodriver 2.x and >= 10. The generated endpoint methods differ between them
    # (e.g. users.get_users(params={...}) vs users.get_users(page=..., in_channel=...)),
    # and the typed posts.create_post() of >= 10 cannot send pending_post_id.
    def _get(self, description, path, params=None):
        return self._call(description, self.mmDriver.client.get, path, params=params)

    def getChannelId(self, channel_name, team_name) :
        team_id = self.getTeamId(team_name)
        if team_id is None:
            raise RuntimeError('team not found: {}'.format(team_name))
        return self._get('get channel', '/api/v4/teams/{}/channels/name/{}'.format(quote(team_id, safe=''), quote(channel_name, safe='')))['id']

    def getTeamId(self, team_name):
        exists = self._get('check team', '/api/v4/teams/name/{}/exists'.format(quote(team_name, safe='')))
        if isinstance(exists, dict): # the API returns {"exists": bool}
            exists = exists.get('exists', False)
        if not exists:
            return None
        return self._get('get team', '/api/v4/teams/name/{}'.format(quote(team_name, safe='')))['id']

    def getMyId(self) :
        return self._get('get me', '/api/v4/users/me')['id']

    def _getUsersData(self, scope_key, scope_id, per_page=200):
        # with the max of 200 per page, we need to iterate a bit over the pages
        users_data = []
        pgNo = 0
        while True:
            page = self._get('get users', '/api/v4/users', params={
                    scope_key   :   scope_id,
                    'page'      :   str(pgNo),
                    'per_page'  :   per_page,
            })
            if not page:
                return users_data
            users_data += page
            pgNo += 1

    def getTeamMembersData(self, team_id, per_page=200) :
        # get all users for a team
        return self._getUsersData('in_team', team_id, per_page)

    def getChannelMembersData(self, channel_id, per_page=200) :
        # get all users for a channel (fetched once per run, then cached)
        if channel_id not in self.members_cache:
            self.members_cache[channel_id] = self._getUsersData('in_channel', channel_id, per_page)
        return self.members_cache[channel_id]

    def getChannelMembers(self, channel_id, per_page=200) :
        users_data = self.getChannelMembersData(channel_id, per_page)
        return [user['id'] for user in users_data]

    def getIdNameDict(self, channel_id):
        users_data = self.getChannelMembersData(channel_id)
        return {user['id'] : user['username'] for user in users_data}

    def _findPosts(self, channel_id, user_id, message, since):
        # root posts by user_id with the same message, created at/after since (oldest first).
        # ('since' selects posts *modified* after it, so check create_at as well.)
        result = self.mmDriver.client.get('/api/v4/channels/{}/posts'.format(quote(channel_id, safe='')), params={'since': since})
        found = [post for post in (result.get('posts') or {}).values()
                 if post.get('user_id') == user_id and not post.get('delete_at') and not post.get('root_id')
                 and (post.get('create_at') or 0) >= since
                 and (post.get('message') or '').strip() == message.strip()]
        return sorted(found, key=lambda post: (post.get('create_at') or 0, post.get('id') or ''))

    def _removeDuplicates(self, channel_id, user_id, message, since):
        # after a re-post, delete any copy that a stalled earlier attempt has also created.
        try:
            found = self._findPosts(channel_id, user_id, message, since)
            for post in found[1:]:
                self.mmDriver.client.delete('/api/v4/posts/{}'.format(quote(post['id'], safe='')))
                warn('deleted a duplicate post ({})'.format(post['id']))
        except Exception as e:
            warn('could not check for duplicate posts: {}'.format(describe_error(e)))

    def post(self, channel_id, message, **kwargs):
        self._login()
        my_id = self.mmDriver.client.userid
        now_ms = int(time.time() * 1000)
        since = now_ms - post_lookback_ms
        param = kwargs | {
            'channel_id':   channel_id,
            'message'   :   message,
            # lets the server de-duplicate a repeated request while the first one is fresh (its cache lasts 30 s)
            'pending_post_id': '{}:{}:{}'.format(my_id, now_ms, os.getpid()),
            }
        last_error = None
        maybe_posted = False # an earlier attempt may have been processed by the server
        settle = False       # the last attempt may still be in progress on the server
        for n in range(self.retries + 1):
            if last_error is not None:
                wait = max(retry_wait(n - 1), post_settle_s if settle else 0)
                warn('post failed ({}); retrying in {} s ({}/{})'.format(
                    describe_error(last_error), wait, n, self.retries))
                sleep(wait)
                settle = False
                # never re-post unless we have confirmed that no earlier attempt created the post.
                try:
                    existing = self._findPosts(channel_id, my_id, message, since)
                except Exception as e:
                    if not self._is_transient(e):
                        raise
                    last_error = e
                    continue
                if existing:
                    warn('the post had been created by an earlier attempt; not posting again')
                    return existing[0]
            try:
                response = self.mmDriver.client.post('/api/v4/posts', options=param)
            except Exception as e:
                if not self._is_transient(e):
                    raise
                last_error = e
                if self._maybe_processed(e):
                    maybe_posted = settle = True
                continue
            if maybe_posted:
                self._removeDuplicates(channel_id, my_id, message, since)
                self.duplicate_checks.append((time.time() + post_recheck_s, channel_id, my_id, message, since))
            return response
        raise last_error

    def finish(self):
        # a stalled earlier attempt may commit even after the re-post: check once more later.
        for due, channel_id, user_id, message, since in self.duplicate_checks:
            wait = due - time.time()
            if wait > 0:
                sleep(wait)
            self._removeDuplicates(channel_id, user_id, message, since)
        self.duplicate_checks = []

class SlackManager(Manager):
    bold_sign, mention_bra, mention_ket = '*', '<', '>'

    def __init__(self, **config: Dict[str, Any]):
        self.client = WebClient(token=config['token'])

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
                s = line.strip()
                if not s or s[0] == '#':
                    continue
                fields = s.split()
                if len(fields) < 2:
                    warn('ignored a malformed line in {}: {!r}'.format(dictionary_file, s))
                    continue
                a, b = fields[:2]
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

def http_get(url, interval=API_interval, retries=HTTP_retries):
    # GET with a timeout, retrying on network errors / 429 / 5xx.
    # Returns the response (any other status), or raises FetchError.
    API_sleep(interval)
    last_error = None
    for n in range(retries + 1):
        if last_error is not None:
            wait = retry_wait(n - 1)
            warn('GET {} failed ({}); retrying in {} s ({}/{})'.format(url, last_error, wait, n, retries))
            sleep(wait)
        try:
            response = requests.get(url, timeout=HTTP_timeout)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError, requests.exceptions.ContentDecodingError) as e:
            last_error = type(e).__name__
            continue
        except requests.exceptions.RequestException as e:
            raise FetchError('GET {} failed: {}: {}'.format(url, type(e).__name__, e))
        if response.status_code in transient_status:
            last_error = 'HTTP {}'.format(response.status_code)
            continue
        return response
    raise FetchError('GET {} failed: {}'.format(url, last_error))

def get_rating(atcoderid, interval=API_interval):
    # returns the latest rating (0 if never rated), or None if unavailable for this user.
    # raises FetchError if atcoder.jp does not respond.
    urlbase = 'https://atcoder.jp/users/{}/history/json/'
    response = http_get(urlbase.format(atcoderid), interval)
    try:
        if response.status_code // 100 != 2:
            raise ValueError('HTTP {}'.format(response.status_code))
        contest_record = response.json()
        if contest_record:
            return int(contest_record[-1]['NewRating'])
        else:
            return 0
    except (ValueError, KeyError, TypeError, IndexError) as e:
        warn('could not get the rating of {}: {}'.format(atcoderid, e))
        return None

def replace_symlink(target, link_name):
    # point link_name at target atomically (in the current directory)
    if os.path.lexists(link_name) and not os.path.islink(link_name):
        backup = '{}.bak-{}'.format(link_name, datetime.now().strftime(time_format))
        warn('{} was a regular file; renamed to {}'.format(link_name, backup))
        os.rename(link_name, backup)
    tmp = '{}.tmp-{}'.format(link_name, os.getpid())
    if os.path.lexists(tmp):
        os.unlink(tmp)
    os.symlink(target, tmp)
    os.replace(tmp, link_name)

def _excepthook(exc_type, exc, tb):
    # put a timestamp in the log before the traceback
    warn('aborted: {}'.format(exc_type.__name__))
    if '<html' in _safe_str(exc).lower():
        # the message is a whole (nginx) error page: show its title only
        sys.stderr.write('Traceback (most recent call last):\n')
        traceback.print_tb(tb, file=sys.stderr)
        summary = describe_error(exc)
        if error_status(exc) is not None:
            summary = '{}: {}'.format(exc_type.__name__, summary)
        sys.stderr.write(summary + '\n')
        return
    sys.__excepthook__(exc_type, exc, tb)

if __name__ == '__main__':
    sys.excepthook = _excepthook
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
    parser.add_argument('--mm-timeout', type=float, default=MM_timeout,
                        help='timeout (sec.) of each Mattermost API request (default={}).'.format(MM_timeout))
    parser.add_argument('--mm-retries', type=int, default=MM_retries,
                        help='retries of a Mattermost API call on network errors/429/5xx (default={}).'.format(MM_retries))
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
        config['url'] = args.server
        config['scheme'] = args.scheme
        config['port'] = args.port
        config['token_id'] = args.token_id
        config['token'] = token
        config['request_timeout'] = args.mm_timeout if args.mm_timeout > 0 else None
        config['retries'] = max(0, args.mm_retries)
        ManagerClass = MattermostManager
    else: # Slack
        team_name = url = None
        if args.channel:
            channel_name = args.channel
        config = {'token': token}
        ManagerClass = SlackManager
    
    manager = ManagerClass(**config)

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
            if not line.strip() or line.lstrip()[0] == '#':
                continue
            fields = line.rstrip().split('\t')
            if len(fields) < 3:
                warn('ignored a malformed line in {}: {!r}'.format(userlist_file_path, line.rstrip()))
                continue
            nickname, snsid, atcoderid = fields[:3]
            if snsid in transpose_dict:
                snsid = transpose_dict[snsid]
            if snsid in members:
                member_info[atcoderid]['nickname'] = nickname
                member_info[atcoderid]['snsid'] = snsid
    atcoder_ids = set(member_info.keys())

    # read the previous record
    user_last_scores = defaultdict(lambda: defaultdict(lambda: None))
    new_members = set()
    first_run = not os.path.isfile(last_rec_file_path)
    if not first_run:
        with open(last_rec_file_path, 'r') as f:
            lines = f.readlines()
            for line in lines:
                if not line.strip():
                    continue
                atcoderid, ac, point = line.rstrip().split()[:3]
                user_last_scores[atcoderid]['problem_count'] = int(ac)
                user_last_scores[atcoderid]['point_sum'] = int(point)
        new_members = atcoder_ids - set(user_last_scores.keys())
    if os.path.isfile(latest_rec_file_path):
        with open(latest_rec_file_path, 'r') as f:
            lines = f.readlines()
            for line in lines:
                if not line.strip():
                    continue
                atcoderid, latest_ac, latest_point, latest_rating = (line.rstrip().split()+[None])[:4]
                if atcoderid in user_last_scores:
                    user_last_scores[atcoderid]['latest_point'] = int(latest_point)
                    if not latest_rating in [None, '']:
                        user_last_scores[atcoderid]['latest_rating'] = int(latest_rating)

    # get the new status from atcoder problems
    rec_file = rec_file_format.format(datetime.now().strftime(time_format), os.getpid())
    rec_file_path = rec_dir + rec_file
    user_scores = dict()
    unfetched = [] # members whose status could not be fetched (network errors / 5xx)
    rating_available = True
    try:
        for atcoderid in atcoder_ids:
            scores = dict()
            try:
                for recname, url in zip(['problem_count', 'point_sum'], urls):
                    user_data = http_get(url.format(atcoderid), API_interval)
                    if user_data.status_code // 100 != 2: # the account has been deleted/renamed.
                        break
                    try:
                        scores[recname] = int(user_data.json()['count'])
                    except (ValueError, KeyError, TypeError) as e:
                        raise FetchError('unexpected response from {}: {}'.format(url.format(atcoderid), e))
            except FetchError as e:
                unfetched.append(atcoderid)
                if len(unfetched) >= 3 and len(unfetched) > len(user_scores):
                    # failing for most members: AtCoder Problems itself seems to be down.
                    raise FetchError('{} (and {} more members failed)'.format(e, len(unfetched) - 1))
                warn('{}; {} is left out of this run'.format(e, atcoderid))
                continue
            if len(scores) < 2:
                warn('{} was not found on AtCoder Problems (HTTP {}); skipped'.format(atcoderid, user_data.status_code))
                continue
            user_scores[atcoderid] = scores
            if atcoderid in new_members:
                user_last_scores[atcoderid].update(scores)
            # the rating is always re-fetched, since it can change without new ACs.
            rating = None
            if rating_available:
                try:
                    rating = get_rating(atcoderid, API_interval)
                except FetchError as e:
                    warn('{}; ratings are not updated in this run'.format(e))
                    rating_available = False
            if rating is None and atcoderid in user_last_scores:
                # keep the last known rating, so that a color change is detected next time
                rating = user_last_scores[atcoderid]['latest_rating']
            scores['rating'] = rating
            scores['rating_str'] = '' if rating is None else str(rating)
    except FetchError as e:
        # AtCoder Problems is unavailable: leave all the records untouched, so that the next run covers this cycle.
        warn('{}; aborted without posting or updating the records'.format(e))
        sys.exit(1)
    if not user_scores:
        warn('no member status was obtained; aborted without posting or updating the records')
        sys.exit(1)
    # write the new status
    with open(rec_file_path, 'w') as f:
        for atcoderid in user_scores.keys():
            print(atcoderid, user_scores[atcoderid]['problem_count'], user_scores[atcoderid]['point_sum'], user_scores[atcoderid]['rating_str'],sep='\t', file=f)
        # members left out keep their previous values, so that their progress is counted next time.
        for atcoderid in unfetched:
            if atcoderid in user_last_scores:
                last = user_last_scores[atcoderid]
                print(atcoderid, last['problem_count'], last['point_sum'], '' if last['latest_rating'] is None else last['latest_rating'], sep='\t', file=f)
    # back-record new members' status
    new_members = new_members & set(user_scores.keys())
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
        if i > 0 and accomp_list[i][1:] == accomp_list[i-1][1:-1]:
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
            post_lines.append(post_line_format.format(rank, rank_marks[rank-1 if rank < len(rank_marks) else -1], id_name_dict[snsid], ac, point, manager.mention_bra, manager.mention_ket))
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
        if first_run:
            warn('no previous record for "{}"; recorded the current status without posting'.format(args.cycle))
        else:
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
        replace_symlink(rec_file, last_rec_file)

    if args.postpromotion:
        for atcoderid, scores in user_scores.items():
            cur = scores['rating']
            prev = user_last_scores[atcoderid]['latest_rating'] if atcoderid in user_last_scores else None
            if (cur is not None) and (prev is not None):
                red = len(colors) - 1 # 3200+ is still red
                cc = min(cur // 400, red) if cur > 0 else -1
                pc = min(prev // 400, red) if prev > 0 else -1
                format_name = None
                if pc < cc:
                    format_name = 'promotion'
                elif 0 <= cc < pc:
                    format_name = 'relegation'
                if format_name is not None:
                    message = post_format[format_name].format(
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
        replace_symlink(rec_file, latest_rec_file)

    manager.finish()
