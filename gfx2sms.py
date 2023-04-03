#!/usr/bin/env python
# coding: utf-8

import os
from os import path
import os.path
import sys
from datetime import datetime
from pathlib import Path
import struct
import numpy as np
from PIL import Image, ImageOps, ImageEnhance, ImageChops
import cProfile

# 32 x 28 tiles filling a screen where a tile is 8x8
# for the SMS the color depth is 4bits = 16 colors per tile
PAL_COLORS = 4 #in bits 
MAX_X = 256
MAX_Y = 240 #max resolution is only available for the SMS2-VDP! 

TILE_WIDTH = 8
TILE_HEIGHT = 8

# Rec. 709 (sRGB) luma coef
PR, PG, PB = 0.2126, 0.7152, 0.0722
MAX_DIST = PR * 255**2 + PG * 255**2 + PB * 255**2

SMS_COLOR_PALETTE = [   (0x00,0x00,0x00),(0x54,0x00,0x00),(0xab,0x00,0x00),(0xff,0x00,0x00),
                        (0x00,0x54,0x00),(0x54,0x54,0x00),(0xab,0x54,0x00),(0xff,0x54,0x00),
                        (0x00,0xab,0x00),(0x54,0xab,0x00),(0xab,0xab,0x00),(0xff,0xab,0x00),
                        (0x00,0xff,0x00),(0x54,0xff,0x00),(0xab,0xff,0x00),(0xff,0xff,0x00),
                        (0x00,0x00,0x54),(0x54,0x00,0x54),(0xab,0x00,0x54),(0xff,0x00,0x54),
                        (0x00,0x54,0x54),(0x54,0x54,0x54),(0xab,0x54,0x54),(0xff,0x54,0x54),
                        (0x00,0xab,0x54),(0x54,0xab,0x54),(0xab,0xab,0x54),(0xff,0xab,0x54),
                        (0x00,0xff,0x54),(0x54,0xff,0x54),(0xab,0xff,0x54),(0xff,0xff,0x54),
                        (0x00,0x00,0xab),(0x54,0x00,0xab),(0xab,0x00,0xab),(0xff,0x00,0xab),
                        (0x00,0x54,0xab),(0x54,0x54,0xab),(0xab,0x54,0xab),(0xff,0x54,0xab),
                        (0x00,0xab,0xab),(0x54,0xab,0xab),(0xab,0xab,0xab),(0xff,0xab,0xab),
                        (0x00,0xff,0xab),(0x54,0xff,0xab),(0xab,0xff,0xab),(0xff,0xff,0xab),
                        (0x00,0x00,0xff),(0x54,0x00,0xff),(0xab,0x00,0xff),(0xff,0x00,0xff),
                        (0x00,0x54,0xff),(0x54,0x54,0xff),(0xab,0x54,0xff),(0xff,0x54,0xff),
                        (0x00,0xab,0xff),(0x54,0xab,0xff),(0xab,0xab,0xff),(0xff,0xab,0xff),
                        (0x00,0xff,0xff),(0x54,0xff,0xff),(0xab,0xff,0xff),(0xff,0xff,0xff) ]

now = datetime.now

def get_key(dic, search_value):
    for key, value in dic.items():
        if value == search_value:
            return key

def distribute_error(data, x, y, quant_error):
    error_table = {7.0: (1, 0), 3.0: (-1, 1), 5.0: (0, 1), 1.0: (1, 1)}
    #import pdb; pdb.set_trace()
    height, width, _ = data.shape
    for error in error_table.keys(): 
        x_diff, y_diff = error_table[error]
        #import pdb; pdb.set_trace()
        x_nb = x + x_diff
        y_nb = y + y_diff
        if 0 <= x_nb < width and 0 <= y_nb < height:  
            comp_new_pixel(data, x_nb, y_nb, quant_error, error) 

#def nearest( subjects, query ):
#    return min( subjects, key = lambda subject: sum( (s - q) ** 2 for s, q in zip( subject, query ) ) )

def closest(color, palette):
    colors = np.array(palette)
    color = np.array(color)
    distances = np.sqrt(np.sum((colors-color)**2,axis=1))
    index_of_smallest = np.where(distances==np.amin(distances))
    smallest_distance = colors[index_of_smallest]
    return tuple(smallest_distance[0]) 

def color_dist(first_color, second_color):
    return (
            PR * (second_color[0] - first_color[0])**2 +
            PG * (second_color[1] - first_color[1])**2 +
            PB * (second_color[2] - first_color[2])**2
           ) / MAX_DIST
  
def comp_quant_error(old_pixel, new_pixel):
    return [old_pixel[i] - new_pixel[i] for i, _ in enumerate(old_pixel)]

def comp_new_pixel(data, x, y, quant_error, error_weight):
    for idx, val in enumerate(data[y][x]):
        new_color = val + quant_error[idx] * error_weight / 16.0
        if new_color > 255:
            new_color = 255
        elif new_color < 0:
            new_color = 0
        #print(f"x: {x} y: {y} idx: {idx} val: {val} new_color: {new_color} quant_error: {quant_error} error_weight: {error_weight}")
        data[y][x][idx] = new_color

def dithering(img, color_palette):
    data = np.asarray(img).copy()
    color_cache = {}
    width, height = img.size[0], img.size[1]
    print(f"[{now().strftime('%Y-%m-%d %H:%M:%S')}] executing Floyd-Steinberg dithering for {width}*{height} image..", end="")
    for y in range(0, height):
        for x in range(0, width):
            old_pixel = tuple(data[y][x])
            if old_pixel not in color_cache:
                new_pixel = closest(old_pixel, SMS_COLOR_PALETTE)
                color_cache[old_pixel] = new_pixel
            else:
                new_pixel = color_cache[old_pixel]
            if color_dist(old_pixel, new_pixel) < 0.0025:
                continue
            data[y][x] = new_pixel
            quant_error = comp_quant_error(old_pixel, new_pixel)
            distribute_error(data, x, y, quant_error)
    print("done")
    
    print(f"[{now().strftime('%Y-%m-%d %H:%M:%S')}] correcting used colors..", end="")
    color_cache = {}
    for y in range(height):
        for x in range(width):
            search = tuple(data[y][x])
            if search not in color_cache:
                color = closest(search, color_palette)
                color_cache[search] = color
            else:
                color = color_cache[search] 
            if color != search:
                data[y][x] = color
    print("done")
    
    return Image.fromarray(data)

def convert(output_name, grayscale, resize):
    print(os.getcwd())
    print(f"[{now().strftime('%Y-%m-%d %H:%M:%S')}] open {output_name}..")
    with Image.open(output_name) as img:
        if grayscale:
            print(f"[{now().strftime('%Y-%m-%d %H:%M:%S')}] convert to grayscale..")
            img = ImageOps.grayscale(img)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.5*2)
            #img = img.convert("1")
            #img.show()
 
        #import pdb; pdb.set_trace()
        # TODO: reduce tiles shrink image
        
        width, height = img.size
        try:
            color_cnt = len(img.getcolors(maxcolors=65536))
        except:
            print(f"[{now().strftime('%Y-%m-%d %H:%M:%S')}] pil cannot process file {output_name}..")
            return
            
        if color_cnt > 2**PAL_COLORS:
            print("too many colors")
            ##return
        
        if width > MAX_X or height > MAX_Y:
            print("invalid image dimensions")
            ##return
            
        if resize:
            print(f"[{now().strftime('%Y-%m-%d %H:%M:%S')}] resizing to {resize}..")
            img = img.resize(resize)
        
        # convert single band color representation to RGB
        if "".join(img.getbands()) != "RGB":
            print(f"[{now().strftime('%Y-%m-%d %H:%M:%S')}] converting to RGB..")
            img = img.convert("RGB")
        
        # mapping of used color palette color of platform
        Color_Map = {}
        # translate used rgb tuple to corresponding index of color palette
        Color_Index = {}
        
        # using lambda expression to get darker color in front of the palette
        print(f"[{now().strftime('%Y-%m-%d %H:%M:%S')}] creating color mapping..")
        for idx, color in enumerate(sorted(img.getcolors(maxcolors=65536), key=lambda x: x[-1][0]**2 +x [-1][1]**2 + x[-1][2]**2)):
            # color is a rgb pair of a pixel in the picture but needed a value similiar to platform palette
            matched_color = closest(color[-1], SMS_COLOR_PALETTE)
            index = len(list(dict.fromkeys(Color_Index.values())))
           
            #color already in use, reuse palette index
            if matched_color in Color_Map.values():
                index = Color_Index[get_key(Color_Map, matched_color)] 
                print(f"[{now().strftime('%Y-%m-%d %H:%M:%S')}] mapped doubled color {color[-1]} found at index {index} will be ignored!")        
            
            # add mapping of used color to nearest color match
            Color_Map[color[-1]] = matched_color
            # set mapping used color to palette index
            Color_Index[color[-1]] = index
        
        curr_palette = list(dict.fromkeys(Color_Map.values()))
        max_color = len(curr_palette)
         
        Color_Index_SMS = {}
        for color in Color_Index:
            Color_Index_SMS[Color_Map[color]] = Color_Index[color]
        
        Color_Index = Color_Index_SMS        
        
        print(f"[{now().strftime('%Y-%m-%d %H:%M:%S')}] start dithering..")
        img = dithering(img, curr_palette)
        print(f"[{now().strftime('%Y-%m-%d %H:%M:%S')}] colors(#{len(curr_palette)}): {curr_palette}")
        #img.show()
         
        #import pdb; pdb.set_trace()
        filename = path.splitext(output_name)[0]
        
        # write color palette
        print(f"[{now().strftime('%Y-%m-%d %H:%M:%S')}] writing color palette..")
        used_colors = {}
        with open(os.path.join(os.getcwd(), os.path.split(filename + ".pal")[-1]), "wb") as writer:
            # look up for the index of the used colors relating to the machine color palette
            for color in Color_Map:
                val = SMS_COLOR_PALETTE.index(Color_Map[color])
                if val in used_colors:
                    continue
                print(f"[{now().strftime('%Y-%m-%d %H:%M:%S')}]\tusing color {val:0{2}} {hex(val)}")
                writer.write(struct.pack('B', val))
                used_colors[val] = 1
            
            # fill the rest with zeros
            while writer.tell() < 2**PAL_COLORS:
                writer.write(struct.pack('B', 0))
        
        # write planar tiles data format
        print(f"[{now().strftime('%Y-%m-%d %H:%M:%S')}] creating tile data..", end="")
        with open(os.path.join(os.getcwd(), os.path.split(filename + ".bin")[-1]), "wb") as writer:
            for tile_y in range(height // TILE_HEIGHT):
                for tile_x in range(width // TILE_WIDTH):
                    #region contain 8x8 pixel data
                    region = img.crop((tile_x * TILE_WIDTH, tile_y * TILE_HEIGHT, (tile_x + 1) * TILE_WIDTH, (tile_y + 1) * TILE_HEIGHT))
                    # no idea why I have to mirror the tile
                    region = ImageOps.mirror(region)
                    #convert rgb data to color index which references to color in the palette
                    color_data = [item for item in region.getdata()]
                    
                    #take 8 pixels
                    for pos in range(0, len(color_data), TILE_WIDTH):
                        # color index coded as value between 0 and 15 for SMS
                        for shifter in range(PAL_COLORS):
                            val = 0
                            #iterate through 8 pixel and check lowest bit is set 
                            for column in range(TILE_WIDTH):
                                val += ((Color_Index[color_data[pos + column]] >> shifter) & 0b1) << column
                            #    import pdb; pdb.set_trace()
                            writer.write(struct.pack('B', val))
        print("done")                          
def process(args):
    if os.path.exists(args[1]):
        grayscale = len(args) > 2 and args[2] == '-gs' 
        resize = None
        if len(args) > 3 and args[2] == '--resize': 
            resize = tuple(map(lambda x: int(x), args[3].split(',')))
        convert(args[1], grayscale, resize)
            
def main():
    if len(sys.argv) > 1:
        if path.exists(sys.argv[1]):
            process(sys.argv)
            #cProfile.run("process(sys.argv)", sort="tottime")
        else:
            print("file %s doesn't exist" % (sys.argv[1]))
    else:
        print("not enough arguments")

if __name__ == '__main__':
    main()
