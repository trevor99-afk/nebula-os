"""NebulaOS system tools.

The `nebula` package is the shared, unprivileged backend for NebulaOS's own
tools: system status and monitoring, the hardware compatibility report, the
System Doctor and update management. Front ends (the `nebula` command today,
the Nebula Control Center later) call into it and use its JSON output.

Rules every module follows:
- Values come from real system sources (/proc, /sys, systemd, rpm-ostree...).
  Anything that cannot be read is reported as None, never guessed.
- Commands run without a shell, with a timeout (see util.run).
- Nothing changes the system without an explicit user confirmation.
"""

__version__ = "0.1.0"
