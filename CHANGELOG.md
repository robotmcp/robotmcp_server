# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2025-01-25

### Added
- CLI commands for module management: `add`, `remove`, `list`, `list-tools`, `update`, `repair`
- `update` command to update all MCP server modules to their latest commits
- `repair` command to re-init missing or broken submodules (non-destructive)
- Git status display in `list` command (branch/commit, dirty state, untracked files)
- Module compatibility check at startup and in list commands
- Modules without integration support display as "not compatible"

## [2.0.0] - 2025-01-23

### Changed
- Major release with submodule integration architecture

## [1.18.0]

### Added
- Submodule auto-discovery - automatically find and register MCP tools from git submodules
- Submodule dependencies are auto-installed at startup
- Decoupled submodule configuration (submodules manage their own config via environment variables)

## [1.17.0]

### Added
- Enhanced `verify` command with comprehensive diagnostics (server, tunnel, DNS, connectivity)

## [1.16.2]

### Changed
- Use importlib.metadata for version (single source of truth from pyproject.toml)

## [1.16.1]

### Fixed
- SSE endpoint to support shared member access (consistent with /mcp)

## [1.16.0]

### Added
- Display version in CLI status output

## [1.15.0]

### Added
- Shared member access - users added via dashboard can now connect to shared MCP servers

## [1.14.0]

### Changed
- **BREAKING**: Change default port from 8000 to 8766. Existing tunnels must be recreated with `robotmcp-server logout && robotmcp-server`

## [1.13.0]

### Added
- JWT tokens for stateless OAuth (tokens survive server restarts)
- Endpoint compatibility documentation

## [1.12.0]

### Changed
- Supabase centralized logging (replaces CloudWatch for security)

## [1.11.0]

### Added
- AWS CloudWatch logging integration with JSON structured logs

## [1.10.0]

### Added
- Comprehensive INFO-level logging for all MCP server activities

## [1.9.0]

### Added
- Secure POST-based CLI login
- Claude theme for OAuth pages

### Fixed
- WSL browser opening

## [1.8.0]

### Added
- OAuth templates
- CLI improvements

## [1.7.0]

### Added
- Cloudflare tunnel integration

## [1.0.0]

### Added
- Initial release with OAuth 2.1 and Streamable HTTP
