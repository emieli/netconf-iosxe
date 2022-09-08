import os
from ncclient import manager
from rich import print
from lxml import etree

if __name__ == "__main__":

    device = {
        "host": "10.0.0.2",
        "port": 830,
        "username": "emil",
        "password": "emil",
        "hostkey_verify": False,
    }
    # with manager.connect(**device) as nconf:
    #     print(list(nconf.server_capabilities)) 

    '''imports and "device" definition omitted '''
    # with manager.connect(**device) as nconf:
    #     nc_reply = nconf.get_config(source="running")
    #     print(type(nc_reply)) 

    with manager.connect(**device) as nconf:
        nc_reply = nconf.get_config(source="running")
        xml_data = etree.tostring(
            nc_reply.data_ele, 
            pretty_print=True
        ).decode()
        print(xml_data) 