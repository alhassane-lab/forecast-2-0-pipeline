aws_region   = "eu-west-1"
project_name = "forecast"
environment  = "prod"

vpc_id = "vpc-0bda51e6099e8b061"
# Must be a PUBLIC subnet (route to Internet Gateway) for NAT placement.
public_subnet_id = "subnet-01ec17ee34fdbcbf6"
private_subnet_ids = [
  "subnet-01ec17ee34fdbcbf6",
  "subnet-0403a7c24fb649b8c",
  "subnet-0631d4f7da0f7a822"
]

namespace_name   = "mongo.internal"
mongo_image      = "052443862943.dkr.ecr.eu-west-1.amazonaws.com/forecast-mongodb-rs:6.0-rs"
replica_set_name = "rs0"
root_username    = "admin"

allowed_security_group_ids = [
  "sg-062056db10833656d",
  "sg-044a64ffb823f313d"
]

allowed_cidr_blocks = []

task_cpu        = 1024
task_memory     = 2048
ebs_size_gb     = 50
ebs_volume_type = "gp3"
ebs_iops        = 3000
ebs_throughput  = 125

kms_key_id = null

tags = {
  Owner = "data-engineering"
}
