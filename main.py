"""
Copyright 2020 dv8silencer

This file is part of eth1voting.

eth1voting is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 3 of the License, or
(at your option) any later version.

eth1voting is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with eth1voting; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA -->
"""

import requests
import json
import urllib.parse
import base64

epochsPerVotingPeriod = 64
host = "127.0.0.1"
port = "3500"
gethhost = "192.168.1.7"
gethport = "8545"
slotsPerEpoch = 32
slotsPerVotingPeriod = epochsPerVotingPeriod * slotsPerEpoch

# eth1Data represents a particular candidate that is being voted for during the voting period
# this has __hash__ and __eq__ as it is used as a key in a dictionary


class eth1Data:
    def __init__(self, root, hashval):
        self.depositRoot = root
        self.blockHash = hashval

    def __hash__(self):
        return hash((self.depositRoot, self.blockHash))

    def __eq__(self, other):
        return self.__hash__() == other.__hash__()

# eth1DataStats stores stats on each of the eth1data candidates


class eth1DataStats:
    def __init__(self):
        self.count = 0
        self.graffiti = []
        self.prysm = 0
        self.lighthouse = 0
        self.teku = 0
        self.nimbus = 0
        self.withinBounds = False


response = requests.get(
    'http://{}:{}/eth/v1alpha1/beacon/chainhead'.format(host, port))
data = response.content.decode()
data = json.loads(data)
headSlot = int(data['headSlot'])
headEpoch = int(data['headEpoch'])

lastVotingPeriodStartEpoch = (
    headEpoch // epochsPerVotingPeriod - 1) * epochsPerVotingPeriod
thisVotingPeriodStartEpoch = lastVotingPeriodStartEpoch + epochsPerVotingPeriod
nextVotingPeriodStartEpoch = thisVotingPeriodStartEpoch + epochsPerVotingPeriod
lastVotingPeriodStartSlot = lastVotingPeriodStartEpoch * slotsPerEpoch

print("headEpoch={} lastVotingPeriodStartEpoch={} thisVotingPeriodStartEpoch={} \
nextVotingPeriodStartEpoch={}".format(headEpoch, lastVotingPeriodStartEpoch, thisVotingPeriodStartEpoch, nextVotingPeriodStartEpoch))

print("================================")
# CREATE CANONICAL CHAIN TO EXCLUDE ORPHANS

chain = []
finalizedSlot = int(data['finalizedSlot'])
finalizedEpoch = int(data['finalizedEpoch'])
# Saving finalizedRoot in own var in case I want it in the future
finalizedRoot = data['finalizedBlockRoot']
currentRoot = finalizedRoot

while True:
    response = requests.get("http://{}:{}/eth/v1alpha1/beacon/blocks?root={}".format(
        host, port, urllib.parse.quote(currentRoot)))
    data = response.content.decode()
    data = json.loads(data)
    tempSlot = int(data['blockContainers'][0]['block']['block']['slot'])
    if (tempSlot == 0) or (tempSlot < lastVotingPeriodStartSlot):
        break
    chain.append(currentRoot)
    currentRoot = data['blockContainers'][0]['block']['block']['parentRoot']

# THIS PERIOD
votesThis = {}

# slotsThusFar will only include slots in the finalized chain
slotsThusFar = (finalizedEpoch - thisVotingPeriodStartEpoch) * slotsPerEpoch

if(slotsThusFar <= 0):
    print("Insuffient data for current voting period.  Exiting.")
    quit()

print("For the ONGOING voting period (startEpoch={} \
startSlot={} through epoch={} slot={}, {:.2f}% complete):".format(thisVotingPeriodStartEpoch,
                                                                  thisVotingPeriodStartEpoch*slotsPerEpoch,
                                                                  nextVotingPeriodStartEpoch-1,
                                                                  (nextVotingPeriodStartEpoch *
                                                                   slotsPerEpoch)-1,
                                                                  100*(float(slotsThusFar)/slotsPerVotingPeriod)))

# To establish "vote for majority" algorithm time bounds
seconds_per_slot = 12
seconds_per_eth1_block = 13
eth1_follow_distance = 2048
genesis_time = 1605700800  # Prymont
upper_bound_ts = genesis_time + (thisVotingPeriodStartEpoch*slotsPerEpoch *
                                 seconds_per_slot) - (eth1_follow_distance*seconds_per_eth1_block)
lower_bound_ts = genesis_time + (thisVotingPeriodStartEpoch*slotsPerEpoch *
                                 seconds_per_slot) - (eth1_follow_distance*seconds_per_eth1_block * 2)


for epoch in range(thisVotingPeriodStartEpoch, headEpoch):
    for slot in range(epoch * slotsPerEpoch, (epoch+1) * slotsPerEpoch):
        if slot == 0:
            continue
        response = requests.get(
            "http://{}:{}/eth/v1alpha1/beacon/blocks?slot={}".format(host, port, slot))
        data = response.content.decode()
        data = json.loads(data)
        if data["blockContainers"] == list():
            continue
        if data['blockContainers'][0]['blockRoot'] not in chain:
            continue
        tempDepositRoot = data['blockContainers'][0]['block']['block']['body']['eth1Data']['depositRoot']
        hexDepositRoot = base64.b64decode(tempDepositRoot).hex()
        tempBlockHash = data['blockContainers'][0]['block']['block']['body']['eth1Data']['blockHash']
        hexBlockHash = base64.b64decode(tempBlockHash).hex()
        thisEth1Data = eth1Data(hexDepositRoot, hexBlockHash)
        neweth1DataStat = eth1DataStats()
        currentData = votesThis.get(thisEth1Data, neweth1DataStat)
        currentData.count += 1
        currentData.graffiti.append(
            base64.b64decode(data['blockContainers'][0]['block']['block']['body']['graffiti']))
        votesThis[thisEth1Data] = currentData

for item in votesThis.items():
    for eachGraffiti in item[1].graffiti:
        lowercased = str(eachGraffiti, "utf-8").lower()
        if ("prylabs" in lowercased) or ("prysm" in lowercased):
            item[1].prysm += 1
        if ("lighthouse" in lowercased) or (("lh" in lowercased) and ("ef" in lowercased) and ("temp" in lowercased)):
            item[1].lighthouse += 1
        if "teku" in lowercased:
            item[1].teku += 1
        if "nimbus" in lowercased:
            item[1].nimbus += 1
    # Obtain timestamp from eth1 endpoint
    url = "http://{}:{}/".format(gethhost, gethport)
    payload = {
        "method": "eth_getBlockByHash",
        "params": ["0x" + item[0].blockHash, True],
        "jsonrpc": "2.0",
        "id": 0,
    }
    response = requests.post(url, json=payload).json()
    try:
        block_ts = int(response["result"]["timestamp"], 0)
    except:
        continue
    if (block_ts < upper_bound_ts) and (block_ts > lower_bound_ts):
        item[1].withinBounds = True


sortedThis = {k: v for k, v in sorted(
    votesThis.items(), key=lambda item: item[1].count, reverse=True)}

print("Ordering of tally (last column): Prysm,Lightouse,Teku,Nimbus")
for item in sortedThis.items():
    print("depositRoot=0x{}... blockHash=0x{}".format((item[0].depositRoot)[:10],
                                                      item[0].blockHash,))
    print("withinBounds={}  count={} ({:.2f}% of full period {:.2f}% of\
 potential votes THUS far. Tally=P{},L{},T{},N{})".format(
        item[1].withinBounds,
        item[1].count,
        100*float(item[1].count)/slotsPerVotingPeriod,
        100*float(item[1].count)/slotsThusFar,
        item[1].prysm, item[1].lighthouse, item[1].teku, item[1].nimbus))
