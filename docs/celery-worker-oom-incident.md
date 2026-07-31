# Incident: Celery worker OOM-killed mid-import (stuck imports, resetting progress)

## Symptoms

- A Zoho historical import ran for ~5 hours, appeared to complete (CVs were
  visible in Talent Pool), but a week later the integration still showed
  `Import running 1293/200` and `Last synced: Never`.
- Later, a fresh import's "found" count visibly reset mid-run (e.g. 1600 →
  200) with no error shown anywhere in the UI.
- Worker logs eventually showed the real signal:
  ```
  Process 'ForkPoolWorker-1' pid:8 exited with 'signal 9 (SIGKILL)'
  Task handler raised error: WorkerLostError('Worker exited prematurely: signal 9 (SIGKILL) Job: 15.')
  ```

## Root cause

`SIGKILL` with no matching application-level exception is the signature of
an **OOM kill** — the kernel/container runtime forcibly terminates a
process for using too much memory, which bypasses all of that process's
own code. No `except`, no `finally`, nothing gets a chance to run.

`docker-compose.prod.yml` capped `celery_worker` at 2G memory / 1 CPU.
`docker stats` showed the worker using **~920MiB at idle** — before any
task ran — leaving barely 1.1G of headroom for concurrent CV-parsing/OCR
work. The host also had **0 swap configured**, so any spike past the
ceiling went straight to `SIGKILL` with no cushion.

Because the kill is a hard process termination, not a raised exception:

- The ingestion import task's own `try/except/finally` never ran, so its
  DB row was left exactly as it last was (`RUNNING`, stale progress)
  instead of failing cleanly — this is why the run got stuck for a week.
- Celery's `autoretry_for=(Exception,)` never caught it either (it only
  catches exceptions the task itself raises). Nothing auto-recovered until
  a human retriggered the import — which is what looked like "found reset
  to 200": a brand-new run starting over, not the old one continuing.

Three compounding contributors were found, in order of how directly they
fed the OOM:

1. **Leaked OpenAI clients** (`app/modules/ai/service.py`):
   `EmbeddingAIService` opened an `AsyncOpenAI` client (owning an `httpx`
   connection pool) on every call and never closed it. One CV import
   queues one embedding-generation task per processed CV, so a large
   import could leak dozens of unclosed clients into a single worker
   process before it got recycled.
2. **Too many concurrent workers for the memory budget**: no
   `--concurrency` was set on the worker command, so Celery defaulted to
   one forked child per CPU core *as the container sees it* — a cgroup CPU
   quota (`cpus: '1.0'`) does not reduce that count, it only limits CPU
   time per process. Several memory-heavy children could run at once,
   all sharing the same 2G ceiling.
3. **Uncached NLP model reload**: `spacy.load("en_core_web_sm")` was
   called fresh *inside* the CV parsing task, once per CV, instead of once
   per worker process (the API process already did this correctly via
   `app.state.nlp`). Reloading the model on every CV added real memory
   churn during exactly the bursts (a mailbox import) most likely to
   trigger the OOM.

## Fixes applied

1. **`EmbeddingAIService.close()`** — added, and called in a `finally`
   block at all three call sites in `app/modules/ai/tasks.py`, matching
   the existing close pattern already used for the Anthropic client.
2. **`--concurrency=2`** added to the worker's Celery command in
   `docker-compose.prod.yml`, bounding how many memory-heavy processes run
   at once to match the container's actual CPU/memory budget.
3. **`worker_max_tasks_per_child`: 1000 → 100** (`app/core/celery_app.py`)
   — a forked child gets replaced (memory reset to zero) far sooner, so
   any leak, found or not, has much less room to accumulate.
4. **`_get_nlp()` module-level cache** (`app/modules/ai/tasks.py`) — the
   spaCy model now loads once per worker process instead of once per CV.
5. **`celery_worker` memory limit raised 2G → 3G**
   (`docker-compose.prod.yml`) — `docker stats`/`free -h` confirmed the
   host had real headroom (7.8G total, other services running well under
   their own limits), so this wasn't overcommitting; it was correcting a
   ceiling that was simply too tight for a worker that also does OCR/NLP.
6. **Orphaned-run recovery** (separate but related fix,
   `app/modules/ingestion/service.py` + `tasks.py`): a RUNNING/PENDING
   import run untouched for over `STALE_RUN_TIMEOUT` (3h) is now treated
   as orphaned. `trigger_historical_import` self-heals it automatically
   instead of blocking forever, and a new Celery Beat task
   (`reap_stale_import_runs_task`, every 30 min) proactively marks orphaned
   runs failed so the UI reflects reality even before anyone retries. This
   doesn't prevent the OOM, but it bounds the damage from a worker dying
   mid-task to 30 minutes instead of indefinitely.
7. **Attachment pre-download filtering** (`app/modules/ingestion/
   adapters/{gmail,zoho}.py`): both adapters downloaded every attachment's
   full bytes for every message before the size/extension filter ever ran
   on them. A mailbox with a few large non-CV attachments (video, zip,
   photos) could pull all of that into worker memory only to discard it.
   Now filtered before download using metadata the provider's listing
   already supplies.

## Still to do (VPS-level, not a repo change)

Add swap on the host as a cushion of last resort — with 0 swap, any
transient spike has no graceful degradation path, only an instant kill:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

Note: a container with an explicit Docker memory limit (like
`celery_worker`'s `3G`) is typically capped at that limit for RAM+swap
combined by default — host swap mainly protects the **host as a whole**
under combined memory pressure (e.g. running another project alongside
this one), not this one container's individual ceiling on its own.

## Diagnostic pattern worth remembering

`SIGKILL` + `WorkerLostError` in Celery logs, with no matching application
exception anywhere, means: check memory, not application logic. It's not
something retry/exception-handling code can ever catch — the process is
dead before any of that code gets a chance to run. `docker stats
--no-stream <container>` and `free -h` are the tools that turn a guess
into a diagnosis — they're what distinguished "too much concurrency",
"a slow leak", and "the ceiling itself is too low" from each other here,
rather than fixing all three speculatively without evidence.

## Related PRs

- `fix/ingestion-stale-import-runs` — orphaned run self-heal + reaper task
- `fix/ingestion-progress-not-live` — live progress polling, correct
  percentage math, missing "Failed" stat tile
- `fix/celery-embedding-client-leak-and-contact-task` — the OOM
  investigation and fixes documented above
