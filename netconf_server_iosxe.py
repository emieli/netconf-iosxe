import pexpect
import xmltodict
from netaddr import IPAddress


class NetconfServerIOSXE:
    """Python class for interacting with IOS-XE Netconf Server via SSH."""

    def __init__(self, name: str, ip: str, port=830, debug=False, username="admin", password="admin"):

        self.counter = 0
        self.debug = debug
        self.ip = ip
        self.name = name
        self.port = port
        self.username = username
        self.password = password

    @property
    def message_id(self):
        """Each netconf message should use a unique message ID"""
        self.counter += 1
        return self.counter

    def connect(self) -> None:
        """Setting up netconf SSH connection to server"""

        """Initial SSH connection attempt"""
        try:
            ssh = pexpect.spawn(f"ssh {self.username}@{self.ip} -p {self.port} -s netconf")
        except pexpect.exceptions.TIMEOUT:
            return f"Error when connecting to {self.name}: {ssh.before.decode('utf8')}"

        """Check for "password" or "unknown host" output"""
        try:
            index = ssh.expect(["password: ", "Are you sure you want to continue connecting"])
        except pexpect.exceptions.EOF:
            return f"Error when connecting to {self.name}: {ssh.before.decode('utf8')}"

        if index == 1:
            """Save host key"""
            ssh.sendline("yes")
            ssh.expect("password: ")

        """Enter password"""
        try:
            ssh.sendline(self.password)
            if self.debug:
                print("Password entered")
            ssh.expect("]]>]]>")
        except pexpect.exceptions.TIMEOUT:
            return f"Error when connecting to {self.name}: {ssh.before.decode('utf8')}"

        """Retrieve session ID, this is only really used for kill-session."""
        output = ssh.before.decode("utf-8").replace('<?xml version="1.0" encoding="UTF-8"?>', "")
        output = xmltodict.parse(output)
        self.session_id = output["hello"]["session-id"]
        self.ssh = ssh

        """Sending initial netconf Hello message"""
        message = {
            "hello": {
                "@xmlns": "urn:ietf:params:xml:ns:netconf:base:1.0",
                "capabilities": {"capability": "urn:ietf:params:netconf:base:1.0"},
            }
        }
        xml = xmltodict.unparse(message)
        ssh.sendline(xml + "]]>]]>")
        if self.debug:
            print("Hello message sent")
        ssh.expect("]]>]]>")

        return

    def discard_changes(self):
        """Discard any previous config changes in the candidate datastore, giving us a clean slate"""

        message = {
            "rpc": {
                "@message-id": self.message_id,
                "@xmlns": "urn:ietf:params:xml:ns:netconf:base:1.0",
                "discard-changes": None,
            }
        }
        return self.send_message(message)

    def get_ospf_neighbors(self) -> dict:
        """Retrieve all current OSPF neighbor router-IDs. Returns a dictionary in this format:\n
        {'GigabitEthernet4': '10.0.0.4', 'GigabitEthernet3': '10.0.0.3'}"""

        message = {
            "rpc": {
                "@message-id": self.message_id,
                "@xmlns": "urn:ietf:params:xml:ns:netconf:base:1.0",
                "get": {"filter": {"ospf-oper-data": {"@xmlns": "http://cisco.com/ns/yang/Cisco-IOS-XE-ospf-oper"}}},
            }
        }
        output = self.send_message(message)

        """Process the output and return data in the dictionary format we specified above"""
        try:
            output = output["data"]["ospf-oper-data"]["ospfv2-instance"]["ospfv2-area"]["ospfv2-interface"]
        except KeyError:
            """No data found, return nothing"""
            return

        neighbors = {}
        for interface in output:
            if "ospfv2-neighbor" in interface:
                neighbor = IPAddress(interface["ospfv2-neighbor"]["nbr-id"])
                neighbors[interface["name"]] = str(neighbor)
        return neighbors

    def get_config_interfaces(self) -> dict:
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
        return self.send_message(message)

    def configure_interface(self, name, ip, netmask):
        """Configure an interface with an IP-addres and a netmask"""

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
                            "interface": {
                                "name": name,
                                "ipv4": {
                                    "@xmlns": "urn:ietf:params:xml:ns:yang:ietf-ip",
                                    "address": {"ip": ip, "netmask": netmask},
                                },
                            },
                        },
                    },
                },
            },
        }
        return self.send_message(message)

    def remove_interface_ip(self, name, ip):
        """Remove an IP-address from the selected interface"""

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
                                    "name": name,
                                    "ipv4": {
                                        "@xmlns": "urn:ietf:params:xml:ns:yang:ietf-ip",
                                        "address": {"@xc:operation": "remove", "ip": ip},
                                    },
                                }
                            ],
                        },
                    },
                },
            },
        }
        return self.send_message(message)

    def get_route(self, prefix):
        """Check the routing table for information about a specific prefix"""

        message = {
            "rpc": {
                "@message-id": self.message_id,
                "@xmlns": "urn:ietf:params:xml:ns:netconf:base:1.0",
                "get": {
                    "filter": {
                        "routing-state": {
                            "@xmlns": "urn:ietf:params:xml:ns:yang:ietf-routing",
                            "routing-instance": {
                                "name": "default",
                                "ribs": {
                                    "rib": {
                                        "name": "ipv4-default",
                                        "routes": {
                                            "route": {
                                                "destination-prefix": prefix,
                                            }
                                        },
                                    }
                                },
                            },
                        }
                    }
                },
            },
        }
        return self.send_message(message)

    def close_session(self):
        """Gracefully kills the netconf session, undoing any changes so far."""

        message = {
            "rpc": {
                "@message-id": self.message_id,
                "@xmlns": "urn:ietf:params:xml:ns:netconf:base:1.0",
                "close-session": None,
            }
        }
        return self.send_message(message)

    def validate(self):
        """ "Validates" the config, I haven't ever seen it actually do anything."""

        message = {
            "rpc": {
                "@message-id": self.message_id,
                "@xmlns": "urn:ietf:params:xml:ns:netconf:base:1.0",
                "validate": {"source": {"candidate": None}},
            }
        }
        return self.send_message(message)

    def commit_with_confirm(self, timeout: int = 30):
        """Apply config changes, then wait the timeout period. If no second commit
        is received before the timer expires, then rollback."""

        message = {
            "rpc": {
                "@message-id": self.message_id,
                "@xmlns": "urn:ietf:params:xml:ns:netconf:base:1.0",
                "commit": {"confirmed": None, "confirm-timeout": timeout},
            }
        }
        return self.send_message(message)

    def commit(self):
        """Apply changes without possibility of rollbacks."""

        message = {
            "rpc": {
                "@message-id": self.message_id,
                "@xmlns": "urn:ietf:params:xml:ns:netconf:base:1.0",
                "commit": None,
            }
        }
        return self.send_message(message)

    def lock_candidate(self):
        """Lock the candidate datastore so that only we can make changes"""

        message = {
            "rpc": {
                "@message-id": self.message_id,
                "@xmlns": "urn:ietf:params:xml:ns:netconf:base:1.0",
                "lock": {"target": {"candidate": None}},
            }
        }
        return self.send_message(message)

    def lock_running(self):
        """Lock running config so that only we can make changes"""

        message = {
            "rpc": {
                "@message-id": self.message_id,
                "@xmlns": "urn:ietf:params:xml:ns:netconf:base:1.0",
                "lock": {"target": {"running": None}},
            }
        }
        return self.send_message(message)

    def send_message(self, message: dict) -> dict:
        """Send netconf message to server, process output and return it."""

        xml = xmltodict.unparse(message, pretty=True, indent="  ")
        if self.debug:
            print(f"\n====== {self.name} ======")
            print(xml.strip())
        self.ssh.sendline(xml + "]]>]]>")
        self.ssh.expect("]]>]]>")  # end of RPC message
        self.ssh.expect("]]>]]>")  # end of RPC-reply

        output_xml = self.ssh.before.decode("utf-8").replace('<?xml version="1.0" encoding="UTF-8"?>', "")
        output_dict = xmltodict.parse(output_xml)
        if self.debug:
            print(xmltodict.unparse(output_dict, pretty=True, indent="  "))

        if "rpc-error" in output_dict:
            return output_dict["rpc-error"]

        return output_dict["rpc-reply"]
