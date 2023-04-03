#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, division
from sys import argv
from binascii import crc32
from functools import partial
from os import stat
from os.path import splitext, exists, split
from struct import pack, unpack
from time import strftime, gmtime
from datetime import datetime
from platform import python_version_tuple as version
 
__version__ = 0, 1, 1 
__author__ = "darktrym"

version = int(version()[0])

if version < 3:
    input = raw_input

#port of maxims sms/gg header rom reader

'''SMS/GG rom header reader
 by Maxim

 This program reads in and works with the header found in all SMS/GG files
 and also the new SDSC header data.
 It also checks the checksum and tries to interpret the Sega header data.
 It displays all information in human-readable form, fetching strings
 from the offsets given in the SDSC header and splitting nibbles in the Sega
 header.'''

SEGA_TM = 'TMR SEGA'
HEADER_POSITION = 0x7FF0

REGIONS = { 0x3: 'SMS Japan', 0x4: 'SMS Export',
            0x5: 'GG Japan',0x6: 'GG Export',
            0x7:'GG International'}
            
VENDORS = { 0x02: "Sega", 0x03: "Sega",
            0x11: 'Taito', 0x14: 'Namco', 0x15: 'SunSoft',
            0x22: 'Micronet', 0x23: 'Vic Tokai/SIMS [only one]',
            0x25: 'NCS [only one]', 0x26: 'Sigma Enterprises [only one]',
            0x28: 'Genki [only one]', 0x32: 'Wolf Team [only one]',
            0x33: 'Kaneko [only one]', 0x44: 'Sanritsu/SIMS',
            0x45: 'Game Arts/Studio Alex [only one]', 0x48: 'Tengen/Time Warner',
            0x49: 'Telenet Japan [only one]', 0x50: 'EA',
            0x51: 'SystemSoft [only one]', 0x52: 'Microcabin',
            0x53: 'Riverhill Soft', 0x54: 'ASCII corp. [only one]',
            0x60: 'Victor/Loriciel/Infogrames [only one]', 
            0x65: 'Tatsuya Egama/Syueisya/Toei Anumaition/Tsukuda Ideal [only one]',
            0x66: 'Compile', 0x68: 'GRI [only one]', 0x70: 'Virgin', 0x79: 'US Gold',
            0x81: 'Acclaim', 0x83: 'GameTek', 0x87: 'Mindscape', 0x88: 'Domark',
            0x93: 'Sony', 0xA0: 'THQ', 0xA3: 'SNK', 0xA4: 'Microprose [only one]',
            0xB2: 'Disney [only one]', 0xC5: 'Beam Software P/L',
            0xD3: 'Bandai', 0xD9: 'Viacom', 
            0xE9: 'Infocom/Gremlin [only one]', 0xF1: 'Infogrames',
            0xF4: 'Technos Japan Corp. [only one]'}


def calc_checksum(file_name, range_start, range_end, start_value=0):
    '''This function calculates the SMS internal checksum. The parameters should be obvious.'''

    with open(file_name, "rb") as f:
        f.seek(range_start)
        total_read = range_start
        result = start_value
        BUFFER_SIZE = 32 * 1024
        # repeatedly read 32K chunks and checksum them, stopping at end point
        for buffer in iter(partial(f.read, BUFFER_SIZE), b""):
            for count, _ in enumerate(buffer):
                if total_read + count - 1 == range_end:
                    break
                result = (result + byte(buffer[count])) % 2**16
            
            total_read += len(buffer)
            if total_read >= range_end:
                break
        return result % 2**16

def file_size(file_name):
    return stat(file_name).st_size

def file_created(file_name):
    return stat(file_name).st_mtime

def calc_codies_checksum(file_name, num_pages):
    with open(file_name, "rb") as f:
        f.seek(0)
        result = 0
        WORD_SIZE = 2
        total_read = 0
        BUFFER_SIZE = 8 * 1024 * WORD_SIZE
        for buffer in iter(partial(f.read, BUFFER_SIZE), b""):
            words = len(buffer) // WORD_SIZE
            if words > 0: 
                for count in range(words):
                    if not (0x3ff8 <= total_read + count <= 0x3fff):
                        result = (result + unpack("<H", buffer[count * 2:(count + 1) * 2])[0]) % 2**16
                    if total_read + count == num_pages * 0x2000:
                        break
                
            total_read += words
            if words == 0 or words == num_pages * 0x2000:
                break
        return result

def byte(a):
    '''helper for hybrid python 2 & 3 support'''
    
    return a if version == 3 else ord(a)

def crc_file(file_name):
    BUFFER_SIZE = 8 * 1024
    
    with open(file_name, "rb") as f:
        crcbin = 0
        for buffer in iter(partial(f.read, BUFFER_SIZE), b""):
            crcbin = crc32(buffer, crcbin)
        return "%08X" % (crcbin & 0xffffffff)

def main():
    if argv[1:] and exists(argv[1]):
        argc = len(argv)
        argv[2:] = map(lambda x: x.lower(), argv[2:])
        load_file(argv[1], argc == 3 and argv[2] == "force", \
            ((argc == 3 and "auto" == argv[2]) or 
             (argc == 4 and "auto" == argv[3])))
    else:
        print(splitext(split(argv[0])[-1])[0])
        print("author:", __author__)
        print("version: %s" % ".".join(map(str, __version__)))
    
def bcd_fix(inp):
    ''' Takes a BCD byte which has been read as hex and outputs the proper hex value
    eg. BCD value 45 is read as h45 = d69, output value = h2D = d45
    Hard to describe... it just fixes BCDs, OK?
    It doesn't do error checking.'''
    
    return (inp >> 4) * 10 + (inp & 0xf) ##+ 1

def read_string(file_name, offset):
    ''' Reads a null-terminated string from the specified offset'''
    
    result = []
    if offset != 0xffff:
        if offset > file_size(file_name):
            return '*** Warning! Offset beyond EOF ***'
          
        with open(file_name, "rb") as f:
            f.seek(offset);
            for c in iter(partial(f.read, 1), ''):
                result.append(c[0])
                if c == "\0":
                    break
    return "".join(result)

def display_file_info(file_name):
    tabbed_print("File info")
    tabbed_print('Filename = %s' % split(file_name)[-1], 1)
    size = file_size(file_name)
    tabbed_print('Size = %d bytes (%dKB, %dMbits)' % (size, 
        size // 0x400, size // 0x20000))
    tabbed_print('CRC32 = %s' % crc_file(file_name))
    tabbed_print('Fullsum = %04X' % calc_checksum(file_name, 0, file_size(file_name)))
    age = file_created(file_name)
    tabbed_print('Date and time = %s' % strftime("%Y-%m-%d %H:%M:%S", gmtime(age)))

def load_file(file_name, force_patching, auto=False):
    display_file_info(file_name)
    display_sdsc_header(file_name)
    if not (display_sega_header(file_name, HEADER_POSITION, False, force_patching, auto) or
        display_sega_header(file_name, 0x3ff0, False, force_patching, auto) or
        display_sega_header(file_name, 0x1ff0, False, force_patching, auto)):
        display_sega_header(file_name, HEADER_POSITION, True, force_patching, auto)
    display_codemasters_header(file_name)

def display_sdsc_header(file_name):
    if file_size(file_name) < HEADER_POSITION:
        return
        
    header = {}    
    HEADER_SIZE = 4 + 4 + 4 * 2
    with open(file_name, "rb") as f:
        f.seek(0x7fe0)
        data = f.read(HEADER_SIZE)
    (header["SDSCChars"], header["MajorVersion"], header["MinorVersion"], header["day"], 
        header["month"], header["year"], header["AuthorOffset"], header["TitleOffset"], 
        header["ReleaseNotesOffset"]) = unpack("4s4B4H", data)
  
    if header["SDSCChars"] == 'SDSC':
        if header["TitleOffset"] != 0xffff:
            title = read_string(file_name, header["TitleOffset"])
        release_notes = ""
        if header["ReleaseNotesOffset"] != 0xffff:
            release_notes = read_string(file_name, header["ReleaseNotesOffset"])
        author = ""
        if header["AuthorOffset"] not in (0xffff, 0x0000): 
            author = read_string(file_name, header["AuthorOffset"])

        tabbed_print('SDSC header')
        if header["TitleOffset"] != 0xffff:
            tabbed_print('Title = %s' % title)

        if header['AuthorOffset'] not in (0xffff, 0x0000):
            tabbed_print('Author = %s' % author)

        tabbed_print('Program version = %d.%.2d' % (bcd_fix(header["MajorVersion"]), bcd_fix(header["MinorVersion"])))
        timestamp = datetime(bcd_fix(header["year"] >> 8) * 100 + bcd_fix(header["year"] & 0xff), 
                    bcd_fix(header["month"]), bcd_fix(header["day"]))
        tabbed_print('Release date = %s' % timestamp.strftime("%Y-%m-%d"))

        if header["ReleaseNotesOffset"] != 0xffff:
            tabbed_print('Release notes (see below)')  
            tabbed_print(release_notes)

def tabbed_print(string, indent=0, memory=[0]):
    '''helper function which print out strings with leading tabs'''
    memory[0] += indent
    print(memory[0]*"\t", string, sep="")

def compute_checksum(file_name, card_size):
    '''computes checksum from given file name and card size type'''
    QUARTERMBIT, HALFMBIT, MBIT, TWOMBIT, FOURMBIT, EIGHTMBIT = 0xc, 0xe, 0xf, 0x0, 0x1, 0x2
    
    num_pages = {0xa: 0, 0xb: 1, 0xc: 2, 0xd: 3, 0xe: 4, 0xf: 8, 0x0: 16, 0x1: 32, 0x2: 64}
    checksum_calc = -1
    if card_size == 0xa: 
        #8kb unused
        checksum_calc = calc_checksum(file_name, 0, 0x1FEF)
    elif card_size == 0xb: 
        #16kb unused
        checksum_calc = calc_checksum(file_name, 0, 0x3FEF)
    elif card_size == QUARTERMBIT: 
        checksum_calc = calc_checksum(file_name, 0, HEADER_POSITION - 1) 
    elif card_size == 0xd: 
        #48kb unused and broken because header is part of checksum rom range
        checksum_calc = calc_checksum(file_name, 0, 0xbfef) 
    elif card_size == HALFMBIT: 
        checksum_calc = calc_checksum(file_name, 0x8000, 0xffff, calc_checksum(file_name, 0, HEADER_POSITION - 1)) 
    elif card_size == MBIT: 
        checksum_calc = calc_checksum(file_name, 0x8000, 0x1ffff, calc_checksum(file_name, 0, HEADER_POSITION - 1)) 
    elif card_size == TWOMBIT: 
        checksum_calc = calc_checksum(file_name, 0x8000, 0x3ffff, calc_checksum(file_name, 0, HEADER_POSITION - 1))
    elif card_size == FOURMBIT: 
        checksum_calc = calc_checksum(file_name, 0x8000, 0x7ffff, calc_checksum(file_name, 0, HEADER_POSITION - 1))
    elif card_size == EIGHTMBIT: 
        checksum_calc = calc_checksum(file_name, 0x8000, 0xfffff, calc_checksum(file_name, 0, HEADER_POSITION - 1))
      
    return checksum_calc, num_pages.get(card_size, -1)

def get_sega_header(file_name, offset):
    if file_size(file_name) < offset + 16:
        return
        
    header = {}
    HEADER_SIZE = 8 + 3 * 2  + 2
    data = ""
    with open(file_name, "rb") as f:
        f.seek(offset)
        data = f.read(HEADER_SIZE)
    (header["TMRSEGAChars"], header["unknown_value"], header["checksum"], header["part_number"],
        header["version"], header["region_and_cart_size"]) = unpack("<8s3H2B", data)
    return data, header

def display_sega_header(file_name, offset, force, force_patching, auto):
    MASTER_SYSTEM_REGIONS = (0x3, 0x4)
    data, header = get_sega_header(file_name, offset)
    if header["TMRSEGAChars"] == SEGA_TM or force:
        tabbed_print('Sega header', -1) 

        tabbed_print('Full header (ASCII) = %s' % "".join(["%c" % byte(x) if 32 <= byte(x) <= 255 else "." for x in data]), 1)
        tabbed_print('Full header (hex) = %s' % "".join(" %02X" % byte(i) for i in data))
        tabbed_print('Checksum') 
        
        patch_suggestion = False
        if header["region_and_cart_size"] >> 4 != 4: 
            tabbed_print("The region code suggests that this ROM doesn't need a valid checksum.")
            patch_suggestion = True
            
        tabbed_print('From header = 0x%04X' % header["checksum"], 1) 
        checksum_calc, num_pages = compute_checksum(file_name, header["region_and_cart_size"] & 0xF)
        
        # try Codemasters paging checksum if that failed
        if checksum_calc != header["checksum"] and num_pages > 1: # it'd pass anyway if NumPages was 0,1,2
            codies_sega_checksum = calc_checksum(file_name, 0x4000, 0x7FEF, 
                calc_checksum(file_name, 0, 0x3FFF, 0) * (num_pages - 1))
        else:
            codies_sega_checksum = -1

        if codies_sega_checksum != header["checksum"]:
            if header["checksum"] == checksum_calc:
                status_text = 'OK' 
            else:
                status_text = 'bad!'
                patch_suggestion = True
            tabbed_print('Calculated = %04X (%s)' % (checksum_calc, status_text))
        else: 
            tabbed_print('Calculated (Codemasters mapper) = %04X  (OK)' % codies_sega_checksum)
         
        num_pages_type = {-1: 'invalid', 0: '8KB'}    
        temp = num_pages_type.get(num_pages, "%dKB" % (num_pages * 16))
        tabbed_print('Rom size = 0x%02X (%s)' % (header["region_and_cart_size"] & 0xf, temp))
       
        try:
            region_str = REGIONS[header["region_and_cart_size"] >> 4]
        except KeyError:
            region_str = "Unknown"
        tabbed_print('Region code = 0x%02X (%s)' % (header["region_and_cart_size"] >> 4, region_str), -1)
        if header["region_and_cart_size"] >> 4 in MASTER_SYSTEM_REGIONS:
            temp_str ='Product number = '
            if header["version"] & 0xf0 == 0x20: 
                temp_str = "%s2" % temp_str
            temp_str = "%s%04X (" % (temp_str, header["part_number"])
            info = ""
            if 0x0500 <= header["part_number"] <= 0x0599:
                temp_str = '%sC-%s' % (temp_str[:18], temp_str[18:])
                temp_str = '%s%sJapanese' % (temp_str[:19], temp_str[20:])
            elif 0x1300 <= header["part_number"] <= 0x1399: 
                temp_str = '%sG-%sJapanese' % (temp_str[:18], temp_str[18:])
            elif header["part_number"] == 0x3901: 
                info = 'Parker Brothers (incorrect number)'
                # They actually have numbers 4350,60,70 but internally 2 have 3901 and 1 has 0000
            elif 0x4001 <= header["part_number"] <= 0x4499: 
                info = 'The Sega Card (32KB)'
            elif 0x4501 <= header["part_number"] <= 0x4507 or 0x4580 <= header["part_number"] <= 0x4584: 
                info = 'The Sega Cartridge (32KB)'
            elif 0x5051 <= header["part_number"] <= 0x5199: 
                info = 'The Mega Cartridge (128KB)'
            elif 0x5500 <= header["part_number"] <= 0x5599: 
                info = 'The Mega Plus Cartridge (128KB with battery-backed RAM)'
            elif header["part_number"] == 0x5044 or 0x6001 <= header["part_number"] <= 0x6081: 
                info = 'The Combo Cartridge';
            elif 0x7001 <= header["part_number"] <= 0x7499: 
                info = 'The Two-Mega Cartridge (256KB)'
            elif 0x7500 <= header["part_number"] <= 0x7599: 
                info = 'The Two-Mega Plus Cartridge (256KB with battery-backed RAM)'
            elif 0x8001 <= header["part_number"] <= 0x8499: 
                info = 'The 3-Dimensional Mega Cartridge'
            elif 0x9001 <= header["part_number"] <= 0x9499: 
                info = 'The Four-Mega Cartridge (512KB)'
            elif 0x9500 <= header["part_number"] <= 0x9599: 
               info = 'The Four-Mega Plus Cartridge (512KB with battery-backed RAM)'
            else:
                info = 'Unknown'
            temp_str = "%s%s" % (temp_str, info)
            tabbed_print("%s%s)" % (temp_str, '' if header["version"] & 0xf0 != 0x20 else ' (3rd party)'))
        else: 
            # GG games
            # this is nasty but I can't be bothered to clean it up, it works OK
            i = (header["version"] >> 4) * 0x10000 + header["part_number"]
            temp_str = 'Product number = %d%04X ' % (header["version"] >> 4, header["part_number"])

            select = i >> 12
            if select in (2, 3):    
                temp_str = '(%s%sSega' % (temp_str[:17], temp_str[18:])
                if i >> 12 == 3:
                    temp_str = '%sG-%s Japan' % (temp_str[:18], temp_str[18:])
                else:
                    temp_str = '%s of America' % temp_str
                
                select = header["part_number"] >> 8
                if 0x20 <= select <= 0x2f: 
                    temp_str = '%s, >=128KB, Export or International)' % temp_str
                elif 0x31 <= select <= 0x33:
                    temp_str = "%s" % (temp_str, {0x31:", 32KB)", 0x32:", 128KB)", 0x33:", >=256KB)"}[select])
                else:
                  temp_str = '%s)' % temp_str
            
            elif select in VENDORS:
                temp_str = "%s(%s)" % (temp_str, VENDORS[select])
            else:
                temp_str = '(%sUnknown)' % temp_str
            if header["version"] >> 4 > 0:
                temp_str = '%sT-%s' % (temp_str[:17], temp_str[17:])
            tabbed_print(temp_str)

        tabbed_print('Version = %s' % hex(header["version"])[-1])
        tabbed_print('Reserved word = 0x%04X' % header["unknown_value"])
        
        # additional patch functionality
        if patch_suggestion or force_patching: 
            answer = 'y'
            if not force_patching and not auto:
                answer = input("Do want to fix this(default: no)?")
            if answer.lower() in ('y', 'yes'):
                signature = ""
                if not auto:
                    signature = input("Type your signature(maximal length is 3)?")
                # if input is empty take old values
                if not signature:
                    signature = pack("<hB", header["part_number"], header["version"])
                patch_header(file_name, signature)
        return True
    return False

def patch_header(file_name, signature="<D>", region=4):
    '''
        patch the header to pass the region check in consoles outside japan
    
        structure of the header(starts at 7ff0):
       
        Trademark Hint: TMR SEGA(8 Bytes)
        Reserved Space: 00 00 or 20 20(2 Bytes)
        Checksum(litte endian): 34 12(2 Bytes)
        
        Product code(in bcd, max 5 digits): 26702?(2,5 Bytes)
        Version: ?X(0.5 Bytes)
        Region code: X?(0.5 Bytes) (3, 4, 5, 6, 7 = SMS Japan, SMS Export, 
        GG Japan, GG Export, GG International)
        ROM size: ?X (0.5 Bytes)(a, b, c, d, e, f, 0, 1, 2 = 8, 16, 32, 48, 
        128, 256, 512, 1024KB)
    '''
    
    MBIT = 131072
    # prevent buggy 48kb rom size
    rom_size = {MBIT//4: 0xc, 48*1024: 0xd - 1, MBIT//2: 0xe, 
                MBIT: 0xf, 2*MBIT: 0x0, 4*MBIT: 0x1, 8*MBIT: 0x2}
    card_size = rom_size[file_size(file_name)]
    checksum = compute_checksum(file_name, card_size)[0]
    spaces, trademark = "  ", SEGA_TM
    with open(file_name, "r+b") as rom_file:
        rom_file.seek(HEADER_POSITION)
        if version > 2:
            trademark = bytes(trademark, "utf-8")
            signature = ("%s   " % signature).encode("latin1")[:3]
            spaces = bytes(spaces, "utf-8")
        header = pack("8s2s2s3sb", trademark, spaces, pack("<H", checksum), signature, region<<4|card_size)
        rom_file.write(header)

def get_codemasters_header(file_name):
    if file_size(file_name) < HEADER_POSITION:
        return
    
    HEADER_SIZE = 1 + 1 + 1 + 1 + 1 + 1 + 2 + 2 + 6
    header = {}
    data = ""
    with open(file_name, "rb") as f:
        f.seek(0x7fe0)
        data = f.read(HEADER_SIZE)
    (header["num_pages"], header["day"], header["month"],header["year"], header["hour"], header["minute"], 
        header["checksum"], header["inverse_checksum"], header["reserved"])  = unpack("<6B2H6s", data)
    return header
        
def display_codemasters_header(file_name):
    header = get_codemasters_header(file_name)
    WORD_SIZE = 16
    # check it seems to be a likely header
    # I could do more checks...
    # 0 = -0 so blank areas pass this check; they tend to fail the date encode, though.
    if header["inverse_checksum"] == -header["checksum"] % (2**WORD_SIZE):
        try:
            timestamp = datetime(bcd_fix(header["year"]) + 1900, bcd_fix(header["month"]), bcd_fix(header["day"]), 
                 bcd_fix(header["hour"]), bcd_fix(header["minute"]), 0, 0)
        except ValueError:
            return
        tabbed_print('Codemasters header', -1)
        tabbed_print('Date and time = %s' % timestamp.strftime("%Y-%m-%d %H:%M:%S"), 1)
        tabbed_print('Checksum')
        tabbed_print('From header = 0x%04X' % header["checksum"], 1)
        calculated = calc_codies_checksum(file_name, header["num_pages"])
        state = "OK" if header["checksum"] == calculated else "bad!"
        tabbed_print("Calculated = 0x%04X (%s)" % (calculated, state))
        tabbed_print('Rom size = %d pages (%d KB)' % (header["num_pages"], header["num_pages"] * 16))
      
if __name__ == "__main__":
    main()
