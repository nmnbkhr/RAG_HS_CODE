# Phase 5: Infrastructure - Requirements

## Scope

Production-ready infrastructure for the RAG_HS_CODE application using the current
conda/WSL environment. Docker is documented as a future recommendation only.

## Deliverables

### 5.1 Unified Test Runner (CRITICAL)
- Single command to run all phase tests with coverage reporting
- Per-phase and aggregate statistics
- JUnit XML output for CI integration
- Coverage threshold enforcement (90%+)

### 5.2 CI/CD Pipeline - GitHub Actions (HIGH)
- Automated test execution on push/PR
- Conda environment caching
- Coverage reporting
- Branch protection configuration generator

### 5.3 Code Consolidation - Unified Configuration (HIGH)
- Centralized app configuration (constants, paths, env vars)
- Environment variable validation at startup
- Path resolution across WSL/native
- Single source of truth for all settings

### 5.4 Docker Containerization (PARKED)
- **Status:** Documented as recommendation only
- **Reason:** Current conda/WSL environment is the target runtime
- **Recommendation:** See DOCKER_RECOMMENDATIONS.md when ready to containerize

### 5.5 Health Check & Monitoring (MEDIUM)
- Dependency verification (all required packages present)
- External service reachability (WEBOC, NBP, OpenAI)
- File system checks (FAISS index, PDF, .env)
- Conda environment validation
- Structured health report for debugging

### 5.6 Environment Manager (MEDIUM)
- Validates current conda environment against requirements
- Detects missing packages and version mismatches
- Generates updated environment.yml from actual installs
- WSL-specific path handling

## Acceptance Criteria
- [ ] Single command runs all 529+ tests across all phases
- [ ] GitHub Actions workflow validates on push
- [ ] Health check reports system readiness
- [ ] All configuration in one place
- [ ] Environment setup is reproducible
- [ ] 90%+ coverage on Phase 5 modules
