# MongoDB Replica Set on ECS (Terraform)

This stack deploys a private MongoDB replica set on Amazon ECS with:
- 3 MongoDB nodes (`mongo-1`, `mongo-2`, `mongo-3`)
- 1 replica set (`rs0`) with automatic failover
- 1 EBS volume per node via ECS managed EBS volumes
- private DNS discovery using AWS Cloud Map
- no public IP assigned to tasks

## Architecture

- `aws_ecs_cluster`: dedicated MongoDB cluster.
- `aws_ecs_service` x3: one service per node, desired count = 1.
- `aws_ecs_task_definition` x3: custom MongoDB image with replica set bootstrap logic.
- `aws_service_discovery_private_dns_namespace`: private DNS namespace (`mongo.internal` by default).
- `aws_security_group`: traffic locked to Mongo port and approved source SG/CIDR.
- `aws_secretsmanager_secret`: stores root password and replica set key.

## Prerequisites

- Terraform >= 1.6
- AWS credentials with IAM rights for ECS, ECR, EC2, IAM, CloudWatch, Secrets Manager, Service Discovery
- Existing VPC, one public subnet for NAT, and private subnets (with NAT or VPC endpoints to reach ECR/CloudWatch)
- AWS CLI credentials configured
- MongoDB image built from `docker/mongodb-rs` (entrypoint enables auth + replica key)

## Deploy

1. Prepare Terraform variables:
```bash
cd infra/terraform/mongodb-ecs
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars
```

Required vars to check:
- `public_subnet_id`: subnet public (route Internet Gateway) for NAT.
- `private_subnet_ids`: private subnets used for AZ mapping.
- `mongo_image`: ECR image URI built with `ops/aws/build_push_mongodb_rs_image.sh`.

2. Configure remote state backend (S3 + optional DynamoDB lock):
```bash
cp backend.hcl.example backend.hcl
# edit backend.hcl, then export:
export TF_BACKEND_BUCKET="forecast-terraform-state-eu-west-1"
export TF_BACKEND_KEY="mongodb-ecs/prod/terraform.tfstate"
export TF_BACKEND_REGION="eu-west-1"
export TF_BACKEND_USE_LOCKFILE="true"
# optional legacy locking:
# export TF_BACKEND_DYNAMODB_TABLE="forecast-terraform-locks"
```

3. Apply Terraform:
```bash
bash ops/aws/deploy_mongodb_rs_terraform.sh
```

4. Read outputs:
```bash
terraform -chdir=infra/terraform/mongodb-ecs output
```

## Verify replica set

Use ECS Exec on `mongo-1` task:
```bash
aws ecs execute-command \
  --cluster <cluster-name> \
  --task <mongo-1-task-id> \
  --container mongodb \
  --interactive \
  --command "mongosh --quiet --eval 'rs.status().members.map(m => ({name:m.name,stateStr:m.stateStr}))'"
```

## Connection string

Output `mongodb_connection_string_template` gives the URI pattern.
Password is stored in Secrets Manager (`bootstrap_secret_arn`).

To test authenticated access, retrieve password from secret JSON key `root_password` and connect with:
`mongodb://admin:<password>@mongo-1.mongo.internal:27017,mongo-2.mongo.internal:27017,mongo-3.mongo.internal:27017/admin?replicaSet=rs0&authSource=admin`

## Notes

- Failover is provided by MongoDB replica set election, not by a load balancer.
- For stricter private networking, add VPC endpoints for ECR, Logs, Secrets Manager, and SSM.
- `mongo_image` must point to the custom image built from `docker/mongodb-rs`.
