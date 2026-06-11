output "vpc_id" {
  description = "ID of the VPC."
  value       = aws_vpc.this.id
}

output "private_subnet_ids" {
  description = "IDs of the private subnets, ordered by availability zone. Workloads belong here."
  value       = aws_subnet.private[*].id
}

output "public_subnet_ids" {
  description = "IDs of the public subnets, ordered by availability zone. Intended for load balancers and the NAT gateway only."
  value       = aws_subnet.public[*].id
}

output "nat_gateway_id" {
  description = "ID of the single NAT gateway serving all private subnets."
  value       = aws_nat_gateway.this.id
}
