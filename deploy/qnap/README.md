# QNAP Deploy Requests

`request.env` is a Git-backed handoff file for the QNAP deploy poller.
It is created by `scripts/request_qnap_deploy.sh` and read by
`scripts/qnap_deploy_poller.sh` on the QNAP.

Do not put secrets in this directory. The request file contains only a commit
ref, addon module names, optional Odoo test tags, and public GitHub URLs.
