package main

import rego.v1

compliant_deployment := {
	"kind": "Deployment",
	"metadata": {"name": "fx-rates"},
	"spec": {"template": {"spec": {
		"securityContext": {"runAsNonRoot": true},
		"containers": [{
			"name": "app",
			"image": "ghcr.io/acr86/paved-road/fx-rates:main",
			"resources": {
				"requests": {"cpu": "25m", "memory": "64Mi"},
				"limits": {"cpu": "250m", "memory": "256Mi"},
			},
			"securityContext": {
				"allowPrivilegeEscalation": false,
				"readOnlyRootFilesystem": true,
				"capabilities": {"drop": ["ALL"]},
			},
		}],
	}}},
}

test_compliant_workload_passes if {
	count(deny) == 0 with input as compliant_deployment
}

test_missing_limits_is_denied if {
	bad := json.patch(compliant_deployment, [{
		"op": "remove",
		"path": "/spec/template/spec/containers/0/resources/limits",
	}])
	some msg in deny with input as bad
	contains(msg, "resources.limits")
}

test_root_user_is_denied if {
	bad := json.patch(compliant_deployment, [{
		"op": "replace",
		"path": "/spec/template/spec/securityContext/runAsNonRoot",
		"value": false,
	}])
	some msg in deny with input as bad
	contains(msg, "runAsNonRoot")
}

test_latest_tag_is_denied if {
	bad := json.patch(compliant_deployment, [{
		"op": "replace",
		"path": "/spec/template/spec/containers/0/image",
		"value": "ghcr.io/acr86/paved-road/fx-rates:latest",
	}])
	some msg in deny with input as bad
	contains(msg, ":latest")
}

test_foreign_registry_is_denied if {
	bad := json.patch(compliant_deployment, [{
		"op": "replace",
		"path": "/spec/template/spec/containers/0/image",
		"value": "docker.io/library/nginx:1.27",
	}])
	some msg in deny with input as bad
	contains(msg, "outside the platform registry")
}

test_missing_capability_drop_is_denied if {
	bad := json.patch(compliant_deployment, [{
		"op": "remove",
		"path": "/spec/template/spec/containers/0/securityContext/capabilities",
	}])
	some msg in deny with input as bad
	contains(msg, "drop ALL")
}

test_cronjob_pod_spec_is_inspected if {
	cronjob := {
		"kind": "CronJob",
		"metadata": {"name": "preview-janitor"},
		"spec": {"jobTemplate": {"spec": {"template": {"spec": {
			"securityContext": {"runAsNonRoot": true},
			"containers": [{
				"name": "janitor",
				"image": "ghcr.io/acr86/paved-road/platform-cli:main",
				"resources": {"requests": {"cpu": "10m"}},
				"securityContext": {
					"allowPrivilegeEscalation": false,
					"readOnlyRootFilesystem": true,
					"capabilities": {"drop": ["ALL"]},
				},
			}],
		}}}}},
	}
	some msg in deny with input as cronjob
	contains(msg, "resources.limits")
}
