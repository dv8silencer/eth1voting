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
print("**SLIGHT DELAY**: HEAD IS REPORTED ABOVE, BUT THIS TOOL FOLLOWS ETH1DATA VOTES FROM ONLY THE FINALIZED PORTION OF CHAIN.")
print("================================")
# CREATE CANONICAL CHAIN TO EXCLUDE ORPHANS, GIVE MORE STABLE VALUES BETWEEN RUNTIMES

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

# PREVIOUS PERIOD
votesLast = {}

print("For the LAST voting period (startEpoch={} startSlot={} through epoch={} \
slot={}):".format(lastVotingPeriodStartEpoch, lastVotingPeriodStartEpoch*slotsPerEpoch,
                  thisVotingPeriodStartEpoch-1, (thisVotingPeriodStartEpoch*slotsPerEpoch)-1))

for epoch in range(lastVotingPeriodStartEpoch, thisVotingPeriodStartEpoch):
    if epoch < 0:
        continue
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
        currentData = votesLast.get(thisEth1Data, neweth1DataStat)
        currentData.count += 1
        votesLast[thisEth1Data] = currentData

sortedLast = {k: v for k, v in sorted(
    votesLast.items(), key=lambda item: item[1].count, reverse=True)}

for item in sortedLast.items():
    print("depositRoot=0x{}... blockHash=0x{}\n\t\tcount={} ({:.2f}%)".format(
        (item[0].depositRoot)[:10], item[0].blockHash, item[1].count, 100 *
        float(item[1].count)/slotsPerVotingPeriod))

print("================================")
print("================================")

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
        votesThis[thisEth1Data] = currentData

sortedThis = {k: v for k, v in sorted(
    votesThis.items(), key=lambda item: item[1].count, reverse=True)}

for item in sortedThis.items():
    print("depositRoot=0x{}... blockHash=0x{}\n\t\tcount={} ({:.2f}% of full period {:.2f}% of\
 potential votes THUS far.)".format(
        (item[0].depositRoot)[:10],
        item[0].blockHash,
        item[1].count,
        100*float(item[1].count)/slotsPerVotingPeriod,
        100*float(item[1].count)/slotsThusFar))
