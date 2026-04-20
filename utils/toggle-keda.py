#!/usr/bin/env python3
# Usage: python3 toggle_keda.py <path-to-yaml> <night|morning>

import os
import sys


if len(sys.argv) == 3:
    file_path = sys.argv[1]
    mode      = sys.argv[2]   #"night" | "morning"
else:
    file_path = os.environ.get("FILE_PATH")
    mode      = os.environ.get("MODE")
    if not file_path or not mode:
        print("Usage: python3 toggle_keda.py <path-to-yaml> <night|morning>")
        sys.exit(1)

if mode not in ["night", "morning"]:
    print("Invalid mode. Use 'night' or 'morning'.")
    sys.exit(1)

if not os.path.isfile(file_path):
    print(f"File not found: {file_path}")
    sys.exit(1)

with open(file_path, "r") as fh:
    lines = fh.readlines()

result = []

if mode == "night":
    # enable keda
    for line in lines:
        if line.startswith("# "):
            result.append(line[2:])  # uncomment
        elif line.rstrip("\n") == "#":
            result.append("\n")  # remove line
        else:
            result.append(line)  # already uncommented / empty
    action = "ENABLED (uncommented)"

else:

    for line in lines:
        stripped = line.rstrip("\n")
        if stripped and not stripped.startswith("#"):
            result.append("# " + line)  # comment
        else:
            result.append(line)  # already commented / empty
    action = "DISABLED (commented)"

with open(file_path, "w") as fh:
    fh.writelines(result)

print(f"KEDA manifest {action}: {file_path}")
