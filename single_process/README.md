# Single Process

The client-server architecture is not very convenient when it comes to
debugging: if you set a breakpoint in the client, the server continues
running and timesout the client or the client's train dies.

By running both, the server and the client, in the same process, we
can set breakpoints in the client and the server stops. Combined
with a long timeout eases debugging.

There's a "Debug Single Process" launch config for VS Code. You can also
run:

```
python -m single_process
```
