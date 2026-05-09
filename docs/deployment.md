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

| Variable | Default | Notes |
|---|---|---|
| `DATA_DIR` | `/data` | Persistent data root (DB + clones) |
| `CONFIG_FILE` | `/config/repos.yaml` | Path to `repos.yaml` |
| `PORT` | `8080` | Uvicorn listen port |
| `STORAGE_BACKEND` | `sqlite` | `sqlite` or `s3` |
| `DB_PATH` | `$DATA_DIR/db/marketplace.db` | SQLite only |
| `S3_ENDPOINT` | — | S3-compatible URL (e.g. MinIO) |
| `S3_BUCKET` | `marketplace` | S3 bucket name |
| `S3_ACCESS_KEY` | — | S3 credentials |
| `S3_SECRET_KEY` | — | S3 credentials |

---

## Kubernetes

### Persistent volumes

Two volumes are required:

| Mount | Access | Purpose |
|---|---|---|
| `/data` | ReadWriteOnce | SQLite DB and cloned repos |
| `/config` | ReadOnlyMany | `repos.yaml` (ConfigMap or shared PV) |

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
  replicas: 1                        # see note above — 1 replica for sqlite
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

Outbound: the container clones git repos at startup and on index refresh. Ensure egress to GitHub (or your git hosts) is allowed.

---

## Health check

```
GET /api/plugins
```

Returns `200` with JSON when healthy. Use as both readiness and liveness probe.
