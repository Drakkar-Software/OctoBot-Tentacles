import json
import logging
import os


def parse_package(package_content):
    description_pos = package_content.find("$package_description")
    if description_pos > -1:
        description_begin_pos = package_content.find("{")
        description_end_pos = package_content.find("}") + 1
        description_raw = package_content[description_begin_pos:description_end_pos]
        description = json.loads(description_raw)
        description_list[description["name"]] = description


if __name__ == '__main__':
    description_list = {}
    package_list_file = "packages_list.json"

    # Foreach folder (not hidden)
    for f in os.listdir(os.getcwd()):
        if os.path.isdir(f) and not f.startswith('.'):
            for filename in os.listdir(f):
                if filename.endswith(".py"):
                    with open("{0}/{1}".format(f, filename), "r") as package:
                        parse_package(package.read())
                        logging.info("Reading package {0}...".format(package))

    # Create package list file
    with open(package_list_file, "w") as package_list:
        package_list.write(json.dumps(description_list))

    logging.info("Generation complete")
