import pexpect
import xmltodict
import yaml
from dataclasses import dataclass


@dataclass
class Interface:
    """An interface object. Variable 'name' is mandatory, the rest are optional."""

    name: str
    description: str = ""
    ip: str = ""
    netmask: str = ""
    enabled: bool = True


class Netconf:
    """Netconf client python class"""

    def __init__(self, server_ip: str, port: str = "830"):

        self.ssh = self.connect(server_ip, port)
        self.counter = 0

    @property
    def message_id(self):
        """Always return a higher value"""
        self.counter += 1
        return self.counter

    def connect(self, server_ip, port):
        """Setting up netconf SSH connection to server"""

        username = "emil"
        password = "emil"

        ssh = pexpect.spawn(f"ssh {username}@{server_ip} -p {port} -s netconf")
        ssh.expect("password: ")
        ssh.sendline(password)
        print("Password entered")
        ssh.expect("]]>]]>")

        """Sending initial netconf Hello message"""
        message = {
            "hello": {
                "@xmlns": "urn:ietf:params:xml:ns:netconf:base:1.0",
                "capabilities": {"capability": "urn:ietf:params:netconf:base:1.0"},
            }
        }
        xml = xmltodict.unparse(message)
        ssh.sendline(xml + "]]>]]>")
        print("Hello message sent")
        ssh.expect("]]>]]>")

        return ssh

    def discard_changes(self):

        message = {
            "rpc": {
                "@message-id": self.message_id,
                "@xmlns": "urn:ietf:params:xml:ns:netconf:base:1.0",
                "discard-changes": None,
            }
        }
        xml = xmltodict.unparse(message)
        self.ssh.sendline(xml + "]]>]]>")
        self.ssh.expect("]]>]]>")  # end of RPC message
        self.ssh.expect("]]>]]>")  # end of RPC-reply

        output = self.ssh.before.decode("utf-8").replace('<?xml version="1.0" encoding="UTF-8"?>', "")
        return xmltodict.parse(output)["rpc-reply"]

    def get_interfaces(self) -> dict:
        """Retrieve interface config"""

        message = {
            "rpc": {
                "@message-id": self.message_id,
                "@xmlns": "urn:ietf:params:xml:ns:netconf:base:1.0",
                "get-config": {
                    "source": {"candidate": None},
                    "filter": {"interfaces": {"@xmlns": "urn:ietf:params:xml:ns:yang:ietf-interfaces"}},
                },
            }
        }
        xml = xmltodict.unparse(message)
        self.ssh.sendline(xml + "]]>]]>")
        self.ssh.expect("]]>]]>")  # end of RPC message
        self.ssh.expect("]]>]]>")  # end of RPC-reply

        output = self.ssh.before.decode("utf-8").replace('<?xml version="1.0" encoding="UTF-8"?>', "")
        output = xmltodict.parse(output)
        if "data" in output["rpc-reply"]:
            return yaml.dump(output["rpc-reply"]["data"]["interfaces"]["interface"])
        return yaml.dump(output)

    def configure_interface(self, intf: Interface):

        print("configure interface")
        interface = {"name": intf.name}
        if intf.description:
            interface["description"] = intf.description
            interface["enabled"] = intf.enabled
        if intf.ip and intf.netmask:
            interface["ipv4"] = {
                "@xmlns": "urn:ietf:params:xml:ns:yang:ietf-ip",
                "address": {"ip": intf.ip, "netmask": intf.netmask},
            }

        message = {
            "rpc": {
                "@message-id": self.message_id,
                "@xmlns": "urn:ietf:params:xml:ns:netconf:base:1.0",
                "edit-config": {
                    "target": {"candidate": None},
                    "error-option": "rollback-on-error",
                    "config": {
                        "interfaces": {
                            "@xmlns": "urn:ietf:params:xml:ns:yang:ietf-interfaces",
                            "interface": interface,
                        },
                    },
                },
            },
        }
        xml = xmltodict.unparse(message)
        self.ssh.sendline(xml + "]]>]]>")
        self.ssh.expect("]]>]]>")  # end of RPC message
        self.ssh.expect("]]>]]>")  # end of RPC-reply

        output = self.ssh.before.decode("utf-8").replace('<?xml version="1.0" encoding="UTF-8"?>', "")
        return xmltodict.parse(output)["rpc-reply"]

    def validate(self):

        print("validate")

        message = {
            "rpc": {
                "@message-id": self.message_id,
                "@xmlns": "urn:ietf:params:xml:ns:netconf:base:1.0",
                "validate": {"source": {"candidate": None}},
            }
        }

        xml = xmltodict.unparse(message)
        self.ssh.sendline(xml + "]]>]]>")
        self.ssh.expect("]]>]]>")  # end of RPC message
        self.ssh.expect("]]>]]>")  # end of RPC-reply

        output = self.ssh.before.decode("utf-8").replace('<?xml version="1.0" encoding="UTF-8"?>', "")
        return xmltodict.parse(output)["rpc-reply"]

    def commit(self):

        print("commit")

        message = {
            "rpc": {"@message-id": self.message_id, "@xmlns": "urn:ietf:params:xml:ns:netconf:base:1.0", "commit": None}
        }

        xml = xmltodict.unparse(message)
        self.ssh.sendline(xml + "]]>]]>")
        self.ssh.expect("]]>]]>")  # end of RPC message
        self.ssh.expect("]]>]]>")  # end of RPC-reply

        output = self.ssh.before.decode("utf-8").replace('<?xml version="1.0" encoding="UTF-8"?>', "")
        return xmltodict.parse(output)["rpc-reply"]


def xml_to_dict() -> dict:

    """Get multiline XML input"""
    buffer = []
    print("Enter XML:")
    while True:
        line = input()
        if not line:
            break
        buffer.append(line)

    xml = "\n".join(buffer)

    """Takes XML input, converts to dictionary"""
    if not xml:
        return ""

    dict = xmltodict.parse(xml)
    print(dict)
    return dict


def main():

    # xml_to_dict()
    # return

    netconf_server = Netconf(server_ip="10.0.0.2")

    output = netconf_server.discard_changes()
    print(output)

    interface = Interface("GigabitEthernet2", "TEST2", "10.10.10.10", "255.255.255.0")
    output = netconf_server.configure_interface(interface)
    print(output)

    interface = Interface("GigabitEthernet3", "TEST3", "11.11.11.11", "255.255.255.0")
    output = netconf_server.configure_interface(interface)
    print(output)

    output = netconf_server.get_interfaces()
    print(output)

    output = netconf_server.validate()
    print(output)

    output = netconf_server.commit()
    print(output)


if __name__ == "__main__":
    main()
