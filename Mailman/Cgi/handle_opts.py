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

"""Process input to user options form."""

import sys
import os, cgi, string
from Mailman import Utils, MailList, Errors, htmlformat
from Mailman import mm_cfg



def PrintResults(results):
    # XXX: blech, yuk, ick
    global list
    global operation
    global doc

    replacements = list.GetStandardReplacements()
    replacements['<mm-results>'] = results
    replacements['<mm-operation>'] = operation
    output = list.ParseTags('handle_opts.html', replacements)

    doc.AddItem(output)
    print doc.Format(bgcolor="#ffffff")
    list.Unlock()
    sys.exit(0)



def main():
    # XXX: blech, yuk, ick
    global list
    global operation
    global doc

    doc = htmlformat.Document()

    path = os.environ['PATH_INFO']
    list_info = Utils.GetPathPieces(path)

    if len(list_info) < 2:
        doc.AddItem(htmlformat.Header(2, "Error"))
        doc.AddItem(htmlformat.Bold("Invalid options to CGI script."))
        print doc.Format(bgcolor="#ffffff")
        sys.exit(0)

    list_name = string.lower(list_info[0])
    user = list_info[1]

    if len(list_info) < 2:
        doc.AddItem(htmlformat.Header(2, "Error"))
        doc.AddItem(htmlformat.Bold("Invalid options to CGI script."))
        print doc.Format(bgcolor="#ffffff")
        sys.exit(0)

    try:
        list = MailList.MailList(list_name)
    except:
        doc.AddItem(htmlformat.Header(2, "Error"))
        doc.AddItem(htmlformat.Bold("%s: No such list." % list_name))
        print doc.Format(bgcolor="#ffffff")
        sys.exit(0)

    if not list._ready:
        doc.AddItem(htmlformat.Header(2, "Error"))
        doc.AddItem(htmlformat.Bold("%s: No such list." % list_name))
        print doc.Format(bgcolor="#ffffff")
        list.Unlock()
        sys.exit(0)

    form = cgi.FieldStorage()

    error = 0
    operation = ""
    user = Utils.LCDomain(user)
    #
    # XXX shouldn't this check use Utils.FindMatchingAddresses?
    #                                               -scott
    if not list.members.has_key(user) \
       and not list.digest_members.has_key(user):
        PrintResults("%s not a member!<p>" % user)

    if form.has_key("unsub"):
        operation = "Unsubscribe"
        if not form.has_key("upw"):
            PrintResults("You must give your password to unsubscribe.<p>")
        else:
            try:
                pw = form["upw"].value
                if list.ConfirmUserPassword(user, pw):
                    list.DeleteMember(user, "web cmd")
            except Errors.MMListNotReady:
                PrintResults("List is not functional.")
            except Errors.MMNoSuchUserError:
                PrintResults("You seem to already be not a member.<p>")
            except Errors.MMBadUserError:
                PrintResults("Your account has gone awry - "
                             "please contact the list administrator!<p>")
            except Errors.MMBadPasswordError:
                PrintResults("That password was incorrect.<p>")
    #	except:
    #	    PrintResults('''An unknown error occured.  <p>
    #Please send mail to <a href=%s>%s</a> explaining 
    #exactly what you did to get this error.<p>''' % (mm_cfg.MAILMAN_OWNER,
    #                                                 mm_cfg.MAILMAN_OWNER))

        PrintResults("You have been unsubscribed.<p>")


    elif form.has_key("emailpw"):
            try:
                list.MailUserPassword(user)
                PrintResults("A reminder of your password "
                             "has been emailed to you.<p>")
            except Errors.MMBadUserError:
                PrintResults("Your password entry has not been found.  The"
                             "  list administrator is being notified.<p>")


    elif form.has_key("othersubs"):
        if not form.has_key('othersubspw'):
            PrintResults("You must specify your password.")
        else:
            try:
                list.ConfirmUserPassword(user, form['othersubspw'].value)
            except Errors.MMListNotReady:
                PrintResults("The list is currently not functional.")
            except Errors.MMNotAMemberError:
                PrintResults("You seem to no longer be a list member.")
            except Errors.MMBadPasswordError:
                PrintResults("Incorrect password.")
            except:
                PrintResults('''An unknown error occured.  <p>
Please send mail to <a href=%s>%s</a> explaining 
exactly what happened to provoke this error.<p>'''
                             % (mm_cfg.MAILMAN_OWNER, mm_cfg.MAILMAN_OWNER))

            doc.AddItem(htmlformat.Header(2,
                                          "List Subscriptions for %s on %s"
                                          % (user, list.host_name)))
            def optionslinks(l, user=user):
                if l.IsMember(user):
                    link = htmlformat.Link(l.GetAbsoluteOptionsURL(user),
                                           l.real_name)
                    return link
            all_links = filter(None, Utils.map_maillists(optionslinks))
            items = htmlformat.OrderedList()
            for i in all_links:
                items.AddItem(i)
            doc.AddItem(items)
            print doc.Format(bgcolor="#ffffff")

    elif form.has_key("changepw"):
        if (form.has_key('opw')
            and form.has_key('newpw')
            and form.has_key('confpw')):
            try:
                list.ConfirmUserPassword(user, form['opw'].value)
                list.ChangeUserPassword(user, 
                                        form['newpw'].value,
                                        form['confpw'].value)
            except Errors.MMListNotReady:
                PrintResults("The list is currently not functional.")
            except Errors.MMNotAMemberError:
                PrintResults("You seem to no longer be a list member.")
            except Errors.MMBadPasswordError:
                PrintResults("The old password you supplied was incorrect.")
            except Errors.MMPasswordsMustMatch:
                PrintResults("Passwords must match.")
            except:
                PrintResults('''An unknown error occured.  <p>
Please send mail to <a href=%s>%s</a> explaining 
exactly what happened to provoke this error.<p>'''
                             % (mm_cfg.MAILMAN_OWNER, mm_cfg.MAILMAN_OWNER))

            PrintResults("Your password has been changed.")
        else:
            PrintResults("You must specify your old password,"
                         " and your new password twice.")

    else:
        # If keys don't exist, set them to whatever they were. (essentially
        # a noop)
        if form.has_key("digest"):
            digest_value = eval(form["digest"].value)
        else:
            digest_value = list.GetUserOption(user, mm_cfg.Digests)
        if form.has_key("mime"):
            mime = eval(form["mime"].value)
        else:
            mime = list.GetUserOption(user, mm_cfg.DisableMime)
        if form.has_key("dontreceive"):
            dont_receive = eval(form["dontreceive"].value)
        else:
            dont_receive = list.GetUserOption(user, mm_cfg.DontReceiveOwnPosts)
        if form.has_key("ackposts"):
            ack_posts    = eval(form["ackposts"].value)
        else:
            ack_posts    = list.GetUserOption(user, mm_cfg.AcknowlegePosts)
        if form.has_key("disablemail"):
            disable_mail = eval(form["disablemail"].value)
        else:
            disable_mail = list.GetUserOption(user, mm_cfg.DisableDelivery)
        if form.has_key("conceal"):
            conceal = eval(form["conceal"].value)
        else:
            conceal = list.GetUserOption(user, mm_cfg.ConcealSubscription)

        if not form.has_key("digpw"):
            PrintResults("You must supply a password to change options.")
        try:
            list.ConfirmUserPassword(user, form['digpw'].value)
        except Errors.MMAlreadyDigested:
            pass
        except Errors.MMAlreadyUndigested:
            pass
        except Errors.MMMustDigestError:
            PrintResults("List only accepts digest members.")
        except Errors.MMCantDigestError:
            PrintResults("List doesn't accept digest members.")
        except Errors.MMNotAMemberError:
            PrintResults("%s isn't subscribed to this list."
                         % mail.GetSender())
        except Errors.MMListNotReady:
            PrintResults("List is not functional.")
        except Errors.MMNoSuchUserError:
            PrintResults("%s is not subscribed to this list."
                         % mail.GetSender())
        except Errors.MMBadPasswordError:
            PrintResults("You gave the wrong password.")
        except:
            PrintResults('''An unknown error occured.  <p>
            Please send mail to <a href="mailto:%(owner)s">%(owner)s</a>
            explaining exactly what happened to provoke this error.<p>'''
                         % {'owner': mm_cfg.MAILMAN_OWNER})

        list.SetUserOption(user, mm_cfg.DisableDelivery, disable_mail)
        list.SetUserOption(user, mm_cfg.DontReceiveOwnPosts, dont_receive)
        list.SetUserOption(user, mm_cfg.AcknowlegePosts, ack_posts)
        list.SetUserOption(user, mm_cfg.DisableMime, mime)
        try:
            list.SetUserDigest(user, digest_value)
        except (Errors.MMAlreadyDigested, Errors.MMAlreadyUndigested):
            pass
        list.SetUserOption(user, mm_cfg.ConcealSubscription, conceal)
        PrintResults("You have successfully set your options.")


    list.Unlock()
