import requests
import json
import urllib.parse

epochsPerVotingPeriod = 64
host = "127.0.0.1"
port = "3500"
slotsPerEpoch = 32
slotsPerVotingPeriod = epochsPerVotingPeriod * slotsPerEpoch


class eth1Data:
    def __init__(self, root, hashval):
        self.depositRoot = root
        self.blockHash = hashval

    def __hash__(self):
        return hash((self.depositRoot, self.blockHash))

    def __eq__(self, other):
        return self.__hash__() == other.__hash__()


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

print("headEpoch={} lastVotingPeriodStartEpoch={} thisVotingPeriodStartEpoch={}\
     nextVotingPeriodStartEpoch={}".format(headEpoch, lastVotingPeriodStartEpoch, thisVotingPeriodStartEpoch, nextVotingPeriodStartEpoch))

# CREATE CANONICAL CHAIN TO REMOVE ORPHANS

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

print("For the last voting period (startEpoch={} startSlot={} through epoch={}\
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
        thisEth1Data = eth1Data(data['blockContainers'][0]['block']['block']['body']['eth1Data']['depositRoot'],
                                data['blockContainers'][0]['block']['block']['body']['eth1Data']['blockHash'])

        votesLast[thisEth1Data] = votesLast.get(thisEth1Data, 0) + 1

sortedLast = {k: v for k, v in sorted(
    votesLast.items(), key=lambda item: item[1], reverse=True)}

for item in sortedLast.items():
    print("depositRoot={} blockHash={} count={} ({:.2f}%)".format(
        item[0].depositRoot, item[0].blockHash, item[1], 100*float(item[1])/slotsPerVotingPeriod))

# THIS PERIOD
votesThis = {}

# slotsThusFar will only include slots in the finalized chain
slotsThusFar = (finalizedEpoch - thisVotingPeriodStartEpoch) * slotsPerEpoch

print("For the ongoing voting period (startEpoch={} \
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
        thisEth1Data = eth1Data(data['blockContainers'][0]['block']['block']['body']['eth1Data']['depositRoot'],
                                data['blockContainers'][0]['block']['block']['body']['eth1Data']['blockHash'])

        votesThis[thisEth1Data] = votesThis.get(thisEth1Data, 0) + 1

sortedThis = {k: v for k, v in sorted(
    votesThis.items(), key=lambda item: item[1], reverse=True)}

for item in sortedThis.items():
    print("depositRoot={} blockHash={} count={} ({:.2f}% of full period {:.2f}% of potential votes THUS far)".format(
        item[0].depositRoot,
        item[0].blockHash,
        item[1],
        100*float(item[1])/slotsPerVotingPeriod,
        100*float(item[1])/slotsThusFar))
