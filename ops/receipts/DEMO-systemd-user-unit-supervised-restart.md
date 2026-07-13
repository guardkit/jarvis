# O-30 DEMO — systemd USER unit supervised restart (E2-S3(d))

Run 2026-07-13T17:42:48Z on `promaxgb10-41b1`. A **throwaway transient**
`systemd --user` unit (`systemd-run --user`) wrapping a trivial long-running
process, with the **same `Restart=on-failure` policy** the real units carry
(`jarvis/ops/systemd/jarvis-frontdoor.service` and
`forge/ops/systemd/forge-langgraph-sidecar.service`). Killing the process
proves the systemd user manager supervises and auto-restarts it — the mechanism
that replaces the bare `langgraph dev` / `nohup langgraph dev` front door + sidecar.
No real unit was installed or enabled; this transient unit was removed after.

## Result
```
unit            : frontdoor-restart-demo-e2s3.service  (transient, Type=exec, Restart=on-failure, RestartSec=1)
before kill     : MainPID=89824  NRestarts=0  Active=active
action          : kill -9 89824   (simulate the process dying)
poll (1s): t1:activating/PID=0/NRestarts=0 t2:activating/PID=89951/NRestarts=1 t3:active/PID=89951/NRestarts=1
-> the user manager restarted it: MainPID changed (89824 -> 89951), NRestarts 0 -> 1,
   Active returned to 'active'. Restart=on-failure supervised the crash.
```

## journalctl --user -u frontdoor-restart-demo-e2s3 (last 15 lines)
```
Jul 13 18:42:22 promaxgb10-41b1 systemd[2208]: frontdoor-restart-demo-e2s3.service: Scheduled restart job, restart counter is at 1.
Jul 13 18:42:22 promaxgb10-41b1 systemd[2208]: Starting frontdoor-restart-demo-e2s3.service - /bin/sh -c "echo \"front-door STUB alive, pid \$\$\"; exec sleep 3600"...
Jul 13 18:42:22 promaxgb10-41b1 systemd[2208]: Started frontdoor-restart-demo-e2s3.service - /bin/sh -c "echo \"front-door STUB alive, pid \$\$\"; exec sleep 3600".
Jul 13 18:42:22 promaxgb10-41b1 sh[88671]: front-door STUB alive, pid $
Jul 13 18:42:45 promaxgb10-41b1 systemd[2208]: Stopping frontdoor-restart-demo-e2s3.service - /bin/sh -c "echo \"front-door STUB alive, pid \$\$\"; exec sleep 3600"...
Jul 13 18:42:45 promaxgb10-41b1 systemd[2208]: Stopped frontdoor-restart-demo-e2s3.service - /bin/sh -c "echo \"front-door STUB alive, pid \$\$\"; exec sleep 3600".
Jul 13 18:42:45 promaxgb10-41b1 systemd[2208]: Starting frontdoor-restart-demo-e2s3.service - /bin/sh -c "echo \"front-door STUB alive, pid \$\$\"; exec sleep 3600"...
Jul 13 18:42:45 promaxgb10-41b1 systemd[2208]: Started frontdoor-restart-demo-e2s3.service - /bin/sh -c "echo \"front-door STUB alive, pid \$\$\"; exec sleep 3600".
Jul 13 18:42:45 promaxgb10-41b1 sh[89824]: front-door STUB alive, pid $
Jul 13 18:42:46 promaxgb10-41b1 systemd[2208]: frontdoor-restart-demo-e2s3.service: Main process exited, code=killed, status=9/KILL
Jul 13 18:42:46 promaxgb10-41b1 systemd[2208]: frontdoor-restart-demo-e2s3.service: Failed with result 'signal'.
Jul 13 18:42:47 promaxgb10-41b1 systemd[2208]: frontdoor-restart-demo-e2s3.service: Scheduled restart job, restart counter is at 1.
Jul 13 18:42:47 promaxgb10-41b1 systemd[2208]: Starting frontdoor-restart-demo-e2s3.service - /bin/sh -c "echo \"front-door STUB alive, pid \$\$\"; exec sleep 3600"...
Jul 13 18:42:47 promaxgb10-41b1 systemd[2208]: Started frontdoor-restart-demo-e2s3.service - /bin/sh -c "echo \"front-door STUB alive, pid \$\$\"; exec sleep 3600".
Jul 13 18:42:47 promaxgb10-41b1 sh[89951]: front-door STUB alive, pid $
```
