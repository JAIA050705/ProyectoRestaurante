#!/usr/bin/env python3
"""
preflight.py - Phase 0 of the AWS deployment.

Checks what the AWS account (for example an AWS Academy Learner Lab) lets us
do BEFORE we design anything on top of it. It answers:
  * Do the credentials work, and in which region?
  * Can we launch EC2 instances, use the LabInstanceProfile, allocate IPs?
  * Are S3, Systems Manager (Parameter Store), CloudWatch and RDS available?
  * What already exists in the account (so we do not collide with it)?

By default it is READ-ONLY: it only lists things and uses the EC2 "DryRun"
mode (AWS checks the permission and answers, but creates nothing).

With --write-tests it also creates and immediately deletes a few tiny
throw-away resources (an S3 bucket, a parameter, an alarm, a security group,
an Elastic IP) to prove that writing really works.

Usage:
    python preflight.py --region us-east-1
    python preflight.py --region us-east-1 --write-tests
Needs:  pip install boto3
"""
import argparse
import json
import sys
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError

OK, WARN, FAIL, SKIP = "OK", "WARN", "FAIL", "SKIP"
DENIED_CODES = {
    "AccessDenied", "AccessDeniedException", "UnauthorizedOperation",
    "UnauthorizedAccess", "OperationNotPermitted", "AuthorizationError",
}
CREDENTIAL_CODES = {
    "ExpiredToken", "ExpiredTokenException", "InvalidClientTokenId",
    "AuthFailure", "SignatureDoesNotMatch", "InvalidToken",
}
ICONS = {OK: "[ OK ]", WARN: "[WARN]", FAIL: "[FAIL]", SKIP: "[ -- ]"}

results = []          # every line of the report
facts = {}            # values that later checks reuse


def record(group, name, status, detail=""):
    results.append({"group": group, "check": name, "status": status, "detail": detail})
    print(f"{ICONS[status]} {name}" + (f"  ->  {detail}" if detail else ""))


def check(group, name, func):
    """Runs one check. func returns (status, detail). Errors become FAIL or WARN."""
    try:
        status, detail = func()
    except ClientError as error:
        code = error.response["Error"]["Code"]
        message = error.response["Error"].get("Message", "")[:110]
        if code in CREDENTIAL_CODES:
            status, detail = FAIL, f"credentials problem ({code}). Start the lab again and copy new credentials"
        elif code in DENIED_CODES:
            status, detail = FAIL, f"denied by the account ({code})"
        else:
            status, detail = WARN, f"{code}: {message}"
    except BotoCoreError as error:
        status, detail = WARN, f"{type(error).__name__}: {str(error)[:110]}"
    except Exception as error:  # a bug in this script must not hide the other checks
        status, detail = WARN, f"unexpected {type(error).__name__}: {str(error)[:110]}"
    record(group, name, status, detail)
    return status


def dry_run(call, **kwargs):
    """EC2 DryRun: DryRunOperation means 'you would be allowed'."""
    try:
        call(DryRun=True, **kwargs)
    except ClientError as error:
        if error.response["Error"]["Code"] == "DryRunOperation":
            return
        raise


def mask_account(account):
    return "****" + account[-4:]


# ----------------------------------------------------------------- the checks

def check_identity(session):
    def identity():
        data = session.client("sts").get_caller_identity()
        facts["account"] = data["Account"]
        arn = data["Arn"]
        parts = arn.split(":")[-1].split("/")          # role/<role-name>/<session>
        role = parts[1] if len(parts) > 1 else parts[0]
        facts["role"] = role
        facts["learner_lab"] = role == "voclabs"
        kind = "AWS Academy Learner Lab" if facts["learner_lab"] else "regular account/role"
        return OK, f"account {mask_account(data['Account'])}, role '{role}' ({kind})"
    return check("Identity", "Credentials work (STS)", identity)


def check_region(session, region):
    def zones():
        ec2 = session.client("ec2", region_name=region)
        names = [z["ZoneName"] for z in ec2.describe_availability_zones()["AvailabilityZones"]
                 if z["State"] == "available"]
        facts["zones"] = names
        return OK, f"{region} has {len(names)} available zones: {', '.join(names)}"
    return check("Identity", f"Region {region} is usable", zones)


def check_ec2(session, region):
    ec2 = session.client("ec2", region_name=region)
    ssm = session.client("ssm", region_name=region)
    group = "EC2"

    def vpc():
        vpcs = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])["Vpcs"]
        if not vpcs:
            return WARN, "no default VPC (the deploy script would have to create networking)"
        facts["vpc_id"] = vpcs[0]["VpcId"]
        subnets = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [facts["vpc_id"]]}])["Subnets"]
        facts["subnet_id"] = subnets[0]["SubnetId"] if subnets else None
        return OK, f"default VPC {facts['vpc_id']} with {len(subnets)} subnets"
    check(group, "Default VPC and subnets", vpc)

    def types():
        wanted = ["t3.micro", "t3.small", "t3.medium", "t4g.small", "t4g.medium"]
        offered = ec2.describe_instance_type_offerings(
            LocationType="region", Filters=[{"Name": "instance-type", "Values": wanted}]
        )["InstanceTypeOfferings"]
        names = sorted(o["InstanceType"] for o in offered)
        facts["types"] = names
        missing = [t for t in wanted if t not in names]
        status = OK if "t3.small" in names else WARN
        return status, f"offered: {', '.join(names) or 'none'}" + (f" | not listed: {', '.join(missing)}" if missing else "")
    check(group, "Instance types we may use", types)

    def ami(arch):
        def inner():
            name = f"/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-{arch}"
            value = ssm.get_parameter(Name=name)["Parameter"]["Value"]
            facts["ami_" + arch] = value
            return OK, f"Amazon Linux 2023 {arch}: {value}"
        return inner
    for arch in ("x86_64", "arm64"):
        check(group, f"Latest Amazon Linux 2023 AMI ({arch})", ami(arch))

    def keys():
        pairs = [k["KeyName"] for k in ec2.describe_key_pairs()["KeyPairs"]]
        facts["key_pairs"] = pairs
        return OK, f"existing key pairs: {', '.join(pairs) or 'none'}"
    check(group, "Key pairs", keys)

    # Permission checks that create nothing
    image = facts.get("ami_x86_64")
    subnet = facts.get("subnet_id")
    if image and subnet:
        base = dict(ImageId=image, InstanceType="t3.small", MinCount=1, MaxCount=1, SubnetId=subnet)

        def launch():
            dry_run(ec2.run_instances, **base)
            return OK, "launch of a t3.small would be allowed"
        check(group, "May launch an instance (DryRun)", launch)

        def launch_profile():
            dry_run(ec2.run_instances, IamInstanceProfile={"Name": "LabInstanceProfile"}, **base)
            facts["profile_ok"] = True
            return OK, "launch with the LabInstanceProfile would be allowed"
        check(group, "May launch with LabInstanceProfile (DryRun)", launch_profile)
    else:
        record(group, "May launch an instance (DryRun)", SKIP, "missing AMI or subnet from the previous checks")

    def sg():
        dry_run(ec2.create_security_group, GroupName="rr-preflight", Description="preflight",
                VpcId=facts["vpc_id"])
        return OK, "creating a security group would be allowed"
    if facts.get("vpc_id"):
        check(group, "May create a security group (DryRun)", sg)

    def eip():
        dry_run(ec2.allocate_address, Domain="vpc")
        return OK, "allocating an Elastic IP would be allowed"
    check(group, "May allocate an Elastic IP (DryRun)", eip)

    def vol():
        dry_run(ec2.create_volume, AvailabilityZone=facts["zones"][0], Size=8, VolumeType="gp3")
        return OK, "creating an EBS volume would be allowed"
    if facts.get("zones"):
        check(group, "May create an EBS volume (DryRun)", vol)

    # What already exists
    def inventory():
        reservations = ec2.describe_instances(Filters=[{
            "Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]}])["Reservations"]
        instances = [i for r in reservations for i in r["Instances"]]
        eips = ec2.describe_addresses()["Addresses"]
        volumes = ec2.describe_volumes()["Volumes"]
        return OK, f"{len(instances)} instances, {len(eips)} Elastic IPs, {len(volumes)} volumes already in this region"
    check(group, "Existing resources (to avoid surprises)", inventory)


def check_s3(session, region):
    def buckets():
        names = [b["Name"] for b in session.client("s3", region_name=region).list_buckets()["Buckets"]]
        return OK, f"{len(names)} existing buckets"
    check("S3", "List buckets", buckets)


def check_ssm(session, region):
    def params():
        data = session.client("ssm", region_name=region).describe_parameters(MaxResults=5)["Parameters"]
        return OK, f"Parameter Store reachable ({len(data)} parameters shown)"
    check("Parameter Store", "Read Parameter Store", params)


def check_iam(session):
    def profile():
        data = session.client("iam").get_instance_profile(InstanceProfileName="LabInstanceProfile")
        roles = [r["RoleName"] for r in data["InstanceProfile"]["Roles"]]
        facts["profile_role"] = roles
        return OK, f"LabInstanceProfile exists with role(s): {', '.join(roles)}"
    status = check("IAM", "LabInstanceProfile exists", profile)
    if status != OK and facts.get("learner_lab"):
        print("       (IAM read access can be blocked in the lab; the DryRun above is the real test)")


def check_cloudwatch(session, region):
    def alarms():
        session.client("cloudwatch", region_name=region).describe_alarms(MaxRecords=1)
        return OK, "CloudWatch reachable"
    check("CloudWatch", "Read alarms", alarms)


def check_rds(session, region):
    rds = session.client("rds", region_name=region)

    def instances():
        found = rds.describe_db_instances()["DBInstances"]
        return OK, f"RDS reachable, {len(found)} existing databases"
    check("RDS", "Read RDS", instances)

    def offer():
        options = rds.describe_orderable_db_instance_options(
            Engine="mysql", DBInstanceClass="db.t3.micro", MaxRecords=100)["OrderableDBInstanceOptions"]
        versions = sorted({o["EngineVersion"] for o in options})
        facts["rds_versions"] = versions
        status = OK if versions else WARN
        return status, f"MySQL on db.t3.micro, versions: {', '.join(versions[-5:]) or 'none'}"
    check("RDS", "MySQL db.t3.micro is offered", offer)


def check_pricing(session):
    def prices():
        session.client("pricing", region_name="us-east-1").describe_services(ServiceCode="AmazonEC2", MaxResults=1)
        return OK, "Price List API reachable (cost_report.py can use live prices)"
    check("Pricing", "Price List API", prices)


# ---------------------------------------------------- tiny create-and-delete tests

def write_tests(session, region):
    group = "Write tests"
    suffix = uuid.uuid4().hex[:8]

    def s3():
        client = session.client("s3", region_name=region)
        bucket = f"rr-preflight-{suffix}"
        args = {"Bucket": bucket}
        if region != "us-east-1":
            args["CreateBucketConfiguration"] = {"LocationConstraint": region}
        client.create_bucket(**args)
        try:
            client.put_object(Bucket=bucket, Key="test.txt", Body=b"hello")
            client.delete_object(Bucket=bucket, Key="test.txt")
        finally:
            client.delete_bucket(Bucket=bucket)
        return OK, "created a bucket, wrote and deleted an object, deleted the bucket"
    check(group, "S3 create / write / delete", s3)

    def ssm():
        client = session.client("ssm", region_name=region)
        name = f"/rr-preflight/{suffix}"
        client.put_parameter(Name=name, Value="secret-" + suffix, Type="SecureString")
        try:
            value = client.get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"]
            if value != "secret-" + suffix:
                return WARN, "stored value did not match"
        finally:
            client.delete_parameter(Name=name)
        facts["ssm_write"] = True
        return OK, "SecureString parameter created, read back and deleted"
    check(group, "Parameter Store SecureString", ssm)

    def alarm():
        client = session.client("cloudwatch", region_name=region)
        name = f"rr-preflight-{suffix}"
        client.put_metric_alarm(
            AlarmName=name, Namespace="AWS/EC2", MetricName="StatusCheckFailed_System",
            Dimensions=[{"Name": "InstanceId", "Value": "i-00000000000000000"}],
            Statistic="Maximum", Period=60, EvaluationPeriods=2, Threshold=1,
            ComparisonOperator="GreaterThanOrEqualToThreshold",
            AlarmActions=[f"arn:aws:automate:{region}:ec2:reboot"])
        client.delete_alarms(AlarmNames=[name])
        return OK, "alarm with a 'reboot instance' action created and deleted"
    check(group, "CloudWatch alarm with reboot action", alarm)

    ec2 = session.client("ec2", region_name=region)

    def security_group():
        group_id = ec2.create_security_group(GroupName=f"rr-preflight-{suffix}", Description="preflight test",
                                             VpcId=facts["vpc_id"])["GroupId"]
        ec2.delete_security_group(GroupId=group_id)
        return OK, "security group created and deleted"
    if facts.get("vpc_id"):
        check(group, "Security group create / delete", security_group)

    def elastic_ip():
        allocation = ec2.allocate_address(Domain="vpc")["AllocationId"]
        ec2.release_address(AllocationId=allocation)
        return OK, "Elastic IP allocated and released"
    check(group, "Elastic IP allocate / release", elastic_ip)


# ------------------------------------------------------------------- summary

def status_of(group, check_name):
    for item in results:
        if item["group"] == group and item["check"] == check_name:
            return item["status"]
    return None


def summary(did_write_tests):
    print("\n" + "=" * 64)
    print("WHAT THIS MEANS FOR THE PLAN")
    print("=" * 64)
    launch = status_of("EC2", "May launch an instance (DryRun)") == OK
    profile = status_of("EC2", "May launch with LabInstanceProfile (DryRun)") == OK
    eip = status_of("EC2", "May allocate an Elastic IP (DryRun)") == OK
    rds = status_of("RDS", "Read RDS") == OK
    s3 = status_of("S3", "List buckets") == OK
    ssm_read = status_of("Parameter Store", "Read Parameter Store") == OK
    pricing = status_of("Pricing", "Price List API") == OK

    def line(ok, good, bad):
        print(("  + " if ok else "  - ") + (good if ok else bad))

    line(launch, "Phase 1 is possible: EC2 can be launched by script.",
         "EC2 launch is NOT confirmed: stop here and send me this report.")
    line(profile, "The instance can use LabInstanceProfile (to read S3 and Parameter Store).",
         "LabInstanceProfile is not confirmed: secrets would travel in the user-data (weaker).")
    line(eip, "A fixed public IP (Elastic IP) is possible.",
         "No Elastic IP: the public address will change after each restart.")
    line(s3, "S3 can hold the WAR files and the database backups.",
         "S3 is not confirmed: the WAR would be copied with scp instead.")
    line(ssm_read, "Parameter Store is reachable for the secrets.",
         "Parameter Store not confirmed: the fallback is secrets in the user-data.")
    line(rds, "RDS is available: Phase 2 (database on RDS) is an option.",
         "RDS not available: the database stays on the EC2 instance.")
    line(pricing, "Live prices can be read for the cost report.",
         "No Price List API: the cost report will use fixed prices that I must verify.")
    if not did_write_tests:
        print("\nNext: run again with --write-tests to prove that creating things really works.")


def main():
    parser = argparse.ArgumentParser(description="Preflight checks for the AWS deployment")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--profile", default=None, help="AWS profile name (optional)")
    parser.add_argument("--write-tests", action="store_true",
                        help="also create and delete tiny throw-away resources")
    parser.add_argument("--json", default="preflight_report.json", help="where to save the report")
    args = parser.parse_args()

    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    print(f"Preflight in region {args.region}" + (" (with write tests)" if args.write_tests else " (read-only)"))
    print("-" * 64)

    if check_identity(session) != OK:
        print("\nStop: the identity could not be verified, so nothing else can be checked.")
        print("1) In AWS Academy press Start Lab, wait for the green dot, open AWS Details,")
        print("   and copy the credentials again (they change every session).")
        print("2) Check that your internet connection works and that 'aws sts get-caller-identity' answers.")
        sys.exit(1)

    check_region(session, args.region)
    check_ec2(session, args.region)
    check_iam(session)
    check_s3(session, args.region)
    check_ssm(session, args.region)
    check_cloudwatch(session, args.region)
    check_rds(session, args.region)
    check_pricing(session)
    if args.write_tests:
        write_tests(session, args.region)

    summary(args.write_tests)

    report = {"region": args.region, "write_tests": args.write_tests, "results": results,
              "facts": {k: v for k, v in facts.items() if k not in ("account",)}}
    with open(args.json, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    print(f"\nReport saved to {args.json}")
    fails = [r for r in results if r["status"] == FAIL]
    print(f"Totals: {sum(r['status'] == OK for r in results)} OK, "
          f"{sum(r['status'] == WARN for r in results)} WARN, {len(fails)} FAIL")


if __name__ == "__main__":
    main()
