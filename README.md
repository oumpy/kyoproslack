# 競プロSlack Bot Scripts by Python

## ACRank (acrank.py)

原案・原作：AtamaokaC

### 概要

前回実行以降のメンバーのAtCoder精進状況（新規AC数、得点）をAtCoder Problemsから取得し、上位をランキングにして指定したチャネルへ投稿する。これにより、みんなで盛り上がっていっそう精進することができる（たぶん）。

中身はすべてPython 3で書かれている。SDK for Pythonの`slack.WebClient`を使ってSlackにアクセスする。

### 準備

デフォルトで必要なファイル／ディレクトリは次の3つ。

- `~/var/acrank/record/`：記録を保存するためのディレクトリ。
- `~/var/acrank/memberlist.txt`：メンバーのリスト。「名前　SlackのID　AtCoderのID」をタブ区切りで並べた行の集合。名前はコメントみたいなもので実際は使用しない。
- `~/var/acrank/slack_token`：Slack用のトークン。

### 使い方

上記のファイルを設置して、

```bash
$ python acrank.py week 先週
```

のように実行すると、

```
【先週のAtCoder ACランキング】
1位：....
```

のようにSlackに投稿してくれる（初回は投稿なし、その時点までの総AC数・点数の記録のみ）。第1引数のweekは別のサイクル同士を区別する記号なので、何でもよいが、次回も同じものを指定する。第2引数はタイトルに反映される。

Botとして運用する場合は、crontabに記述して定時に動かすとよい。以下は設定例。

```bash
#min    hour    day     month   week    command
0       6       *       *       1       acrank.py week 先週 -a
0       21      *       *       4       acrank.py week 今週 --inprogress
30      20      *       *       6       acrank.py week 今週 --inprogress --mute
0       6       1       *       *       sleep 10 && acrank.py month `lastmonth`月
```

### オプション

- `--inprogress`：サイクルをリセットせず、途中経過を投稿する。次の投稿はこの投稿に対するスレッド返信投稿（チャネルにも投稿あり）となる。
- `--mute`：すでに`--inprogress`で投稿した経過がある場合、チャネルへの投稿なしでスレッド内のみとする。
- `--noslack`：Slackに投稿する代わりに投稿メッセージを標準出力に出力する。
- `-c (channel name)`：投稿するチャネルを指定する。デフォルトは`'competition'`。
- `-n (integer)`：指定した順位までをランキング。デフォルトは5。
- `-s (integer)`：指定した問題数以上を解いていれば、順位に関わらずランクインとする。`0`を指定した場合は何も効力がない。
- `-a` / `--allsolvers`：1問以上解いた人はランク外も名前のみ発表。
- `--slacktoken (string)`：Slack API Bot Tokenを直接指定（slack_tokenファイルは無視される）。

### 補助スクリプト

【〜月の、、】と簡単に設定するため（だけ）の簡単なシェルスクリプト。

- `thismonth`：今月は何月か（例：2、12など）を表示する。
- `lastmonth`：先月は何月だったかを表示する。1月に実行すると12。
- `showmonth.py`：さらに高機能なPythonスクリプト。デフォルト動作は`this_month`と同じ。以下のオプションあり。
  - `-p` / `--prev`：前月。単独で指定すると`last_month`と同じ。
  - `-n` / `--next`：来月。
  - `-a (integer)` / `--after (integer)`：何ヶ月後かを指定。負の数もOK。
  - `--set_month (integer)`：現在ではなく指定した月を起点にする。
  - `-s` / `--slacksymbol`：Slack用に各月のシンボルを添えて出力。`:bamboo: 1`、`:christmas_tree:12`など。

