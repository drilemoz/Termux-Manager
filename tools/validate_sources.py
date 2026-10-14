#!/usr/bin/env python3
from __future__ import annotations
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from integrate import validate_manager

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--manager', type=Path, required=True)
    a=p.parse_args()
    manifest=validate_manager(a.manager)
    paths=[a.manager/'manager.sh',*sorted((a.manager/'modules').rglob('*.sh'))]
    for file in paths:
        subprocess.run(['bash','-n',str(file)], check=True)
    print(f"Manager {manifest['version']}: {len(paths)} Bash sources syntax checked")

if __name__=='__main__':
    main()
