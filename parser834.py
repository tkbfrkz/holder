import os
import tarfile
import subprocess
import xml.etree.ElementTree as ET
import datetime
import sys
import shutil

exe_path = r'X12Parser.exe'

tar_file = sys.argv[1]
try:
    process_dt = datetime.datetime.strptime(tar_file, '%Y_%m_%d.tar')
    process_date = process_dt.strftime('%Y-%m-%d')
except ValueError:
    print("File name format is incorrenct. Please pass the original .tar file in the format yyyy_mm_dd.tar")
    exit(0)

if not os.path.isfile(tar_file):
    print('Could not find the tar file. Was it moved or deleted?')
    exit(0)

if not os.path.isfile(exe_path):
    print('We need a valid X12 Parser helper program to proceed. Please contact dev for the helper program.')
    exit(0)

my_tar = tarfile.open(tar_file)
my_tar.extractall('./temp') # specify which folder to extract to
my_tar.close()

def parse(input_file, output_file):
    subprocess.call([exe_path, input_file, output_file])

def none_blank(txt):
    return '' if txt is None else txt.strip()

def print_depth(element, max_depth, depth=0):
    if depth == max_depth:
        return
    for child in element:
        print('\t' * depth, child.tag, child.attrib, none_blank(child.text))
        print_depth(child, max_depth, depth + 1)

def depth_search(el, condition, max_depth, depth, result):
    if depth == max_depth:
        return result
    for child in el:
        if condition(child):
            result.append(child)
        else:
            depth_search(child, condition, max_depth, depth + 1, result)
    return result

def parse_2750(el):
    for child in el:
        if child.tag == 'N1':
            for child_2 in child:
                if child_2.tag == 'N102':
                    nm = child_2.text
        if child.tag == 'REF':
            for child_2 in child:
                if child_2.tag == 'REF02':
                    val = child_2.text
    return nm, val

parsed_results = []

for fn in os.listdir('./temp'):
    if not fn.endswith('.x12'):
        continue
    infile = os.path.join('./temp', fn)
    outfile = os.path.join('./temp', 'temp.xml')
    parse(infile, outfile)
    root = ET.parse(outfile).getroot()
    res = depth_search(
        root,
        lambda x: x.tag == 'Loop' and x.attrib['Name'] == 'MEMBER LEVEL DETAIL',
        10, 0, []
    )
    for res_item in res:
        x2750 = depth_search(res_item, lambda x: x.tag == 'Loop' and x.attrib['Name'] == 'Reporting Category', 10, 0,
                             [])
        names = depth_search(res_item, lambda x: x.tag == 'Loop' and x.attrib['Name'] == 'MEMBER NAME', 10, 0, [])

        res_dict = {}
        for xel in x2750:
            tup = parse_2750(xel)
            if tup[0] in res_dict:
                print('dup', tup[0])
            res_dict[tup[0]] = tup[1]
        for name in names:
            for child in name:
                if child.tag == 'NM1':
                    for child_2 in child:
                        if child_2.tag == 'NM103':
                            ln = child_2.text
                        elif child_2.tag == 'NM104':
                            fn = child_2.text

        if 'RECERT DATE' in res_dict:
            recert = datetime.datetime.strptime(res_dict['RECERT DATE'], '%Y%m%d').strftime('%Y-%m-%d')
        else:
            recert = None
        parsed_results.append({
            'name': f'{fn} {ln}',
            'NAMI': res_dict.get('NAMI'),
            'EXCESS': res_dict.get('EXCESS'),
            'RECERT DATE': recert
        })

import csv
with open('output.csv', 'w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['name', 'NAMI', 'EXCESS', 'RECERT DATE'])
    for res in parsed_results:
        writer.writerow([res['name'], res['NAMI'], res['EXCESS'], res['RECERT DATE']])
shutil.rmtree('./temp')