"""
module for handling pending subscriptions
"""

import os 
import sys
import posixfile
import marshal
import time
import whrandom
import mm_cfg
import flock

DB_PATH = os.path.join(mm_cfg.DATA_DIR,"pending_subscriptions.db")
LOCK_PATH = os.path.join(mm_cfg.LOCK_DIR, "pending_subscriptions.lock")


VERIFY_FMT = """\
	%(listname)s -- confirmation of subscription -- request %(cookie)s

You or someone (%(requestor)s) has requested that your email
address (%(email)s) be subscribed to the %(listname)s mailling
list at %(listaddress)s.  If you wish to fulfill this request,
please simply reply to this message, or mail %(request_addr)s
with the following line, and only the following line in the
message body: 

confirm %(cookie)s

If you do not wish to subscribe to this list, please simply ignore  
or delete this message.
"""

# ' icky emacs font lock thing


def get_pending():
    " returns a dict containing pending information"
    try:
        fp = open(DB_PATH,"r" )
    except IOError:
        return {}
    dict = marshal.load(fp)
    return dict


def gencookie(p=None):
    if p is None:
        p = get_pending()
    while 1:
        newcookie = int(whrandom.random() * 1000000)
        if p.has_key(newcookie) or newcookie < 100000:
            continue
        return newcookie

def set_pending(p):
    lock_file = flock.FileLock(LOCK_PATH)
    lock_file.lock()
    fp = open(DB_PATH, "w") 
    marshal.dump(p, fp) 
    fp.close() 
    lock_file.unlock()

def add2pending(email_addr, password, digest, cookie): 
    ts = int(time.time())
    processed = 0
    p = get_pending()
    p[cookie] = (email_addr, password, digest,  ts)
    set_pending(p)


