#!/usr/bin/env python3
# This file is part of the GAMM_PDFs_FROM_CONFTOOL project.
# Copyright GAMM_PDFs_FROM_CONFTOOL developers and contributors. All rights reserved.
# License: BSD 2-Clause License (https://opensource.org/licenses/BSD-2-Clause)

"""

Some vocabulary used in documentation:
	
	BoA - Book of Abstracts
	
	DSP - Daily Scientific Program
	The pdf which contains one session per row, grouping all sessions at a certain time into respective tables
	
	contributions are talks or presentations with specific relevant paper, topic, speakers, ...
	contributions are shown as fields in the DSP, and each abstract in the book of abstracts belongs to a contribution
	
	sessions are a conftool object, they group together multiple contributions taking place in the same location consecutively. They are chaired by a specific chair for that session.
	
	sessionBlock/sec/section is a group of sessions that start on the same general specifier. S02.05 and S02.02 are both in sessionBlock S02

"""



import datetime as dt
import pandas as pd
import re
import argparse

from html2latex import html2latex

# store session length config in a class to allow using them in match case
sessionlengths = lambda: None

####### vvvvvv CHANGE THIS vvvvvv ########### <--------------------------------------------------------------------------
# sessionlengths.default = 20
sessionlengths.default = 15
####### ^^^^^^ CHANGE THIS ^^^^^^ ########### <--------------------------------------------------------------------------

sessionlengths.double = 2*sessionlengths.default
sessionlengths.threeHalf = int(1.5*sessionlengths.default)

subsession_separation_chars = "[._]"  # regex pattern to split sessions like A01_01 or S06c.05 into their parent sessions A01 and S06c at chars . or _

################################################################################
# cleaner routine that handles all characters giving plain pdflatex trouble    #
################################################################################
def utf8_clean(instr):
	utf8_to_latex = {
	" &": " \&",
	# "#": "\\#",
	# "Γ": "\\ensuremath\\Gamma ",
	# "Ω": "\\ensuremath\\Omega ",
	# "∑": "\\ensuremath\\Sigma ",
	# "∇": "\\ensuremath\\nabla ",
	# "Δ": "\\ensuremath\\Delta ",
	# "√": "\\ensuremath\\sqrt",
	# "⋆": "\\ensuremath\\ast ",
	# "λ": "\\ensuremath\\lambda ",
	# "φ": "\\ensuremath\\varphi ",
	# "ε": "\\ensuremath\\varepsilon ",
	# "ϕ": "\\ensuremath\\Phi ",
	# "∈": "\\ensuremath\\in ",
	# "ψ": "\\ensuremath\\psi ",
	# "ξ": "\\ensuremath\\xi ",
	# "π": "\\ensuremath\\pi ",
	# "μ": "\\ensuremath\\mu ",
	# "∞": "\\ensuremath\\infty ",
	# "β": "\\ensuremath\\beta ",
	# "ω": "\\ensuremath\\omega ",
	# "→": "\\ensuremath\\rightarrow ",
	# "\u03c3": "\\ensuremath\\sigma ",
	# "θ": "\\ensuremath\\Theta ",
	# "\R": "\\mathbb{R}",
	# "≤": "\\ensuremath\\leq",
	# "\u2003": "~",
	# "\u202F": "~",
	# "\u2248": "",
	# "\u2212": "-",
	# "\u0308": '\\"',
	# "\u0301": "\\\'",
	# "\u001B": "",
	# "^2": "\\textsuperscript{2}",
	# "^m": "\\textsuperscript{m}",
	# "\percent": "\%", # we replaced % by \percent in html2latex
	# "\&=": "&="
	}

	for key, value in utf8_to_latex.items():
		instr = instr.replace(key, value)
	return instr

################################################################################
# for the daily schedule we need to know how long a contribution is,           #
# and advance time by 20 minutes                                               #
################################################################################
# get time difference in minutes
def get_duration(start, end):
	dt1 = dt.datetime.fromisoformat(start)
	dt2 = dt.datetime.fromisoformat(end)
	return int((dt2-dt1).total_seconds() / 60)
def get_ses_length(session):
	return int(( session.session_end - session.session_start ).total_seconds() / 60)

def advance_slot(start, times, slot):
	delta = dt.timedelta(seconds=times* slot*60)
	return start + delta

################################################################################
# helper routines fetching row entries from the CSV dataframe into easier to   #
# handle dictioniaries                                                         #
################################################################################
def get_section_info(org, section):
	if section.startswith('DFG-PP'):
		section = section.replace('DFG-PP', 'SPP')
	if section.startswith('DFG-GRK'):
		section = section.replace('DFG-GRK', 'GRK')
	sect_organ = org[org['track_type'].str.startswith(section)]
	organizers = ''
	title = '\\color{red}{NOT AVAILABLE}'
	first = True
	for _, row in sect_organ.iterrows():
		if not first:
			organizers += '\\newline '
		organizers += f'{row["name"]}, {row["firstname"]} {{\\em ({row["organisation"]})}}'
		title = row["track_type"]
		first = False
	return title, organizers

def get_session_info(session):
	
	start = session['session_start']
	end   = session['session_end']
	
	chairs = []
	for i in range(10):
		if f'chair{i}' in session.keys():
			chairs.append(str( session[f'chair{i}'] ))
	chairs = r' \newline '.join(chairs)

	session = {
		"chairs"   : chairs,
		"number"   : session['session_short'],
		"name"     : session['session_title'],
		"room"     : session['session_room'],
		"start"    : start.strftime("%H:%M"),
		"end"      : end.strftime("%H:%M"),
		"date"     : start.strftime("%B %d, %Y")
	}
	return session

# for a given session, get the nth presentation's info
def get_contribution_info(session, idx, RvML=False):
	
	if not f'p{idx}_title' in session.keys():
		return None
	
	ptitle     = f'p{idx}_title'
	pauthors   = f'p{idx}_authors'
	porgas     = f'p{idx}_organisations'
	ppresenter = f'p{idx}_presenting_author'
	pabstract  = f'p{idx}_abstract'
	pstart     = f'p{idx}_start'
	pend       = f'p{idx}_end'
	
	# if session['session_short'] == "A04_06":
	# 	print(session.to_string())
	# 	print(idx)
	
	presenter = session[ppresenter]
	if pd.isna(presenter):
		return None
	authors = session[pauthors]
	authors = authors.replace(presenter, f'\\presenter{{{presenter}}}')
	presenter = re.sub(r'(\s*\(\d+(,\d+)*\))?,?$', '', presenter)  # remove orga footnote thingies
	
	if session['session_short'].startswith('Poster'):
		duration = 0
	else:
		duration = get_duration(session[pstart], session[pend])
	if session[pabstract] != session[pabstract]:
		abstract = ''
	else:
		abstract = html2latex(session[pabstract])
	if RvML:
		start = dt.datetime.fromisoformat(session[pstart]).strftime('%H:%M')
		end   = dt.datetime.fromisoformat(session[pend]).strftime('%H:%M')
	else:
		start = session[pstart]
		end   = session[pend]
	
	contribution = {
		"title"         : latexEscape(session[ptitle]),
		"authors"       : authors,
		"presenter"     : presenter,
		"start"         : start,
		"end"           : end,
		"duration"      : duration,
		"abstract"      : abstract,
		"organizations" : session[porgas]
	}
	return contribution

def get_plenary_info(row):
	start = row['session_start']
	end   = row['session_end']
	if pd.isna(row['chair1']):
		chair = r'\color{red} NOT AVAILABLE'
	else:
		chair = row['chair1']
	if pd.isna(row['p1_organisations']):
		speaker = r'\presenter{' + row['p1_presenting_author'] + '}'
	else:
		speaker = r'\presenter{' + row['p1_presenting_author'] + '} {\\em (' + row['p1_organisations'] + ')}'
	contribution = {
		"session"  : row['session_short'],
		"title"    : row['p1_title'],
		"speaker"  : speaker,
		"abstract" : html2latex(row['p1_abstract']),
		"chair"    : chair,
		"room"     : row['session_room'],
		"start"    : start.strftime("%H:%M"),
		"end"      : end.strftime("%H:%M"),
		"date"     : start.strftime("%B %d, %Y")
	}
	return contribution

################################################################################
# helpers for writing the actual section files in LaTeX                        #
################################################################################
def latexEscape(string):
	# string = string.replace('\\', r'\backslash')
	return string

# calculate the width of a field for a table with n columns
def getTableColWidth(n,factor=1):
	
	# total target width of the table in cm
	availableWidth = 26
	
	# width of the left most field containing the session name and room
	headerWidth = 2
	
	# default margin of longtable is 6pt, where a pt is 1/72 inch and an inch 2.54cm
	margin = 6 * 1/72 * 2.54
	
	# available space after header
	availableWidth -= headerWidth + margin*2
	
	# divide space evenly between all fields
	availableWidth /= n
	
	# scale accordingly for double length talks etc.
	availableWidth *= factor
	
	# margin is added on, so we must account for it
	availableWidth -= margin*2
	
	return f'{{{availableWidth}cm}}'

def write_PML(df, outdir):
	file = open(outdir+'/PML.tex', 'w', encoding='utf-8')
	for _, row in df.iterrows():
		PML = get_plenary_info(row)
		ostring  = f'\\Prandtl{{{PML["title"]}}}%\n'
		ostring += f'        {{{PML["session"]}}}%\n'
		ostring += f'        {{{PML["speaker"]}}}%\n'
		ostring += f'        {{{PML["date"]}}}%\n'
		ostring += f'        {{{PML["start"]}}}%\n'
		ostring += f'        {{{PML["end"]}}}%\n'
		ostring += f'        {{{PML["room"]}}}%\n'
		ostring += f'        {{{PML["chair"]}}}%\n'
		ostring += f'        {{{PML["abstract"]}}}%\n'
		ostring = utf8_clean(ostring)
		file.write(ostring)
		file.close()
	return '\\input{PML.tex}\n'

def write_PL(df, outdir):
	inputs = ''
	for _, row in df.iterrows():
		PL = get_plenary_info(row)
		fname = f'{PL["session"]}.tex'
		file = open(outdir+'/'+fname, 'w', encoding='utf-8')
		ostring  = f'\\Plenary{{{PL["title"]}}}%\n'
		ostring += f'        {{{PL["session"]}}}%\n'
		ostring += f'        {{{PL["speaker"]}}}%\n'
		ostring += f'        {{{PL["date"]}}}%\n'
		ostring += f'        {{{PL["start"]}}}%\n'
		ostring += f'        {{{PL["end"]}}}%\n'
		ostring += f'        {{{PL["room"]}}}%\n'
		ostring += f'        {{{PL["chair"]}}}\n'
		ostring += f'        {{{PL["abstract"]}}}%\n'
		ostring = utf8_clean(ostring)
		file.write(ostring)
		file.close()
		inputs += f'\\input{{{fname}}}\n'
	return inputs

def write_RvML(df, outdir):
	file = open(outdir+'/RvML.tex', 'w', encoding='utf-8')
	for _, row in df.iterrows():
		date = row['session_start'].strftime("%B %d, %Y")
		room = row['session_room']
		ostring = ''
		for j in range(1,3):
			RvML = get_contribution_info(row,j, RvML=True)
			if not pd.isna(row[f'p{j}_presenting_author']):
				ostring += f'\\Mises{{{RvML["title"]}}}%\n'
				ostring +=  '       {Richard von Mises Lecture}%\n'
				ostring += f'       {{\\presenter{{{RvML["presenter"]}}}~{{\\em({RvML["organizations"]})}}}}%\n'
				ostring += f'       {{{date}}}%\n'
				ostring += f'       {{{RvML["start"]}}}%\n'
				ostring += f'       {{{RvML["end"]}}}%\n'
				ostring += f'       {{{room}}}{{}}%\n'
		ostring = utf8_clean(ostring)
		file.write(ostring)
		file.close()
	return '\\input{RvML.tex}\n'

def write_section(org, sessionBlock, sessions, outdir, toc_sessions_silent=False):
	sessions = sessions[sessions['session_short'].str.startswith(sessionBlock)]
	
	if sessions.empty:
		return
	
	fname = sessionBlock.replace(' ', '_')
	fullname = outdir+'/'+fname+'.tex'
	file = open(fullname, 'w', encoding='utf-8')
	
	# EFDC change: efdc has no organizer info, the column track_type doesn't even exist
	# title, organizers = get_section_info(org, sessionBlock)
	organizers = '---'
	title = sessions["session_title"].unique()
	if len(title) != 1:
		print(f"warning: found varying titles for sessionBlock {sessionBlock}:\n{title}")
	title = title[0]
	
	ostring  = f'\\Section{{{sessionBlock}: {title}}}%\n'
	ostring += f'        {{{organizers}}}\n\n'

	for _, row in sessions.iterrows():
		S = get_session_info(row)
		if toc_sessions_silent:
			ostring += r'\SSession'
		else:
			ostring += r'\Session'
		ostring += f'{{{S["number"]}}}%\n'
		ostring += f'{{{S["name"]}}}%\n'
		ostring += f'{{{S["date"]}}}%\n'
		ostring += f'{{{S["start"]}}}%\n'
		ostring += f'{{{S["end"]}}}%\n'
		ostring += f'{{{S["room"]}}}%\n'
		ostring += f'{{{S["chairs"]}}}%\n'
		for i in range(100):
			C = get_contribution_info(row, i)
			if C is None:
				continue
			organizations = C["organizations"]
			organizations = organizations.replace('; ','\\newline ')
			start = re.sub('^.* ','', C["start"])
			ostring += f'\\Contribution{{{C["title"]}}}%\n'
			ostring += f'{{{C["authors"]}}}%\n'
			ostring += f'{{{start}}}%\n'
			ostring += f'{{{organizations}}}\n'
			ostring += f'{{{html2latex(C["abstract"])}}}%\n'
	ostring = utf8_clean(ostring)
	file.write(ostring)
	file.close()
	return fname

def write_sections(organizers, sessions, outdir):
	inputs = ''
	# print(sessions["session_short"].str.rsplit(".",expand=True,n=1).iloc[:,0].unique())  # EFDC change: gamm splits at end, efdc at beginning
	
	for sessionBlock in sessions["session_short"].str.split(subsession_separation_chars,expand=True,n=1).iloc[:,0].unique():
		# if i == 6:
		# 	fname = write_section(organizers, f'S{i:02}.1', sessions, outdir)
		# 	inputs += f'\\input{{{fname}}}\n'
		# 	fname = write_section(organizers, f'S{i:02}.2', sessions, outdir)
		# 	inputs += f'\\input{{{fname}}}\n'
		# 	continue
		
		fname = write_section(organizers, sessionBlock, sessions, outdir)
		inputs += f'\\input{{{fname}}}\n'
	return inputs

def write_minis(organizers, MS, YRM, outdir):
	inputs = ''
	for i in range(len(MS)):
		name = f'MS{i+1}'
		fname = write_section(organizers, name, MS, outdir,
							  toc_sessions_silent=True)
		inputs += f'\\input{{{fname}}}\n'

	for i in range(len(YRM)):
		name = f'YRM{i+1}'
		fname = write_section(organizers, name, YRM, outdir,
							  toc_sessions_silent=True)
		inputs += f'\\input{{{fname}}}\n'
	return inputs

def write_dfg(organizers, df, outdir):
	inputs = ''
	for _, row in df.iterrows():
		fname = write_section(organizers, row['session_short'], df, outdir,
							  toc_sessions_silent=True)
		inputs += f'\\input{{{fname}}}\n'
	return inputs

################################################################################
# routine for writing the tables in the daily session program                 #
################################################################################
def make_session_table(sessionsAtTime, start, n, withMises=False):  # function used only in make_dsp
	
	# translation reference:
	#	BC → n=4
	#	XY → n=6
	#	xy → n=3
	#	mM → n=2
	#	A- → n=1
	#	T → n=3    // highlighted, use T
	#	t → n=1.5  // highlighted, use T
	
	column_sequence = ''.join(((f'X{getTableColWidth(n)}',f'Y{getTableColWidth(n)}')*-(-n//2))[:n])
	inputs = f'\\begin{{longtable}}{{P{column_sequence}|}}\n'
	
	inputs += r'    \rowcolor{primary}'
	for i in range(n):
		slot_start = advance_slot(start, i, sessionlengths.default).strftime("%H:%M")
		inputs += rf'& \raisebox{{-2pt}}{{\Large\bfseries\textcolor{{white}}{{{slot_start}}}}}'
	inputs += '\\\\\n\\endhead\n'
	skip = False
	for _, session in sessionsAtTime.iterrows():
		inputs += rf"\white{{\detokenize{{{session['session_short']}}}}}\newline\white{{\small\detokenize{{ ({session['session_room']})}}}}"
		
		# This was added for EFDC, didn't exist in GAMM
		inputs += rf"\newline\newline\white{{\small\detokenize{{{session['chair1_name']}}}}}"
		
		j = 0 # j counts speakers/contributions in the session CSV
		for i in range(n): # i counts fields in row
			if skip:
				skip = False
				continue
			
			inputs += '\n&'  # allways add cell, even if no info in cell
			
			j += 1
			contribution = get_contribution_info(session, j)
			
			if contribution is None:
				if session['session_short'] == 'RvML':
					inputs += r'\footnotesize{\bfseries Price winner(s) and title(s) will be announced in the Opening}'
				
				continue
			
			infofield = rf'\footnotesize{{\bfseries {contribution["title"]}}}\newline\presenter{{{contribution["presenter"]}}}'
			
			match contribution["duration"]:
				case 60: # PLenary lectures (incl Prandtl)
					inputs += infofield
				case sessionlengths.double: # Topcial Speakers
					skip = True # double length slot, so skip next time-slot in the loop
					
					inputs += f'\\multicolumn{{2}}{{T{getTableColWidth(n,2)}}}{{'  # double width field
					inputs += infofield
					inputs += f'}}'
					
				case sessionlengths.threeHalf: # either von Mises Lecture session with 2 talks or Minisymposium with 4 talks
					print("MS",i,j)
					if session['session_short'] == 'RvML':
						if withMises:
							inputs += infofield
						else:
							inputs += r'\footnotesize{\bfseries Price winner(s) and title(s) will be announced in the Opening}'
					else:
						noSlots = n*sessionlengths.default // sessionlengths.miniSymposium
						
						if i == 0:  # start
							inputs += rf'\multicolumn{{{n}}}{{{getTableColWidth(n,n)}}}{{\noindent\begin{{tabularx}}{{\linewidth}}{{@{{}}BCBC@{{}}}}'
						
						inputs += infofield
						
						if i == noSlots-1:  # end
							inputs += r'\end{tabularx}}'
							break  # replaces drop_extra_empty, by doing the same functionally, behaves better if missing contrib in 4-ses-ms
					
				case sessionlengths.default: # the default 15 or 20 minutes section talks
					shift = get_duration(advance_slot(start,i,sessionlengths.default).isoformat(), contribution["start"])
					if shift > 0: # there is a gap in the schedule
						j -= 1 # revisit contribution for next column
					else:
						inputs += infofield
				
				case _:
					raise SystemExit('make_session_table: non-standard contribution length detected')
		inputs += '\\\\\\hline\n'
	inputs += '\\end{longtable}\n'
	return utf8_clean(inputs)

def make_postersession_table(sessionsAtTime, start):  # function used only in make_dsp
	
	inputs = f'\\begin{{longtable}}{{PX{getTableColWidth(1)}|}}\n'
	
	inputs += '    \\rowcolor{primary}'
	inputs += f'&\\white{{{start.strftime("%H:%M")}}}'
	inputs += '\\\\\n\\endhead\n'
	for _, session in sessionsAtTime.iterrows():
		sname = session['session_short']
		sroom = session['session_room']
		inputs += rf'\white{{\detokenize{{{sname}}}}}\newline\white{{\small\detokenize{{ ({sroom})}}}}'
		for i in range(100): # just loop through enough entries of the session
			
			contribution = get_contribution_info(session, i)
			if contribution is None:
				continue
			
			inputs += '\n&'
			inputs += rf'\footnotesize{{\bfseries {contribution["title"]}}}\newline\presenter{{{contribution["presenter"]}}}'
			inputs += '\\\\\\hline\n'
			
	inputs += '\\end{longtable}\n'
	return utf8_clean(inputs)

def make_room_session_table(session, withMises=False, standalone=False):
	
	day = session.session_start.strftime("%A, %B %d")
	stime = session.session_start.strftime("%H:%M")
	etime = session.session_end.strftime("%H:%M")
	
	inputs = r"\small" +'\n'
	if standalone:
		inputs += fr'\fancyhead[D]{{\Large\bfseries {day}}}'
		inputs += fr'\fancyhead[C]{{\Large\bfseries {session.session_room}}}'
		inputs += fr'\fancyhead[R]{{\Large\bfseries {stime}--{etime}}}'
		inputs += r"\begin{samepage}"
		inputs += fr"\begin{{minipage}}{{0.22\textwidth}}\hfill \huge\bfseries\detokenize{{{session['session_short']}:}}\hspace*{{15pt}}\end{{minipage}}"
		inputs += fr"\begin{{minipage}}{{0.78\textwidth}}\bfseries\large\detokenize{{{session['session_title']}}}\end{{minipage}}}}"
		inputs += "\\vspace{10pt} \n\n"
		inputs += fr"\begin{{minipage}}{{0.22\textwidth}}\hfill \large\detokenize{{Chair:}}\hspace*{{15pt}}\end{{minipage}}"
		inputs += fr"\begin{{minipage}}{{0.78\textwidth}}\bfseries\large\detokenize{{{session['chair1_name']}}}\end{{minipage}}}}"
		# inputs += fr"{{\large\bfseries\detokenize{{{session['chair1_name']}}}}}"
		inputs += "\\vspace{20pt} \n\n"
	else:
		inputs += f'\n\\begin{{samepage}}\n\\section*{{{day}\\hfill{stime}--{etime}}}\n'
		inputs += f"\n\\begin{{center}}\\huge\\bfseries\\detokenize{{{session['session_short']}}}\\end{{center}}\n"
	inputs += '\\begin{tabularx}{\\linewidth}{|A|B|}\n\\hline\n'
	for i in range(99):
		contribution = get_contribution_info(session, i)
		
		if session['session_short'] == 'RvML' and i == 1 and (contribution is None or not withMises):
			cstart = session.session_start.strftime("%H:%M")
			inputs += f'{cstart}&\n'
			inputs += r'\textbf{Price winner(s) and title(s) will be announced in the Opening}\\ \hline' +'\n'
			continue
		
		if contribution is None:
			continue
		
		if contribution["duration"] == 0: # set explicitly for posters
			cstart = session.session_start.strftime("%H:%M")
		else:
			cstart = dt.datetime.fromisoformat(contribution["start"]).strftime("%H:%M")
		inputs += f'{cstart}&\n'
		if standalone:
			inputs += rf'\footnotesize\textbf{{{contribution["title"]}}}'
			# authors = re.sub(r'\s*\((\d+(?:,\d+)*)\)', r'$^\\textbf{\\footnotesize \,\g<1>}$', contribution["authors"])
			authors = re.sub(r'\s*\((\d+(?:,\d+)*)\)', '', contribution["authors"])
			inputs += rf'\vspace{{2pt}} \newline {{{authors}}}'
			# orgas = re.sub(r'(^|;\s*)(\d+):\s*', r'\g<1>$^\\textbf{\\scriptsize \g<2>}$', contribution["organizations"])
			# inputs += rf'\vspace{{5pt}} \newline \scriptsize{{{orgas}}}'
		else:
			inputs += rf'\textbf{{{contribution["title"]}}}\newline\textit{{{contribution["presenter"]}}}'
		inputs += r"\\ \hline" +'\n'

	inputs += '\\end{tabularx}\n\\end{samepage}\n'

	return utf8_clean(inputs)
################################################################################
# top-level routines for generating the book of abstracts and daily session    #
# program                                                                      #
################################################################################
def make_boa(df, withMises):
	# Filter by the categories desired as chapter in the BoA
	getSessions = lambda acronym: df[df['session_short'].str.startswith(acronym)].sort_values(by='session_short')
	
	# EFDC change: new session acronyms
	# DFG              = getSessions('DFG')
	# Prandtl          = getSessions('PML')
	# Plenaries        = getSessions('PL')
	# Minisymposia     = getSessions('MS')
	# YoungResearchers = getSessions('YRM')
	# Contributed      = getSessions('S')
	DFG              = getSessions('DFG')
	Prandtl          = getSessions('PML')
	Plenaries        = getSessions('PL')
	Minisymposia     = getSessions('MS')
	YoungResearchers = getSessions('YRM')
	Contributed      = getSessions('A')
	
	# Read the relevant Organizer information exported from ConfTool
	Organizers = pd.read_csv('CSV/organizers.csv',
							sep=';',
							quotechar='"',
							# usecols=['track_type', 'name', 'firstname', 'organisation'])
							usecols=['name', 'firstname', 'organisation'])  # EFDC change - track_type does not exist
	# drop everyone whos not a session organizer and sort by sections
	# Organizers = Organizers[Organizers.track_type.notnull()].sort_values(by='track_type')  # EFDC change - track_type does not exist

	outdir  = './LaTeX/Book_of_abstracts/Sessions/'
	inputs  = '\\chapter{Prandtl Memorial Lecture and Plenary~Lectures}\n'
	inputs += write_PML(Prandtl, outdir)
	inputs += write_PL(Plenaries, outdir)
	if withMises:
		vonMises = df[df['session_short'].str.startswith('RvML')].sort_values(by='session_short')
		inputs  += '\\chapter{Richard von Mises Price Lecture(s)}\n'
		inputs  += write_RvML(vonMises, outdir)
	inputs += '\\chapter{Minisymposia and Young~Researchers~Minisymposia}\n'
	inputs += write_minis(Organizers, Minisymposia, YoungResearchers, outdir)
	inputs += '\\chapter{DFG Programs}\n'
	inputs += write_dfg(Organizers, DFG, outdir)
	inputs += '\\chapter{Contributed Sessions}\n'
	inputs += write_sections(Organizers, Contributed, outdir)

	boa = open('./LaTeX/Book_of_abstracts/BookOfAbstracts.tex', 'w', encoding = 'utf-8')
	contents = r'''\nonstopmode
\documentclass[colorlinks]{gamm-boa}

\begin{document}
\tableofcontents
CONTENTS
\printindex
\end{document}
'''
	contents = contents.replace('CONTENTS', inputs)
	boa.write(contents)
	boa.close()

def make_dsp(sessions, withMises):
	
	# iterate over bunches of sessions starting at the same time
	inputs = ''
	old_day = None
	sessions = sessions.sort_values(['session_start','session_short'])
	for start, sessionsAtTime in sessions.groupby('session_start'):
		
		day = start.strftime("%A, %B %d")
		if old_day != day:
			old_day = day
			inputs += f'\\chapter{{{day}}}\n'
		#inputs += f'\\section*{{{start.strftime("%H:%M")}}}\n'
		length = get_ses_length(sessionsAtTime.iloc[0])
		if len(sessionsAtTime) == 1:
			if sessionsAtTime['session_short'].values[0].startswith('Poster'):
				inputs += make_postersession_table(sessionsAtTime, start)
			else:
				inputs += make_session_table(sessionsAtTime, start, 1, withMises=withMises)
		else:
			num_slots = length // sessionlengths.default
			inputs += make_session_table(sessionsAtTime, start, num_slots, withMises=withMises)
			# inputs += make_postersession_table(sessionsAtTime, start)
	contents = r'''\nonstopmode
		\documentclass[colorlinks]{gamm-dsp}
		
		\begin{document}
		\tableofcontents
		\arrayrulecolor{primary}
		
		CONTENTS
		\printindex
		\end{document}
	'''
	contents = contents.replace('CONTENTS', inputs)
	with open('./LaTeX/Daily_Scientific_Program/Daily_Scientific_Program.tex', 'w') as dsp:
		dsp.write(contents)

def make_room_plans(sessions, withMises):
	outdir = './LaTeX/Daily_Scientific_Program/rooms/'
	
	with open('./LaTeX/Daily_Scientific_Program/room_template.tex', 'r') as template_file:
		template = template_file.read()
	
	sessions = sessions.sort_values(['session_room','session_start'])
	for room, roomsessions in sessions.groupby('session_room'):
		print(f'Generating room: {room}\n')
		room = room.replace('/', '-')
		old_day = ''
		inputs = ''
		for _, row in roomsessions.iterrows():
			day = row['session_start'].strftime("%A, %B %d")
			if old_day != day:
				old_day = day
				inputs += '\n\\pagebreak[4]'
			inputs += make_room_session_table(row, withMises=withMises)
		contents = template.replace('ROOM', room)
		contents = contents.replace('CONTENTS', inputs)
		
		with open(f'{outdir}{room}.tex', 'w') as room_file:
			room_file.write(contents)

def make_session_plans(sessions, withMises):
	outdir = './LaTeX/Daily_Scientific_Program/days/'
	
	days = {}
	
	sessions = sessions.sort_values(['session_start','session_room'])
	for _, session in sessions.iterrows():
		day = session.session_start.strftime("%A, %B %d")
		
		if day not in days:
			days[day] = []
		days[day].append( make_room_session_table(session, withMises=withMises, standalone=True) )
	
	for day, dayTexs in days.items():
		contents = r"""
			\documentclass{article}
			
			% \usepackage[a3paper,margin=2cm]{geometry}
			\usepackage[a4paper,landscape,margin=2cm,bmargin=1cm]{geometry}
			\usepackage[fontsize=15.0,parindent=0]{fontsize}
			\usepackage[ngerman,american]{babel}
			\usepackage{fontspec}
			\setmainfont{Open Sans}
			\pagestyle{empty}
			
			\usepackage{tabularx, array}
			\newcolumntype{A}{>{\centering}p{5ex}}
			\newcolumntype{B}{>{\raggedright\arraybackslash}X}
			
			\usepackage{fancyhdr}
			\pagestyle{fancy}
			\fancyhf{}
			\renewcommand{\headrulewidth}{0.66pt}
			\setlength{\headheight}{22.0pt}
			\setlength{\arrayrulewidth}{1pt}
			\renewcommand{\arraystretch}{1.5}
			
			\newcommand{\presenter}[1]{\underline{#1}}
			
			\begin{document}
			
			CONTENTS
			
			\end{document}
			
			%%% Local Variables:
			%%% mode: latex
			%%% TeX-master: t
			%%% End:
		"""
		if day in ["Monday, September 16","Friday, September 20"]:
			contents = contents.replace('a4paper,landscape', 'a3paper,portrait' )
		print(f"day: printed {len(dayTexs)} sessions on at least as many pages")
		contents = contents.replace('CONTENTS', '\n\\pagebreak[4]'.join(dayTexs) )
		with open(f'{outdir}{day}.tex', 'w') as day_file:
			day_file.write(contents)


################################################################################
# Main function                                                                #
################################################################################
def main():
	parser = argparse.ArgumentParser(description='Generate PDFs for conference materials.')
	parser.add_argument('-m', '--withMises', action='store_true', help='onclude von Mises lecturer(s) and title(s)')
	args = parser.parse_args()
	
	if args.withMises:
		withMises = True
	else:
		withMises = False
	
	print(f'\nInclude von Mises Prize lectures: {withMises}\n\n')
	
	# Read the Sessions exported from ConfTool
	sessions = pd.read_csv('CSV/sessions.csv', sep=';', quotechar='"')
	sessions['session_start'] = pd.to_datetime(sessions['session_start'])
	sessions['session_end'] = pd.to_datetime(sessions['session_end'])
	
	# print('\nGenerating book of abstracts LaTeX files\n')
	# make_boa(sessions, withMises=withMises)
	
	# Daily Scientific Program
	# make a PDF of one table per each starting time of sessions.
	# Left to right is chronological talks within the sessions, top to bottom is the different sessions at the same time
	print('\nGenerating Session Table LaTeX files\n')
	make_dsp(sessions, withMises=withMises)
	
	# Make separate PDFs for each room, listing contributions there chronologically day by day
	# print('\nGenerating Room Plan LaTeX files\n')  # TODO: RWTH revert
	# make_room_plans(sessions, withMises=withMises)
	
	# Make pages for each session, so per room and starttime. Group them into PDFs by day
	print('\nGenerating Daily Room Plan LaTeX files\n')
	make_session_plans(sessions, withMises=withMises)

if __name__ == "__main__":
	main()
