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


"""Miscellaneous essential routines.

This includes actual message transmission routines, address checking and
message and address munging, a handy-dandy routine to map a function on all
the mailing lists, and whatever else doesn't belong elsewhere.

"""

import sys
import os
import string
import re
# XXX: obsolete, should use re module
import regsub
import fcntl
import random
import mm_cfg


# Valid toplevel domains for when we check the validity of an email address.

valid_toplevels = ["com", "edu", "gov", "int", "mil", "net", "org",
"inc", "af", "al", "dz", "as", "ad", "ao", "ai", "aq", "ag", "ar",
"am", "aw", "au", "at", "az", "bs", "bh", "bd", "bb", "by", "be",
"bz", "bj", "bm", "bt", "bo", "ba", "bw", "bv", "br", "io", "bn",
"bg", "bf", "bi", "kh", "cm", "ca", "cv", "ky", "cf", "td", "cl",
"cn", "cx", "cc", "co", "km", "cg", "ck", "cr", "ci", "hr", "cu",
"cy", "cz", "dk", "dj", "dm", "do", "tp", "ec", "eg", "sv", "gq",
"ee", "et", "fk", "fo", "fj", "fi", "fr", "gf", "pf", "tf", "ga",
"gm", "ge", "de", "gh", "gi", "gb", "uk", "gr", "gl", "gd", "gp",
"gu", "gt", "gn", "gw", "gy", "ht", "hm", "hn", "hk", "hu", "is",
"in", "id", "ir", "iq", "ie", "il", "it", "jm", "jp", "jo", "kz",
"ke", "ki", "kp", "kr", "kw", "kg", "la", "lv", "lb", "ls", "lr",
"ly", "li", "lt", "lu", "mo", "mg", "mw", "my", "mv", "ml", "mt",
"mh", "mq", "mr", "mu", "mx", "fm", "md", "mc", "mn", "ms", "ma",
"mz", "mm", "na", "nr", "np", "an", "nl", "nt", "nc", "nz", "ni",
"ne", "ng", "nu", "nf", "mp", "no", "om", "pk", "pw", "pa", "pg",
"py", "pe", "ph", "pn", "pl", "pt", "pr", "qa", "re", "ro", "ru",
"rw", "kn", "lc", "vc", "sm", "st", "sa", "sn", "sc", "sl", "sg",
"sk", "si", "sb", "so", "za", "es", "lk", "sh", "pm", "sd", "sr",
"sj", "sz", "se", "ch", "sy", "tw", "tj", "tz", "th", "tg", "tk",
"to", "tt", "tn", "tr", "tm", "tc", "tv", "ug", "ua", "um", "us",
"uy", "uz", "vu", "va", "ve", "vn", "vg", "vi", "wf", "eh", "ws",
"ye", "yu", "zr", "zm", "zw", "su"]

def list_names():
    """Return the names of all lists in default list directory."""
    got = []
    for fn in os.listdir(mm_cfg.LIST_DATA_DIR):
	if not (
	    os.path.exists(
		os.path.join(os.path.join(mm_cfg.LIST_DATA_DIR, fn),
			     'config.db'))):
	    continue
	got.append(fn)
    return got

# a much more naive implementation than say, Emacs's fill-paragraph!
def wrap(text, column=70):
    """Wrap and fill the text to the specified column.

    Wrapping is always in effect, although if it is not possible to wrap a
    line (because some word is longer than `column' characters) the line is
    broken at the next available whitespace boundary.  Paragraphs are also
    always filled, unless the line begins with whitespace.  This is the
    algorithm that the Python FAQ wizard uses, and seems like a good
    compromise.

    """
    wrapped = ''
    # first split the text into paragraphs, defined as a blank line
    paras = re.split('\n\n', text)
    for para in paras:
        # fill
        lines = []
        fillprev = 0
        for line in string.split(para, '\n'):
            if not line:
                lines.append(line)
                continue
            if line[0] in string.whitespace:
                fillthis = 0
            else:
                fillthis = 1
            if fillprev and fillthis:
                # if the previous line should be filled, then just append a
                # single space, and the rest of the current line
                lines[-1] = string.rstrip(lines[-1]) + ' ' + line
            else:
                # no fill, i.e. retain newline
                lines.append(line)
            fillprev = fillthis
        # wrap each line
        for text in lines:
            while text:
                if len(text) <= column:
                    line = text
                    text = ''
                else:
                    bol = column
                    # find the last whitespace character
                    while bol > 0 and text[bol] not in string.whitespace:
                        bol = bol - 1
                    # now find the last non-whitespace character
                    eol = bol
                    while eol > 0 and text[eol] in string.whitespace:
                        eol = eol - 1
                    # watch out for text that's longer than the column width
                    if eol == 0:
                        # break on whitespace after column
                        eol = column
                        while eol < len(text) and \
                              text[eol] not in string.whitespace:
                            eol = eol + 1
                        bol = eol
                        while bol < len(text) and \
                              text[bol] in string.whitespace:
                            bol = bol + 1
                        bol = bol - 1
                    line = text[:eol+1] + '\n'
                    text = text[bol+1:]
                wrapped = wrapped + line
            wrapped = wrapped + '\n'
        wrapped = wrapped + '\n'
    return wrapped
    

def SendTextToUser(subject, text, recipient, sender, add_headers=[]):
    import Message
    msg = Message.OutgoingMessage()
    msg.SetSender(sender)
    msg.SetHeader('Subject', subject, 1)
    msg.SetBody(QuotePeriods(text))
    DeliverToUser(msg, recipient, add_headers=add_headers)

def DeliverToUser(msg, recipient, add_headers=[]):
    """Use smtplib to deliver message.

    Optional argument add_headers should be a list of headers to be added
    to the message, e.g. for Errors-To and X-No-Archive."""
    # We fork to ensure no deadlock.  Otherwise, even if sendmail is
    # invoked in forking mode, if it eg detects a bad address before
    # forking, then it will try deliver to the errorsto addr *in the
    # foreground*.  If the errorsto happens to be the list owner for a list
    # that is doing the send - and holding a lock - then the delivery will
    # hang pending release of the lock - deadlock.
    if os.fork():
        return
    sender = msg.GetSender()

    try:
        try:
            msg.headers.remove('\n')
        except ValueError:
            pass
        if not msg.getheader('to'):
            msg.headers.append('To: %s\n' % recipient)
        for i in add_headers:
            if i and i[-1] != '\n':
              i = i + '\n'
            msg.headers.append(i)

        text = string.join(msg.headers, '')+ '\n'+ QuotePeriods(msg.body)
        import OutgoingQueue
        queue_id = OutgoingQueue.enqueueMessage(sender, recipient, text)
        TrySMTPDelivery(recipient,sender,text,queue_id)
        # Just in case there's still something waiting to be sent...
        OutgoingQueue.processQueue()
    finally:
        os._exit(0)

def TrySMTPDelivery(recipient, sender, text, queue_entry):
    import smtplib
    try:
        con = smtplib.SmtpConnection(mm_cfg.SMTPHOST)
        con.helo(mm_cfg.DEFAULT_HOST_NAME)
        con.send(to=recipient,frm=sender,text=text)
        con.quit()
        import OutgoingQueue
        OutgoingQueue.dequeueMessage(queue_entry)
    finally:
#    except: # Todo: This might want to handle special cases.    
        pass # Just try again later.
def QuotePeriods(text):
    return string.join(string.split(text, '\n.\n'), '\n .\n')

def ValidEmail(str):
    """Verify that the an email address isn't grossly invalid."""
    # Pretty minimal, cheesy check.  We could do better...
    if ((string.find(str, '|') <> -1) or (string.find(str, ';') <> -1)
	or str[0] == '-'):
	raise mm_err.MMHostileAddress
    if string.find(str, '/') <> -1:
	if os.path.isdir(os.path.split(str)[0]):
	    raise mm_err.MMHostileAddress
    user, domain_parts = ParseEmail(str)
    if not domain_parts:
	if string.find(str, '@') < 1:
	    return 0
	else:
	    return 1
    if len(domain_parts) < 2:
	return 0
##     if domain_parts[-1] not in valid_toplevels:
## 	if len(domain_parts) <> 4:
## 	    return 0
## 	try:
## 	    domain_parts = map(eval, domain_parts) 
## 	except:
## 	    return 0
## 	for i in domain_parts:
## 	    if i < 0 or i > 255:
## 		return 0
    return 1


#
def GetPathPieces(path):
    l = string.split(path, '/')
    try:
	while 1:
	    l.remove('')
    except ValueError:
	pass
    return l

nesting_level = None
def GetNestingLevel():
  global nesting_level
  if nesting_level == None:
    try:
      path = os.environ['PATH_INFO']
      if path[0] <> '/': 
        path= '/' + path
      nesting_level = len(string.split(path, '/')) - 1
    except KeyError:
      nesting_level = 0
  return nesting_level

def MakeDirTree(path, perms=0775, verbose=0):
    made_part = '/'
    path_parts = GetPathPieces(path)
    for item in path_parts:
	made_part = os.path.join(made_part, item)
	if os.path.exists(made_part):
	    if not os.path.isdir(made_part):
		raise "RuntimeError", ("Couldn't make dir tree for %s.  (%s"
				       " already exists)" % (path, made_part))
	else:
	    ou = os.umask(0)
	    try:
		os.mkdir(made_part, perms)
	    finally:
		os.umask(ou)
	    if verbose:
		print 'made directory: ', madepart
  
# This takes an email address, and returns a tuple containing (user,host)
def ParseEmail(email):
    user = None
    domain = None
    email = string.lower(email)
    at_sign = string.find(email, '@')
    if at_sign < 1:
	return (email, None)
    user = email[:at_sign]
    rest = email[at_sign+1:]
    domain = string.split(rest, '.')
    return (user, domain)

# Return 1 if the 2 addresses match.  0 otherwise.
# Might also want to match if there's any common domain name...
# There's password protection anyway.

def AddressesMatch(addr1, addr2):
    "True when username matches and host addr of one addr contains other's."
    user1, domain1 = ParseEmail(addr1)
    user2, domain2 = ParseEmail(addr2)
    if user1 != user2:
	return 0
    if domain1 == domain2:
        return 1
    elif not domain1 or not domain2:
        return 0
    for i in range(-1 * min(len(domain1), len(domain2)), 0):
        # By going from most specific component of host part we're likely
        # to hit a difference sooner.
        if domain1[i] != domain2[i]:
            return 0
    return 1


def FindMatchingAddresses(name, array):
    """Given an email address, and a list of email addresses, returns the
    subset of the list that matches the given address.  Should sort based
    on exactness of match, just in case."""

    def CallAddressesMatch (x, y=name):
	return AddressesMatch(x,y)

    matches = filter(CallAddressesMatch, array)
    return matches
  
def GetRandomSeed():
    chr1 = int(random.random() * 57) + 65
    chr2 = int(random.random() * 57) + 65
    return "%c%c" % (chr1, chr2)


def SnarfMessage(msg):
    if msg.unixfrom:
	text = msg.unixfrom + string.join(msg.headers, '') + '\n' + msg.body
    else:
	text = string.join(msg.headers, '') + '\r\n' + msg.body
    return (msg.GetSender(), text) 


def QuoteHyperChars(str):
    arr = regsub.splitx(str, '[<>"&]')
    i = 1
    while i < len(arr):
	if arr[i] == '<':
	    arr[i] = '&lt;'
	elif arr[i] == '>':
	    arr[i] = '&gt;'
	elif arr[i] == '"':
	    arr[i] = '&quot;'
	else:     #if arr[i] == '&':
	    arr[i] = '&amp;'
	i = i + 2
    return string.join(arr, '')

# Just changing these two functions should be enough to control the way
# that email address obscuring is handled.

def ObscureEmail(addr, for_text=0):
    """Make email address unrecognizable to web spiders, but invertable.

    When for_text option is set (not default), make a sentence fragment
    instead of a token."""
    if for_text:
	return re.sub("@", " at ", addr)
    else:
	return re.sub("@", "__at__", addr)

def UnobscureEmail(addr):
    """Invert ObscureEmail() conversion."""
    # Contrived to act as an identity operation on already-unobscured
    # emails, so routines expecting obscured ones will accept both.
    return re.sub("__at__", "@", addr)

def map_maillists(func, names=None, unlock=None, verbose=0):
    """Apply function (of one argument) to all list objs in turn.

    Returns a list of the results.

    Optional arg 'names' specifies which lists, default all.
    Optional arg unlock says to unlock immediately after instantiation.
    Optional arg verbose says to print list name as it's about to be
    instantiated, CR when instantiation is complete, and result of
    application as it shows."""
    from MailList import MailList
    if names == None: names = list_names()
    got = []
    for i in names:
	if verbose: print i,
	l = MailList(i)
	if verbose: print
	if unlock and l.Locked():
	    l.Unlock()
	got.append(apply(func, (l,)))
	if verbose: print got[-1]
	if not unlock:
	    l.Unlock()
	del l
    return got


def chunkify(members, chunksize=mm_cfg.ADMIN_MEMBER_CHUNKSIZE):
     """
     return a list of lists of members
     """
     members.sort()
     res = []
     while 1:
         if not members:
             break
         chunk = members[:chunksize]
         res.append(chunk)
         members = members[chunksize:]
     return res


def maketext(templatefile, dict, raw=0):
    """Make some text from a template file.

    Reads the `templatefile', relative to mm_cfg.TEMPLATE_DIR, does string
    substitution by interpolating in the `dict', and if `raw' is false,
    wraps/fills the resulting text by calling wrap().
    """
    file = os.path.join(mm_cfg.TEMPLATE_DIR, templatefile)
    fp = open(file)
    template = fp.read()
    fp.close()
    if raw:
        return template % dict
    return wrap(template % dict)
