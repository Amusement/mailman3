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


"""Mixin class with message delivery routines."""


import string, os, sys
import operator
import errno
import mm_cfg
import Errors
import Utils


# Note that the text templates for the various messages have been moved into
# the templates directory.

# We could abstract these two better...
class Deliverer:
    def AddNonStandardHeaders(self, headers, zaplist=None):
        # Add headers like Precedence: and other useful headers.  None of
        # these are standard and finding information on some of them are
        # fairly difficult.  Some are just common practice, and we'll add more 
        # here as they become necessary.  A good place to look is
        # http://www.dsv.su.se/~jpalme/ietf/jp-ietf-home.html
        #
        # None of these headers are added if they already exist
        d = {}
        if zaplist is None:
            zaplist = headers
        for h in zaplist:
            i = string.find(h, ':')
            key = string.lower(h[:6])
            d[key] = key
        if not d.has_key('x-mailman-version'):
            headers.append('X-Mailman-Version: %s\n' % mm_cfg.VERSION)
        # semi-controversial: some don't want this included at all, others
        # want the value to be `list'
        if not d.has_key('precedence'):
            headers.append('Precedence: bulk\n')
        # Other list related non-standard headers.  Defined in:
        #
        # Grant Neufeld and Joshua D. Baer: The Use of URLs as Meta-Syntax for
        # Core Mail List Commands and their Transport through Message Header
        # fields, draft-baer-listspec-01.txt, September 1997.
        #
        # Referenced in
        #
        # http://www.dsv.su.se/~jpalme/ietf/mail-attributes.html
        if not d.has_key('list-id'):
            headers.append('List-Id: %s\n' % self.GetListIdentifier())
        # These currently seem like overkill.  Maybe add them in later when
        # the draft gets closer to a standard
        # List-Subscribe
        # List-Unsubscribe
        # List-Owner
        # List-Help
        # List-Post
        # List-Archive
        # List-Software
        # X-Listserver

    # This method assumes the sender is list-admin if you don't give one.
    def SendTextToUser(self, subject, text, recipient, sender=None,
                       add_headers=None):
        if add_headers is None:
            add_headers = []
        if not sender:
            sender = self.GetAdminEmail()
        self.AddNonStandardHeaders(add_headers)
        Utils.SendTextToUser(subject, text, recipient, sender,
                             add_headers=add_headers)

    def DeliverToUser(self, msg, recipient):
        # This method assumes the sender is the one given by the message.
        add_headers = []
        self.AddNonStandardHeaders(add_headers, msg.headers)
        add_headers.append('Errors-To: %s\n' % self.GetAdminEmail())
        Utils.DeliverToUser(msg, recipient, add_headers=add_headers)

    def QuotePeriods(self, text):
	return string.join(string.split(text, '\n.\n'), '\n .\n')

    #
    # this function is used to deliver messages
    # that are sent to <listname>-admin.  the sender
    # is the envelope sender of the message, or if
    # that is not available, the sender via Message.GetSender()
    # the recipients arg is a list of the current list
    # owners.  We don't mess with adding list specific
    # headers on body modifications so that the address
    # will work just like a normal forwarding address
    #
    def DeliverToOwner(self, msg, recipients):
        if not (len(recipients)):
            return
        sender = msg.GetEnvelopeSender()
        if not sender:
            sender = msg.GetSender()
        if sender:
            if not '@' in sender:
                sender = sender + "@" + mm_cfg.DEFAULT_HOST_NAME
        else:
            sender = self.GetAdminEmail()
        cmd = "%s %s" % (mm_cfg.PYTHON,
                         os.path.join(mm_cfg.SCRIPTS_DIR, "deliver"))
        cmdproc = os.popen(cmd, 'w')

        cmdproc.write("%d\n" % self.num_spawns)
        cmdproc.write("%s\n" % sender)
        for r in recipients:
            # Mustn't send blank lines before end of recipients:
            if not r: continue
            cmdproc.write(r + "\n")
        cmdproc.write('\n')
        cmdproc.write(string.join(msg.headers, '') + "\n")
	cmdproc.write(self.QuotePeriods(msg.body))
	status = cmdproc.close()
        if status:
            self.LogMsg('deliverer',
                        'Non-zero exit status: %d\nCommand: %s'
                        (status >> 8), cmd)

    def DeliverToList(self, msg, recipients, 
                      header="", footer="", remove_to=0, tmpfile_prefix = ""):
	if not(len(recipients)):
	    return
        # Massage the headers.
        if remove_to:
            del msg['to']
            del msg['x-to']
	    msg.headers.append('To: %s\n' % self.GetListEmail())
	if self.reply_goes_to_list:
            del msg['reply-to']
            msg.headers.append('Reply-To: %s\n' % self.GetListEmail())
	msg.headers.append('Sender: %s\n' % self.GetAdminEmail())
	msg.headers.append('Errors-To: %s\n' % self.GetAdminEmail())
        self.AddNonStandardHeaders(msg.headers)
	msg.headers.append('X-BeenThere: %s\n' % self.GetListEmail())

        cmd = "%s %s" % (mm_cfg.PYTHON,
                         os.path.join(mm_cfg.SCRIPTS_DIR, "deliver"))
        cmdproc = os.popen(cmd, 'w')

        cmdproc.write("%d\n" % self.num_spawns)
        cmdproc.write("%s\n" % self.GetAdminEmail())
        for r in recipients:
            # Mustn't send blank lines before end of recipients:
            if not r: continue
            cmdproc.write(r + "\n")
        cmdproc.write("\n")             # Empty line for end of recipients.
        cmdproc.write(string.join(msg.headers, '') + "\n")
	if header:                      # The *body* header:
	    cmdproc.write(header + "\n")
	cmdproc.write(self.QuotePeriods(msg.body))
	if footer:
	    cmdproc.write(footer)

        status = cmdproc.close()
        if status:
            self.LogMsg('deliverer', 
                        'Non-zero exit status: %d\nCommand: %s',
                        (status >> 8), cmd)

    def SendPostAck(self, msg, sender):
	subject = msg.getheader('subject')
	if not subject:
	    subject = '[none]'
        else:
            sp = self.subject_prefix
            if (len(subject) > len(sp)
                and subject[0:len(sp)] == sp):
                # Trim off subject prefix
                subject = subject[len(sp):]
        # get the text from the template
        body = Utils.maketext(
            'postack.txt',
            {'subject'     : subject,
             'listname'    : self.real_name,
             'listinfo_url': self.GetAbsoluteScriptURL('listinfo'),
             })
	self.SendTextToUser('%s post acknowlegement' % self.real_name,
                            body, sender)

    def CreateSubscribeAck(self, name, password):
	if self.welcome_msg:
	    welcome = Utils.wrap(self.welcome_msg) + '\n'
	else:
	    welcome = ''
        if self.umbrella_list:
            umbrella = Utils.wrap(
                "(Since this is a list of mailing lists, administrative"
                " notices like the password reminder will be sent to"
                " your membership administrative address, %s.)\n"
                % self.GetMemberAdminEmail(name))
        else:
            umbrella = ''
        # get the text from the template
        body = Utils.maketext(
            'subscribeack.txt',
            {'real_name'   : self.real_name,
             'host_name'   : self.host_name,
             'welcome'     : welcome,
             'umbrella'    : umbrella,
             'emailaddr'   : self.GetListEmail(),
             'listinfo_url': self.GetAbsoluteScriptURL('listinfo'),
             'optionsurl'  : self.GetAbsoluteOptionsURL(name),
             'password'    : password,
             })
        return body


    def SendSubscribeAck(self, name, password, digest):
        if not self.send_welcome_msg:
	    return
	if digest:
	    digest_mode = '(Digest mode)'
	else:
	    digest_mode = ''
        self.SendTextToUser(subject = 'Welcome To "%s"! %s' % (self.real_name, 
							       digest_mode),
			    recipient = self.GetMemberAdminEmail(name),
			    text = self.CreateSubscribeAck(name, password))

    def SendUnsubscribeAck(self, name):
	self.SendTextToUser(subject = 'Unsubscribed from "%s"\n' % 
			               self.real_name,
			    recipient = self.GetMemberAdminEmail(name),
			    text = Utils.wrap(self.goodbye_msg))

    def MailUserPassword(self, user):
        listfullname = '%s@%s' % (self.real_name, self.host_name)
        ok = 1
        # find the case-preserved version of the user's address
        cpuser = self.members.get(self.FindUser(user))
        if cpuser <> 0:
            user = cpuser
        if user and self.passwords.has_key(user):
            recipient = self.GetMemberAdminEmail(user)
            subj = '%s maillist reminder\n' % listfullname
            # get the text from the template
            text = Utils.maketext(
                'userpass.txt',
                {'user'       : user,
                 'listname'   : self.real_name,
                 'password'   : self.passwords[user],
                 'options_url': self.GetAbsoluteOptionsURL(user),
                 'requestaddr': self.GetRequestEmail(),
                 'adminaddr'  : self.GetAdminEmail(),
                 })
        else:
            ok = 0
            recipient = self.GetAdminEmail()
            subj = '%s user %s missing password!\n' % (listfullname, user)
            text = Utils.maketext(
                'nopass.txt',
                {'username'     : `user`,
                 'internal_name': self._internal_name,
                 })
	self.SendTextToUser(subject = subj,
			    recipient = recipient,
                            text = text,
                            add_headers=["Errors-To: %s"
                                         % self.GetAdminEmail(),
                                         "X-No-Archive: yes",
                                         "Precedence: bulk"])
        if not ok:
             raise Errors.MMBadUserError
