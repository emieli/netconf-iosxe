import xmltodict
import yaml


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
    print(yaml.dump(dict))


if __name__ == "__main__":
    xml_to_dict()
