# Admission policies for every workload the platform renders. These run in
# CI (conftest over rendered kustomize output): a manifest that violates them
# never reaches a cluster, including preview environments. The policies are
# themselves unit-tested — see workloads_test.rego.
package main

import rego.v1

workload_kinds := {"Deployment", "StatefulSet", "Job"}

pod_spec := input.spec.template.spec if input.kind in workload_kinds

pod_spec := input.spec.jobTemplate.spec.template.spec if input.kind == "CronJob"

containers contains c if some c in pod_spec.containers

subject := sprintf("%s/%s", [input.kind, input.metadata.name])

# --- resource governance ----------------------------------------------------

deny contains msg if {
	some c in containers
	not c.resources.limits
	msg := sprintf("%s: container %q must declare resources.limits — unbounded containers starve neighbors", [subject, c.name])
}

deny contains msg if {
	some c in containers
	not c.resources.requests
	msg := sprintf("%s: container %q must declare resources.requests — the scheduler cannot place what it cannot size", [subject, c.name])
}

# --- runtime hardening --------------------------------------------------------

deny contains msg if {
	count(containers) > 0
	not pod_spec.securityContext.runAsNonRoot == true
	msg := sprintf("%s: pod securityContext must set runAsNonRoot: true", [subject])
}

deny contains msg if {
	some c in containers
	not c.securityContext.allowPrivilegeEscalation == false
	msg := sprintf("%s: container %q must set allowPrivilegeEscalation: false", [subject, c.name])
}

deny contains msg if {
	some c in containers
	caps := object.get(c, ["securityContext", "capabilities", "drop"], [])
	not "ALL" in caps
	msg := sprintf("%s: container %q must drop ALL capabilities", [subject, c.name])
}

deny contains msg if {
	some c in containers
	not c.securityContext.readOnlyRootFilesystem == true
	msg := sprintf("%s: container %q must set readOnlyRootFilesystem: true", [subject, c.name])
}

# --- image provenance ---------------------------------------------------------

deny contains msg if {
	some c in containers
	endswith(c.image, ":latest")
	msg := sprintf("%s: container %q pins :latest — deploys must be reproducible", [subject, c.name])
}

deny contains msg if {
	some c in containers
	not contains(c.image, ":")
	msg := sprintf("%s: container %q has no image tag — deploys must be reproducible", [subject, c.name])
}

deny contains msg if {
	some c in containers
	not startswith(c.image, "ghcr.io/acr86/paved-road/")
	msg := sprintf("%s: container %q image %q is outside the platform registry", [subject, c.name, c.image])
}
