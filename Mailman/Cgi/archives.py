#! /usr/bin/env/python
#
# Copyright (C) 1998 by the Free Software Foundation, Inc.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software 
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

# This script is being deprecated, in favor hookups for an external archiver.

# We don't need to lock in this script, because we're never going to change
# data.

import sys
import os, types, posix, string
from Mailman import Utils, MailList, htmlformat

print "Content-type: text/html"
print

path = os.environ['PATH_INFO']
list_info = Utils.GetPathPieces(path)

if len(list_info) < 1:
    print "<h2>Invalid options to CGI script.</h2>"
    sys.exit(0)

list_name = string.lower(list_info[0])

try:
  list = MailList.MailList(list_name)
except:
  print "<h2>%s: No such list.</h2>" % list_name
  sys.exit(0)

if not list._ready:
    print "<h2>%s: No such list.</h2>" % list_name
    sys.exit(0)

def GetArchiveList(list):
    archive_list = htmlformat.UnorderedList()
    
    def ArchiveFilter(str):
	if str[:7] <> 'volume_':
	    return 0
	try:
	    x = eval(str[7:])
	    if type(x) <> types.IntType:
		return 0
	    if x < 1:
		return 0
	    return 1
	except:
	    return 0
    try:
	dir_listing = filter(ArchiveFilter, os.listdir(list.archive_dir()))
    except posix.error:
	return "<h3><em>No archives are currently available.</em></h3>"
    if not len(dir_listing):
	return "<h3><em>No archives are currently available.</em></h3>"
    for dir in dir_listing:
	link = htmlformat.Link("%s/%s" % (list._base_archive_url, dir),
			       "Volume %s" % dir[7:])
	archive_list.AddItem(link)

    return archive_list.Format()
	
    
    

replacements = list.GetStandardReplacements()
replacements['<mm-archive-list>'] = GetArchiveList(list)

# Just doing print list.ParseTags(...) calls ParseTags twice???
text = list.ParseTags('archives.html', replacements)
print text
