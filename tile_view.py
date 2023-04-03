#!/usr/bin/env python
from sys import argv
path = argv[1] if len(argv) > 1 else r"C:\programmieren\master system\helloworld\gfx\font.fnt"
with open(path, "rb") as f:
    for index, value in enumerate(f.read(), 1):
        for n in range(8):
            print("x" if ord(value) & (1 << n) else ".", end="")
        print()
        if index % 8 == 0:
            print()