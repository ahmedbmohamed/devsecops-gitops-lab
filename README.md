# devsecops-gitops-lab

A hands-on lab showing a complete **DevSecOps + GitOps** flow on a local Kubernetes cluster:
a small Flask app is tested, built, **scanned for vulnerabilities (Trivy)**, pushed to a
container registry, and deployed automatically by **ArgoCD** from a **Helm** chart.

**Stack:** Python (Flask) · Docker · GitHub Actions · Trivy · GHCR · Helm · ArgoCD · minikube

## Architecture

```mermaid
flowchart LR
    Dev[Developer] -->|git push| GH[GitHub repo]
    GH --> CI[GitHub Actions]
    subgraph CI pipeline
        T[Unit tests] --> B[Docker build]
        B --> S[Trivy scan<br/>fail on HIGH/CRITICAL]
        S --> P[Push image to GHCR]
        P --> U[Update image tag<br/>in Helm values.yaml]
    end
    CI --> T
    U -->|commit| GH
    GH -->|ArgoCD watches repo| A[ArgoCD]
    A -->|sync| K[(minikube cluster)]
    K --> App[Flask app pods]
```

## How it works

1. The pipeline runs when `app/` or the workflow file (`.github/workflows/ci.yml`) changes, or manually via `workflow_dispatch`.
2. **Test** → **Build** → **Trivy scan**. If a fixable HIGH or CRITICAL vulnerability is found, the pipeline fails and nothing is pushed.
3. The image is pushed to GitHub Container Registry (`ghcr.io`) tagged with the short commit SHA.
4. The pipeline commits the new tag into `helm/devsecops-app/values.yaml`.
5. ArgoCD detects the Git change and syncs the cluster automatically (`selfHeal` and `prune` enabled).

Git is the single source of truth: no `kubectl apply` by hand.

## Repository layout

```
app/                    Flask app, Dockerfile, unit tests
helm/devsecops-app/     Helm chart (Deployment, Service, security context, probes)
argocd/application.yaml ArgoCD Application (auto-sync)
.github/workflows/      CI pipeline
docs/SETUP.md           Step-by-step setup guide
```

## Security practices demonstrated

- Image vulnerability scanning with Trivy, enforced as a pipeline gate
- Container runs as non-root, read-only root filesystem, all Linux capabilities dropped
- Resource requests and limits, readiness and liveness probes
- No secrets in the repo; registry login uses the built-in `GITHUB_TOKEN`

## Quick start

See [docs/SETUP.md](docs/SETUP.md) for the full walkthrough (about 45 minutes).

## Screenshots

### CI pipeline

![GitHub Actions run with test and build-scan-push jobs both green](docs/images/01-pipeline-green.png)
*A push to `main` runs `test`, then `build-scan-push`. The whole run took under a minute.*

![Steps of the build-scan-push job](docs/images/01b-pipeline-steps.png)
*Inside `build-scan-push`: build, Trivy scan, push to GHCR, then commit the new image tag to the Helm values.*

### Security gate (Trivy)

![Trivy scan step output in the pipeline log](docs/images/02-trivy-scan.png)
*Trivy scans the freshly built image before anything is pushed.*

![Trivy scan result](docs/images/02b-trivy-result.png)
*No fixable HIGH or CRITICAL vulnerabilities, so the pipeline is allowed to push.*

![Trivy report legend: '0' means clean](docs/images/02c-trivy-legend.png)
*In Trivy's report, `0` means the target was scanned and is clean.*

### GitOps deployment (ArgoCD)

![ArgoCD application devsecops-app shown as Healthy and Synced](docs/images/03-argocd-synced.png)
*ArgoCD tracks `helm/devsecops-app` on `main` and reports the app `Healthy` and `Synced`.*

![ArgoCD resource tree for devsecops-app](docs/images/03b-argocd-tree.png)
*Synced to the CI bot's tag commit: Service, Deployment, ReplicaSet and two running pods.*

### The running app

![curl calls to the app's / and /healthz endpoints](docs/images/04-pods-and-curl.png)
*Through a port-forward, `/` returns the deployed version (the commit SHA) and `/healthz` returns `ok`.*

## GitOps in action

I changed the app message and pushed. CI built, scanned and pushed the image, then committed the
new tag to the Helm values. ArgoCD rolled it out with no manual command.

![curl to the app returning the v2 message and version ac53bd0](docs/images/06-new-version-curl.png)
*The app now answers "v2", with the new image tag `ac53bd0` as its version.*

To test self-healing, I ran `kubectl scale deployment devsecops-app -n demo --replicas=5` by hand.
ArgoCD (`selfHeal`) reverted it to 2 pods within seconds.

![kubectl get pods showing three extra pods terminating after the manual scale](docs/images/07-selfheal.png)
*The three extra pods are terminated about a second after they start; the two original pods keep running.*

## Proof that the security gate blocks bad images

I opened a pull request that added `requests==2.19.1`, a version with known vulnerabilities.

![Pull request checks: test passed, build-scan-push failed](docs/images/09-pr-blocked.png)
*On the PR, `test` passes and `build-scan-push` fails.*

![build-scan-push job steps: Trivy scan failed, push steps skipped](docs/images/08b-gate-steps.png)
*The pipeline stopped at the Trivy step. The GHCR login, image push and tag update were skipped, so nothing was pushed.*

![Trivy findings for requests 2.19.1](docs/images/08c-trivy-findings.png)
*Trivy found 7 HIGH vulnerabilities (0 CRITICAL) in `requests` 2.19.1, all fixed in later versions.*

The PR was closed without merging, so `main` never received the vulnerable dependency.

## Problems I hit and fixed

**Wrong action version.** The pipeline failed with `Unable to resolve action aquasecurity/trivy-action@0.28.0`.
The tag `0.28.0` no longer resolves; the upstream tags now have a `v` prefix. I pinned the action to the full commit SHA of `v0.36.0`, checked against the
upstream repo with `git ls-remote`, so a moved or re-pointed tag can't change what runs. I also
pinned the runner to `ubuntu-24.04` instead of `ubuntu-latest`.

**Push race between two runs.** The last pipeline step commits the new image tag and pushes it to
`main`. If two runs overlap, or `main` moves while a run is in progress, that push is rejected as
non-fast-forward. Fix: a `concurrency` group per branch queues runs instead of running them in
parallel, and the step runs `git pull --rebase origin main` before editing `values.yaml`, so the
tag commit always lands on top of the latest `main`.

**Docker Desktop auto-update stopped the cluster.** Docker Desktop updated itself in the
background and restarted its engine. That restarted the minikube container on new ports, and
`kubectl` failed with `connection refused`. `minikube status` showed the kubelet and API server
stopped and the kubeconfig stale. Re-running `minikube start` brought everything back without
data loss and rewrote the kubeconfig. Turning off Docker Desktop's automatic updates prevents it
from happening again.

## What I learned / next steps

- Add a Trivy IaC scan for the Helm chart (`trivy config`)
- Sign images with cosign
- Add an Ingress and TLS
- Add Prometheus metrics
- Keep the Trivy scanner version current (the pipeline runs 0.70.0)
