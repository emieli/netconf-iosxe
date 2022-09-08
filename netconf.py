import os
from ncclient import manager
from rich import print
from lxml import etree

def get_capabilities(device):
    with manager.connect(**device) as nconf:
        print(list(nconf.server_capabilities)) 

def get_config(device):

    with manager.connect(**device) as nconf:
        nc_reply = nconf.get_config(source="running")
        xml_data = etree.tostring(
            nc_reply.data_ele, 
            pretty_print=True
        ).decode()
        print(xml_data)
    return

def configure_loopback(device):

    with open('loopback_config.xml', 'r') as file:
        loopback_config = file.read()
    
    with manager.connect(**device) as m:
        nc_reply = m.edit_config(target='candidate', config=loopback_config)
        print(nc_reply)
        nc_reply = m.commit()
        print(nc_reply)
    
    return

def main():

    device = {
        "host": "10.0.0.2",
        "port": 830,
        "username": "emil",
        "password": "emil",
        "hostkey_verify": False,
    }

    #get_capabilities(device)
    #get_config(device)
    configure_loopback(device)


if __name__ == "__main__":
    main()
