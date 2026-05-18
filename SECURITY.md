# Security Policy

## Supported Versions

`agentfuzz` is in alpha (v0.1). Security fixes will land on `main` and ship
in the next release. No older versions are supported.

## Reporting a Vulnerability

Please **do not** open a public issue for security reports.

Email **pavansubhash@gmail.com** with:

- A description of the issue.
- A minimal reproduction (code or steps).
- The version of `agentfuzz` and Python you're using.

You'll get an acknowledgment within 72 hours and a fix or coordinated
disclosure timeline within 14 days. If you're reporting an issue that
affects an extra (e.g. the LangGraph adapter), please mention which one.

## Threat Model

`agentfuzz` is a *testing* tool — its job is to deliberately inject failures
into agents you run yourself. It is **not** designed to defend against
malicious input in production. Two specific notes:

1. **Prompt-injection payloads.** The bundled OWASP LLM01 catalog contains
   strings designed to attack agents. Treat them as you would any fuzzer
   corpus — don't log them to systems where their presence could trigger
   unrelated alerts.
2. **Fault-injected results.** Faults may insert strings that look like
   credentials, PII, or exfiltration commands. They're synthetic, but
   downstream systems (DLP scanners, log shippers) may flag them.

If you find a way for `agentfuzz` to compromise the host system it runs on,
or to interfere with code it isn't explicitly asked to wrap, please report it.
