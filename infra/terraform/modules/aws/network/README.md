# aws/network

AWS mirror of the GCP network module, with the same conceptual contract: one VPC, private and public subnets spread across a configurable number of availability zones, a single NAT gateway for private egress, VPC flow logs shipped to CloudWatch, and the default security group pinned closed. It is the network substrate every other AWS module in this repository expects to plug into: workloads consume `private_subnet_ids`, edge components (load balancers) consume `public_subnet_ids`.

## Usage

```hcl
module "network" {
  source = "../../modules/aws/network"

  name_prefix             = "platform-staging"
  vpc_cidr                = "10.20.0.0/16"
  az_count                = 2
  flow_log_retention_days = 30
}

module "service" {
  source = "../../modules/aws/service"

  subnet_ids = module.network.private_subnet_ids
  # ...
}
```

## Inputs

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `name_prefix` | `string` | — | Prefix for every resource name and Name tag. |
| `vpc_cidr` | `string` | — | VPC IPv4 CIDR; prefix must be /16–/24. Subnets get 4 extra prefix bits. |
| `az_count` | `number` | `2` | AZ spread (1–3); one private + one public subnet per AZ. |
| `flow_log_retention_days` | `number` | `30` | CloudWatch retention for flow logs (must be a CloudWatch-supported value). |

## Outputs

| Name | Description |
|------|-------------|
| `vpc_id` | ID of the VPC. |
| `private_subnet_ids` | Private subnet IDs, ordered by AZ. |
| `public_subnet_ids` | Public subnet IDs, ordered by AZ. |
| `nat_gateway_id` | ID of the single NAT gateway. |

## Opinions

- **Workloads live in private subnets only.** Public subnets exist for the NAT gateway and load balancers, nothing else. Even there, `map_public_ip_on_launch` is off: anything that needs a public address has to ask for one explicitly, so a public IP is always a reviewable line in a diff, never an accident.
- **The default security group is intentionally bricked.** `aws_default_security_group` is declared with zero ingress and zero egress rules, which strips AWS's permissive defaults and reverts any out-of-band edits on the next apply. Anything attached to it can talk to nothing, which surfaces "forgot to assign a security group" as an immediate, loud failure instead of silent open access.
- **One NAT gateway until traffic costs justify three.** A NAT gateway costs roughly $32/month plus per-GB processing, so per-AZ NAT triples a fixed cost most environments never need. The accepted trade-offs are cross-AZ data charges for egress from the other AZs and the loss of private-subnet egress if the NAT's AZ goes down (in-VPC and inbound-via-LB traffic is unaffected). When egress volume or availability requirements outgrow this, the migration is mechanical: per-AZ NAT gateways plus per-AZ private route tables — the single private route table in this module is the only thing that changes shape.
- **Flow logs are not optional.** Every VPC ships ALL-traffic flow logs to CloudWatch with enforced retention and a least-privilege IAM role scoped to its own log group. You can tune how long to keep them; you cannot turn them off.
- **Subnet numbering leaves room to grow.** The cidrsubnet layout reserves index gaps between the private and public ranges, so a future tier (for example an isolated data tier with no NAT route) slots in without renumbering existing subnets.
