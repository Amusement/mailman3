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

'''Mixin class for gatewaying mail to news, and news to mail.'''

# All these things should already be imported, so might as well do them here
# at the top level
import os
import string
import re
import time
import mm_cfg

# XXX: Bogus, but might as we do it `legally'
QuickEscape = 'QuickEscape'

class GatewayManager:
    def InitVars(self):
        # Configurable
        self.nntp_host        = ''
        self.linked_newsgroup = ''
        self.gateway_to_news  = 0
        self.gateway_to_mail  = 0

    def GetConfigInfo(self):
        return [
            'Mail-to-News and News-to-Mail gateway services.',
            ('nntp_host', mm_cfg.String, 50, 0,
             'The Internet address of the machine your News server '
             'is running on.',
             'The News server is not part of Mailman proper.  You have to '
             'already have access to a NNTP server, and that NNTP server '
             'has to recognize the machine this mailing list runs on as '
             'a machine capable of reading and posting news.'),
            ('linked_newsgroup', mm_cfg.String, 50, 0,
              'The name of the Usenet group to gateway to and/or from.'),
            ('gateway_to_news',  mm_cfg.Toggle, ('No', 'Yes'), 0,
             'Should posts to the mailing list be resent to the '
             'newsgroup?'),
            ('gateway_to_mail',  mm_cfg.Toggle, ('No', 'Yes'), 0,
             'Should newsgroup posts not sent from the list be resent '
             'to the list?')
            ]

    # This function is called from cron/gate_news and assumes the following
    # have been asserted:
    # - that the list gates from news to mail
    # - that list has an nntp_host and linked_newsgroup
    # - that the connection has been opened
    # - that this method is run in a child process
    # - that the watermark is non-zero
    def PollNewsGroup(self, conn, wm, first, last):
        import nntplib
        # NEWNEWS is not portable and has synchronization issues...  Use a
        # watermark system instead.
        for num in range(max(wm+1, first), last+1):
            try:
                headers = conn.head(`num`)[3]
                found_to = 0
                for header in headers:
                    i = string.find(header, ':')
                    if i > 0 and string.lower(header[:i]) == 'to':
                        found_to = 1
                    if header[:i] <> 'X-BeenThere':
                        continue
                    if header[i:] == ': %s' % self.GetListEmail():
                        raise QuickEscape
                body = conn.body(`num`)[3]
                # Create the pipe to the Mail posting script.  Note that it is
                # not installed executable, so we'll tack on the path to
                # Python we discovered when we configured Mailman
                cmd = '%s %s %s nonews' % (
                    mm_cfg.PYTHON,
                    os.path.join(mm_cfg.SCRIPTS_DIR, 'post'),
                    self._internal_name)
                file = os.popen(cmd, 'w')
                file.write(string.join(headers,'\n'))
                # If there wasn't already a TO: header, add one.
                if not found_to:
                    file.write("\nTo: %s" % self.GetListEmail())
                file.write('\n\n')
                file.write(string.join(body,'\n'))
                file.write('\n')
                file.close()
            except nntplib.error_temp:
                pass # Probably canceled, etc...        
            except QuickEscape:
                pass # We gated this TO news, don't repost it!
                                
    def SendMailToNewsGroup(self, mail_msg):
        import Message
        error = []
        if not self.linked_newsgroup:
            error.append('no newsgroup')
        if not self.nntp_host:
            error.append('no NNTP host')
        if error:
            msg = 'NNTP gateway improperly configured: ' + \
                  string.join(error, ', ')
            self.LogMsg('error', msg)
            return
        try:
            if self.tmp_prevent_gate:
                return
        except AttributeError:
            pass # Wasn't remailed by the news gater then.  Let it through.
        # Fork in case the nntp connection hangs.
        if not os.fork():
            # child
            import nntplib
            # Now make the news message...
            msg = Message.NewsMessage(mail_msg)
            # Ok, munge headers, etc.
            subj = msg.getheader('subject')
            if subj:
                subjpref = self.subject_prefix
                if not re.match('(re:? *)?' + re.escape(subjpref), subj, re.I):
                    msg.SetHeader('Subject', '%s%s' % (subjpref, subj))
            else:
                msg.SetHeader('Subject', '%s(no subject)' % prefix)
            if self.reply_goes_to_list:
                del msg['reply-to']
                msg.headers.append('Reply-To: %s\n' % self.GetListEmail())
            # if we already have a sender header, don't add another one; use
            # the header that's already there.
            if not msg.getheader('sender'):
                msg.headers.append('Sender: %s\n' % self.GetAdminEmail())
            msg.headers.append('Errors-To: %s\n' % self.GetAdminEmail())
            msg.headers.append('X-BeenThere: %s\n' % self.GetListEmail())
            ngheader = msg.getheader('newsgroups')
            if ngheader is not None:
                # see if the Newsgroups: header already contains our
                # linked_newsgroup.  If so, don't add it again.  If not,
                # append our linked_newsgroup to the end of the header list
                ngroups = map(string.strip, string.split(ngheader, ','))
                if self.linked_newsgroup not in ngroups:
                    ngroups.append(self.linked_newsgroup)
                    ngheader = string.join(ngroups, ',')
                    # subtitute our new header for the old one.  XXX Message
                    # class should have a __setitem__()
                    del msg['newsgroups']
                    msg.headers.append('Newsgroups: %s\n' % ngroups)
            else:
                # Newsgroups: isn't in the message
                msg.headers.append('Newsgroups: %s\n' % self.linked_newsgroup)
            # Note: Need to be sure 2 messages aren't ever sent to the same
            # list in the same process, since message ID's need to be unique.
            # Could make the ID be mm.listname.postnum instead if that happens
            if msg.getheader('Message-ID') is None:
                msg.headers.append('Message-ID: <mm.%s.%s@%s>\n' %
                                   (time.time(), os.getpid(), self.host_name))
            if msg.getheader('Lines') is None:
                msg.headers.append('Lines: %s\n' % 
                                   len(string.split(msg.body,"\n")))
            del msg['received']

            # TBD: Gross hack to ensure that we have only one
            # content-transfer-encoding header.  More than one barfs NNTP.  I
            # don't know why we sometimes have more than one such header, and
            # it probably isn't correct to take the value of just the first
            # one.  What if there are conflicting headers???
            #
            # This relies on the new interface for getaddrlist() returning
            # values for all present headers, and the fact that the legal
            # values are usually not parseable as addresses.  Yes this is
            # another bogosity.
            cteheaders = msg.getaddrlist('content-transfer-encoding')
            if cteheaders:
                ctetuple = cteheaders[0]
                ctevalue = ctetuple[1]
                del msg['content-transfer-encoding']
                msg['content-transfer-encoding'] = ctevalue

            # NNTP is strict about spaces after the colon in headers.
            for n in range(len(msg.headers)):
                line = msg.headers[n]
                i = string.find(line,":")
                if i <> -1 and line[i+1] <> ' ':
                    msg.headers[n] = line[:i+1] + ' ' + line[i+1:]
            con = nntplib.NNTP(self.nntp_host)
            con.post(msg)
            con.quit()
            os._exit(0)
