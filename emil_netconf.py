import pexpect
import xmltodict
import yaml
from dataclasses import dataclass
import json


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

        self.ssh, self.session_id = self.connect(server_ip, port)
        self.counter = 0

    @property
    def message_id(self):
        """Always return a higher value"""
        self.counter += 1
        return self.counter

    def connect(self, server_ip, port) -> object:
        """Setting up netconf SSH connection to server"""

        username = "emil"
        password = "emil"

        ssh = pexpect.spawn(f"ssh {username}@{server_ip} -p {port} -s netconf")
        ssh.expect("password: ")
        ssh.sendline(password)
        print("Password entered")
        ssh.expect("]]>]]>")

        output = ssh.before.decode("utf-8").replace('<?xml version="1.0" encoding="UTF-8"?>', "")
        output = xmltodict.parse(output)
        session_id = output["hello"]["session-id"]

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

        return ssh, session_id

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
        return xmltodict.parse(output)

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

    def remove_interface_ip(self, interface_name):

        output = self.get_interfaces()
        for interface in output["rpc-reply"]["data"]["interfaces"]["interface"]:
            if not interface["name"] == interface_name:
                continue

            print(interface)
            del interface["ipv4"]["address"]

            message = {
                "rpc": {
                    "@message-id": self.message_id,
                    "@xmlns": "urn:ietf:params:xml:ns:netconf:base:1.0",
                    "edit-config": {
                        "target": {"candidate": None},
                        "error-option": "rollback-on-error",
                        "config": {
                            "@xmlns:xc": "urn:ietf:params:xml:ns:netconf:base:1.0",
                            "interfaces": {
                                "@xmlns": "urn:ietf:params:xml:ns:yang:ietf-interfaces",
                                "interface": [
                                    {
                                        "name": "GigabitEthernet2",
                                        "ipv4": {
                                            "@xmlns": "urn:ietf:params:xml:ns:yang:ietf-ip",
                                            "address": {"@xc:operation": "remove", "ip": "10.10.10.10"},
                                        },
                                    }
                                ],
                            },
                        },
                    },
                },
            }
            xml = xmltodict.unparse(message, pretty=True)
            print(xml)
            self.ssh.sendline(xml + "]]>]]>")
            self.ssh.expect("]]>]]>")  # end of RPC message
            self.ssh.expect("]]>]]>")  # end of RPC-reply

            output = self.ssh.before.decode("utf-8").replace('<?xml version="1.0" encoding="UTF-8"?>', "")
            return xmltodict.parse(output)["rpc-reply"]

    def close_session(self):

        message = {
            "rpc": {
                "@message-id": self.message_id,
                "@xmlns": "urn:ietf:params:xml:ns:netconf:base:1.0",
                "close-session": None,
            }
        }

        xml = xmltodict.unparse(message)
        print(xml)
        self.ssh.sendline(xml + "]]>]]>")
        self.ssh.expect("]]>]]>")  # end of RPC message
        self.ssh.expect("]]>]]>")  # end of RPC-reply

        output = self.ssh.before.decode("utf-8").replace('<?xml version="1.0" encoding="UTF-8"?>', "")
        return xmltodict.parse(output)

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

    def commit_with_confirm(self):

        message = {
            "rpc": {
                "@message-id": self.message_id,
                "@xmlns": "urn:ietf:params:xml:ns:netconf:base:1.0",
                "commit": {"confirmed": None, "confirm-timeout": 20},
            }
        }

        xml = xmltodict.unparse(message)
        self.ssh.sendline(xml + "]]>]]>")
        self.ssh.expect("]]>]]>")  # end of RPC message
        self.ssh.expect("]]>]]>")  # end of RPC-reply

        output = self.ssh.before.decode("utf-8").replace('<?xml version="1.0" encoding="UTF-8"?>', "")
        return xmltodict.parse(output)["rpc-reply"]

    def commit(self):

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
    netconf_server = Netconf(server_ip="10.0.0.2")
    netconf_server.discard_changes()

    interface = Interface("GigabitEthernet2", "TEST2", "10.10.10.10", "255.255.255.0")
    output = netconf_server.configure_interface(interface)
    print(output)

    output = netconf_server.commit()
    print(output)

    output = netconf_server.remove_interface_ip("GigabitEthernet2")
    print(output)

    output = netconf_server.commit()
    print(output)


if __name__ == "__main__":
    main()
