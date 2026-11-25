"""
Shared settings and helpers for deploy.py and destroy.py.
Every AWS resource created by these scripts carries the tag Project=restaurant-review,
and destroy.py only ever touches resources with that tag. Your other lab work is safe.
"""
import boto3

PROJECT = "restaurant-review"
TAGS = {"Project": PROJECT, "ManagedBy": "deploy.py"}

DEFAULT_REGION = "us-east-1"
KEY_NAME = "rr-project-key"
SG_NAME = "rr-web-sg"
INSTANCE_NAME = "rr-server"
EIP_NAME = "rr-server-ip"
PARAM_PREFIX = "/restaurant-review/prod"
INSTANCE_PROFILE = "LabInstanceProfile"      # the profile AWS Academy gives us (role LabRole)
CONTEXT_ROOT = "RestaurantReviewAPI"          # the app lives at http://IP/RestaurantReviewAPI/
GLASSFISH_VERSION = "8.0.4"
MYSQL_CONNECTOR_VERSION = "8.4.0"
KEEP_WARS = 10                                # old WAR files kept in S3 for rollbacks


def make_session(profile, region):
    return boto3.Session(profile_name=profile, region_name=region)


def account_id(session):
    return session.client("sts").get_caller_identity()["Account"]


def bucket_name(session, region):
    # S3 names are global, so the account id makes ours unique
    return f"{PROJECT}-{account_id(session)}-{region}"


def tag_list(name=None):
    tags = [{"Key": k, "Value": v} for k, v in TAGS.items()]
    if name:
        tags.append({"Key": "Name", "Value": name})
    return tags


def tag_spec(resource_type, name):
    return {"ResourceType": resource_type, "Tags": tag_list(name)}


def project_filter():
    return {"Name": "tag:Project", "Values": [PROJECT]}


def find_instances(ec2, states=("pending", "running", "stopping", "stopped")):
    reservations = ec2.describe_instances(Filters=[
        project_filter(),
        {"Name": "tag:Name", "Values": [INSTANCE_NAME]},
        {"Name": "instance-state-name", "Values": list(states)},
    ])["Reservations"]
    return [i for r in reservations for i in r["Instances"]]


def find_addresses(ec2):
    return ec2.describe_addresses(Filters=[project_filter()])["Addresses"]
