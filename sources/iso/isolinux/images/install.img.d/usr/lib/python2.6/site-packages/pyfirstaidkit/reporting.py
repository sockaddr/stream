# First Aid Kit - diagnostic and repair tool for Linux
# Copyright (C) 2007 Martin Sivak <msivak@redhat.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import Queue
import logging
import thread
import weakref
import re
import time

from errors import *

Logger = logging.getLogger("firstaidkit")

#semantics values
#first the "task" levels for START and STOP
FIRSTAIDKIT = 100
TASKER = 90
PLUGINSYSTEM = 80
PLUGIN = 70
FLOW = 60
TASK = 50

#semantics
START = 0
STOP = 1
PROGRESS = 2
INFO = 3
ALERT = 4
EXCEPTION = 5
TABLE = 6 #types for arbitrary table-like organized iterables
TREE = 7  #nested iterables organized as tree
ISSUE = 8  #New issue object was created or changed
CHOICE_QUESTION = 990 #a Question object, "reply" specifies a Reports object
TEXT_QUESTION = 991
FILENAME_QUESTION = 992
PASSWORD_QUESTION = 993
CONFIG_QUESTION = 994
ANSWER = 999 #Data sent in reply to a *_QUESTION
END = 1000 #End of operations, final message

class Origin(object):
    """Class which defines mandatory interface for origin,
    when using the reporting system"""
    name = "Origin:Unknown"

    def __init__(self, name):
        self.name = name

class Question(object):
    """A pending question to the user.

    Object identity is used to match questions and replies."""

    def __init__(self, prompt, options = {}):
        self.prompt = prompt
        self.options = options

    def send_answer(self, question_message, answer, origin = None):
        assert question_message["message"] is self
        question_message["reply"].put \
            (answer, origin, FIRSTAIDKIT, ANSWER,
             importance = question_message["importance"], inreplyto = self)
        question_message["reply"].end(level = FIRSTAIDKIT, origin = origin)

class ConfigQuestion(Question):
    """A question that allows list of configurable variables

    Each item is a tuple (id, title, value,
                          tooltip, regexp_validator, validator_error_msg)"""
    
    def __init__(self, title, description, items, options = {}):
        super(ConfigQuestion, self).__init__(title, options)
        assert len(items) > 0
        self.title = title
        self.description = description
        self.mode = options.get("mode", 1)

        def _fillrow(x):
            if self.mode == 2:
                model = x[6]
            else:
                model = None
                
            return (x[0], x[1], x[2], x[3],
                    re.compile("^("+x[4]+")$"), x[5], model)
        
        self.items = map(_fillrow, items)

class ChoiceQuestion(Question):
    """A question that offers multiple options.

    Each option is a tuple of (return value, description)."""

    def __init__(self, prompt, choices, options = {}):
        super(ChoiceQuestion, self).__init__(prompt, options)
        assert len(choices) > 0
        self.choices = choices

class TextQuestion(Question):
    """A question that asks for a string."""
    pass # No special behavior

class FilenameQuestion(TextQuestion):
    """A question that asks for a file name."""
    pass # No special behavior

class PasswordQuestion(Question):
    """A question that asks for a password."""

    def __init__(self, prompt, confirm, options = {}):
        super(PasswordQuestion, self).__init__(prompt, options)
        self.confirm = confirm

class Reports(object):
    """Instances of this class are used as reporting mechanism by which the
    plugins can comminucate back to whatever frontend we are using.

    Message has the following parts:
    origin - who sent the message (instance of the plugin, Pluginsystem, ...)
    level - which level of First Aid Kit sent the message (PLUGIN, TASKER, ..)
    action - what action does the message describe
                (INFO, ALERT, PROGRESS, START, STOP, DATA, END)
    importance - how is that message important (debug, info, error, ...)
                 this must be number, possibly the same as in logging module
    message - the message itself
              for INFO and ALERT semantics, this is an arbitrary  text
              for PROGRESS, this is  (x,y) pair denoting progress
                (on step x from y steps) or None to hide the progress
              for START and STOP, there is no mandatory message and the
                importance specifies the level
              for *_QUESTION, this is a Qustion object
    reply - an instance of Reports that should receive the replies
    inreplyto - in replies, "message" from the associated question message
    title - title of the message
    """

    def __init__(self, maxsize=-1, silent = False, parent  = None, name = None):
        """silent - silently discard messages that don't fit in the queue
        maxsize - size of the buffer"""
        self._queue = Queue.Queue(maxsize = maxsize)
        self._queue_lock = thread.allocate_lock()
        self._silent = silent
        self._mailboxes = []
        self._notify = []
        self._notify_all = []
        self._parent  = parent
        if not name:
            self._name = "Reporting"
        else:
            self._name = name


    def notify(self, cb, *args, **kwargs):
        """When putting anything new into the Queue, run notifications
        callbacks. Usefull for Gui and single-thread reporting.
        The notification function has parameters: reporting object,
        message recorded to the queue, any parameters provided
        when registering"""
        return self._notify.append((cb, args, kwargs))
    
    def notify_all(self, cb, *args, **kwargs):
        """When putting anything new into the Queue or mailboxes
        belonging to this Reporting object, run notifications
        callbacks. Usefull for logging.
        The notification function has parameters: reporting object,
        message recorded to the queue, any parameters provided
        when registering"""
        return self._notify_all.append((cb, args, kwargs))

    def put(self, message, origin, level, action, importance = logging.INFO,
            reply = None, inreplyto = None, title = "", destination = None):
        """destination hold reference to another Reporting object"""

        if destination is not None:
            return destination.put(message = message, origin = origin, level = level, action = action, importance = importance, reply = reply, title = title, inreplyto = inreplyto)

        origin_msg = Origin(origin.name)
        
        data = {"level": level, "origin": origin_msg, "action": action,
                "importance": importance, "message": message,
                "reply": reply, "inreplyto": inreplyto, "title": title, "remote": False, "remote_name": "LOCAL", "remote_address": ""}

        self.put_raw(data)

    def put_raw(self, data, destination = None):
        if destination is not None:
            return destination.put_raw(data)

        try:
            self._queue.put(data, block = False)
        except Queue.Full:
            if not self._silent:
                raise

        #call all the notify callbacks
        for func, args, kwargs in self._notify:
            func(self, data, *args, **kwargs)
        
        #call all the notify-all callbacks
        self.notifyAll(self, data)

    def get(self, mailbox = None, *args, **kwargs):
        if mailbox is not None:
            return mailbox.get(*args, **kwargs)

        return self._queue.get(*args, **kwargs)

    def openMailbox(self, maxsize=-1):
        """Allocate new mailbox for replies"""

        mb = Reports(maxsize = maxsize, parent = self)
        self._queue_lock.acquire()
        try:
            self._mailboxes.append(mb)
        finally:
            self._queue_lock.release()

        return mb

    def removeMailbox(self, mb):
        """Remove mailbox from the mailbox list"""
        self._queue_lock.acquire()
        try:
            self._mailboxes.remove(mb)
        finally:
            self._queue_lock.release()

    def closeMailbox(self):
        """Close mailbox when not needed anymore"""
        self._parent.removeMailbox(self)

    def notifyAll(self, data, sender=None):
        if sender is None:
            sender = self

        #call all the notify-all callbacks
        for func, args, kwargs in self._notify_all:
            func(sender, data, *args, **kwargs)

        if self._parent:
            self._parent.notifyAll(data, sender)

    #There will be helper methods inspired by logging module
    def end(self, origin, level = PLUGIN):
        return self.put(None, origin, level, END, importance = 1000)

    def error(self, message, origin, inreplyto = None, level = PLUGIN, action = INFO):
        Logger.error(origin.name+": "+message)
        return self.put(message, origin, level, action,
                importance = logging.ERROR, inreplyto = inreplyto)

    def start(self, origin, inreplyto = None, level = PLUGIN, message = ""):
        return self.put(message, origin, level, START,
                importance = logging.DEBUG, inreplyto = inreplyto)
    def stop(self, origin, inreplyto = None, level = PLUGIN, message = ""):
        return self.put(message, origin, level, STOP,
                importance = logging.DEBUG, inreplyto = inreplyto)

    def progress(self, position, maximum, origin, inreplyto = None, level = PLUGIN,
            importance = logging.INFO):
        return self.put((position, maximum), origin, level, PROGRESS,
                importance = importance, inreplyto = inreplyto)

    def issue(self, issue, origin, inreplyto = None, level = PLUGIN, importance = logging.INFO):
        Logger.debug(origin.name+": issue changed state to "+str(issue))
        return self.put(issue, origin, level, ISSUE, importance = importance, inreplyto = inreplyto)

    def info(self, message, origin, inreplyto = None, level = PLUGIN, importance = logging.INFO):
        Logger.info(origin.name+": "+message)
        return self.put(message, origin, level, INFO, importance = importance, inreplyto = inreplyto)

    def debug(self, message, origin, inreplyto = None, level = PLUGIN, importance = logging.DEBUG):
        Logger.debug(origin.name+": "+message)
        return self.put(message, origin, level, INFO, importance = importance, inreplyto = inreplyto)

    def tree(self, message, origin, inreplyto = None, level = PLUGIN, importance = logging.INFO,
            title = ""):
        return self.put(message, origin, level, TREE, importance = importance,
                title = title, inreplyto = inreplyto)

    def table(self, message, origin, inreplyto = None, level = PLUGIN, importance = logging.INFO,
            title = ""):
        return self.put(message, origin, level, TABLE,
                importance = importance, title = title, inreplyto = inreplyto)

    def alert(self, message, origin, inreplyto = None, level = PLUGIN, importance = logging.WARNING):
        return self.put(message, origin, level, ALERT, importance = importance, inreplyto = inreplyto)

    def exception(self, message, origin, inreplyto = None, level = PLUGIN, importance = logging.ERROR):
        Logger.error(origin.name+": "+message)
        return self.put(message, origin, level, EXCEPTION,
                importance = importance, inreplyto = inreplyto)

    def __blocking_question(self, fn, args, kwargs):
        mb = self.openMailbox()
        try:
            question = fn(mb, *args, **kwargs)
            r = mb.get()
            assert r["action"] in (ANSWER, END)
            if r["action"] == END:
                raise NoAnswerException()
            assert r["inreplyto"] is question
            answer = r["message"]
            r = mb.get()
            assert r["action"] == END
        finally:
            mb.closeMailbox()
        return answer

    def choice_question(self, reply_mb, prompt, choices, origin, level = PLUGIN,
                        importance = logging.ERROR, options = {}):
        q = ChoiceQuestion(prompt, choices, options)
        self.put(q, origin, level, CHOICE_QUESTION, importance = importance,
                 reply = reply_mb)
        return q

    def choice_question_wait(self, *args, **kwargs):
        return self.__blocking_question(self.choice_question, args, kwargs)

    def text_question(self, reply_mb, prompt, origin, level = PLUGIN,
                      importance = logging.ERROR, options = {}):
        q = TextQuestion(prompt, options)
        self.put(q, origin, level, TEXT_QUESTION, importance = importance,
                 reply = reply_mb)
        return q

    def text_question_wait(self, *args, **kwargs):
        return self.__blocking_question(self.text_question, args, kwargs)

    def password_question(self, reply_mb, prompt, origin, level = PLUGIN,
                          importance = logging.ERROR, confirm = False, options = {}):
        q = PasswordQuestion(prompt, confirm, options)
        self.put(q, origin, level, PASSWORD_QUESTION, importance = importance,
                 reply = reply_mb)
        return q

    def password_question_wait(self, *args, **kwargs):
        return self.__blocking_question(self.password_question, args, kwargs)

    def filename_question(self, reply_mb, prompt, origin, level = PLUGIN,
                          importance = logging.ERROR, options = {}):
        q = FilenameQuestion(prompt, options)
        self.put(q, origin, level, FILENAME_QUESTION, importance = importance,
                 reply = reply_mb)
        return q

    def filename_question_wait(self, *args, **kwargs):
        return self.__blocking_question(self.filename_question, args, kwargs)

    def config_question(self, reply_mb, title, description,
                        items, origin, level = PLUGIN,
                        importance = logging.ERROR, options = {}):
        q = ConfigQuestion(title, description, items, options = options)
        self.put(q, origin, level, CONFIG_QUESTION, importance = importance,
                 reply = reply_mb)
        return q

    def config_question_wait(self, *args, **kwargs):
        return self.__blocking_question(self.config_question, args, kwargs)
