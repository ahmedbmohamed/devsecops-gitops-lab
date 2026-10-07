# Setup guide

## Prerequisites

Install on your machine (Linux, macOS, or Windows with WSL2):

- Git
- Docker
- minikube
- kubectl
- Helm

Check: `docker --version && minikube version && kubectl version --client && helm version`

## 1. Create the GitHub repository

1. On github.com, create a **public** repository named `devsecops-gitops-lab` (no README, it already exists locally).
2. Replace `YOUR_GITHUB_USERNAME` (lowercase) in these two files:
   - `helm/devsecops-app/values.yaml`
   - `argocd/application.yaml`
3. Push the project:

```bash
cd devsecops-gitops-lab
git init -b main
git add .
git commit -m "Initial commit: DevSecOps GitOps lab"
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/devsecops-gitops-lab.git
git push -u origin main
```

## 2. Let GitHub Actions write to the repo

Repo → **Settings → Actions → General → Workflow permissions** → choose
**Read and write permissions** → Save. (Needed so the pipeline can commit the new image tag.)

## 3. Run the pipeline once

The first push triggers the pipeline (it only runs when `app/` changes). If it did not run, make a tiny change in `app/app.py` and push again.

Open the **Actions** tab and check: test → build → Trivy scan → push → tag update.
Take a screenshot of the green run.

## 4. Make the image public

GitHub profile → **Packages** → `devsecops-gitops-lab` → **Package settings** → **Change visibility → Public**.
(This lets minikube pull the image without a pull secret.)

## 5. Start the cluster and install ArgoCD

```bash
minikube start --driver=docker
kubectl create namespace argocd
kubectl apply -n argocd --server-side -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl wait --for=condition=available deployment --all -n argocd --timeout=300s
```

Get the admin password and open the UI:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d; echo
kubectl port-forward svc/argocd-server -n argocd 8081:443
```

Browse to https://localhost:8081 (user `admin`, accept the self-signed certificate warning).

## 6. Deploy the app with ArgoCD

```bash
kubectl apply -f argocd/application.yaml
kubectl get pods -n demo -w
```

In the ArgoCD UI the app `devsecops-app` should become **Synced** and **Healthy**.

Test the app:

```bash
kubectl port-forward svc/devsecops-app -n demo 8080:80
curl http://localhost:8080/
curl http://localhost:8080/healthz
```

## 7. See GitOps in action

1. Edit the message in `app/app.py`, commit, and push.
2. Watch the pipeline build, scan, push, and commit a new tag.
3. Watch ArgoCD roll out the new version without any manual command.
4. Try `kubectl scale deployment devsecops-app -n demo --replicas=5`: ArgoCD reverts it (`selfHeal`).

## 8. Prove the security gate works (great for the README)

Temporarily pin an old base image in `app/Dockerfile` (for example `python:3.8-slim`),
push, and show the pipeline **failing at the Trivy step**. Screenshot it, then revert.

## Troubleshooting

| Problem | Fix |
|---|---|
| `ImagePullBackOff` | The GHCR package is still private, or `YOUR_GITHUB_USERNAME` was not replaced |
| Pipeline cannot push the tag commit | Step 2 (write permissions) not done |
| Trivy fails on a fresh image | Update the base image or dependency versions in `app/` |
| ArgoCD shows `OutOfSync` forever | Check `repoURL` and that the repo is public |
