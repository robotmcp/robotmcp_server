# Project Guidelines

## Version Control (Gitflow)

### Branch Structure

| Branch | Purpose | Merges to |
|--------|---------|-----------|
| `main` | Production releases (tagged) | - |
| `develop` | Integration branch | `main` |
| `feature/*` | New features | `develop` |
| `release/*` | Release preparation | `main` + `develop` |
| `hotfix/*` | Urgent production fixes | `main` + `develop` |

### PR Rules
- **Default PR base**: `develop`
- Feature PRs: `feature/*` → `develop`
- Release PRs: `release/*` → `main` (then back-merge to `develop`)
- Hotfix PRs: `hotfix/*` → `main` (then back-merge to `develop`)

### Commit Rules
1. Keep commits atomic (one change per commit)
2. Use conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`, `ci:`, `style:`
3. Test before pushing

### Gitflow Branching Model

**Main Branches:**
| Branch | Purpose |
|--------|---------|
| `main` | Production-ready code, always stable |
| `develop` | Integration branch for features |

**Supporting Branches:**
| Branch | Created from | Merges into | Naming |
|--------|--------------|-------------|--------|
| Feature | `develop` | `develop` | `feature/*` |
| Release | `develop` | `main` and `develop` | `release/*` |
| Hotfix | `main` | `main` and `develop` | `hotfix/*` |

**Workflow:**
```
main ─────●─────────────────●─────────────●───→
          │                 ↑             ↑
          │           release/1.0    hotfix/1.0.1
          │                 ↑             │
develop ──●──●──●──●──●─────●─────────────●───→
             ↑     ↑
        feature/A  feature/B
```

**Branch Commands:**
```bash
# Start a feature
git checkout develop
git checkout -b feature/my-feature

# Finish a feature
git checkout develop
git merge --no-ff feature/my-feature
git branch -d feature/my-feature

# Start a release
git checkout develop
git checkout -b release/1.0.0

# Finish a release
git checkout main
git merge --no-ff release/1.0.0
git checkout develop
git merge --no-ff release/1.0.0
git branch -d release/1.0.0

# Start a hotfix
git checkout main
git checkout -b hotfix/1.0.1

# Finish a hotfix
git checkout main
git merge --no-ff hotfix/1.0.1
git checkout develop
git merge --no-ff hotfix/1.0.1
git branch -d hotfix/1.0.1
```

### Version Numbering (SemVer)

| Part | When to bump | Example |
|------|--------------|---------|
| MAJOR | Breaking changes | 1.0.0 → 2.0.0 |
| MINOR | New features (backward compatible) | 1.0.0 → 1.1.0 |
| PATCH | Bug fixes | 1.0.0 → 1.0.1 |

### Release Process

**When to tag:**
- MINOR version changes (new features) → create git tag + update documentation
- MAJOR version changes (breaking changes) → create git tag + update documentation
- PATCH version changes (bug fixes) → no tag required

**Workflow:**
1. Create `release/vX.Y.Z` from `develop`
2. Update version in `pyproject.toml`
3. PR to `main`, merge, tag as `vX.Y.Z`
4. Back-merge `main` to `develop`

```bash
# After merging to main
git checkout main
git pull
git tag -a v1.1.0 -m "Release v1.1.0: description of changes"
git push origin v1.1.0
```
