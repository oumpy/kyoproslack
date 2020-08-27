#!/usr/bin/env python3
# -*- coding: utf-8 -*- 

import os
import sys
import time
import numpy as np

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import torch.nn.utils as torchutils

from visual import VisualAngleDataset
from visual import VisualAngleBatch

from model import Model

if __name__ == '__main__':

    # 引数の設定

    seed           = int(sys.argv[1])    # 乱数シード
    batchsize      = int(sys.argv[2])    # バッチサイズ

    scpfile_angle  = sys.argv[3]         # 頭部角度データの scp ファイル名
    scpfile_visual = sys.argv[4]         # 映像データの scp ファイル名
                                         
    orgfile        = sys.argv[5]         # 推定元モデルファイル名
    estfile        = sys.argv[6]         # 推定後モデルファイル名

    drop_rate      = float(sys.argv[7])  # 映像フレームのドロップ率

    spec           = sys.argv[8]         # モデルタイプ

    # 乱数シードの設定

    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    
    # 学習データの読み込み準備

    ids = []
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        ids.append(line.strip())

    dataset = VisualAngleDataset(ids,
                                 scpfile_angle,
                                 scpfile_visual)

    dataloader = torch.utils.data.DataLoader(dataset,
                                             batch_size=4,
                                             num_workers=4,
                                             collate_fn=VisualAngleBatch,
                                             shuffle=False)

    # モデルの準備

    spec = [int(x) for x in spec.split('_')]
    if len(spec)!=5:
        raise RuntimeError('#0 in train.py')

    c1 = spec[0]
    c2 = spec[1]
    f3 = spec[2]
    n4 = spec[3]
    f5 = spec[4]

    model = Model(c1=c1, c2=c2, f3=f3, n4=n4, f5=f5)
    if orgfile.lower() != 'none':
        model.load_state_dict(torch.load(orgfile))
    model.cuda()

    # モデルパラメータの学習

    criterion = nn.MSELoss().cuda()
    optimizer = optim.Adam(model.parameters())

    for visuals, angles in dataloader:

        # 映像フレームドロップ処理

        for n in range(len(visuals)):
            tmp_drop_rate = np.random.rand(1)*drop_rate
            drops = np.random.rand(len(visuals[n]))>tmp_drop_rate
            visuals[n] = np.asarray([x[1] if x[0] else np.zeros_like(x[1])
                                     for x in zip(drops, visuals[n])],
                                    dtype=np.float32)

        # モデルパラメータの更新

        visuals = torch.from_numpy(visuals).cuda()
        angles  = torch.from_numpy( angles).cuda()

        model.zero_grad()
        y, _ = model(visuals)
        
        y = y.view(-1)
        angles = angles.view(-1)

        loss = criterion(y[-900.0<angles], angles[-900.0<angles])

        loss.backward()
        optimizer.step()

        print('%f'%loss)
        sys.stdout.flush()

    # モデルの保存

    torch.save(model.state_dict(), estfile)
