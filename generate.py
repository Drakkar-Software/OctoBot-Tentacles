import json
import logging
import os


def parse_package(package_content):
    description_pos = package_content.find("$tentacle_description")
    if description_pos > -1:
        description_begin_pos = package_content.find("{")
        description_end_pos = package_content.find("}") + 1
        description_raw = package_content[description_begin_pos:description_end_pos]
        description = json.loads(description_raw)
        description_list[description["name"]] = description


def read_package(path):
    for file_name in os.listdir(path):
        if file_name.endswith(".py"):
            with open("{0}/{1}".format(path, file_name), "r") as package:
                parse_package(package.read())
                logging.info("Reading tentacle {0}...".format(package))
        else:
            file_name = "{0}/{1}".format(path, file_name)
            if os.path.isdir(file_name) and not path.startswith('.'):
                read_package(file_name)


if __name__ == '__main__':
    description_list = {}
    package_list_file = "tentacles_list.json"

    # Foreach folder (not hidden)
    for root_dir in os.listdir(os.getcwd()):
        if os.path.isdir(root_dir) and not root_dir.startswith('.'):
            read_package(root_dir)

    # Create package list file
    with open(package_list_file, "w") as package_list:
        package_list.write(json.dumps(description_list))

    logging.info("Generation complete")
