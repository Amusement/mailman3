# Notice that unlike majordomo, message headers/footers aren't going
# on until After the post has been added to the digest / archive.  I
# tried putting a footer on the bottom of each message on a majordomo
# list once, but it sucked hard, because you'd see the footer 100
# times in each digest.

try:
    import mm_cfg
except ImportError:
    raise RuntimeError, ('missing mm_cfg - has mm_cfg_dist been configured '
			 'for the site?')

import sys, os, marshal, string, posixfile, time
import re
import mm_utils, mm_err

from mm_admin import ListAdmin
from mm_deliver import Deliverer
from mm_mailcmd import MailCommandHandler 
from mm_html import HTMLFormatter 
from mm_archive import Archiver
from mm_digest import Digester
from mm_security import SecurityManager
from mm_bouncer import Bouncer

# Expression for generally matching the "Re: " prefix in message subject lines:
SUBJ_REGARDS_PREFIX = "[rR][eE][: ]*[ ]*"

# Note: 
# an _ in front of a member variable for the MailList class indicates
# a variable that does not save when we marshal our state.

# Use mixins here just to avoid having any one chunk be too large.

class MailList(MailCommandHandler, HTMLFormatter, Deliverer, ListAdmin, 
	       Archiver, Digester, SecurityManager, Bouncer):
    def __init__(self, name=None):
	MailCommandHandler.__init__(self)
	self._internal_name = name
	self._ready = 0
	self._log_files = {}		# 'class': log_file_obj
	if name:
	    if name not in list_names():
		raise mm_err.MMUnknownListError, 'list not found'
	    self._full_path = os.path.join(mm_cfg.LIST_DATA_DIR, name)
	    # Load in the default values so that old data files aren't
	    # hosed by new versions of the program.
	    self.InitVars(name)
	    self.Load()

    def GetAdminEmail(self):
	return '%s-admin@%s' % (self._internal_name, self.host_name)

    def GetRequestEmail(self):
	return '%s-request@%s' % (self._internal_name, self.host_name)

    def GetListEmail(self):
	return '%s@%s' % (self._internal_name, self.host_name)

    def GetScriptURL(self, script_name):
	return os.path.join(self.web_page_url, '%s/%s' % 
			    (script_name, self._internal_name))


    def GetUserOption(self, user, option):
	if option == mm_cfg.Digests:
	    return user in self.digest_members
	if not self.user_options.has_key(user):
	    return 0
	return not not self.user_options[user] & option

    def SetUserOption(self, user, option, value):
	if not self.user_options.has_key(user):
	    self.user_options[user] = 0
	if value:
	    self.user_options[user] = self.user_options[user] | option
	else:
	    self.user_options[user] = self.user_options[user] & ~(option)
	if not self.user_options[user]:
	    del self.user_options[user]
	self.Save()

    def FindUser(self, email):
	matches = mm_utils.FindMatchingAddresses(email,
						 (self.members
						  + self.digest_members))
	if not matches or not len(matches):
	    return None
	return matches[0]

    def InitVars(self, name='', admin='', crypted_password=''):
	# Non-configurable list info 
	self._internal_name = name
	self._lock_file = None
	self._mime_separator = '__--__--' 

	# Must save this state, even though it isn't configurable
	self.volume = 1
	self.members = [] # self.digest_members is inited in mm_digest
	self.data_version = mm_cfg.VERSION
	self.last_post_time = 0
	
	self.post_id = 1.  # A float so it never has a chance to overflow.
	self.user_options = {}

	# This stuff is configurable
	self.filter_prog = mm_cfg.DEFAULT_FILTER_PROG
	self.dont_respond_to_post_requests = 0
	self.num_spawns = mm_cfg.DEFAULT_NUM_SPAWNS
	self.advertised = mm_cfg.DEFAULT_LIST_ADVERTISED
	self.max_num_recipients = mm_cfg.DEFAULT_MAX_NUM_RECIPIENTS
	self.max_message_size = mm_cfg.DEFAULT_MAX_MESSAGE_SIZE
	self.web_page_url = mm_cfg.DEFAULT_URL   
	self.owner = [admin]
	self.reply_goes_to_list = mm_cfg.DEFAULT_REPLY_GOES_TO_LIST
	self.posters = []
	self.bad_posters = []
	self.moderated = mm_cfg.DEFAULT_MODERATED
	self.require_explicit_destination = \
		mm_cfg.DEFAULT_REQUIRE_EXPLICIT_DESTINATION
	self.bounce_matching_headers = \
		mm_cfg.DEFAULT_BOUNCE_MATCHING_HEADERS
	self.real_name = '%s%s' % (string.upper(self._internal_name[0]), 
				   self._internal_name[1:])
	self.description = ''
	self.info = ''
	self.welcome_msg = None
	self.goodbye_msg = None
	self.auto_subscribe = mm_cfg.DEFAULT_AUTO_SUBSCRIBE
	self.closed = mm_cfg.DEFAULT_CLOSED
	self.obscure_addresses = mm_cfg.DEFAULT_OBSCURE_ADDRESSES
	self.member_posting_only = mm_cfg.DEFAULT_MEMBER_POSTING_ONLY
	self.web_subscribe_requires_confirmation = \
		mm_cfg.DEFAULT_WEB_SUBSCRIBE_REQUIRES_CONFIRMATION
	self.host_name = mm_cfg.DEFAULT_HOST_NAME

	# Analogs to these are initted in Digester.InitVars
	self.nondigestable = mm_cfg.DEFAULT_NONDIGESTABLE

	Digester.InitVars(self) # has configurable stuff
	SecurityManager.InitVars(self, crypted_password)
	HTMLFormatter.InitVars(self)
	Archiver.InitVars(self) # has configurable stuff
	ListAdmin.InitVars(self)
	Bouncer.InitVars(self)

	# These need to come near the bottom because they're dependent on
	# other settings.
	self.subject_prefix = mm_cfg.DEFAULT_SUBJECT_PREFIX % self.__dict__
	self.msg_header = mm_cfg.DEFAULT_MSG_HEADER
	self.msg_footer = mm_cfg.DEFAULT_MSG_FOOTER

    def GetConfigInfo(self):
	config_info = {}
	config_info['digest'] = Digester.GetConfigInfo(self)
	config_info['archive'] = Archiver.GetConfigInfo(self)

	config_info['general'] = [
	    ('real_name', mm_cfg.String, 50, 0,
	     'The public name of this list'),

	    ('owner', mm_cfg.EmailList, (3,30), 0,
	     'The list admin\'s email address '
	     '(or addresses if more than 1 admin)'),

	    ('description', mm_cfg.String, 50, 0,
	     'A one sentence description of this list'),

	    ('info', mm_cfg.Text, (7, 65), 0, 
	     'An informational paragraph about the list'),

	    ('subject_prefix', mm_cfg.String, 10, 0,
	     'Subject line prefix - to distinguish list messages in '
	     'mailbox summaries.'),

	    ('advertised', mm_cfg.Radio, ('No', 'Yes'), 0,
	     'Advertise this list when people ask what lists are on '
	     'this machine?'),

	    ('welcome_msg', mm_cfg.Text, (4, 65), 0,
	     'List specific portion of welcome sent to new subscribers'),

	    ('goodbye_msg', mm_cfg.Text, (4, 65), 0,
	     'Text sent to people leaving the list.'
	     'If empty, no unsubscribe message will be sent.'),

	    ('reply_goes_to_list', mm_cfg.Radio, ('Poster', 'List'), 0,
	     'Are replies to a post directed to poster or the list?'),

	    ('moderated', mm_cfg.Radio, ('No', 'Yes'), 0,
	     'Anti-spam: Must posts be approved by a moderator?'),

 	    ('require_explicit_destination', mm_cfg.Radio, ('No', 'Yes'), 0,
 	     'Anti-spam: Must posts have list named in destination (to, cc) '
	     '  field?'),

	    # Note that leading whitespace in the matchexp is trimmed - you can
	    # defeat that by, eg, containing it in gratuitous square brackets.
 	    ('bounce_matching_headers', mm_cfg.Text, ('6', '60'), 0,
 	     'Anti-spam: Bounce posts with header containing regexp match;'
	     ' divide header name and (case-insensitive) match regexp'
	     ' with colon'),

	    ('posters', mm_cfg.EmailList, (5, 30), 1,
	     'Email addresses whose posts are auto-approved '
	     '(adding anyone to this list will make this a moderated list)'),

	    ('bad_posters', mm_cfg.EmailList, (5, 30), 1,
	     'Anti-spam: Email addresses whose posts should always be '
	     'bounced until you approve them, no matter what other options '
	     'you have set'),

	    ('closed', mm_cfg.Radio, ('Anyone', 'List members', 'No one'), 0,
	     'Anti-spam: Who can view subscription list'),

	    ('obscure_addresses', mm_cfg.Radio, ('No', 'Yes'), 0,
	     "Anti-spam: Show member addrs so they're not directly "
	     ' recognizable as email addrs?'),

	    ('member_posting_only', mm_cfg.Radio, ('No', 'Yes'), 0,
	     'Anti-spam: Only list members can send mail to the list '
	     'without approval'),

	    ('auto_subscribe', mm_cfg.Radio, ('No', 'Yes'), 0,
	     'Subscribes are done automatically w/o admins approval'),

	    # If auto_subscribe is off, this is ignored, essentially.
	    ('web_subscribe_requires_confirmation', mm_cfg.Radio,
	     ('None', 'Requestor confirms via email', 'Admin approves'), 0,
	     'Extra confirmation for off-the-web subscribes'),

	    ('dont_respond_to_post_requests', mm_cfg.Radio, ('Yes', 'No'), 0,
	     'Send mail to poster when their mail is held awaiting approval?'),

	    ('filter_prog', mm_cfg.String, 40, 0,
	     'Program to pass text through before processing, if any? '
	     '(Useful, eg, for signature auto-stripping, etc...)'),

	    ('max_num_recipients', mm_cfg.Number, 3, 0, 
	     'Anti-spam: Max number of TO and CC recipients before admin '
	     'approval is required.  Use 0 for no limit.'),

	    ('max_message_size', mm_cfg.Number, 3, 0,
	     'Maximum length in Kb of a message body. '
	     'Use 0 for no limit.'),

	    ('num_spawns', mm_cfg.Number, 3, 0,
	     'Number of outgoing connections to open at once '
	     '(Expert users only)'),

	    ('host_name', mm_cfg.Host, 50, 0, 'Host name this list prefers'),

	    ('web_page_url', mm_cfg.String, 50, 0,
	     'Base URL for Mailman web interface')
	    ]

	config_info['nondigest'] = [
	    ('nondigestable', mm_cfg.Toggle, ('No', 'Yes'), 1,
	     'Can subscribers choose to receive mail singly, '
	     'rather than in digests?'),

	    ('msg_header', mm_cfg.Text, (4, 65), 0,
	     'Header added to mail sent to regular list members'),
	    # Note: Can have "%(field)s" format entries which will be
	    # resolved against list object __dict__ at message send time.
	    # Need to list some of the useful fields for the long-help.
	    
	    ('msg_footer', mm_cfg.Text, (4, 65), 0,
	     'Footer added to mail sent to regular list members'),
	    # See msg_header note.
	    ]

	config_info['bounce'] = Bouncer.GetConfigInfo(self)
	return config_info

    def Create(self, name, admin, crypted_password):
	if name in list_names():
	    raise ValueError, 'List %s already exists.' % name
	else:
	    mm_utils.MakeDirTree(os.path.join(mm_cfg.LIST_DATA_DIR, name))
	self._full_path = os.path.join(mm_cfg.LIST_DATA_DIR, name)
	self._internal_name = name
	self.Lock()
	self.InitVars(name, admin, crypted_password)
	self._ready = 1
	self.InitTemplates()
	self.Save()
	self.CreateFiles()

    def CreateFiles(self):
	# Touch these files so they have the right dir perms no matter what.
	# A "just-in-case" thing.  This shouldn't have to be here.
	ou = os.umask(002)
	try:
	    import mm_archive
	    open(os.path.join(self._full_path,
			      mm_archive.ARCHIVE_PENDING), "a+").close()
	    open(os.path.join(self._full_path,
			      mm_archive.ARCHIVE_RETAIN), "a+").close()
	    open(os.path.join(mm_cfg.LOCK_DIR, '%s.lock' % 
			      self._internal_name), 'a+').close()
	    open(os.path.join(self._full_path, "next-digest"), "a+").close()
	    open(os.path.join(self._full_path, "next-digest-topics"),
		 "a+").close()
	finally:
	    os.umask(ou)
	
    def Save(self):
	# If more than one client is manipulating the database at once, we're
	# pretty hosed.  That's a good reason to make this a daemon not a
	# program.
	self.IsListInitialized()
	ou = os.umask(002)
	try:
	    file = open(os.path.join(self._full_path, 'config.db'), 'w')
	finally:
	    os.umask(ou)
	dict = {}
	for (key, value) in self.__dict__.items():
	    if key[0] <> '_':
		dict[key] = value
	marshal.dump(dict, file)
	file.close()

    def Load(self):
	self.Lock()
	try:
	    file = open(os.path.join(self._full_path, 'config.db'), 'r')
	except IOError:
	    raise mm_cfg.MMBadListError, 'Failed to access config info'
	try:
	    dict = marshal.load(file)
	except (EOFError, ValueError, TypeError):
	    raise mm_cfg.MMBadListError, 'Failed to unmarshal config info'
	for (key, value) in dict.items():
	    setattr(self, key, value)
	file.close()
	self._ready = 1
	self.CheckVersion()

    def LogMsg(self, kind, msg, *args):
	"""Append a message to the log file for messages of specified kind."""
	# For want of a better fallback,  we use sys.stderr if we can't get
	# a log file.  We need a better way to warn of failed log access...
	if self._log_files.has_key(kind):
	    logf = self._log_files[kind]
	else:
	    logfn = os.path.join(mm_cfg.LOG_DIR, kind)
	    ou = os.umask(002)
	    try:
		try:
		    logf = self._log_files[kind] = open(logfn, 'a+')
		except IOError, diag:
		    logf = self._log_files[kind] = sys.stderr
		    self._log_files['config'] = sys.stderr
		    self.LogMsg('config',
				"Access failed to log file %s, %s, "
				"using sys.stderr.",
				logfn, `str(diag)`)
	    finally:
		os.umask(ou)
	stamp = time.strftime("%b %d %H:%M:%S %Y",
			      time.localtime(time.time()))
	logf.write("%s %s\n" % (stamp, msg % args))
	if hasattr(logf, 'flush'):
	    logf.flush()

    def CheckVersion(self):
	if self.data_version == mm_cfg.VERSION:
	    return
	else:
	    pass  # This function is just here to ease upgrades in the future.

	self.data_version = mm_cfg.VERSION
	self.Save()

    def IsListInitialized(self):
	if not self._ready:
	    raise mm_err.MMListNotReady

    def AddMember(self, name, password, digest=0, web_subscribe=0):
	self.IsListInitialized()
	# Remove spaces... it's a common thing for people to add...
	name = string.join(string.split(string.lower(name)), '')
	# Validate the e-mail address to some degree.
	if not mm_utils.ValidEmail(name):
	    raise mm_err.MMBadEmailError
	if self.IsMember(name):
	    raise mm_err.MMAlreadyAMember
	if not digest:
	    if not self.nondigestable:
		raise mm_err.MMMustDigestError
	    if (self.auto_subscribe and web_subscribe and 
		self.web_subscribe_requires_confirmation):
		if self.web_subscribe_requires_confirmation == 1:
		    raise mm_err.MMWebSubscribeRequiresConfirmation
		else:
		    self.AddRequest('add_member', digest, name, password)
	    elif self.auto_subscribe:
		self.ApprovedAddMember(name, password, digest)
	    else:
		self.AddRequest('add_member', digest, name, password)
	else: 
	    if not self.digestable:
		raise mm_err.MMCantDigestError
	    if self.auto_subscribe:
		self.ApprovedAddMember(name, password, digest)
	    else:
		self.AddRequest('add_member', digest, name, password)

    def ApprovedAddMember(self, name, password, digest):
	if self.IsMember(name):
	    raise mm_err.MMAlreadyAMember
	if digest:
	    self.digest_members.append(name)
	    self.digest_members.sort()
	else:
	    self.members.append(name)
	    self.members.sort()
	self.passwords[name] = password
	self.SendSubscribeAck(name, password, digest)
	self.Save()

    def DeleteMember(self, name):
	self.IsListInitialized()
# FindMatchingAddresses *should* never return more than 1 address.
# However, should log this, just to make sure.
	aliases = mm_utils.FindMatchingAddresses(name, self.members + 
						 self.digest_members)
	if not len(aliases):
	    raise mm_err.MMNoSuchUserError

	def DoActualRemoval(alias, me=self):
	    try:
		del me.passwords[alias]
	    except KeyError: 
		pass
	    try:
		me.members.remove(alias)
	    except ValueError:
		pass
	    try:
		me.digest_members.remove(alias)
	    except ValueError:
		pass

	map(DoActualRemoval, aliases)
	if self.goodbye_msg and len(self.goodbye_msg):
	    self.SendUnsubscribeAck(name)
	self.ClearBounceInfo(name)
	self.Save()

    def IsMember(self, address):
	return len(mm_utils.FindMatchingAddresses(address, self.members +
						    self.digest_members))

    def HasExplicitDest(self, msg):
	"True if list name is explicitly included among the to or cc addrs."
	# Note that host can be different!  This allows, eg, for relaying
	# from remote lists that have the same name.  Still stringent, but
	# offers a way to provide for remote exploders.
	lowname = string.lower(self.real_name)
	for recip in msg.getaddrlist('to') + msg.getaddrlist('cc'):
	    if lowname == string.lower(string.split(recip[1], '@')[0]):
		return 1
	return 0

    def parse_matching_header_opt(self):
	"""Return a list of triples [(field name, regex, and line), ...]."""
	# Note that leading whitespace in the matchexp is trimmed - you can
	# defeat that by, eg, containing it in gratuitous square brackets.
	mho = self.bounce_matching_headers
	all = []
	for line in string.split(mho, '\n'):
	    if not string.strip(line):
		# Skip blank lines.
		continue
	    try:
		h, e = re.split(":[ 	]*", line)
		all.append((h, e, line))
	    except ValueError:
		raise mm_err.MMBadConfigError, line
	return all


    def HasMatchingHeader(self, msg):
	"""True if named header field (case-insensitive matches regexp.

	Case insensitive.

	Returns constraint line which matches or empty string for no
	matches."""
	
	try:
	    pairs = self.parse_matching_header_opt()
	except mm_err.MMBadConfigError, line:
	    # Whoops - some bad data got by:
	    self.LogMsg("config", "%s - "
			"bad bounce_matching_header line %s"
			% (self.real_name, `line`))

	for field, matchexp, line in pairs:
	    fragments = msg.getallmatchingheaders(field)
	    subjs = []
	    l = len(field)
	    for f in fragments:
		# Consolidate header lines, stripping header name & whitespace.
		if (len(f) > l
		    and f[l] == ":"
		    and string.lower(field) == string.lower(f[0:l])):
		    # Non-continuation line - trim header name:
		    subjs.append(f[l+1:])
		elif not subjs:
		    # Whoops - non-continuation that matches?
		    subjs.append(f)
		else:
		    # Continuation line.
		    subjs[-1] = subjs[-1] + f
	    for s in subjs:
		if re.search(matchexp, s, re.I):
		    return line
	return 0

#msg should be an IncomingMessage object.
    def Post(self, msg, approved=0):
##	print "Post in"			# DEBUG
	self.IsListInitialized()
	sender = msg.GetSender()
	# If it's the admin, which we know by the approved variable,
	# we can skip a large number of checks.
	if not approved:
##	    print "Post checking..."			# DEBUG
	    if len(self.bad_posters):
		addrs = mm_utils.FindMatchingAddresses(sender,
						       self.bad_posters)
		if len(addrs):
		    self.AddRequest('post', mm_utils.SnarfMessage(msg),
				'Post from an untrusted origin.')
	    if len(self.posters):
		addrs = mm_utils.FindMatchingAddresses(sender, self.posters)
		if not len(addrs):
		    self.AddRequest('post', mm_utils.SnarfMessage(msg),
				    'Only approved posters may post without '
				    'moderator approval.')
	    elif self.moderated:
		self.AddRequest('post', mm_utils.SnarfMessage(msg),
				'Moderated list.',
				# Add an extra arg to avoid generating an
				# error mail.
				1)
	    if self.member_posting_only and not self.IsMember(sender):
		self.AddRequest('post', mm_utils.SnarfMessage(msg),
				'Postings from member addresses only.')
	    if self.max_num_recipients > 0:
		recips = []
		toheader = msg.getheader('to')
		if toheader:
		    recips = recips + string.split(toheader, ',')
		ccheader = msg.getheader('cc')
		if ccheader:
		    recips = recips + string.split(ccheader, ',')
		if len(recips) > self.max_num_recipients:
		    self.AddRequest('post', mm_utils.SnarfMessage(msg),
				    'Too many recipients.')
 	    if (self.require_explicit_destination and
 		  not self.HasExplicitDest(msg)):
 		self.AddRequest('post', mm_utils.SnarfMessage(msg),
 				'Missing explicit list destination.')
 	    if self.bounce_matching_headers:
		triggered = self.HasMatchingHeader(msg)
		if triggered:
		    # Darn - can't include the matching line for the admin
		    # message because the info would also go to the sender.
		    self.AddRequest('post', mm_utils.SnarfMessage(msg),
				    'Suspicious header content.')
	    if self.max_message_size > 0:
		if len(msg.body)/1024. > self.max_message_size:
		    self.AddRequest('post', mm_utils.SnarfMessage(msg),
				    'Message body too long (>%dk)' % 
				    self.max_message_size)
	if self.digestable:
	    self.SaveForDigest(msg)
	if self.archive:
	    self.ArchiveMail(msg)
	# Prepend the subject_prefix to the subject line.
	subj = msg.getheader('subject')
	prefix = self.subject_prefix
	if prefix:
	    prefix = prefix + ' '
	if not subj:
	    msg.SetHeader('Subject', '%s(no subject)' % prefix)
	elif not re.match("(re:? *)?" + re.escape(self.subject_prefix),
			  subj, re.I):
	    msg.SetHeader('Subject', '%s%s' % (prefix, subj))

	dont_send_to_sender = 0
	ack_post = 0
	# Try to get the address the list thinks this sender is
	sender = self.FindUser(msg.GetSender())
	if sender:
	    if self.GetUserOption(sender, mm_cfg.DontReceiveOwnPosts):
		dont_send_to_sender = 1
	    if self.GetUserOption(sender, mm_cfg.AcknowlegePosts):
		ack_post = 1
	# Deliver the mail.
##	print "post about to deliver"	# DEBUG
	recipients = self.members[:] 
	if dont_send_to_sender:
	    recipients.remove(sender)
	def DeliveryEnabled(x, s=self, v=mm_cfg.DisableDelivery):
	    return not s.GetUserOption(x, v)
	recipients = filter(DeliveryEnabled, recipients)
##	print "post delivering"	# DEBUG
	self.DeliverToList(msg, recipients,
			   self.msg_header % self.__dict__,
			   self.msg_footer % self.__dict__)
	if ack_post:
	    self.SendPostAck(msg, sender)
	self.last_post_time = time.time()
	self.post_id = self.post_id + 1
##	print "post done"	# DEBUG
	self.Save()

    def Lock(self):
	try:
	    if self._lock_file:
		return
	except AttributeError:
	    return
	ou = os.umask(0)
	try:
	    self._lock_file = posixfile.open(
		os.path.join(mm_cfg.LOCK_DIR, '%s.lock' % self._internal_name),
		'a+')
	finally:
	    os.umask(ou)
	self._lock_file.lock('w|', 1)
    
    def Unlock(self):
	self._lock_file.lock('u')
	self._lock_file.close()
	self._lock_file = None

    def __repr__(self):
	if self._lock_file: un = ""
	else: un = "un"
	return ("<%s.%s %slocked instance at %s>"
		% (self.__module__, self.__class__.__name__,
		   un, hex(id(self))[2:]))

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
