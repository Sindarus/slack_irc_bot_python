#!/usr/bin/env python2
# -*- coding: utf8 -*-

import time
import json
import re
import unicodedata
from slackclient import SlackClient

import config as c
import central_unit

from message import *
from chan import *

class SlackBot:
    def __init__(self):
        print("SLACKBOT: Initiating slackclient")
        self.client = SlackClient(c.SLACKBOT_TOKEN)
        print("SLACKBOT: Slackclient initiated")

        if c.WELCOME_MESSAGES:
            self.send_welcome_msg()

    def send_welcome_msg(self):
        print("SLACKBOT: Sending welcome msg")
        for cur_twinning in central_unit.twinnings.table:
            for cur_chan in cur_twinning:
                if cur_chan.chat_type == "Slack":
                    self.client.api_call( "chat.postMessage",
                        channel=cur_chan.chan_name,
                        text="(Init) Twinning this chan with : " + central_unit.twinnings.get_chan_twins(cur_chan).__repr__(),
                        username="relai-irc",
                        icon_emoji=':robot_face:'
                    )

    def retrieve_chan_names(self):
        print("SLACKBOT: retrieving channel names")
        self.chan_names = {}
        data = self.client.api_call("channels.list")
        for channel in data["channels"]:
            self.chan_names[channel["id"]] = "#" + channel["name"]

    def chan_name(self, id):
        """Given a slack channel id, this function returns the name of the channel"""
        try:
            ret = self.chan_names[id]
        except Exception as e:  #if chan_names[id] is unknown
            self.retrieve_chan_names() #retrieve chan names again
            #try another time before giving up
            try:
                ret = self.chan_names[id]
            except Exception as e:
                print("WARNING: could not find chan name")
                ret = id #fallback: keep id as name
        return ret

    def retrieve_user_names(self):
        print("SLACKBOT: retrieving user names")
        self.user_names = {}
        data = self.client.api_call("users.list")
        for user in data["members"]:
            self.user_names[user["id"]] = user["name"]

    def user_name(self, id):
        """Given a slack user id, this function returns the name of the user"""
        try:
            ret = self.user_names[id]
        except Exception as e:  #if user_names[id] is unknown
            self.retrieve_user_names() #retrieve chan names again
            #try another time before giving up
            try:
                ret = self.user_names[id]
            except Exception as e:
                print("WARNING: could not find chan name")
                ret = id #fallback: keep id as name
        return ret

    def start(self):
        # retrieve chan names and user names needed to replace chan and user IDs
        self.retrieve_chan_names()
        self.retrieve_user_names()

        # initiating websocket connection to slack
        if not self.client.rtm_connect():
            print("SLACKBOT: There was a problem starting the real time messaging system for slack.")
            exit()
        else:
            print("SLACKBOT: Successfully started real time messaging system for slack")

        # main loop
        print("SLACKBOT: Launching main loop for slack")
        while True:
            time.sleep(c.SLACKBOT_REFRESH_TIME)

            # reading websocket
            print("SLACKBOT: reading slack messages")
            last_read = self.client.rtm_read()

            if not last_read:
                print("No message")
                continue

            # trying to harvest a message from what we've read from websocker
            msg = ""
            try:
                msg = last_read[0]['text']
                channel = last_read[0]['channel']
                user = last_read[0]['user']
            except Exception, e:
                print("Not a message because : " + e.__repr__());
                continue

            if msg == "":
                print("empty message")
                continue

            #retrieve real names, not IDs
            channel = self.chan_name(channel)
            user = self.user_name(user)

            #encoding everything to utf8, so that it's compatible with the rest
            #msg = unicodedata.normalize('NFKD', msg).encode('Latin-1', 'ignore')
            msg = msg.encode("utf-8")
            channel = channel.encode("utf-8")
            user = user.encode('utf8')

            msg = self.replace_user_id_in_msg(msg).encode('utf8')

            # transfering to central unit
            print("(SLACK " + channel + ") " + user + " : " + msg)
            central_unit.handle_msg(Message(
                chan_orig = Chan("Slack", channel),
                author = user,
                msg = msg)
            )

    def replace_user_id_in_msg(self, msg):
        """when a message is posted on slack and it references another user,
        the user's name is replaced by its ID. Pass the message through this
        function to get the name back"""

        #posting @name on slack would be replaced by, for example:
        #<@UAAAAAAAA>

        while(True):
            res = re.search("<@(U[0-9A-Z]{8})>", msg)
            if type(res).__name__ == 'NoneType':    # if there's no match
                return msg
            else:
                cur_name = self.user_name(res.group(1))
                msg = msg.replace(res.group(), "@" + cur_name)

        return msg

    def post_msg(self, chan_name, msg):
        #sending msg to slack
        self.client.api_call(
            "chat.postMessage",
            channel=chan_name,
            text=msg.msg,
            username=msg.author,
            icon_emoji=c.SLACK_ICON_EMOJI
        )
