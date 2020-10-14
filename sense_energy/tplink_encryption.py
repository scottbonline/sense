# Based on: https://github.com/softScheck/tplink-smartplug/blob/dcf978b970356c3edd941583d277612182381f2c/tplink_smartplug.py
#
# TP-Link Wi-Fi Smart Plug Protocol Client
# For use with TP-Link HS-100 or HS-110
#
# by Lubomir Stroetmann
# Copyright 2016 softScheck GmbH
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Modifications Copyright (C) 2020, Charles Powell

from struct import pack


def _generate_tplink(unencrypted):
    key = 171
    for unencryptedbyte in unencrypted:
        key = key ^ unencryptedbyte
        yield key


def tp_link_encrypt(string):
    unencrypted = string.encode()
    return pack(">I", len(unencrypted)) + bytes(_generate_tplink(unencrypted))


def tp_link_decrypt(string):
    key = 171
    result = ""
    for i in string:
        a = key ^ i
        key = i
        result += chr(a)
    return result
