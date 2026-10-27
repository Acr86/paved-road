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

compliant_inference := json.patch(compliant_deployment, [
	{"op": "replace", "path": "/metadata/name", "value": "similarity-search"},
	{"op": "add", "path": "/spec/template/metadata", "value": {
		"labels": {"pavedroad.dev/workload": "inference"},
		"annotations": {"pavedroad.dev/model": "hashing@v1"},
	}},
	{"op": "add", "path": "/spec/template/spec/containers/0/startupProbe", "value": {"httpGet": {"path": "/readyz", "port": "http"}}},
	{"op": "add", "path": "/spec/template/spec/containers/0/readinessProbe", "value": {"httpGet": {"path": "/readyz", "port": "http"}}},
])

test_compliant_inference_workload_passes if {
	count(deny) == 0 with input as compliant_inference
}

test_inference_rules_do_not_apply_to_plain_services if {
	# compliant_deployment has no startupProbe and no model annotation — and must still pass.
	count(deny) == 0 with input as compliant_deployment
}

test_inference_without_startup_probe_is_denied if {
	bad := json.patch(compliant_inference, [{
		"op": "remove",
		"path": "/spec/template/spec/containers/0/startupProbe",
	}])
	some msg in deny with input as bad
	contains(msg, "startupProbe")
}

test_inference_without_readiness_probe_is_denied if {
	bad := json.patch(compliant_inference, [{
		"op": "remove",
		"path": "/spec/template/spec/containers/0/readinessProbe",
	}])
	some msg in deny with input as bad
	contains(msg, "readinessProbe")
}

test_inference_without_model_provenance_is_denied if {
	bad := json.patch(compliant_inference, [{
		"op": "remove",
		"path": "/spec/template/metadata/annotations",
	}])
	some msg in deny with input as bad
	contains(msg, "pavedroad.dev/model")
}
