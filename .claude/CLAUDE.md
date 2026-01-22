# Project Guidelines

## Version Control

### Commit Rules
1. Keep commits atomic (one change per commit)
2. Test before pushing

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
1. Merge your feature/release branch into `main`
2. Create the tag on `main` pointing to the merge commit
3. Push the tag to remote

```bash
# After merging to main
git checkout main
git pull
git tag -a v1.1.0 -m "Release v1.1.0: description of changes"
git push origin v1.1.0
```
