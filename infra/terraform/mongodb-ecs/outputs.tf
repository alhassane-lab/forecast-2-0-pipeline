output "cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.mongo.name
}

output "mongodb_security_group_id" {
  description = "MongoDB security group"
  value       = aws_security_group.mongodb.id
}

output "mongodb_members" {
  description = "Replica set member endpoints"
  value       = [for node in local.nodes : "${node.service_name}.${var.namespace_name}:${var.mongo_port}"]
}

output "mongodb_connection_string_template" {
  description = "Connection string template with placeholder password"
  value       = "mongodb://${var.root_username}:<password>@${join(",", [for node in local.nodes : "${node.service_name}.${var.namespace_name}:${var.mongo_port}"])}/admin?replicaSet=${var.replica_set_name}&authSource=admin"
}

output "bootstrap_secret_arn" {
  description = "Secrets Manager secret containing root password and replica key"
  value       = aws_secretsmanager_secret.mongo_bootstrap.arn
  sensitive   = true
}

output "backup_vault_name" {
  description = "AWS Backup vault name for MongoDB volumes"
  value       = var.enable_backups ? aws_backup_vault.mongodb[0].name : null
}

output "backup_plan_id" {
  description = "AWS Backup plan ID for MongoDB volumes"
  value       = var.enable_backups ? aws_backup_plan.mongodb[0].id : null
}

output "alarm_topic_arn" {
  description = "SNS topic ARN used for MongoDB alarms"
  value       = var.enable_monitoring ? aws_sns_topic.mongodb_alerts[0].arn : null
}
