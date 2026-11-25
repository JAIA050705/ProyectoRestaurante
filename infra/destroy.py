#!/usr/bin/env python3
"""
destroy.py - removes everything deploy.py created (and only that).

Only resources tagged Project=restaurant-review are touched. Anything else in
your lab account is left alone. It shows the plan first and asks for
confirmation (use --yes to skip the question).

    python destroy.py                 # keeps the SSH key
    python destroy.py --delete-key    # also deletes the key pair and the .pem
"""
import argparse
import os
import sys
import time

from botocore.exceptions import ClientError

import config

HERE = os.path.dirname(os.path.abspath(__file__))


def say(message):
    print(message, flush=True)


def code_of(error):
    return error.response["Error"]["Code"]


def main():
    parser = argparse.ArgumentParser(description="Remove the Restaurant Review resources from AWS")
    parser.add_argument("--region", default=config.DEFAULT_REGION)
    parser.add_argument("--profile", default=None)
    parser.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    parser.add_argument("--delete-key", action="store_true", help="also delete the SSH key pair and the .pem")
    parser.add_argument("--key-name", default=config.KEY_NAME)
    args = parser.parse_args()

    session = config.make_session(args.profile, args.region)
    ec2, s3, ssm, cw = (session.client(n) for n in ("ec2", "s3", "ssm", "cloudwatch"))
    bucket = config.bucket_name(session, args.region)

    instances = config.find_instances(ec2, states=["pending", "running", "stopping", "stopped"])
    addresses = config.find_addresses(ec2)
    groups = ec2.describe_security_groups(Filters=[config.project_filter()])["SecurityGroups"]
    alarms = [a["AlarmName"] for a in cw.describe_alarms(AlarmNamePrefix="rr-")["MetricAlarms"]]
    params = []
    for page in ssm.get_paginator("get_parameters_by_path").paginate(Path=config.PARAM_PREFIX, Recursive=True):
        params += [p["Name"] for p in page["Parameters"]]

    bucket_mine = False
    try:
        tags = s3.get_bucket_tagging(Bucket=bucket)["TagSet"]
        bucket_mine = {"Key": "Project", "Value": config.PROJECT} in tags
        if not bucket_mine:
            say(f"WARNING: bucket {bucket} exists but is not tagged Project={config.PROJECT}; it will NOT be touched.")
    except ClientError:
        pass

    say("This will delete:")
    for i in instances:
        say(f"  server        {i['InstanceId']} ({i['State']['Name']}) and its disks")
    for a in addresses:
        say(f"  Elastic IP    {a['PublicIp']}")
    for g in groups:
        say(f"  firewall      {g['GroupName']} ({g['GroupId']})")
    for a in alarms:
        say(f"  alarm         {a}")
    for p in params:
        say(f"  secret/param  {p}")
    if bucket_mine:
        say(f"  S3 bucket     {bucket} (WARs and database backups included)")
    if args.delete_key:
        say(f"  key pair      {args.key_name} and its .pem file")
    if not (instances or addresses or groups or alarms or params or bucket_mine or args.delete_key):
        say("  (nothing: everything is already removed)")
        return

    if not args.yes and input("\nType 'yes' to continue: ").strip().lower() != "yes":
        say("Cancelled. Nothing was deleted.")
        return

    if alarms:
        cw.delete_alarms(AlarmNames=alarms)
        say("alarms deleted")

    if instances:
        ids = [i["InstanceId"] for i in instances]
        ec2.terminate_instances(InstanceIds=ids)
        say("terminating the server...")
        ec2.get_waiter("instance_terminated").wait(InstanceIds=ids)
        say("server terminated")

    for a in addresses:
        for _ in range(10):
            try:
                ec2.release_address(AllocationId=a["AllocationId"])
                say(f"Elastic IP {a['PublicIp']} released")
                break
            except ClientError as error:
                if code_of(error) not in ("InvalidIPAddress.InUse", "AuthFailure"):
                    raise
                time.sleep(5)

    for g in groups:
        for _ in range(12):
            try:
                ec2.delete_security_group(GroupId=g["GroupId"])
                say(f"firewall {g['GroupName']} deleted")
                break
            except ClientError as error:
                if code_of(error) != "DependencyViolation":
                    raise
                time.sleep(5)
        else:
            say(f"could not delete {g['GroupName']} yet; run destroy.py again in a minute")

    for i in range(0, len(params), 10):
        ssm.delete_parameters(Names=params[i:i + 10])
    if params:
        say("secrets and parameters deleted")

    if bucket_mine:
        for page in s3.get_paginator("list_object_versions").paginate(Bucket=bucket):
            items = [{"Key": o["Key"], "VersionId": o["VersionId"]}
                     for o in page.get("Versions", []) + page.get("DeleteMarkers", [])]
            if items:
                s3.delete_objects(Bucket=bucket, Delete={"Objects": items})
        s3.delete_bucket(Bucket=bucket)
        say("S3 bucket emptied and deleted")

    if args.delete_key:
        ec2.delete_key_pair(KeyName=args.key_name)
        pem = os.path.join(HERE, f"{args.key_name}.pem")
        if os.path.exists(pem):
            os.remove(pem)
        say("key pair deleted")

    say("\nDone. The lab account has no restaurant-review resources left.")


if __name__ == "__main__":
    try:
        main()
    except ClientError as error:
        say(f"AWS answered with an error: {code_of(error)}: {error.response['Error'].get('Message', '')}")
        sys.exit(1)
