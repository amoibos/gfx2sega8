#!/usr/bin/env python
# coding: utf-8

import os
from os import path
import sys
from pathlib import Path
import struct
from PIL import Image, ImageOps

# 32 x 24 tiles filling a screen where a tile 8x8 tile dimension
# for the SG the color depth is 1bit = 2 colors per tile
PAL_COLORS = 1 # in bits
MAX_X = 256
MAX_Y = 192

TILE_WIDTH = 8
TILE_HEIGHT = 8

# first color is used for transparent
SG_COLOR_PALETTE = [    (0x00,0x00,0x00),(0x00,0x00,0x00),(0x21,0xC8,0x42),(0x5E,0xDC,0x78),
                        (0x54,0x55,0xED),(0x7D,0x76,0xFC),(0xD4,0x52,0x4D),(0x42,0xEB,0xF5),
                        (0xFC,0x55,0x54),(0xFF,0x79,0x78),(0xD4,0xC1,0x54),(0xE6,0xCE,0x80),
                        (0x21,0xB0,0x3B),(0xC9,0x5B,0xBA),(0xCC,0xCC,0xCC),(0xFF,0xFF,0xFF)]



def nearest_color(subjects, query):
    return min(subjects, key = lambda subject: sum((s - q) ** 2 for s, q in zip(subject, query)))

def convert(output_name):
    with Image.open(output_name) as img:
        width, height = img.size
        color_cnt = len(img.getcolors())
        
        if color_cnt > 2**PAL_COLORS:
            print("too many colors")
            return
        
        if width > MAX_X or height > MAX_Y:
            print("invalid image dimensions")
            return
        
        # convert single band color representation to RGB
        if "".join(img.getbands()) != "RGB":
            img = img.convert('RGB')
        
        # store color palette information
        Color_Map = {}
        # translate color information to corresponding index of color palette
        Color_Index = {}
        
        for idx, color in enumerate(img.getcolors()):
            #import pdb; pdb.set_trace()
            Color_Map[color[-1]] = nearest_color(SG_COLOR_PALETTE, color[-1])
            Color_Index[color[-1]] = idx 
               
        filename = path.splitext(output_name)[0]
        
        # write color palette
        with open(filename + ".pal", "wb") as writer:
            # look up for the index of the used colors relating to the machine color palette
            for color in Color_Map:
                val = SG_COLOR_PALETTE.index(Color_Map[color])
                #skip transparence color
                if val == 0:
                    val = 1
                writer.write(struct.pack('B', val))
            
            # fill the rest with zeros
            while writer.tell() < 16:#2**PAL_COLORS:
                writer.write(struct.pack('B', 10))
        
        
        # write tiles data
        with open(filename + ".bin", "wb") as writer:
            for tile_y in range(height // TILE_HEIGHT):
                for tile_x in range(width // TILE_WIDTH):
                    region = img.crop((tile_x * TILE_WIDTH, tile_y * TILE_HEIGHT, (tile_x + 1) * TILE_WIDTH, (tile_y + 1) * TILE_HEIGHT))
                    # no idea why I have to mirror the tile
                    region = ImageOps.mirror(region)
                    data = [Color_Index[item] for item in region.getdata()]
                    for pos in range(0, len(data), TILE_WIDTH):
                        for shifter in range(PAL_COLORS):
                            val = 0
                            for column in range(TILE_WIDTH):
                                val += ((data[pos + column] >> shifter) & 0b1) << column
                            #    import pdb; pdb.set_trace()
                            writer.write(struct.pack('B', val))

def process(args):
    if os.path.exists(args[1]):
        convert(args[1])


def main():
    if len(sys.argv) > 1:
        if path.exists(sys.argv[1]):
            process(sys.argv)
        else:
            print("file %s doesn't exist" % (sys.argv[1]))
    else:
        print("not enough arguments")



if __name__ == '__main__':
    main()