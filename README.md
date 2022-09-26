# What is this?
This was an exercise in learning how to interact with IOS-XE device using the Netconf protocol.

Topology:

    R2--R3
     \  /
      R4

The topology consists of three links interconnecting R2, R3 and R4. All links run /29 subnets in the
10/8 range using the 10.X.Y.Z model:
 - X, lower node ID
 - Y, higher node ID
 - Z, local node ID

For the R2-R3 link, the R2 address is 10.2.3.2/29. The R3 address is 10.2.3.3/29. 
All links are configured with OSPF.

## Network-wide transaction
Using this topology, I attempted to simulate a "network-wide" transaction where all linknets were
changed from using a 10. address to a 11. address. The goal was to demonstrate how a change was
prepared in the candidate datastore, applied on all routers with a commit-confirm, verified, and if 
successful committed one more time to the running datastore. If anything went wrong, the final commit would not trigger and the config would be rolled back to a
previously known working config.

## What main() does
1. We connect to all routers with netconf
2. We discard any previous changes and lock the candidate config so that noone else can make changes
3. We get all current OSPF neighbors, giving us something something to compare against later
4. We reconfigure all interfaces from using a 10. to a 11. address.
   This step is odd because we must remove the same address twice. This is probably due to a bug as the 
   IOS-XE node adds the old 10. address twice whenever a commit-confirm "fails" and config is rolled back.
   This means that we need to remove it twice for it to be fully removed.
5. We configure the new interface IP-addresses.
6. We perform a commit-confirm without a timeout of 30 seconds. If the change is not committed again
   within 30 seconds, roll back. Useful if something goes wrong.
7. Wait 15 seconds for config changes to be applied and OSPF adjacencies to come back up.
   Then check the OSPF adjacencies, and if they match the previous neighbors then the change was 
   successful.
8. If OSPF neighbor match, run the final commit to fully apply config and prevent a rollback.

## Out-of-band necessary
This lab worked since I was able to directly connect all IOS-XE nodes to the script-host (10.1.1.111/24) 
that ran this script. This script will not work if any router, say R3, is only reachable from the script-
host via R2 or R4, as running the "commit-confirm" command on R3 will hang and timeout, so the R4 commit
will never have a chance to run. The script-host must have out-of-band access to each router.

## IOS-XE config example (R2, running 17.3.2)

    aaa new-model
    aaa authorization exec default local
    username admin privilege 15 password admin
    !
    netconf-yang
    netconf-yang feature candidate-datastore
    !
    interface GigabitEthernet1
    description Script-host
    ip address 10.1.1.2 255.255.255.0
    !
    interface GigabitEthernet3
    description R2-R3 link
    ip address 10.2.3.2 255.255.255.248
    ip ospf network point-to-point
    ip ospf 1 area 0
    !
    interface GigabitEthernet4
    description R2-R4 link
    ip address 10.2.4.2 255.255.255.248
    ip ospf network point-to-point
    ip ospf 1 area 0
    !

# Install

    apt install python3-venv
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install xmltodict pexpect pyyaml netaddr

### Run

    source venv/bin/activate
    python3 main.py