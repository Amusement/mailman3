#! /usr/bin/env python
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

"""Process subscription or roster requests from listinfo form."""

import sys
import os, cgi, string
from regsub import gsub
from Mailman import Utils, MailList, Errors, htmlformat
from Mailman import mm_cfg

def main():
    doc = htmlformat.Document()
    if not os.environ.has_key("PATH_INFO"):
        doc.AddItem(htmlformat.Header(2, "Error"))
        doc.AddItem(htmlformat.Bold("You must include a listname in the url."))
        print doc.Format(bgcolor="#ffffff")
        sys.exit(0)
    path = os.environ['PATH_INFO']
    list_info = Utils.GetPathPieces(path)
    list_name = string.lower(list_info[0])

    if len(list_info) < 1:
        doc.AddItem(htmlformat.Header(2, "Error"))
        doc.AddItem(htmlformat.Bold("Invalid options to CGI script."))
        print doc.Format(bgcolor="#ffffff")
        sys.exit(0)

    try:
      list = MailList.MailList(list_name)
    except:
      doc.AddItem(htmlformat.Header(2, "Error"))
      doc.AddItem(htmlformat.Bold("%s: No such list." % list_name ))
      print doc.Format(bgcolor="#ffffff")
      sys.exit(0)


    if not list._ready:
        doc.AddItem(htmlformat.Header(2, "Error"))
        doc.AddItem(htmlformat.Bold("%s: No such list." % list_name ))
        print doc.Format(bgcolor="#ffffff")
        list.Unlock()
        sys.exit(0)

    form = cgi.FieldStorage()

    error = 0
    results = ''

    def call_script(which, pathinfo, list):
        "A little bit of a hack to call one of the scripts..."
        os.environ['PATH_INFO'] = string.join(pathinfo, '/')
        list.Unlock()
        pkg = __import__('Mailman.Cgi', globals(), locals(), [which])
        mod = getattr(pkg, which)
        mod.main()
        sys.exit(0)

    #######
    # Preliminaries done, actual processing of the form input below.

    if (form.has_key("UserOptions")
          or (form.has_key("info") and not form.has_key("email"))):

        # Go to user options section.

        if not form.has_key("info"):
            doc.AddItem(htmlformat.Header(2, "Error"))
            doc.AddItem(
                htmlformat.Bold("You must supply your email address."))
            doc.AddItem(list.GetMailmanFooter())
            print doc.Format(bgcolor="#ffffff")
            list.Unlock()
            sys.exit(0)
        addr = form['info'].value
        member = list.FindUser(addr)
        if not member:
            doc.AddItem(htmlformat.Header(2, "Error"))
            doc.AddItem(htmlformat.Bold("%s has no subscribed addr <i>%s</i>."
                                        % (list.real_name, addr)))
            doc.AddItem(list.GetMailmanFooter())
            print doc.Format(bgcolor="#ffffff")
            list.Unlock()
            sys.exit(0)
        list.Unlock()
        call_script('options', [list._internal_name, member], list)
        return                          # Should not get here!

    if not form.has_key("email"):
        error = 1
        results = results + "You must supply a valid email address.<br>"
        #
        # define email so we don't get a NameError below
        # with if email == list.GetListEmail() -scott
        #
        email = ""
    else:
        email = form["email"].value

    remote = remote_addr()
    if email == list.GetListEmail():
        error = 1
        if remote: remote = "Web site " + remote
        else:      remote = "unidentified origin"
        badremote = "\n\tfrom " + remote
        list.LogMsg("mischief", ("Attempt to self subscribe %s:%s"
                                 % (email, badremote)))
        results = results + "You must not subscribe a list to itself!<br>"

    if not form.has_key("pw") or not form.has_key("pw-conf"):
        error = 1
        results = (results
                   + "You must supply a valid password, and confirm it.<br>")
    else:
        pw  = form["pw"].value
        pwc = form["pw-conf"].value

    if not error and (pw <> pwc):
        error = 1
        results = results + "Your passwords did not match.<br>"

    if form.has_key("digest"):
        try:
            digest = int(form['digest'].value)
        except ValueError:
            # TBD: Hmm, this shouldn't happen
            digest = 0

    if not list.digestable:
        digest = 0
    elif not list.nondigestable:
        digest = 1


    if error:
        PrintResults(list, results, doc)

    else:
        try:
            if list.FindUser(email):
                raise Errors.MMAlreadyAMember
            if digest:
                digesting = " digest"
            else:
                digesting = ""
            list.AddMember(email, pw, digest, remote)
        #
        # check for all the errors that list.AddMember can throw
        # options  on the web page for this cgi
        #
        except Errors.MMBadEmailError:
            results = results + ("Mailman won't accept the given email "
                                 "address as a valid address. (Does it "
                                 "have an @ in it???)<p>")
        except Errors.MMListNotReady:
            results = results + ("The list is not fully functional, and "
                                 "can not accept subscription requests.<p>")
        except Errors.MMSubscribeNeedsConfirmation:
            results = results + ("Confirmation from your email address is "
                                 "required, to prevent anyone from covertly "
                                 "subscribing you.  Instructions are being "
                                 "sent to you at %s." % email)

        except Errors.MMNeedApproval, x:
            results = results + ("Subscription was <em>deferred</em> "
                                 "because:<br> %s<p>Your request must "
                                 "be approved by the list admin.  "
                                 "You will receive email informing you "
                                 "of the moderator's descision when they "
                                 "get to your request.<p>" % x)
        except Errors.MMHostileAddress:
            results = results + ("Your subscription is not allowed because "
                                 "the email address you gave is insecure.<p>")
        except Errors.MMAlreadyAMember:
            results = results + "You are already subscribed!<p>"
        #
        # these shouldn't happen, but if someone's futzing with the cgi
        # they might -scott
        #
        except Errors.MMCantDigestError:
            results = results + "No one can subscribe to the digest of this list!"
        except Errors.MMMustDigestError:
            results = results + "This list only supports digest subscriptions!"
        else:
            results = results + "You have been successfully subscribed to %s." % (list.real_name)
            list.Save()

    PrintResults(list, results, doc)
    list.Unlock()



def PrintResults(list, results, doc):
    replacements = list.GetStandardReplacements()
    replacements['<mm-results>'] = results
    output = list.ParseTags('subscribe.html', replacements)

    doc.AddItem(output)
    print doc.Format(bgcolor="#ffffff")
    list.Unlock()
    sys.exit(0)

def remote_addr():
    "Try to return the remote addr, or if unavailable, None."
    if os.environ.has_key('REMOTE_HOST'):
        return os.environ['REMOTE_HOST']
    elif os.environ.has_key('REMOTE_ADDR'):
        return os.environ['REMOTE_ADDR']
    else:
        return None
                                
