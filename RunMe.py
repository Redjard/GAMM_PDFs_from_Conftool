import subprocess
import os
import sys
import argparse
import shutil
from glob import glob

def make_boa():
    try:
        os.chdir(os.path.join("LaTeX", "Book_of_abstracts"))
        subprocess.check_call(["latexmk", "-pdf", "BookOfAbstracts.tex"])
        shutil.copy("BookOfAbstracts.pdf", cwd)
    finally:
        os.chdir(cwd)

def make_dsp():
    try:
        os.chdir(os.path.join("LaTeX", "Daily_Scientific_Program"))
        subprocess.check_call(["latexmk", "-pdf", "Daily_Scientific_Program.tex"])
        shutil.copy("Daily_Scientific_Program.pdf", cwd)
    finally:
        os.chdir(cwd)

def make_room_plans():
    try:
        os.chdir(os.path.join("LaTeX", "Daily_Scientific_Program", "rooms"))
        for tex_file in glob("*.tex"):
            subprocess.check_call(["latexmk", "-pdf", tex_file])
        for pdf_file in glob("*.pdf"):
            shutil.copy(pdf_file, cwd)
    finally:
        os.chdir(cwd)

def main():
    parser = argparse.ArgumentParser(description='Generate PDFs for conference materials.')
    parser.add_argument('-b', '--boa', action='store_true', help='Generate book of abstracts')
    parser.add_argument('-d', '-s', '--dsp', action='store_true', help='Generate daily scientific program')
    parser.add_argument('-r', '--rooms', action='store_true', help='Generate room plans')
    parser.add_argument('-a', '--all', action='store_true', help='Generate all PDFs')
    args = parser.parse_args()

    # Fetch data from ConfTool Pro
    subprocess.check_call([sys.executable, "get_conftool_data.py"])
    # Create LaTeX files
    subprocess.check_call([sys.executable, "BoA_DSP_generator.py"])

    if args.boa:
        make_boa()
    if args.dsp:
        make_dsp()
    if args.rooms:
        make_room_plans()
    if args.all or not any(vars(args).values()):
        make_boa()
        make_dsp()
        make_room_plans()

if __name__ == "__main__":
    cwd = os.getcwd()
    main()