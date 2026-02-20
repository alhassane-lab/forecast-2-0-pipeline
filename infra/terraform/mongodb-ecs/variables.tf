variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-1"
}

variable "project_name" {
  description = "Project prefix for resource names"
  type        = string
  default     = "forecast"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "vpc_id" {
  description = "VPC id where ECS services run"
  type        = string
}

variable "public_subnet_id" {
  description = "Public subnet id used to place the NAT gateway"
  type        = string
}

variable "private_subnet_ids" {
  description = "Existing private subnet ids used for AZ mapping of dedicated MongoDB subnets"
  type        = list(string)
}

variable "mongo_private_subnet_cidrs" {
  description = "CIDRs for dedicated private MongoDB subnets (one per AZ/subnet id)"
  type        = list(string)
  default = [
    "172.31.48.0/24",
    "172.31.49.0/24",
    "172.31.50.0/24"
  ]
}

variable "namespace_name" {
  description = "Cloud Map private DNS namespace"
  type        = string
  default     = "mongo.internal"
}

variable "mongo_port" {
  description = "MongoDB port"
  type        = number
  default     = 27017
}

variable "replica_set_name" {
  description = "MongoDB replica set name"
  type        = string
  default     = "rs0"
}

variable "task_cpu" {
  description = "CPU units per MongoDB ECS task"
  type        = number
  default     = 1024
}

variable "task_memory" {
  description = "Memory (MiB) per MongoDB ECS task"
  type        = number
  default     = 2048
}

variable "ebs_size_gb" {
  description = "EBS volume size in GB per MongoDB node"
  type        = number
  default     = 50
}

variable "ebs_volume_type" {
  description = "EBS volume type"
  type        = string
  default     = "gp3"
}

variable "ebs_iops" {
  description = "EBS iops for gp3"
  type        = number
  default     = 3000
}

variable "ebs_throughput" {
  description = "EBS throughput for gp3"
  type        = number
  default     = 125
}

variable "kms_key_id" {
  description = "Optional KMS key arn/id for EBS encryption"
  type        = string
  default     = null
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to reach MongoDB"
  type        = list(string)
  default     = []
}

variable "allowed_security_group_ids" {
  description = "Security groups allowed to reach MongoDB"
  type        = list(string)
  default     = []
}

variable "root_username" {
  description = "MongoDB root username"
  type        = string
  default     = "admin"
}

variable "mongod_extra_args" {
  description = "Optional extra mongod args"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Additional tags"
  type        = map(string)
  default     = {}
}

variable "mongo_image" {
  description = "MongoDB container image used by ECS tasks"
  type        = string
}

variable "enable_backups" {
  description = "Enable AWS Backup plan for MongoDB volumes"
  type        = bool
  default     = true
}

variable "backup_schedule" {
  description = "Backup schedule expression (AWS cron syntax)"
  type        = string
  default     = "cron(0 3 ? * * *)"
}

variable "backup_start_window_minutes" {
  description = "Backup start window in minutes"
  type        = number
  default     = 60
}

variable "backup_completion_window_minutes" {
  description = "Backup completion window in minutes"
  type        = number
  default     = 180
}

variable "backup_cold_storage_after_days" {
  description = "Days before moving backups to cold storage"
  type        = number
  default     = 30
}

variable "backup_delete_after_days" {
  description = "Days before deleting backups"
  type        = number
  default     = 180
}

variable "enable_monitoring" {
  description = "Enable CloudWatch alarms and SNS notifications"
  type        = bool
  default     = true
}

variable "alarm_notification_emails" {
  description = "Email addresses subscribed to MongoDB alarms"
  type        = list(string)
  default     = []
}

variable "ecs_cpu_high_threshold" {
  description = "CPU utilization threshold for ECS service high-usage alarm"
  type        = number
  default     = 85
}

variable "ecs_memory_high_threshold" {
  description = "Memory utilization threshold for ECS service high-usage alarm"
  type        = number
  default     = 85
}

variable "ecs_running_task_minimum" {
  description = "Minimum expected running task count per MongoDB ECS service"
  type        = number
  default     = 1
}

variable "mongodb_error_log_alarm_threshold" {
  description = "Number of MongoDB error/fatal log events per 5 min before alarm"
  type        = number
  default     = 5
}
