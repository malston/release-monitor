# Feature Request: Add JFrog Artifactory Support for Storing Release Artifacts

## 🚀 Problem Statement

Currently, the release monitor is designed specifically for storing release artifacts into an s3-compatible blob store. Adding Artifactory support would allow users to store artifacts in an Artifactory repository that is setup for image scanning and audit tracking which would allow users to adhere to Security Compliance Standards.

## 💡 Proposed Solution

Add support for Artifactory that allows users to store and monitor releases within from their Concourse pipeline:

1. Create a Concourse task or use an Artifactory Concourse Resource to store the artificts in Artifactory
2. Build a Docker container for running Artifactory locally
3. Add Artifactory specific examples
4. Update documentation with Artifactory instructions
