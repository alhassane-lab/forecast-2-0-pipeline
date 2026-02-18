locals {
  name_prefix = "${var.project_name}-${var.environment}-mongo"

  common_tags = merge(
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
      Component   = "mongodb-replica-set"
    },
    var.tags
  )

  nodes = {
    mongo1 = { service_name = "mongo-1" }
    mongo2 = { service_name = "mongo-2" }
    mongo3 = { service_name = "mongo-3" }
  }

  mongo_members         = join(",", [for node in local.nodes : "${node.service_name}.${var.namespace_name}:${var.mongo_port}"])
  mongo_task_subnet_ids = aws_subnet.mongo_private[*].id
}

data "aws_vpc" "selected" {
  id = var.vpc_id
}

data "aws_subnet" "private_source" {
  count = length(var.private_subnet_ids)
  id    = var.private_subnet_ids[count.index]
}

resource "aws_eip" "nat" {
  domain = "vpc"
  tags   = merge(local.common_tags, { Name = "${local.name_prefix}-nat-eip" })
}

resource "aws_nat_gateway" "mongo" {
  allocation_id = aws_eip.nat.id
  subnet_id     = var.public_subnet_id

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-nat" })
}

resource "aws_subnet" "mongo_private" {
  count             = length(var.private_subnet_ids)
  vpc_id            = var.vpc_id
  cidr_block        = var.mongo_private_subnet_cidrs[count.index]
  availability_zone = data.aws_subnet.private_source[count.index].availability_zone

  map_public_ip_on_launch = false

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-private-${count.index + 1}" })
}

resource "aws_route_table" "mongo_private" {
  vpc_id = var.vpc_id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.mongo.id
  }

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-private-rt" })
}

resource "aws_route_table_association" "mongo_private" {
  count          = length(aws_subnet.mongo_private)
  subnet_id      = aws_subnet.mongo_private[count.index].id
  route_table_id = aws_route_table.mongo_private.id
}

resource "aws_cloudwatch_log_group" "mongodb" {
  name              = "/ecs/${local.name_prefix}"
  retention_in_days = 30
  tags              = local.common_tags
}

resource "aws_security_group" "mongodb" {
  name        = "${local.name_prefix}-sg"
  description = "MongoDB replica set ECS security group"
  vpc_id      = var.vpc_id

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

resource "aws_security_group" "vpce" {
  name        = "${local.name_prefix}-vpce-sg"
  description = "VPC endpoints security group"
  vpc_id      = var.vpc_id

  ingress {
    description     = "HTTPS from MongoDB tasks"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.mongodb.id]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

resource "aws_vpc_endpoint" "interface" {
  for_each = toset([
    "com.amazonaws.${var.aws_region}.secretsmanager",
    "com.amazonaws.${var.aws_region}.logs",
    "com.amazonaws.${var.aws_region}.ecr.api",
    "com.amazonaws.${var.aws_region}.ecr.dkr"
  ])

  vpc_id              = var.vpc_id
  service_name        = each.value
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = local.mongo_task_subnet_ids
  security_group_ids  = [aws_security_group.vpce.id]

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-${replace(each.value, ".", "-")}" })
}

resource "aws_security_group_rule" "intra_replica" {
  type                     = "ingress"
  description              = "Replica set internode traffic"
  from_port                = var.mongo_port
  to_port                  = var.mongo_port
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.mongodb.id
  security_group_id        = aws_security_group.mongodb.id
}

resource "aws_security_group_rule" "from_cidrs" {
  for_each = toset(var.allowed_cidr_blocks)

  type              = "ingress"
  description       = "MongoDB from allowed CIDR"
  from_port         = var.mongo_port
  to_port           = var.mongo_port
  protocol          = "tcp"
  cidr_blocks       = [each.value]
  security_group_id = aws_security_group.mongodb.id
}

resource "aws_security_group_rule" "from_sgs" {
  for_each = toset(var.allowed_security_group_ids)

  type                     = "ingress"
  description              = "MongoDB from allowed security groups"
  from_port                = var.mongo_port
  to_port                  = var.mongo_port
  protocol                 = "tcp"
  source_security_group_id = each.value
  security_group_id        = aws_security_group.mongodb.id
}

resource "aws_service_discovery_private_dns_namespace" "mongo" {
  name        = var.namespace_name
  description = "Private namespace for MongoDB replica set"
  vpc         = var.vpc_id
  tags        = local.common_tags
}

resource "aws_service_discovery_service" "mongo" {
  for_each = local.nodes

  name = each.value.service_name

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.mongo.id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {
    failure_threshold = 1
  }

  tags = local.common_tags
}

resource "aws_iam_role" "task_execution" {
  name = "${local.name_prefix}-task-exec-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "task_execution_managed" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "task_execution_secrets" {
  name = "${local.name_prefix}-task-exec-secrets"
  role = aws_iam_role.task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "kms:Decrypt"
        ]
        Resource = [
          aws_secretsmanager_secret.mongo_bootstrap.arn,
          "*"
        ]
      }
    ]
  })
}

resource "aws_iam_role" "task" {
  name = "${local.name_prefix}-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role" "infrastructure" {
  name = "${local.name_prefix}-infra-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ecs.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "infrastructure_managed" {
  role       = aws_iam_role.infrastructure.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSInfrastructureRolePolicyForVolumes"
}

resource "random_password" "root_password" {
  length  = 24
  special = false
}

resource "random_password" "replica_key" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "mongo_bootstrap" {
  name_prefix = "${local.name_prefix}-bootstrap-"
  description = "MongoDB replica set bootstrap credentials"
  tags        = local.common_tags
}

resource "aws_secretsmanager_secret_version" "mongo_bootstrap" {
  secret_id = aws_secretsmanager_secret.mongo_bootstrap.id
  secret_string = jsonencode({
    root_password = random_password.root_password.result
    repl_key      = random_password.replica_key.result
  })
}

resource "aws_ecs_cluster" "mongo" {
  name = "${local.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = local.common_tags
}

resource "aws_ecs_task_definition" "mongo" {
  for_each = local.nodes

  family                   = "${local.name_prefix}-${each.value.service_name}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = tostring(var.task_cpu)
  memory                   = tostring(var.task_memory)
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = "mongodb"
      image     = var.mongo_image
      essential = true

      environment = [
        { name = "MONGO_PORT", value = tostring(var.mongo_port) },
        { name = "MONGO_DBPATH", value = "/data/db" },
        { name = "MONGO_REPLICA_SET", value = var.replica_set_name },
        { name = "MONGO_NODE_NAME", value = each.value.service_name },
        { name = "MONGO_MEMBERS", value = local.mongo_members },
        { name = "MONGO_ROOT_USERNAME", value = var.root_username },
        { name = "MONGOD_EXTRA_ARGS", value = var.mongod_extra_args }
      ]

      secrets = [
        { name = "MONGO_ROOT_PASSWORD", valueFrom = "${aws_secretsmanager_secret.mongo_bootstrap.arn}:root_password::" },
        { name = "MONGO_REPL_KEY", valueFrom = "${aws_secretsmanager_secret.mongo_bootstrap.arn}:repl_key::" }
      ]

      portMappings = [
        {
          containerPort = var.mongo_port
          hostPort      = var.mongo_port
          protocol      = "tcp"
        }
      ]

      mountPoints = [
        {
          sourceVolume  = "mongo-data"
          containerPath = "/data/db"
          readOnly      = false
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.mongodb.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = each.value.service_name
        }
      }
    }
  ])

  runtime_platform {
    cpu_architecture        = "X86_64"
    operating_system_family = "LINUX"
  }

  volume {
    name                = "mongo-data"
    configure_at_launch = true
  }

  tags = local.common_tags
}

resource "aws_ecs_service" "mongo" {
  for_each = local.nodes

  name                               = "${local.name_prefix}-${each.value.service_name}"
  cluster                            = aws_ecs_cluster.mongo.id
  task_definition                    = aws_ecs_task_definition.mongo[each.key].arn
  desired_count                      = 1
  launch_type                        = "FARGATE"
  platform_version                   = "LATEST"
  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100
  enable_execute_command             = true

  network_configuration {
    subnets          = local.mongo_task_subnet_ids
    security_groups  = [aws_security_group.mongodb.id]
    assign_public_ip = false
  }

  service_registries {
    registry_arn = aws_service_discovery_service.mongo[each.key].arn
  }

  volume_configuration {
    name = "mongo-data"

    managed_ebs_volume {
      role_arn         = aws_iam_role.infrastructure.arn
      size_in_gb       = var.ebs_size_gb
      volume_type      = var.ebs_volume_type
      iops             = var.ebs_iops
      throughput       = var.ebs_throughput
      encrypted        = true
      kms_key_id       = var.kms_key_id
      file_system_type = "xfs"

      tag_specifications {
        resource_type  = "volume"
        propagate_tags = "SERVICE"
      }
    }
  }

  tags = local.common_tags

  depends_on = [
    aws_iam_role_policy_attachment.task_execution_managed,
    aws_iam_role_policy_attachment.infrastructure_managed,
    aws_secretsmanager_secret_version.mongo_bootstrap
  ]
}
