import time
from netconf_server_iosxe import NetconfServerIOSXE

"""This was an exercise in learning how to interact with IOS-XE device using the Netconf protocol.

=== Topology: ===

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

=== Network-wide transaction ===
Using this topology, I attempted to simulate a "network-wide" transaction where all linknets were
changed from using a 10. address to a 11. address. The goal was to demonstrate how a change was
prepared in the candidate datastore, applied on all routers with a commit-confirm, verified, and if 
successful committed one more time to the running datastore.

If anything went wrong, the final commit would not trigger and the config would be rolled back to a
previously known working config.

=== What main() does ===
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

=== Out-of-band necessary ===
This lab worked since I was able to directly connect all IOS-XE nodes to the script-host (10.1.1.111/24) 
that ran this script. This script will not work if any router, say R3, is only reachable from the script-
host via R2 or R4, as running the "commit-confirm" command on R3 will hang and timeout, so the R4 commit
will never have a chance to run. The script-host must have out-of-band access to each router.

=== IOS-XE config example (R2) ===
! Cisco IOS XE Software, Version 17.03.02
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
"""


def main():

    R2 = NetconfServerIOSXE(name="R2", ip="10.1.1.2", debug=True)
    R3 = NetconfServerIOSXE(name="R3", ip="10.1.1.3", debug=False)
    R4 = NetconfServerIOSXE(name="R4", ip="10.1.1.4", debug=False)
    routers = [R2, R3, R4]

    """Set up Netconf connection"""
    for router in routers:
        error = router.connect()
        if error:
            quit(error)

    """Discard previous config changes and lock the candidate config so no one else can make changes"""
    for router in routers:
        router.discard_changes()
        router.lock_candidate()

    """Get OSPF neighbors"""
    for router in routers:
        router.ospf_neighbors = router.get_ospf_neighbors()
        print(router.ospf_neighbors)

    """Reconfigure interfaces"""
    R2.remove_interface_ip(name="GigabitEthernet3", ip="10.2.3.2")
    R2.remove_interface_ip(name="GigabitEthernet3", ip="10.2.3.2")
    R2.remove_interface_ip(name="GigabitEthernet4", ip="10.2.4.2")
    R2.remove_interface_ip(name="GigabitEthernet4", ip="10.2.4.2")
    R2.configure_interface(name="GigabitEthernet3", ip="11.2.3.2", netmask="255.255.255.248")
    R2.configure_interface(name="GigabitEthernet4", ip="11.2.4.2", netmask="255.255.255.248")

    R3.remove_interface_ip(name="GigabitEthernet2", ip="10.2.3.3")
    R3.remove_interface_ip(name="GigabitEthernet2", ip="10.2.3.3")
    R3.remove_interface_ip(name="GigabitEthernet4", ip="10.3.4.3")
    R3.remove_interface_ip(name="GigabitEthernet4", ip="10.3.4.3")
    R3.configure_interface(name="GigabitEthernet2", ip="11.2.3.3", netmask="255.255.255.248")
    R3.configure_interface(name="GigabitEthernet4", ip="11.3.4.3", netmask="255.255.255.248")

    R4.remove_interface_ip(name="GigabitEthernet3", ip="10.3.4.4")
    R4.remove_interface_ip(name="GigabitEthernet3", ip="10.3.4.4")
    R4.remove_interface_ip(name="GigabitEthernet2", ip="10.2.4.4")
    R4.remove_interface_ip(name="GigabitEthernet2", ip="10.2.4.4")
    R4.configure_interface(name="GigabitEthernet3", ip="11.3.4.4", netmask="255.255.255.248")
    R4.configure_interface(name="GigabitEthernet2", ip="11.2.4.4", netmask="255.255.255.248")

    """Attempt to apply changes, we get 30 seconds to check for errors"""
    R2.commit_with_confirm(timeout=30)
    R3.commit_with_confirm(timeout=30)
    R4.commit_with_confirm(timeout=30)

    time.sleep(15)

    """Get OSPF neighbors again"""
    for router in routers:
        ospf_neighbors = router.get_ospf_neighbors()
        if ospf_neighbors != router.ospf_neighbors:
            print(f"{router.name} OSPF neighbors mismatch!")
            print(f"  Before: {router.ospf_neighbors}")
            print(f"   After: {ospf_neighbors}")
            quit("  Script aborted")

    """Commit changes if all went well"""
    R2.commit()
    R3.commit()
    R4.commit()

    print("Success!")


if __name__ == "__main__":
    # xml_to_dict()
    main()
