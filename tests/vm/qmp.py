#!/usr/bin/env python3
"""Drive a running test VM through QEMU's QMP socket, like a person at the screen.

  qmp.py SOCKET shot FILE.png          screenshot of the VM display
  qmp.py SOCKET type 'some text'       type text (US keyboard layout)
  qmp.py SOCKET key ctrl-alt-f3        press a key combination (QEMU key names)
  qmp.py SOCKET click X Y W H          left click at X,Y on a W x H screen
  qmp.py SOCKET powerdown              ACPI power button
  qmp.py SOCKET quit                   stop QEMU at once

Standard library only, so it runs inside the NebulaOS image or on the host.
"""
import json
import os
import socket
import sys
import time

SHIFTED = {
    '!': '1', '@': '2', '#': '3', '$': '4', '%': '5', '^': '6', '&': '7', '*': '8', '(': '9', ')': '0',
    '_': 'minus', '+': 'equal', '{': 'bracket_left', '}': 'bracket_right', '|': 'backslash',
    ':': 'semicolon', '"': 'apostrophe', '~': 'grave_accent', '<': 'comma', '>': 'dot', '?': 'slash',
}
PLAIN = {
    ' ': 'spc', '-': 'minus', '=': 'equal', '[': 'bracket_left', ']': 'bracket_right', '\\': 'backslash',
    ';': 'semicolon', "'": 'apostrophe', '`': 'grave_accent', ',': 'comma', '.': 'dot', '/': 'slash',
    '\n': 'ret', '\t': 'tab',
}


class QMP:
    def __init__(self, path):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(path)
        self.file = self.sock.makefile("rw")
        self._read()  # greeting
        self.cmd("qmp_capabilities")

    def _read(self):
        while True:
            msg = json.loads(self.file.readline())
            if "event" not in msg:
                return msg

    def cmd(self, name, **args):
        self.file.write(json.dumps({"execute": name, "arguments": args}) + "\n")
        self.file.flush()
        reply = self._read()
        if "error" in reply:
            raise SystemExit(f"QMP {name}: {reply['error'].get('desc')}")
        return reply.get("return")

    def keys(self, names, hold_ms=60):
        self.cmd("send-key", keys=[{"type": "qcode", "data": n} for n in names], **{"hold-time": hold_ms})


def key_for(ch):
    if ch.isalpha():
        return (["shift", ch.lower()] if ch.isupper() else [ch])
    if ch.isdigit():
        return [ch]
    if ch in SHIFTED:
        return ["shift", SHIFTED[ch]]
    if ch in PLAIN:
        return [PLAIN[ch]]
    raise SystemExit(f"cannot type {ch!r}")


def main(argv):
    if len(argv) < 3:
        raise SystemExit(__doc__)
    q = QMP(argv[1])
    action, rest = argv[2], argv[3:]
    if action == "shot":
        q.cmd("screendump", filename=rest[0], format="png")
    elif action == "type":
        # A guest UI under load drops keys that arrive too fast; 0.12 s apart is reliable.
        delay = float(os.environ.get("NEBULA_VM_TYPE_DELAY", "0.12"))
        for ch in rest[0]:
            q.keys(key_for(ch))
            time.sleep(delay)
    elif action == "key":
        for combo in rest:
            q.keys(combo.split("-"))
            time.sleep(0.15)
    elif action == "click":
        x, y, w, h = (int(v) for v in rest)
        ax, ay = x * 32767 // max(w - 1, 1), y * 32767 // max(h - 1, 1)
        q.cmd("input-send-event", events=[
            {"type": "abs", "data": {"axis": "x", "value": ax}},
            {"type": "abs", "data": {"axis": "y", "value": ay}}])
        time.sleep(0.1)
        for down in (True, False):
            q.cmd("input-send-event", events=[{"type": "btn", "data": {"down": down, "button": "left"}}])
            time.sleep(0.08)
    elif action == "powerdown":
        q.cmd("system_powerdown")
    elif action == "quit":
        q.cmd("quit")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
