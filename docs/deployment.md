# Deployment Guide

## Docker image

```bash
docker build -t local-claude-marketplace .
```

The image:

- Base: `python:3.14-slim` + `git`
- Installs deps via `uv sync --no-dev --frozen`
- Exposes port `8080`
- Entry: `uvicorn src.marketplace.main:app --host 0.0.0.0 --port 8080`

---

## Local / single-host (docker compose)

```bash
# edit config/repos.yaml to add your sources (one community source is included by default)
docker compose up -d
```

The compose file mounts:

- `./data` → `/data` — SQLite DB and git clones (write)
- `./config` → `/config` — `repos.yaml` source list (read-only)

---

## Environment variables

> **Machine-readable source of truth:** [`deployment-contract.yaml`](deployment-contract.yaml) is the parsed contract (`kind: DeploymentContract`) consumed by the `k8s-deployment-drift` audit — it enumerates every env var (required/optional + default) and every Secret / ConfigMap the deployment must provide. `tests/test_deployment_contract.py` derives the env list from the code (AST walk of `src/`) and fails CI if this table and the contract drift from what the code reads. The table below is human-facing prose; edit the contract too when a setting changes.

| Variable | Default | Notes |
| --- | --- | --- |
| `DATA_DIR` | `/data` | Persistent data root (DB + clones) |
| `CONFIG_FILE` | `/config/repos.yaml` | Path to `repos.yaml` |
| `PORT` | `8080` | Uvicorn listen port |
| `STORAGE_BACKEND` | `sqlite` | `sqlite` or `s3` |
| `DB_PATH` | `$DATA_DIR/db/marketplace.db` | SQLite only |
| `S3_ENDPOINT` | — | S3-compatible URL (e.g. MinIO) |
| `S3_BUCKET` | `marketplace` | S3 bucket name |
| `S3_ACCESS_KEY` | — | S3 credentials |
| `S3_SECRET_KEY` | — | S3 credentials |
| `GIT_AUTH_TOKEN` | — | PAT for sources with `requires_auth: true`; injected into HTTPS URL at clone/pull time, never stored |
| `LOG_LEVEL` | `INFO` | Logging level (read in `main.py`) |

---

## Kubernetes

### Persistent volumes

Two volumes are required:

| Mount     | Access        | Purpose                               |
| --------- | ------------- | ------------------------------------- |
| `/data`   | ReadWriteOnce | SQLite DB and cloned repos            |
| `/config` | ReadOnlyMany  | `repos.yaml` (ConfigMap or shared PV) |

**Do not run multiple replicas with `STORAGE_BACKEND=sqlite`** — SQLite does not support concurrent writers from separate pods. Use `s3` backend for multi-replica deployments.

### ConfigMap for repos.yaml

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: marketplace-config
data:
  repos.yaml: |
    repos:
      - url: https://github.com/VoltAgent/awesome-claude-code-subagents
        name: awesome-claude-code-subagents
        description: Community skills and agents
        ownership: remote
        format: auto
```

### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: marketplace
spec:
  replicas: 1 # see note above — 1 replica for sqlite
  selector:
    matchLabels:
      app: marketplace
  template:
    metadata:
      labels:
        app: marketplace
    spec:
      containers:
        - name: marketplace
          image: local-claude-marketplace:latest
          ports:
            - containerPort: 8080
          env:
            - name: DATA_DIR
              value: /data
            - name: CONFIG_FILE
              value: /config/repos.yaml
            - name: STORAGE_BACKEND
              value: sqlite
          volumeMounts:
            - name: data
              mountPath: /data
            - name: config
              mountPath: /config
              readOnly: true
          readinessProbe:
            httpGet:
              path: /api/plugins
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 10
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: marketplace-data
        - name: config
          configMap:
            name: marketplace-config
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: marketplace-data
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
---
apiVersion: v1
kind: Service
metadata:
  name: marketplace
spec:
  selector:
    app: marketplace
  ports:
    - port: 80
      targetPort: 8080
```

### Private repos (GIT_AUTH_TOKEN)

If any source has `requires_auth: true`, inject the PAT via a Secret:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: marketplace-git-auth
type: Opaque
stringData:
  GIT_AUTH_TOKEN: "ghp_YourTokenHere"
```

Reference in the container spec alongside other env:

```yaml
env:
  - name: GIT_AUTH_TOKEN
    valueFrom:
      secretKeyRef:
        name: marketplace-git-auth
        key: GIT_AUTH_TOKEN
```

The token is used only during clone/pull; it is not stored in the DB or written to disk.

---

### S3 backend (multi-replica)

Set `STORAGE_BACKEND=s3` and supply S3 credentials via a Secret:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: marketplace-s3
type: Opaque
stringData:
  S3_ENDPOINT: "https://s3.amazonaws.com"
  S3_BUCKET: "my-marketplace-bucket"
  S3_ACCESS_KEY: "AKIAIOSFODNN7EXAMPLE"
  S3_SECRET_KEY: "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
```

Reference in the container spec:

```yaml
envFrom:
  - secretRef:
      name: marketplace-s3
```

With S3 backend, replicas can scale freely — `/data` PVC is only needed for git clones (still required, but can be `emptyDir` if clones are ephemeral).

---

## Networking

The app exposes one HTTP port (`8080`). No TLS termination is built in — terminate at an ingress/load balancer.

Outbound: the container clones git repos at startup and on index refresh. Ensure egress to GitHub (or your git hosts) is allowed. For private repos, supply `GIT_AUTH_TOKEN` via environment — it is injected ephemerally and never written to disk.

---

## Health check

```
GET /api/plugins
```

Returns `200` with JSON when healthy. Use as both readiness and liveness probe.
